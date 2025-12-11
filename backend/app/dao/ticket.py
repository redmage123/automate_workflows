"""
Ticket Data Access Object.

WHAT: DAO for ticket CRUD operations and workflow management.

WHY: Encapsulates all ticket database operations with:
1. Org-scoped queries for multi-tenancy
2. Status workflow validation
3. SLA due date calculation
4. Comment and attachment management
5. Search and filtering

HOW: Uses SQLAlchemy 2.0 async with proper session management.
"""

from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ticket import (
    Ticket,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    TicketComment,
    TicketAttachment,
    SLA_CONFIG,
)
from app.core.exceptions import (
    TicketNotFoundError,
    ValidationError,
    AuthorizationError,
)


# Valid status transitions
VALID_STATUS_TRANSITIONS = {
    TicketStatus.OPEN: [TicketStatus.IN_PROGRESS, TicketStatus.CLOSED],
    TicketStatus.IN_PROGRESS: [
        TicketStatus.WAITING,
        TicketStatus.RESOLVED,
        TicketStatus.OPEN,
    ],
    TicketStatus.WAITING: [TicketStatus.IN_PROGRESS, TicketStatus.CLOSED],
    TicketStatus.RESOLVED: [TicketStatus.CLOSED, TicketStatus.IN_PROGRESS],
    TicketStatus.CLOSED: [TicketStatus.OPEN],  # Reopen
}


class TicketDAO:
    """
    Data Access Object for Ticket operations.

    WHAT: Manages ticket CRUD and workflow operations.

    WHY: Centralizes database operations for:
    - Consistent org-scoping
    - Status workflow enforcement
    - SLA calculation
    - Audit trail support

    HOW: All methods are async and use session for transactions.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize TicketDAO with database session.

        Args:
            session: AsyncSession for database operations
        """
        self.session = session

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def create(
        self,
        org_id: int,
        created_by_user_id: int,
        subject: str,
        description: str,
        priority: TicketPriority = TicketPriority.MEDIUM,
        category: TicketCategory = TicketCategory.SUPPORT,
        project_id: Optional[int] = None,
        assigned_to_user_id: Optional[int] = None,
    ) -> Ticket:
        """
        Create a new support ticket.

        WHAT: Creates ticket with SLA due dates calculated.

        WHY: New tickets need:
        - Automatic SLA timer setup
        - Default status (OPEN)
        - Organization scoping

        Args:
            org_id: Organization ID
            created_by_user_id: User creating the ticket
            subject: Ticket subject line
            description: Detailed description
            priority: Ticket priority (affects SLA)
            category: Ticket category
            project_id: Optional linked project
            assigned_to_user_id: Optional assigned user

        Returns:
            Created Ticket instance
        """
        ticket = Ticket(
            org_id=org_id,
            created_by_user_id=created_by_user_id,
            subject=subject,
            description=description,
            status=TicketStatus.OPEN,
            priority=priority,
            category=category,
            project_id=project_id,
            assigned_to_user_id=assigned_to_user_id,
            created_at=datetime.utcnow(),
        )

        # Calculate SLA due dates based on priority
        ticket.calculate_sla_due_dates()

        self.session.add(ticket)
        await self.session.flush()
        await self.session.refresh(ticket)

        return ticket

    async def get_by_id(
        self,
        ticket_id: int,
        org_id: Optional[int] = None,
    ) -> Optional[Ticket]:
        """
        Get ticket by ID with optional org scoping.

        Args:
            ticket_id: Ticket ID
            org_id: Optional org_id for scoping

        Returns:
            Ticket or None if not found
        """
        query = select(Ticket).where(Ticket.id == ticket_id)

        if org_id is not None:
            query = query.where(Ticket.org_id == org_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(
        self,
        ticket_id: int,
        org_id: Optional[int] = None,
    ) -> Optional[Ticket]:
        """
        Get ticket by ID with comments and attachments loaded.

        Args:
            ticket_id: Ticket ID
            org_id: Optional org_id for scoping

        Returns:
            Ticket with relations or None
        """
        query = (
            select(Ticket)
            .options(
                selectinload(Ticket.comments),
                selectinload(Ticket.attachments),
                selectinload(Ticket.created_by),
                selectinload(Ticket.assigned_to),
                selectinload(Ticket.project),
            )
            .where(Ticket.id == ticket_id)
        )

        if org_id is not None:
            query = query.where(Ticket.org_id == org_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 20,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        category: Optional[TicketCategory] = None,
        project_id: Optional[int] = None,
        assigned_to_user_id: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
        search: Optional[str] = None,
        include_closed: bool = True,
    ) -> Tuple[List[Ticket], int]:
        """
        List tickets with filtering and pagination.

        Args:
            org_id: Organization ID for scoping
            skip: Number of records to skip
            limit: Maximum records to return
            status: Filter by status
            priority: Filter by priority
            category: Filter by category
            project_id: Filter by project
            assigned_to_user_id: Filter by assignee
            created_by_user_id: Filter by creator
            search: Search in subject and description
            include_closed: Whether to include closed tickets

        Returns:
            Tuple of (tickets list, total count)
        """
        # Base query with org scoping
        base_query = select(Ticket).where(Ticket.org_id == org_id)

        # Apply filters
        if status is not None:
            base_query = base_query.where(Ticket.status == status)
        elif not include_closed:
            base_query = base_query.where(Ticket.status != TicketStatus.CLOSED)

        if priority is not None:
            base_query = base_query.where(Ticket.priority == priority)

        if category is not None:
            base_query = base_query.where(Ticket.category == category)

        if project_id is not None:
            base_query = base_query.where(Ticket.project_id == project_id)

        if assigned_to_user_id is not None:
            base_query = base_query.where(
                Ticket.assigned_to_user_id == assigned_to_user_id
            )

        if created_by_user_id is not None:
            base_query = base_query.where(
                Ticket.created_by_user_id == created_by_user_id
            )

        if search:
            search_pattern = f"%{search}%"
            base_query = base_query.where(
                or_(
                    Ticket.subject.ilike(search_pattern),
                    Ticket.description.ilike(search_pattern),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Get paginated results with eager loading for relationships
        # WHY: Eager loading prevents N+1 queries and allows accessing
        # relationships without lazy loading in async context.
        list_query = (
            base_query.options(
                selectinload(Ticket.created_by),
                selectinload(Ticket.assigned_to),
                selectinload(Ticket.comments),
                selectinload(Ticket.attachments),
            )
            .order_by(Ticket.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(list_query)
        tickets = list(result.scalars().all())

        return tickets, total

    async def update(
        self,
        ticket_id: int,
        org_id: int,
        subject: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[TicketPriority] = None,
        category: Optional[TicketCategory] = None,
        project_id: Optional[int] = None,
        assigned_to_user_id: Optional[int] = None,
    ) -> Ticket:
        """
        Update ticket details.

        Args:
            ticket_id: Ticket ID
            org_id: Organization ID for scoping
            subject: New subject (optional)
            description: New description (optional)
            priority: New priority (optional)
            category: New category (optional)
            project_id: New project link (optional)
            assigned_to_user_id: New assignee (optional)

        Returns:
            Updated Ticket

        Raises:
            TicketNotFoundError: If ticket not found
        """
        ticket = await self.get_by_id(ticket_id, org_id)
        if not ticket:
            raise TicketNotFoundError(
                message="Ticket not found",
                details={"ticket_id": ticket_id},
            )

        if subject is not None:
            ticket.subject = subject

        if description is not None:
            ticket.description = description

        if priority is not None and priority != ticket.priority:
            ticket.priority = priority
            # Recalculate SLA if priority changed
            ticket.calculate_sla_due_dates()

        if category is not None:
            ticket.category = category

        if project_id is not None:
            ticket.project_id = project_id

        if assigned_to_user_id is not None:
            ticket.assigned_to_user_id = assigned_to_user_id

        ticket.updated_at = datetime.utcnow()

        await self.session.flush()
        # Re-fetch with eager loading to include relationships
        # WHY: refresh() doesn't reload relationships, so we need to
        # re-fetch the ticket with all relationships for the response.
        return await self.get_by_id_with_relations(ticket_id, org_id)

    async def delete(self, ticket_id: int, org_id: int) -> bool:
        """
        Delete a ticket.

        WHAT: Hard delete ticket and all related data.

        WHY: Only admins can delete tickets.

        Args:
            ticket_id: Ticket ID
            org_id: Organization ID for scoping

        Returns:
            True if deleted, False if not found
        """
        ticket = await self.get_by_id(ticket_id, org_id)
        if not ticket:
            return False

        await self.session.delete(ticket)
        await self.session.flush()

        return True

    # =========================================================================
    # Status Workflow
    # =========================================================================

    async def change_status(
        self,
        ticket_id: int,
        org_id: int,
        new_status: TicketStatus,
    ) -> Ticket:
        """
        Change ticket status with workflow validation.

        WHAT: Transitions ticket to new status.

        WHY: Enforces valid status transitions and updates timestamps.

        Args:
            ticket_id: Ticket ID
            org_id: Organization ID
            new_status: Target status

        Returns:
            Updated Ticket

        Raises:
            TicketNotFoundError: If ticket not found
            ValidationError: If transition not valid
        """
        ticket = await self.get_by_id(ticket_id, org_id)
        if not ticket:
            raise TicketNotFoundError(
                message="Ticket not found",
                details={"ticket_id": ticket_id},
            )

        # Validate transition
        valid_transitions = VALID_STATUS_TRANSITIONS.get(ticket.status, [])
        if new_status not in valid_transitions:
            raise ValidationError(
                message="Invalid status transition",
                details={
                    "current_status": ticket.status.value,
                    "requested_status": new_status.value,
                    "valid_transitions": [s.value for s in valid_transitions],
                },
            )

        old_status = ticket.status
        ticket.status = new_status
        ticket.updated_at = datetime.utcnow()

        # Update status-specific timestamps
        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.utcnow()
        elif new_status == TicketStatus.CLOSED:
            ticket.closed_at = datetime.utcnow()
        elif new_status == TicketStatus.OPEN and old_status == TicketStatus.CLOSED:
            # Reopening - clear closed timestamp
            ticket.closed_at = None
            ticket.resolved_at = None

        await self.session.flush()
        # Re-fetch with eager loading to include relationships
        return await self.get_by_id_with_relations(ticket_id, org_id)

    async def assign(
        self,
        ticket_id: int,
        org_id: int,
        assigned_to_user_id: Optional[int],
    ) -> Ticket:
        """
        Assign or unassign a ticket.

        Args:
            ticket_id: Ticket ID
            org_id: Organization ID
            assigned_to_user_id: User ID to assign (None to unassign)

        Returns:
            Updated Ticket
        """
        ticket = await self.get_by_id(ticket_id, org_id)
        if not ticket:
            raise TicketNotFoundError(
                message="Ticket not found",
                details={"ticket_id": ticket_id},
            )

        ticket.assigned_to_user_id = assigned_to_user_id
        ticket.updated_at = datetime.utcnow()

        # Auto-transition to IN_PROGRESS if assigned while OPEN
        if assigned_to_user_id and ticket.status == TicketStatus.OPEN:
            ticket.status = TicketStatus.IN_PROGRESS

        await self.session.flush()
        # Re-fetch with eager loading to include relationships
        return await self.get_by_id_with_relations(ticket_id, org_id)

    async def record_first_response(
        self,
        ticket_id: int,
        org_id: int,
    ) -> Ticket:
        """
        Record first response time for SLA tracking.

        Args:
            ticket_id: Ticket ID
            org_id: Organization ID

        Returns:
            Updated Ticket
        """
        ticket = await self.get_by_id(ticket_id, org_id)
        if not ticket:
            raise TicketNotFoundError(
                message="Ticket not found",
                details={"ticket_id": ticket_id},
            )

        if ticket.first_response_at is None:
            ticket.first_response_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(ticket)

        return ticket

    # =========================================================================
    # SLA Queries
    # =========================================================================

    async def get_sla_breached_tickets(
        self,
        org_id: Optional[int] = None,
    ) -> List[Ticket]:
        """
        Get tickets with breached SLA.

        Args:
            org_id: Optional org filter

        Returns:
            List of tickets with breached SLA
        """
        now = datetime.utcnow()

        # Response SLA breached: no first_response_at and due date passed
        response_breached = and_(
            Ticket.first_response_at.is_(None),
            Ticket.sla_response_due_at.isnot(None),
            Ticket.sla_response_due_at < now,
        )

        # Resolution SLA breached: not resolved/closed and due date passed
        resolution_breached = and_(
            Ticket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED]),
            Ticket.sla_resolution_due_at.isnot(None),
            Ticket.sla_resolution_due_at < now,
        )

        query = select(Ticket).where(
            or_(response_breached, resolution_breached)
        )

        if org_id is not None:
            query = query.where(Ticket.org_id == org_id)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_sla_warning_tickets(
        self,
        org_id: Optional[int] = None,
        warning_threshold_percent: float = 0.75,
    ) -> List[Ticket]:
        """
        Get tickets approaching SLA breach (warning).

        Args:
            org_id: Optional org filter
            warning_threshold_percent: Percent of SLA elapsed for warning

        Returns:
            List of tickets approaching SLA breach
        """
        # This is a simplified version - full implementation would calculate
        # based on elapsed percentage of SLA time
        now = datetime.utcnow()

        # Get open tickets with SLA due dates
        query = (
            select(Ticket)
            .where(
                Ticket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED]),
                or_(
                    Ticket.sla_response_due_at.isnot(None),
                    Ticket.sla_resolution_due_at.isnot(None),
                ),
            )
        )

        if org_id is not None:
            query = query.where(Ticket.org_id == org_id)

        result = await self.session.execute(query)
        tickets = list(result.scalars().all())

        # Filter to warning level (75% elapsed)
        warning_tickets = []
        for ticket in tickets:
            # Check response SLA
            if (
                ticket.first_response_at is None
                and ticket.sla_response_due_at
                and ticket.sla_response_due_at > now
            ):
                total_time = (
                    ticket.sla_response_due_at - ticket.created_at
                ).total_seconds()
                elapsed = (now - ticket.created_at).total_seconds()
                if elapsed / total_time >= warning_threshold_percent:
                    warning_tickets.append(ticket)
                    continue

            # Check resolution SLA
            if (
                ticket.sla_resolution_due_at
                and ticket.sla_resolution_due_at > now
            ):
                total_time = (
                    ticket.sla_resolution_due_at - ticket.created_at
                ).total_seconds()
                elapsed = (now - ticket.created_at).total_seconds()
                if elapsed / total_time >= warning_threshold_percent:
                    warning_tickets.append(ticket)

        return warning_tickets

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(
        self,
        org_id: int,
    ) -> dict:
        """
        Get ticket statistics for an organization.

        Returns:
            Dictionary with ticket counts by status, priority, etc.
        """
        # Count by status
        status_query = (
            select(Ticket.status, func.count(Ticket.id))
            .where(Ticket.org_id == org_id)
            .group_by(Ticket.status)
        )
        status_result = await self.session.execute(status_query)
        status_counts = {row[0].value: row[1] for row in status_result}

        # Count by priority
        priority_query = (
            select(Ticket.priority, func.count(Ticket.id))
            .where(
                Ticket.org_id == org_id,
                Ticket.status != TicketStatus.CLOSED,
            )
            .group_by(Ticket.priority)
        )
        priority_result = await self.session.execute(priority_query)
        priority_counts = {row[0].value: row[1] for row in priority_result}

        # Total and open counts
        total = sum(status_counts.values())
        # open_count is specifically tickets with OPEN status
        open_count = status_counts.get(TicketStatus.OPEN.value, 0)

        # SLA breached count
        breached_tickets = await self.get_sla_breached_tickets(org_id)
        sla_breached_count = len(breached_tickets)

        return {
            "total": total,
            "open_count": open_count,
            "by_status": status_counts,
            "by_priority": priority_counts,
            "sla_breached_count": sla_breached_count,
        }


class TicketCommentDAO:
    """
    Data Access Object for TicketComment operations.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        ticket_id: int,
        user_id: int,
        content: str,
        is_internal: bool = False,
    ) -> TicketComment:
        """
        Create a new comment on a ticket.

        Args:
            ticket_id: Ticket ID
            user_id: User creating the comment
            content: Comment content
            is_internal: Whether this is an internal note

        Returns:
            Created TicketComment
        """
        comment = TicketComment(
            ticket_id=ticket_id,
            user_id=user_id,
            content=content,
            is_internal=is_internal,
            created_at=datetime.utcnow(),
        )

        self.session.add(comment)
        await self.session.flush()
        await self.session.refresh(comment)

        return comment

    async def get_by_id(
        self,
        comment_id: int,
    ) -> Optional[TicketComment]:
        """Get comment by ID."""
        query = select(TicketComment).where(TicketComment.id == comment_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_for_ticket(
        self,
        ticket_id: int,
        include_internal: bool = True,
    ) -> List[TicketComment]:
        """
        List comments for a ticket.

        Args:
            ticket_id: Ticket ID
            include_internal: Whether to include internal notes

        Returns:
            List of comments
        """
        query = (
            select(TicketComment)
            .options(selectinload(TicketComment.user))
            .where(TicketComment.ticket_id == ticket_id)
        )

        if not include_internal:
            query = query.where(TicketComment.is_internal == False)

        query = query.order_by(TicketComment.created_at.asc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        comment_id: int,
        user_id: int,
        content: str,
    ) -> TicketComment:
        """
        Update a comment (only by author).

        Args:
            comment_id: Comment ID
            user_id: User ID (must be author)
            content: New content

        Returns:
            Updated TicketComment

        Raises:
            TicketNotFoundError: If comment not found
            AuthorizationError: If user is not author
        """
        comment = await self.get_by_id(comment_id)
        if not comment:
            raise TicketNotFoundError(
                message="Comment not found",
                details={"comment_id": comment_id},
            )

        if comment.user_id != user_id:
            raise AuthorizationError(
                message="Cannot edit another user's comment",
                details={"comment_id": comment_id},
            )

        comment.content = content
        comment.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(comment)

        return comment

    async def delete(
        self,
        comment_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> bool:
        """
        Delete a comment.

        Args:
            comment_id: Comment ID
            user_id: User ID
            is_admin: Whether user is admin (can delete any comment)

        Returns:
            True if deleted

        Raises:
            TicketNotFoundError: If comment not found
            AuthorizationError: If user is not author and not admin
        """
        comment = await self.get_by_id(comment_id)
        if not comment:
            raise TicketNotFoundError(
                message="Comment not found",
                details={"comment_id": comment_id},
            )

        if comment.user_id != user_id and not is_admin:
            raise AuthorizationError(
                message="Cannot delete another user's comment",
                details={"comment_id": comment_id},
            )

        await self.session.delete(comment)
        await self.session.flush()

        return True


class TicketAttachmentDAO:
    """
    Data Access Object for TicketAttachment operations.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        ticket_id: int,
        uploaded_by_user_id: int,
        filename: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        comment_id: Optional[int] = None,
    ) -> TicketAttachment:
        """
        Create a new attachment.

        Args:
            ticket_id: Ticket ID
            uploaded_by_user_id: User uploading
            filename: Original filename
            file_path: Storage path
            file_size: File size in bytes
            mime_type: MIME type
            comment_id: Optional comment ID

        Returns:
            Created TicketAttachment
        """
        attachment = TicketAttachment(
            ticket_id=ticket_id,
            comment_id=comment_id,
            uploaded_by_user_id=uploaded_by_user_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            created_at=datetime.utcnow(),
        )

        self.session.add(attachment)
        await self.session.flush()
        await self.session.refresh(attachment)

        return attachment

    async def get_by_id(
        self,
        attachment_id: int,
    ) -> Optional[TicketAttachment]:
        """Get attachment by ID."""
        query = select(TicketAttachment).where(TicketAttachment.id == attachment_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_for_ticket(
        self,
        ticket_id: int,
    ) -> List[TicketAttachment]:
        """List attachments for a ticket."""
        query = (
            select(TicketAttachment)
            .where(TicketAttachment.ticket_id == ticket_id)
            .order_by(TicketAttachment.created_at.asc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete(
        self,
        attachment_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> bool:
        """
        Delete an attachment.

        Args:
            attachment_id: Attachment ID
            user_id: User ID
            is_admin: Whether user is admin

        Returns:
            True if deleted

        Raises:
            TicketNotFoundError: If attachment not found
            AuthorizationError: If not authorized
        """
        attachment = await self.get_by_id(attachment_id)
        if not attachment:
            raise TicketNotFoundError(
                message="Attachment not found",
                details={"attachment_id": attachment_id},
            )

        if attachment.uploaded_by_user_id != user_id and not is_admin:
            raise AuthorizationError(
                message="Cannot delete another user's attachment",
                details={"attachment_id": attachment_id},
            )

        await self.session.delete(attachment)
        await self.session.flush()

        return True
