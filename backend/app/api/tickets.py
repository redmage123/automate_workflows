"""
Ticket management API endpoints.

WHAT: RESTful API for support ticket operations.

WHY: Tickets enable structured support workflow with:
1. Priority-based SLA tracking
2. Status workflow management
3. Comment threading with internal notes
4. File attachment support
5. Project linking for context

HOW: FastAPI router with:
- Org-scoped queries (multi-tenancy)
- RBAC (ADMIN can manage, CLIENT can create/view own)
- SLA calculations and monitoring
- Audit logging for all mutations
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    AuthorizationError,
)
from app.db.session import get_db
from app.dao.ticket import TicketDAO, TicketCommentDAO, TicketAttachmentDAO
from app.models.user import User, UserRole
from app.models.ticket import (
    TicketStatus as TicketStatusModel,
    TicketPriority as TicketPriorityModel,
    TicketCategory as TicketCategoryModel,
    Ticket,
)
from app.schemas.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketStatusChange,
    TicketAssign,
    TicketResponse,
    TicketDetailResponse,
    TicketListResponse,
    TicketStats,
    TicketSLAResponse,
    SLAAtRiskResponse,
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    AttachmentResponse,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    UserReference,
)
from app.services.audit import AuditService
from app.services.sla_service import SLAService
from app.services.notification_service import NotificationService


router = APIRouter(prefix="/tickets", tags=["tickets"])


def _user_to_reference(user: Optional[User]) -> Optional[UserReference]:
    """
    Convert User model to UserReference schema.

    WHY: Provides minimal user info for embedding in responses.
    """
    if not user:
        return None
    return UserReference(
        id=user.id,
        email=user.email,
        name=user.name,
    )


def _ticket_to_response(ticket: Ticket, include_counts: bool = True) -> TicketResponse:
    """
    Convert Ticket model to TicketResponse schema.

    WHY: Centralized conversion ensures consistent response format
    and proper handling of computed properties.

    Args:
        ticket: Ticket model instance
        include_counts: Whether to include comment/attachment counts

    Returns:
        TicketResponse schema instance
    """
    from sqlalchemy.orm import object_session
    from sqlalchemy import inspect

    # Helper to safely get a relationship without triggering lazy load
    def safe_get_relationship(attr_name: str):
        """Get relationship value only if already loaded, else None."""
        insp = inspect(ticket)
        if attr_name in insp.dict:
            return getattr(ticket, attr_name, None)
        return None

    # Get relationships safely (only if already loaded)
    created_by = safe_get_relationship('created_by')
    assigned_to = safe_get_relationship('assigned_to')
    comments = safe_get_relationship('comments')
    attachments = safe_get_relationship('attachments')

    return TicketResponse(
        id=ticket.id,
        org_id=ticket.org_id,
        project_id=ticket.project_id,
        subject=ticket.subject,
        description=ticket.description,
        status=TicketStatus(ticket.status.value),
        priority=TicketPriority(ticket.priority.value),
        category=TicketCategory(ticket.category.value),
        sla_response_due_at=ticket.sla_response_due_at,
        sla_resolution_due_at=ticket.sla_resolution_due_at,
        first_response_at=ticket.first_response_at,
        is_sla_response_breached=ticket.is_sla_response_breached,
        is_sla_resolution_breached=ticket.is_sla_resolution_breached,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        created_by=_user_to_reference(created_by),
        assigned_to=_user_to_reference(assigned_to),
        comment_count=len(comments) if include_counts and comments else 0,
        attachment_count=len(attachments) if include_counts and attachments else 0,
    )


def _ticket_to_detail_response(
    ticket: Ticket,
    current_user: User,
) -> TicketDetailResponse:
    """
    Convert Ticket model to TicketDetailResponse with comments.

    WHY: Detail view includes full comments and attachments.
    Note: Internal comments are filtered for non-admin users.

    Args:
        ticket: Ticket model instance with comments loaded
        current_user: Current user for filtering internal notes

    Returns:
        TicketDetailResponse schema instance
    """
    # Filter comments based on user role
    is_admin = current_user.role == UserRole.ADMIN
    comments = []
    for comment in ticket.comments:
        # Hide internal notes from non-admins
        if comment.is_internal and not is_admin:
            continue
        comments.append(
            CommentResponse(
                id=comment.id,
                ticket_id=comment.ticket_id,
                content=comment.content,
                is_internal=comment.is_internal,
                is_edited=comment.is_edited,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                user=_user_to_reference(comment.user) if hasattr(comment, 'user') and comment.user else None,
                attachments=[
                    AttachmentResponse(
                        id=att.id,
                        ticket_id=att.ticket_id,
                        comment_id=att.comment_id,
                        filename=att.filename,
                        file_size=att.file_size,
                        mime_type=att.mime_type,
                        created_at=att.created_at,
                        uploaded_by=_user_to_reference(att.uploaded_by) if hasattr(att, 'uploaded_by') else None,
                        download_url=f"/api/tickets/{ticket.id}/attachments/{att.id}/download",
                    )
                    for att in comment.attachments
                ] if hasattr(comment, 'attachments') else [],
            )
        )

    # Ticket-level attachments
    attachments = [
        AttachmentResponse(
            id=att.id,
            ticket_id=att.ticket_id,
            comment_id=att.comment_id,
            filename=att.filename,
            file_size=att.file_size,
            mime_type=att.mime_type,
            created_at=att.created_at,
            uploaded_by=_user_to_reference(att.uploaded_by) if hasattr(att, 'uploaded_by') else None,
            download_url=f"/api/tickets/{ticket.id}/attachments/{att.id}/download",
        )
        for att in ticket.attachments
        if att.comment_id is None  # Only top-level attachments
    ]

    return TicketDetailResponse(
        id=ticket.id,
        org_id=ticket.org_id,
        project_id=ticket.project_id,
        subject=ticket.subject,
        description=ticket.description,
        status=TicketStatus(ticket.status.value),
        priority=TicketPriority(ticket.priority.value),
        category=TicketCategory(ticket.category.value),
        sla_response_due_at=ticket.sla_response_due_at,
        sla_resolution_due_at=ticket.sla_resolution_due_at,
        first_response_at=ticket.first_response_at,
        is_sla_response_breached=ticket.is_sla_response_breached,
        is_sla_resolution_breached=ticket.is_sla_resolution_breached,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        created_by=_user_to_reference(ticket.created_by) if hasattr(ticket, 'created_by') and ticket.created_by else None,
        assigned_to=_user_to_reference(ticket.assigned_to) if hasattr(ticket, 'assigned_to') and ticket.assigned_to else None,
        comment_count=len(comments),
        attachment_count=len(ticket.attachments) if hasattr(ticket, 'attachments') else 0,
        comments=comments,
        attachments=attachments,
        project_name=ticket.project.name if hasattr(ticket, 'project') and ticket.project else None,
    )


# ============================================================================
# Ticket CRUD Endpoints
# ============================================================================


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ticket",
    description="Create a new support ticket",
)
async def create_ticket(
    data: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """
    Create a new support ticket.

    WHAT: Creates a ticket with SLA due dates calculated automatically.

    WHY: Users create tickets to:
    - Report issues with automation workflows
    - Request new features
    - Ask questions
    - Get general support

    Args:
        data: Ticket creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created ticket data

    Raises:
        ValidationError (400): If data validation fails
    """
    ticket_dao = TicketDAO(db)

    # Create ticket with user's org_id
    ticket = await ticket_dao.create(
        org_id=current_user.org_id,
        created_by_user_id=current_user.id,
        subject=data.subject,
        description=data.description,
        project_id=data.project_id,
        priority=TicketPriorityModel(data.priority.value),
        category=TicketCategoryModel(data.category.value),
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="ticket",
        resource_id=ticket.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={
            "subject": data.subject,
            "priority": data.priority.value,
            "category": data.category.value,
        },
    )

    # Re-fetch ticket with relationships for response
    # WHY: The create() method doesn't eagerly load relationships,
    # so we need to fetch again with full relationships loaded.
    ticket = await ticket_dao.get_by_id_with_relations(ticket.id, current_user.org_id)

    # Send Slack notification (fire-and-forget)
    # WHY: Notify support team of new ticket for quick response
    notification_service = NotificationService()
    await notification_service.notify_ticket_created(
        ticket=ticket,
        org_name=current_user.organization.name if current_user.organization else "Unknown",
        created_by_name=current_user.name or current_user.email,
    )

    return _ticket_to_response(ticket)


@router.get(
    "",
    response_model=TicketListResponse,
    status_code=status.HTTP_200_OK,
    summary="List tickets",
    description="Get paginated list of tickets",
)
async def list_tickets(
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum items to return"),
    status_filter: Optional[TicketStatus] = Query(
        default=None,
        alias="status",
        description="Filter by ticket status",
    ),
    priority_filter: Optional[TicketPriority] = Query(
        default=None,
        alias="priority",
        description="Filter by ticket priority",
    ),
    category_filter: Optional[TicketCategory] = Query(
        default=None,
        alias="category",
        description="Filter by ticket category",
    ),
    project_id: Optional[int] = Query(
        default=None,
        description="Filter by project ID",
    ),
    assigned_to_me: bool = Query(
        default=False,
        description="Only show tickets assigned to current user",
    ),
    created_by_me: bool = Query(
        default=False,
        description="Only show tickets created by current user",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketListResponse:
    """
    List tickets with filters.

    WHAT: Returns paginated list of tickets with optional filters.

    WHY: Users need to:
    - Browse tickets in their organization
    - Filter by status for workflow views
    - Find their own tickets or assignments

    Args:
        skip: Pagination offset
        limit: Maximum items per page
        status_filter: Optional status filter
        priority_filter: Optional priority filter
        category_filter: Optional category filter
        project_id: Optional project filter
        assigned_to_me: Filter to assigned tickets
        created_by_me: Filter to created tickets
        current_user: Current authenticated user
        db: Database session

    Returns:
        Paginated list of tickets
    """
    ticket_dao = TicketDAO(db)
    org_id = current_user.org_id

    # Get tickets and count using the list() method
    # WHY: list() returns a tuple of (tickets, total_count) and handles
    # all filtering internally with proper eager loading.
    tickets, total = await ticket_dao.list(
        org_id=org_id,
        skip=skip,
        limit=limit,
        status=TicketStatusModel(status_filter.value) if status_filter else None,
        priority=TicketPriorityModel(priority_filter.value) if priority_filter else None,
        project_id=project_id,
        assigned_to_user_id=current_user.id if assigned_to_me else None,
        created_by_user_id=current_user.id if created_by_me else None,
    )

    return TicketListResponse(
        items=[_ticket_to_response(t) for t in tickets],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/stats",
    response_model=TicketStats,
    status_code=status.HTTP_200_OK,
    summary="Get ticket statistics",
    description="Get aggregated ticket statistics",
)
async def get_ticket_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketStats:
    """
    Get ticket statistics.

    WHAT: Returns aggregated metrics for dashboard widgets.

    WHY: Quick overview without fetching all ticket data.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Ticket statistics
    """
    ticket_dao = TicketDAO(db)
    stats = await ticket_dao.get_stats(current_user.org_id)

    return TicketStats(
        total=stats["total"],
        by_status=stats["by_status"],
        by_priority=stats["by_priority"],
        open_count=stats["open_count"],
        sla_breached_count=stats["sla_breached_count"],
        avg_resolution_hours=stats.get("avg_resolution_hours"),
    )


@router.get(
    "/sla/at-risk",
    response_model=SLAAtRiskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get tickets at SLA risk",
    description="Get tickets that are breached or approaching SLA breach (ADMIN only)",
)
async def get_sla_at_risk(
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> SLAAtRiskResponse:
    """
    Get tickets at risk of SLA breach.

    WHAT: Returns breached and warning-zone tickets.

    WHY: Enables SLA monitoring dashboard for proactive management.

    RBAC: Requires ADMIN role (SLA monitoring is admin function).

    Args:
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Tickets categorized by SLA risk
    """
    sla_service = SLAService(db)
    result = await sla_service.get_at_risk_tickets(current_user.org_id)
    return SLAAtRiskResponse(**result)


@router.get(
    "/{ticket_id}",
    response_model=TicketDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ticket details",
    description="Get ticket with comments and attachments",
)
async def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailResponse:
    """
    Get ticket by ID with full details.

    WHAT: Returns ticket with comments and attachments.

    WHY: Detail view for reading/responding to tickets.

    Note: Internal comments are hidden from non-admin users.

    Args:
        ticket_id: Ticket ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Ticket detail data

    Raises:
        ResourceNotFoundError (404): If ticket not found
    """
    ticket_dao = TicketDAO(db)

    ticket = await ticket_dao.get_by_id_with_relations(ticket_id, current_user.org_id)

    if not ticket:
        raise ResourceNotFoundError(
            message=f"Ticket with id {ticket_id} not found",
            resource_type="Ticket",
            resource_id=ticket_id,
        )

    return _ticket_to_detail_response(ticket, current_user)


@router.get(
    "/{ticket_id}/sla",
    response_model=TicketSLAResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ticket SLA status",
    description="Get detailed SLA status for a ticket",
)
async def get_ticket_sla(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketSLAResponse:
    """
    Get SLA status for a ticket.

    WHAT: Returns detailed SLA timing information.

    WHY: Enables SLA countdown display and monitoring.

    Args:
        ticket_id: Ticket ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        SLA status details

    Raises:
        ResourceNotFoundError (404): If ticket not found
    """
    sla_service = SLAService(db)
    sla_status = await sla_service.get_sla_status(ticket_id, current_user.org_id)
    return TicketSLAResponse(**sla_status)


@router.put(
    "/{ticket_id}",
    response_model=TicketResponse,
    status_code=status.HTTP_200_OK,
    summary="Update ticket",
    description="Update ticket details (creator or ADMIN)",
)
async def update_ticket(
    ticket_id: int,
    data: TicketUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """
    Update ticket details.

    WHAT: Updates ticket fields (not status - use PATCH /status).

    WHY: Users update tickets to:
    - Correct information
    - Add more details
    - Change priority/category

    RBAC: Creator or ADMIN can update.

    Args:
        ticket_id: Ticket ID
        data: Update data (partial update)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated ticket data

    Raises:
        ResourceNotFoundError (404): If ticket not found
        AuthorizationError (403): If not creator or admin
    """
    ticket_dao = TicketDAO(db)

    # Get ticket
    ticket = await ticket_dao.get_by_id(ticket_id, current_user.org_id)
    if not ticket:
        raise ResourceNotFoundError(
            message=f"Ticket with id {ticket_id} not found",
            resource_type="Ticket",
            resource_id=ticket_id,
        )

    # Check permissions
    is_creator = ticket.created_by_user_id == current_user.id
    is_admin = current_user.role == UserRole.ADMIN
    if not is_creator and not is_admin:
        raise AuthorizationError(
            message="Only ticket creator or admin can update ticket",
            action="update",
            resource_type="Ticket",
            resource_id=ticket_id,
        )

    # Build update dict
    update_data = {}
    if data.subject is not None:
        update_data["subject"] = data.subject
    if data.description is not None:
        update_data["description"] = data.description
    if data.project_id is not None:
        update_data["project_id"] = data.project_id
    if data.priority is not None:
        update_data["priority"] = TicketPriorityModel(data.priority.value)
    if data.category is not None:
        update_data["category"] = TicketCategoryModel(data.category.value)

    # Update ticket
    if update_data:
        # Check if priority changed for SLA recalculation
        old_priority = ticket.priority
        ticket = await ticket_dao.update(ticket_id, current_user.org_id, **update_data)

        # Recalculate SLA if priority changed
        if data.priority and data.priority.value != old_priority.value:
            sla_service = SLAService(db)
            await sla_service.recalculate_sla_for_priority_change(
                ticket_id,
                current_user.org_id,
                TicketPriorityModel(data.priority.value),
            )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="ticket",
        resource_id=ticket_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes=update_data,
    )

    return _ticket_to_response(ticket)


@router.patch(
    "/{ticket_id}/status",
    response_model=TicketResponse,
    status_code=status.HTTP_200_OK,
    summary="Change ticket status",
    description="Change ticket status with workflow validation (ADMIN only)",
)
async def change_ticket_status(
    ticket_id: int,
    data: TicketStatusChange,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """
    Change ticket status.

    WHAT: Updates ticket status with workflow validation.

    WHY: Status changes have business implications:
    - RESOLVED/CLOSED sets resolved_at/closed_at timestamps
    - IN_PROGRESS starts work tracking
    - WAITING pauses SLA timers

    RBAC: Requires ADMIN role.

    Args:
        ticket_id: Ticket ID
        data: Status change data
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated ticket data

    Raises:
        ResourceNotFoundError (404): If ticket not found
        ValidationError (400): If invalid status transition
    """
    ticket_dao = TicketDAO(db)

    ticket = await ticket_dao.change_status(
        ticket_id,
        current_user.org_id,
        TicketStatusModel(data.status.value),
    )

    if not ticket:
        raise ResourceNotFoundError(
            message=f"Ticket with id {ticket_id} not found",
            resource_type="Ticket",
            resource_id=ticket_id,
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="ticket",
        resource_id=ticket_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes={"status": data.status.value},
    )

    return _ticket_to_response(ticket)


@router.patch(
    "/{ticket_id}/assign",
    response_model=TicketResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign ticket",
    description="Assign ticket to a user (ADMIN only)",
)
async def assign_ticket(
    ticket_id: int,
    data: TicketAssign,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """
    Assign ticket to a user.

    WHAT: Sets assigned_to_user_id and updates status to IN_PROGRESS.

    WHY: Assignment indicates who is responsible for the ticket.
    Auto-transitioning to IN_PROGRESS shows work has started.

    RBAC: Requires ADMIN role.

    Args:
        ticket_id: Ticket ID
        data: Assignment data
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated ticket data

    Raises:
        ResourceNotFoundError (404): If ticket not found
    """
    ticket_dao = TicketDAO(db)

    ticket = await ticket_dao.assign(
        ticket_id,
        current_user.org_id,
        data.assigned_to_user_id,
    )

    if not ticket:
        raise ResourceNotFoundError(
            message=f"Ticket with id {ticket_id} not found",
            resource_type="Ticket",
            resource_id=ticket_id,
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="ticket",
        resource_id=ticket_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes={"assigned_to_user_id": data.assigned_to_user_id},
    )

    # Send Slack notification for assignment (fire-and-forget)
    # WHY: Notify team when tickets are assigned for visibility
    if data.assigned_to_user_id:
        notification_service = NotificationService()
        assigned_to_name = (
            ticket.assigned_to.name or ticket.assigned_to.email
            if ticket.assigned_to else "Unknown"
        )
        await notification_service.notify_ticket_assigned(
            ticket=ticket,
            assigned_to_name=assigned_to_name,
            assigned_by_name=current_user.name or current_user.email,
        )

    return _ticket_to_response(ticket)


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete ticket",
    description="Delete a ticket (ADMIN only)",
)
async def delete_ticket(
    ticket_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a ticket.

    WHAT: Permanently deletes a ticket and all related data.

    WHY: ADMINs may need to delete:
    - Test tickets
    - Duplicate tickets
    - Spam tickets

    CAUTION: Cascades to comments and attachments.

    RBAC: Requires ADMIN role.

    Args:
        ticket_id: Ticket ID
        current_user: Current authenticated admin user
        db: Database session

    Raises:
        ResourceNotFoundError (404): If ticket not found
    """
    ticket_dao = TicketDAO(db)

    # Verify ticket exists
    ticket = await ticket_dao.get_by_id(ticket_id, current_user.org_id)
    if not ticket:
        raise ResourceNotFoundError(
            message=f"Ticket with id {ticket_id} not found",
            resource_type="Ticket",
            resource_id=ticket_id,
        )

    # Audit log BEFORE deletion
    audit_service = AuditService(db)
    await audit_service.log_delete(
        resource_type="ticket",
        resource_id=ticket_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"subject": ticket.subject},
    )

    # Delete ticket (cascades to comments/attachments)
    await ticket_dao.delete(ticket_id, current_user.org_id)


# ============================================================================
# Comment Endpoints
# ============================================================================


@router.post(
    "/{ticket_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add comment",
    description="Add a comment to a ticket",
)
async def add_comment(
    ticket_id: int,
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """
    Add a comment to a ticket.

    WHAT: Creates a comment (or internal note) on a ticket.

    WHY: Comments enable:
    - Communication between users and support
    - Internal notes for team discussion
    - Ticket history tracking

    Note: Internal notes can only be created by ADMIN users.

    Args:
        ticket_id: Ticket ID
        data: Comment data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created comment

    Raises:
        ResourceNotFoundError (404): If ticket not found
        AuthorizationError (403): If non-admin tries to create internal note
    """
    ticket_dao = TicketDAO(db)
    comment_dao = TicketCommentDAO(db)

    # Verify ticket exists
    ticket = await ticket_dao.get_by_id(ticket_id, current_user.org_id)
    if not ticket:
        raise ResourceNotFoundError(
            message=f"Ticket with id {ticket_id} not found",
            resource_type="Ticket",
            resource_id=ticket_id,
        )

    # Only admins can create internal notes
    if data.is_internal and current_user.role != UserRole.ADMIN:
        raise AuthorizationError(
            message="Only admins can create internal notes",
            action="create_internal_note",
            resource_type="TicketComment",
        )

    # Create comment
    comment = await comment_dao.create(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content=data.content,
        is_internal=data.is_internal,
    )

    # Mark first response if this is admin responding to client ticket
    if (
        current_user.role == UserRole.ADMIN
        and not data.is_internal
        and ticket.first_response_at is None
        and ticket.created_by_user_id != current_user.id
    ):
        await ticket_dao.record_first_response(ticket_id, current_user.org_id)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="ticket_comment",
        resource_id=comment.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={
            "ticket_id": ticket_id,
            "is_internal": data.is_internal,
        },
    )

    # Send Slack notification for comment (fire-and-forget)
    # WHY: Keep team informed of ticket activity
    # Note: Internal notes are skipped by the notification service
    notification_service = NotificationService()
    await notification_service.notify_comment_added(
        ticket=ticket,
        comment=comment,
        commenter_name=current_user.name or current_user.email,
        is_internal=data.is_internal,
    )

    return CommentResponse(
        id=comment.id,
        ticket_id=comment.ticket_id,
        content=comment.content,
        is_internal=comment.is_internal,
        is_edited=comment.is_edited,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        user=_user_to_reference(current_user),
        attachments=[],
    )


@router.put(
    "/{ticket_id}/comments/{comment_id}",
    response_model=CommentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update comment",
    description="Update a comment (author or ADMIN)",
)
async def update_comment(
    ticket_id: int,
    comment_id: int,
    data: CommentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """
    Update a comment.

    WHAT: Updates comment content.

    WHY: Users may need to fix typos or add information.

    RBAC: Author or ADMIN can update.

    Args:
        ticket_id: Ticket ID
        comment_id: Comment ID
        data: Update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated comment

    Raises:
        ResourceNotFoundError (404): If comment not found
        AuthorizationError (403): If not author or admin
    """
    comment_dao = TicketCommentDAO(db)

    # Get comment
    comment = await comment_dao.get_by_id(comment_id)
    if not comment or comment.ticket_id != ticket_id:
        raise ResourceNotFoundError(
            message=f"Comment with id {comment_id} not found",
            resource_type="TicketComment",
            resource_id=comment_id,
        )

    # Check permissions
    is_author = comment.user_id == current_user.id
    is_admin = current_user.role == UserRole.ADMIN
    if not is_author and not is_admin:
        raise AuthorizationError(
            message="Only comment author or admin can update comment",
            action="update",
            resource_type="TicketComment",
            resource_id=comment_id,
        )

    # Update comment
    comment = await comment_dao.update(comment_id, content=data.content)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="ticket_comment",
        resource_id=comment_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes={"content": "[redacted]"},  # Don't log full content
    )

    return CommentResponse(
        id=comment.id,
        ticket_id=comment.ticket_id,
        content=comment.content,
        is_internal=comment.is_internal,
        is_edited=comment.is_edited,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        user=_user_to_reference(comment.user) if hasattr(comment, 'user') else None,
        attachments=[],
    )


@router.delete(
    "/{ticket_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete comment",
    description="Delete a comment (author or ADMIN)",
)
async def delete_comment(
    ticket_id: int,
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a comment.

    WHAT: Permanently deletes a comment.

    RBAC: Author or ADMIN can delete.

    Args:
        ticket_id: Ticket ID
        comment_id: Comment ID
        current_user: Current authenticated user
        db: Database session

    Raises:
        ResourceNotFoundError (404): If comment not found
        AuthorizationError (403): If not author or admin
    """
    comment_dao = TicketCommentDAO(db)

    # Get comment
    comment = await comment_dao.get_by_id(comment_id)
    if not comment or comment.ticket_id != ticket_id:
        raise ResourceNotFoundError(
            message=f"Comment with id {comment_id} not found",
            resource_type="TicketComment",
            resource_id=comment_id,
        )

    # Check permissions
    is_author = comment.user_id == current_user.id
    is_admin = current_user.role == UserRole.ADMIN
    if not is_author and not is_admin:
        raise AuthorizationError(
            message="Only comment author or admin can delete comment",
            action="delete",
            resource_type="TicketComment",
            resource_id=comment_id,
        )

    # Audit log BEFORE deletion
    audit_service = AuditService(db)
    await audit_service.log_delete(
        resource_type="ticket_comment",
        resource_id=comment_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"ticket_id": ticket_id},
    )

    # Delete comment
    await comment_dao.delete(comment_id, current_user.id)
