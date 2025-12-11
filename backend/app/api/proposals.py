"""
Proposal management API endpoints.

WHAT: RESTful API for proposal CRUD and approval workflow.

WHY: Proposals are critical business documents that:
1. Formalize pricing and scope agreements
2. Track approval workflow with clients
3. Enable invoice generation
4. Support versioning for revisions

HOW: FastAPI router with:
- Org-scoped queries (multi-tenancy)
- RBAC (ADMIN creates/modifies, all can view/approve)
- Workflow endpoints (send, approve, reject, revise)
- Automatic total calculation
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    InvalidStateTransitionError,
)
from app.db.session import get_db
from app.dao.project import ProjectDAO
from app.dao.proposal import ProposalDAO
from app.models.user import User, UserRole
from app.models.project import ProjectStatus as ProjectStatusModel
from app.models.proposal import ProposalStatus as ProposalStatusModel
from app.schemas.proposal import (
    ProposalCreate,
    ProposalUpdate,
    ProposalReject,
    ProposalRevise,
    ProposalResponse,
    ProposalListResponse,
    ProposalStats,
    ProposalStatus,
)
from app.services.audit import AuditService


router = APIRouter(prefix="/proposals", tags=["proposals"])


def _proposal_to_response(proposal, include_internal_notes: bool = True) -> ProposalResponse:
    """
    Convert Proposal model to ProposalResponse schema.

    WHY: Centralized conversion ensures consistent response format
    and proper handling of computed properties. Internal notes
    are filtered based on user role.

    Args:
        proposal: Proposal model instance
        include_internal_notes: If False, hide internal notes (for CLIENT role)

    Returns:
        ProposalResponse schema instance
    """
    return ProposalResponse(
        id=proposal.id,
        title=proposal.title,
        description=proposal.description,
        status=ProposalStatus(proposal.status.value),
        project_id=proposal.project_id,
        org_id=proposal.org_id,
        version=proposal.version,
        previous_version_id=proposal.previous_version_id,
        line_items=proposal.line_items,
        subtotal=float(proposal.subtotal),
        discount_percent=float(proposal.discount_percent) if proposal.discount_percent else None,
        discount_amount=float(proposal.discount_amount) if proposal.discount_amount else None,
        tax_percent=float(proposal.tax_percent) if proposal.tax_percent else None,
        tax_amount=float(proposal.tax_amount) if proposal.tax_amount else None,
        total=float(proposal.total),
        valid_until=proposal.valid_until,
        sent_at=proposal.sent_at,
        viewed_at=proposal.viewed_at,
        approved_at=proposal.approved_at,
        rejected_at=proposal.rejected_at,
        rejection_reason=proposal.rejection_reason,
        notes=proposal.notes if include_internal_notes else None,
        client_notes=proposal.client_notes,
        terms=proposal.terms,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
        is_editable=proposal.is_editable,
        is_expired=proposal.is_expired,
        can_be_approved=proposal.can_be_approved,
    )


def _calculate_proposal_totals(line_items: list[dict], discount_percent: float, tax_percent: float) -> dict:
    """
    Calculate proposal totals from line items.

    WHY: Ensures consistent calculation across create/update operations.

    Args:
        line_items: List of line item dicts
        discount_percent: Discount percentage (0-100)
        tax_percent: Tax percentage (0-100)

    Returns:
        Dict with subtotal, discount_amount, tax_amount, total
    """
    # Calculate subtotal from line items
    if line_items:
        subtotal = sum(
            float(item.get('quantity', 0)) * float(item.get('unit_price', 0))
            for item in line_items
        )
        # Update amounts in line items
        for item in line_items:
            item['amount'] = round(float(item.get('quantity', 0)) * float(item.get('unit_price', 0)), 2)
    else:
        subtotal = 0

    # Calculate discount
    discount_pct = discount_percent or 0
    discount_amount = subtotal * (discount_pct / 100)

    # Calculate subtotal after discount
    subtotal_after_discount = subtotal - discount_amount

    # Calculate tax
    tax_pct = tax_percent or 0
    tax_amount = subtotal_after_discount * (tax_pct / 100)

    # Calculate total
    total = subtotal_after_discount + tax_amount

    return {
        'subtotal': round(subtotal, 2),
        'discount_amount': round(discount_amount, 2),
        'tax_amount': round(tax_amount, 2),
        'total': round(total, 2),
    }


@router.post(
    "",
    response_model=ProposalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create proposal",
    description="Create a new proposal for a project (ADMIN only)",
)
async def create_proposal(
    data: ProposalCreate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Create a new proposal.

    WHAT: Creates a proposal in DRAFT status for a project.

    WHY: ADMINs create proposals to:
    - Formalize pricing for client projects
    - Generate quotes for approval
    - Document scope of work

    RBAC: Requires ADMIN role.
    Security: Validates project belongs to user's org.

    Args:
        data: Proposal creation data
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Created proposal data

    Raises:
        ResourceNotFoundError (404): If project not found
        ValidationError (400): If data validation fails
    """
    project_dao = ProjectDAO(db)
    proposal_dao = ProposalDAO(db)

    # Verify project exists in user's org
    project = await project_dao.get_by_id_and_org(data.project_id, current_user.org_id)
    if not project:
        raise ResourceNotFoundError(
            message=f"Project with id {data.project_id} not found",
            resource_type="Project",
            resource_id=data.project_id,
        )

    # Prepare line items with calculated amounts
    line_items = None
    if data.line_items:
        line_items = [item.model_dump() for item in data.line_items]

    # Calculate totals
    totals = _calculate_proposal_totals(
        line_items or [],
        data.discount_percent or 0,
        data.tax_percent or 0,
    )

    # Create proposal
    proposal = await proposal_dao.create(
        title=data.title,
        description=data.description,
        project_id=data.project_id,
        org_id=current_user.org_id,
        line_items=line_items,
        discount_percent=data.discount_percent,
        tax_percent=data.tax_percent,
        subtotal=totals['subtotal'],
        discount_amount=totals['discount_amount'],
        tax_amount=totals['tax_amount'],
        total=totals['total'],
        valid_until=data.valid_until,
        notes=data.notes,
        client_notes=data.client_notes,
        terms=data.terms,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="proposal",
        resource_id=proposal.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"title": data.title, "project_id": data.project_id, "total": totals['total']},
    )

    return _proposal_to_response(proposal)


@router.get(
    "",
    response_model=ProposalListResponse,
    status_code=status.HTTP_200_OK,
    summary="List proposals",
    description="Get paginated list of proposals for the current organization",
)
async def list_proposals(
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum items to return"),
    status_filter: Optional[ProposalStatus] = Query(
        default=None,
        alias="status",
        description="Filter by proposal status",
    ),
    project_id: Optional[int] = Query(
        default=None,
        description="Filter by project ID",
    ),
    pending_only: bool = Query(
        default=False,
        description="Only return pending proposals (sent or viewed)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposalListResponse:
    """
    List proposals for current organization.

    WHAT: Returns paginated list of proposals with optional filters.

    WHY: Users need to:
    - Browse all proposals in their organization
    - Filter by status for workflow management
    - View proposals by project

    Args:
        skip: Pagination offset
        limit: Maximum items per page
        status_filter: Optional status filter
        project_id: Optional project filter
        pending_only: If True, only sent/viewed proposals
        current_user: Current authenticated user
        db: Database session

    Returns:
        Paginated list of proposals
    """
    proposal_dao = ProposalDAO(db)
    org_id = current_user.org_id
    include_notes = current_user.role == UserRole.ADMIN

    # Get proposals based on filters
    if pending_only:
        proposals = await proposal_dao.get_pending_proposals(org_id, skip=skip, limit=limit)
        status_counts = await proposal_dao.count_by_status(org_id)
        total = status_counts.get('sent', 0) + status_counts.get('viewed', 0)
    elif project_id:
        proposals = await proposal_dao.get_by_project(project_id, org_id, skip=skip, limit=limit)
        total = len(await proposal_dao.get_by_project(project_id, org_id, limit=1000))
    elif status_filter:
        status_enum = ProposalStatusModel(status_filter.value)
        proposals = await proposal_dao.get_by_status(org_id, status_enum, skip=skip, limit=limit)
        status_counts = await proposal_dao.count_by_status(org_id)
        total = status_counts.get(status_filter.value, 0)
    else:
        proposals = await proposal_dao.get_by_org(org_id, skip=skip, limit=limit)
        total = await proposal_dao.count(org_id=org_id)

    return ProposalListResponse(
        items=[_proposal_to_response(p, include_notes) for p in proposals],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/stats",
    response_model=ProposalStats,
    status_code=status.HTTP_200_OK,
    summary="Get proposal statistics",
    description="Get aggregated proposal statistics for the current organization",
)
async def get_proposal_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposalStats:
    """
    Get proposal statistics.

    WHAT: Returns aggregated metrics for dashboard widgets.

    WHY: Quick overview of proposal pipeline:
    - Total value in proposals
    - Approved revenue
    - Pending proposals

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Proposal statistics
    """
    proposal_dao = ProposalDAO(db)
    org_id = current_user.org_id

    # Get counts
    by_status = await proposal_dao.count_by_status(org_id)
    pending_count = by_status.get('sent', 0) + by_status.get('viewed', 0)
    total = sum(by_status.values())

    # Get values
    total_value = await proposal_dao.calculate_total_value(org_id)
    approved_value = await proposal_dao.calculate_total_value(
        org_id, ProposalStatusModel.APPROVED
    )

    return ProposalStats(
        total=total,
        by_status=by_status,
        pending_count=pending_count,
        total_value=float(total_value),
        approved_value=float(approved_value),
    )


@router.get(
    "/{proposal_id}",
    response_model=ProposalResponse,
    status_code=status.HTTP_200_OK,
    summary="Get proposal",
    description="Get proposal details by ID (org-scoped)",
)
async def get_proposal(
    proposal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Get proposal by ID.

    WHAT: Returns proposal details for a specific proposal.

    WHY: Users need to view proposal details for:
    - Review and approval
    - Version comparison
    - Invoice generation

    Security: Enforces org-scoping.
    Note: Internal notes hidden from CLIENT role.

    Args:
        proposal_id: Proposal ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Proposal data

    Raises:
        ResourceNotFoundError (404): If proposal not found
    """
    proposal_dao = ProposalDAO(db)

    proposal = await proposal_dao.get_by_id_and_org(proposal_id, current_user.org_id)

    if not proposal:
        raise ResourceNotFoundError(
            message=f"Proposal with id {proposal_id} not found",
            resource_type="Proposal",
            resource_id=proposal_id,
        )

    # Hide internal notes from CLIENTs
    include_notes = current_user.role == UserRole.ADMIN
    return _proposal_to_response(proposal, include_notes)


@router.put(
    "/{proposal_id}",
    response_model=ProposalResponse,
    status_code=status.HTTP_200_OK,
    summary="Update proposal",
    description="Update proposal details (ADMIN only, draft status only)",
)
async def update_proposal(
    proposal_id: int,
    data: ProposalUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Update proposal details.

    WHAT: Updates proposal fields.

    WHY: ADMINs update proposals to:
    - Adjust pricing before sending
    - Update scope description
    - Modify terms

    RBAC: Requires ADMIN role.
    Constraint: Only DRAFT proposals can be edited.

    Args:
        proposal_id: Proposal ID
        data: Update data (partial update)
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated proposal data

    Raises:
        ResourceNotFoundError (404): If proposal not found
        InvalidStateTransitionError (400): If proposal not editable
    """
    proposal_dao = ProposalDAO(db)

    proposal = await proposal_dao.get_by_id_and_org(proposal_id, current_user.org_id)
    if not proposal:
        raise ResourceNotFoundError(
            message=f"Proposal with id {proposal_id} not found",
            resource_type="Proposal",
            resource_id=proposal_id,
        )

    if not proposal.is_editable:
        raise InvalidStateTransitionError(
            message="Only DRAFT proposals can be edited",
            current_state=proposal.status.value,
            requested_state="edit",
        )

    # Build update dict
    update_data: dict[str, Any] = {}
    if data.title is not None:
        update_data["title"] = data.title
    if data.description is not None:
        update_data["description"] = data.description
    if data.valid_until is not None:
        update_data["valid_until"] = data.valid_until
    if data.notes is not None:
        update_data["notes"] = data.notes
    if data.client_notes is not None:
        update_data["client_notes"] = data.client_notes
    if data.terms is not None:
        update_data["terms"] = data.terms

    # Handle line items and recalculate totals
    if data.line_items is not None:
        line_items = [item.model_dump() for item in data.line_items]
        discount_pct = data.discount_percent if data.discount_percent is not None else float(proposal.discount_percent or 0)
        tax_pct = data.tax_percent if data.tax_percent is not None else float(proposal.tax_percent or 0)

        totals = _calculate_proposal_totals(line_items, discount_pct, tax_pct)
        update_data["line_items"] = line_items
        update_data["subtotal"] = totals['subtotal']
        update_data["discount_amount"] = totals['discount_amount']
        update_data["tax_amount"] = totals['tax_amount']
        update_data["total"] = totals['total']

    if data.discount_percent is not None:
        update_data["discount_percent"] = data.discount_percent
        # Recalculate if line items weren't updated
        if "line_items" not in update_data:
            totals = _calculate_proposal_totals(
                proposal.line_items or [],
                data.discount_percent,
                data.tax_percent if data.tax_percent is not None else float(proposal.tax_percent or 0),
            )
            update_data.update(totals)

    if data.tax_percent is not None:
        update_data["tax_percent"] = data.tax_percent
        # Recalculate if not already done
        if "subtotal" not in update_data:
            totals = _calculate_proposal_totals(
                proposal.line_items or [],
                data.discount_percent if data.discount_percent is not None else float(proposal.discount_percent or 0),
                data.tax_percent,
            )
            update_data.update(totals)

    # Update proposal
    if update_data:
        proposal = await proposal_dao.update(proposal_id, **update_data)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="proposal",
        resource_id=proposal_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes=update_data,
    )

    return _proposal_to_response(proposal)


@router.delete(
    "/{proposal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete proposal",
    description="Delete a proposal (ADMIN only, draft status only)",
)
async def delete_proposal(
    proposal_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a proposal.

    WHAT: Permanently deletes a proposal.

    WHY: ADMINs may need to delete:
    - Draft proposals no longer needed
    - Duplicates
    - Test data

    Constraint: Only DRAFT proposals can be deleted.
    Sent proposals should be revised or expired instead.

    RBAC: Requires ADMIN role.

    Args:
        proposal_id: Proposal ID
        current_user: Current authenticated admin user
        db: Database session

    Raises:
        ResourceNotFoundError (404): If proposal not found
        InvalidStateTransitionError (400): If proposal not in draft
    """
    proposal_dao = ProposalDAO(db)

    proposal = await proposal_dao.get_by_id_and_org(proposal_id, current_user.org_id)
    if not proposal:
        raise ResourceNotFoundError(
            message=f"Proposal with id {proposal_id} not found",
            resource_type="Proposal",
            resource_id=proposal_id,
        )

    if not proposal.is_editable:
        raise InvalidStateTransitionError(
            message="Only DRAFT proposals can be deleted. Use revise for sent proposals.",
            current_state=proposal.status.value,
            requested_state="delete",
        )

    # Audit log before deletion
    audit_service = AuditService(db)
    await audit_service.log_delete(
        resource_type="proposal",
        resource_id=proposal_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"title": proposal.title, "total": float(proposal.total)},
    )

    await proposal_dao.delete(proposal_id)


@router.post(
    "/{proposal_id}/send",
    response_model=ProposalResponse,
    status_code=status.HTTP_200_OK,
    summary="Send proposal",
    description="Send a proposal to the client (ADMIN only)",
)
async def send_proposal(
    proposal_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Send a proposal to the client.

    WHAT: Transitions proposal from DRAFT to SENT status.

    WHY: Sending a proposal:
    - Makes it visible to the client
    - Starts the approval workflow
    - Records sent_at timestamp
    - Updates project status to PROPOSAL_SENT

    RBAC: Requires ADMIN role.
    Constraint: Only DRAFT proposals can be sent.

    Args:
        proposal_id: Proposal ID
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated proposal data

    Raises:
        ResourceNotFoundError (404): If proposal not found
        InvalidStateTransitionError (400): If proposal not in draft
    """
    proposal_dao = ProposalDAO(db)
    project_dao = ProjectDAO(db)

    # Send proposal (DAO validates state)
    proposal = await proposal_dao.send_proposal(proposal_id, current_user.org_id)

    if not proposal:
        # Check if proposal exists
        existing = await proposal_dao.get_by_id_and_org(proposal_id, current_user.org_id)
        if not existing:
            raise ResourceNotFoundError(
                message=f"Proposal with id {proposal_id} not found",
                resource_type="Proposal",
                resource_id=proposal_id,
            )
        raise InvalidStateTransitionError(
            message="Only DRAFT proposals can be sent",
            current_state=existing.status.value,
            requested_state="sent",
        )

    # Update project status to PROPOSAL_SENT
    await project_dao.update_status(
        proposal.project_id,
        current_user.org_id,
        ProjectStatusModel.PROPOSAL_SENT,
    )

    # Audit log - log as UPDATE since status changed
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="proposal",
        resource_id=proposal_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes={"status": {"before": "draft", "after": "sent"}, "project_id": proposal.project_id},
    )

    return _proposal_to_response(proposal)


@router.post(
    "/{proposal_id}/view",
    response_model=ProposalResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark proposal viewed",
    description="Mark a proposal as viewed by the client",
)
async def mark_proposal_viewed(
    proposal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Mark a proposal as viewed.

    WHAT: Transitions proposal from SENT to VIEWED status.

    WHY: Tracking views enables:
    - Knowing client has seen the proposal
    - Follow-up timing
    - Response time metrics

    Note: Called automatically when client opens proposal,
    or manually by client/admin.

    Args:
        proposal_id: Proposal ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated proposal data

    Raises:
        ResourceNotFoundError (404): If proposal not found
    """
    proposal_dao = ProposalDAO(db)

    proposal = await proposal_dao.mark_viewed(proposal_id, current_user.org_id)

    if not proposal:
        # Check if proposal exists
        existing = await proposal_dao.get_by_id_and_org(proposal_id, current_user.org_id)
        if not existing:
            raise ResourceNotFoundError(
                message=f"Proposal with id {proposal_id} not found",
                resource_type="Proposal",
                resource_id=proposal_id,
            )
        # Already viewed or different state - return current state
        return _proposal_to_response(existing, current_user.role == UserRole.ADMIN)

    return _proposal_to_response(proposal, current_user.role == UserRole.ADMIN)


@router.post(
    "/{proposal_id}/approve",
    response_model=ProposalResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve proposal",
    description="Approve a proposal (org-scoped)",
)
async def approve_proposal(
    proposal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Approve a proposal.

    WHAT: Transitions proposal to APPROVED status.

    WHY: Approval is a critical business event:
    - Indicates client acceptance
    - Updates project to APPROVED status
    - Enables invoice generation
    - Records approved_at timestamp

    Constraint: Only SENT or VIEWED proposals can be approved.
    Expired proposals cannot be approved.

    Args:
        proposal_id: Proposal ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated proposal data

    Raises:
        ResourceNotFoundError (404): If proposal not found
        InvalidStateTransitionError (400): If proposal cannot be approved
    """
    proposal_dao = ProposalDAO(db)
    project_dao = ProjectDAO(db)

    proposal = await proposal_dao.approve_proposal(proposal_id, current_user.org_id)

    if not proposal:
        existing = await proposal_dao.get_by_id_and_org(proposal_id, current_user.org_id)
        if not existing:
            raise ResourceNotFoundError(
                message=f"Proposal with id {proposal_id} not found",
                resource_type="Proposal",
                resource_id=proposal_id,
            )
        if existing.is_expired:
            raise InvalidStateTransitionError(
                message="Expired proposals cannot be approved",
                current_state=existing.status.value,
                requested_state="approved",
            )
        raise InvalidStateTransitionError(
            message="Only SENT or VIEWED proposals can be approved",
            current_state=existing.status.value,
            requested_state="approved",
        )

    # Update project status to APPROVED
    await project_dao.update_status(
        proposal.project_id,
        current_user.org_id,
        ProjectStatusModel.APPROVED,
    )

    # Audit log - log as UPDATE since status changed
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="proposal",
        resource_id=proposal_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes={"status": {"before": "sent/viewed", "after": "approved"}, "total": float(proposal.total), "project_id": proposal.project_id},
    )

    return _proposal_to_response(proposal, current_user.role == UserRole.ADMIN)


@router.post(
    "/{proposal_id}/reject",
    response_model=ProposalResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject proposal",
    description="Reject a proposal with optional reason",
)
async def reject_proposal(
    proposal_id: int,
    data: ProposalReject,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Reject a proposal.

    WHAT: Transitions proposal to REJECTED status.

    WHY: Rejection tracking helps:
    - Understand why proposals fail
    - Improve future proposals
    - Follow up with revised offers

    Constraint: Only SENT or VIEWED proposals can be rejected.

    Args:
        proposal_id: Proposal ID
        data: Rejection data with optional reason
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated proposal data

    Raises:
        ResourceNotFoundError (404): If proposal not found
        InvalidStateTransitionError (400): If proposal cannot be rejected
    """
    proposal_dao = ProposalDAO(db)

    proposal = await proposal_dao.reject_proposal(
        proposal_id,
        current_user.org_id,
        reason=data.reason,
    )

    if not proposal:
        existing = await proposal_dao.get_by_id_and_org(proposal_id, current_user.org_id)
        if not existing:
            raise ResourceNotFoundError(
                message=f"Proposal with id {proposal_id} not found",
                resource_type="Proposal",
                resource_id=proposal_id,
            )
        raise InvalidStateTransitionError(
            message="Only SENT or VIEWED proposals can be rejected",
            current_state=existing.status.value,
            requested_state="rejected",
        )

    # Audit log - log as UPDATE since status changed
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="proposal",
        resource_id=proposal_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes={"status": {"before": "sent/viewed", "after": "rejected"}, "reason": data.reason},
    )

    return _proposal_to_response(proposal, current_user.role == UserRole.ADMIN)


@router.post(
    "/{proposal_id}/revise",
    response_model=ProposalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Revise proposal",
    description="Create a revised version of a proposal (ADMIN only)",
)
async def revise_proposal(
    proposal_id: int,
    data: ProposalRevise,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """
    Create a revised proposal.

    WHAT: Creates a new version of an existing proposal.

    WHY: Revisions allow:
    - Updating pricing after feedback
    - Adjusting scope
    - Responding to rejections
    - Maintaining audit trail of changes

    HOW: Original proposal marked as REVISED, new version created
    with incremented version number and link to previous.

    RBAC: Requires ADMIN role.

    Args:
        proposal_id: Original proposal ID
        data: Revision data (fields to update)
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        New proposal version

    Raises:
        ResourceNotFoundError (404): If proposal not found
    """
    proposal_dao = ProposalDAO(db)

    # Build updates dict
    updates: dict[str, Any] = {}
    if data.title is not None:
        updates["title"] = data.title
    if data.description is not None:
        updates["description"] = data.description
    if data.valid_until is not None:
        updates["valid_until"] = data.valid_until
    if data.notes is not None:
        updates["notes"] = data.notes
    if data.client_notes is not None:
        updates["client_notes"] = data.client_notes
    if data.terms is not None:
        updates["terms"] = data.terms

    # Handle line items
    if data.line_items is not None:
        line_items = [item.model_dump() for item in data.line_items]
        updates["line_items"] = line_items

        # Calculate totals
        discount_pct = data.discount_percent if data.discount_percent is not None else 0
        tax_pct = data.tax_percent if data.tax_percent is not None else 0
        totals = _calculate_proposal_totals(line_items, discount_pct, tax_pct)
        updates.update(totals)

    if data.discount_percent is not None:
        updates["discount_percent"] = data.discount_percent
    if data.tax_percent is not None:
        updates["tax_percent"] = data.tax_percent

    # Create revision
    new_proposal = await proposal_dao.create_revision(
        proposal_id,
        current_user.org_id,
        updates,
    )

    if not new_proposal:
        raise ResourceNotFoundError(
            message=f"Proposal with id {proposal_id} not found",
            resource_type="Proposal",
            resource_id=proposal_id,
        )

    # Audit log - revision creates a new proposal
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="proposal",
        resource_id=new_proposal.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={
            "previous_version_id": proposal_id,
            "version": new_proposal.version,
            "updates": list(updates.keys()),
            "is_revision": True,
        },
    )

    return _proposal_to_response(new_proposal)
