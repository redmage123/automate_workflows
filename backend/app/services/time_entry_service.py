"""
Time Entry Service.

WHAT: Business logic for time tracking operations.

WHY: The service layer:
1. Encapsulates time tracking business logic
2. Coordinates between DAOs
3. Enforces business rules (one timer, approval flow)
4. Provides aggregation for reports

HOW: Orchestrates TimeEntryDAO and validates operations
against business rules.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.time_entry import TimeEntryDAO, TimeSummaryDAO
from app.dao.project import ProjectDAO
from app.dao.ticket import TicketDAO
from app.dao.user import UserDAO
from app.models.time_entry import TimeEntry, TimeEntryStatus
from app.models.user import UserRole
from app.core.exceptions import (
    TimeEntryError,
    TimeEntryNotFoundError,
    TimeEntryOverlapError,
    TimeEntryAlreadyInvoicedError,
    AuthorizationError,
    ValidationError,
)


class TimeEntryService:
    """
    Service for time tracking operations.

    WHAT: Provides business logic for time entries.

    WHY: Time tracking enables:
    - Accurate billing based on hours
    - Project budget management
    - Team productivity insights
    - Invoice generation

    HOW: Coordinates DAOs and enforces business rules.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize TimeEntryService.

        Args:
            session: Async database session
        """
        self.session = session
        self.entry_dao = TimeEntryDAO(session)
        self.summary_dao = TimeSummaryDAO(session)
        self.project_dao = ProjectDAO(session)
        self.ticket_dao = TicketDAO(session)
        self.user_dao = UserDAO(session)

    async def create_entry(
        self,
        org_id: int,
        user_id: int,
        entry_date: date,
        description: str,
        duration_minutes: int = 0,
        project_id: Optional[int] = None,
        ticket_id: Optional[int] = None,
        task_type: Optional[str] = None,
        is_billable: bool = True,
        hourly_rate: Optional[Decimal] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> TimeEntry:
        """
        Create a new time entry.

        WHAT: Creates a time tracking record.

        WHY: Records time for billing and reporting.

        Args:
            org_id: Organization ID
            user_id: User who worked
            entry_date: Date of work
            description: Work description
            duration_minutes: Time in minutes
            project_id: Optional project
            ticket_id: Optional ticket
            task_type: Task category
            is_billable: Billable flag
            hourly_rate: Billing rate
            start_time: Start time
            end_time: End time

        Returns:
            Created TimeEntry

        Raises:
            ValidationError: If validation fails
            TimeEntryError: If creation fails
        """
        # Validate project belongs to org
        if project_id:
            project = await self.project_dao.get_by_id_and_org(project_id, org_id)
            if not project:
                raise ValidationError(
                    message="Project not found",
                    details={"project_id": project_id},
                )
            # Use project rate if no rate specified and billable
            if is_billable and hourly_rate is None:
                # Could get rate from project settings if available
                pass

        # Validate ticket belongs to org
        if ticket_id:
            ticket = await self.ticket_dao.get_by_id_and_org(ticket_id, org_id)
            if not ticket:
                raise ValidationError(
                    message="Ticket not found",
                    details={"ticket_id": ticket_id},
                )

        # Calculate duration from times if provided
        if start_time and end_time and duration_minutes == 0:
            delta = end_time - start_time
            duration_minutes = int(delta.total_seconds() / 60)

        # Validate duration
        if duration_minutes < 0:
            raise ValidationError(
                message="Duration cannot be negative",
                details={"duration_minutes": duration_minutes},
            )

        if duration_minutes > 1440:  # 24 hours
            raise ValidationError(
                message="Duration cannot exceed 24 hours",
                details={"duration_minutes": duration_minutes},
            )

        entry = await self.entry_dao.create_entry(
            org_id=org_id,
            user_id=user_id,
            entry_date=entry_date,
            description=description,
            duration_minutes=duration_minutes,
            project_id=project_id,
            ticket_id=ticket_id,
            task_type=task_type,
            is_billable=is_billable,
            hourly_rate=hourly_rate,
            start_time=start_time,
            end_time=end_time,
        )

        return entry

    async def get_entry(
        self,
        entry_id: int,
        org_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> TimeEntry:
        """
        Get a time entry by ID.

        WHAT: Retrieves entry details.

        WHY: View entry information.

        Args:
            entry_id: Entry ID
            org_id: Organization ID
            user_id: Requesting user
            is_admin: Whether user is admin

        Returns:
            TimeEntry

        Raises:
            TimeEntryNotFoundError: If not found
            AuthorizationError: If user lacks access
        """
        entry = await self.entry_dao.get_by_id_and_org(entry_id, org_id)
        if not entry:
            raise TimeEntryNotFoundError(
                message="Time entry not found",
                entry_id=entry_id,
            )

        # Check access - user can see own entries or admin can see all
        if not is_admin and entry.user_id != user_id:
            raise AuthorizationError(
                message="You can only view your own time entries",
            )

        return entry

    async def update_entry(
        self,
        entry_id: int,
        org_id: int,
        user_id: int,
        is_admin: bool = False,
        **kwargs,
    ) -> TimeEntry:
        """
        Update a time entry.

        WHAT: Updates entry fields.

        WHY: Allows editing draft entries.

        Args:
            entry_id: Entry ID
            org_id: Organization ID
            user_id: Requesting user
            is_admin: Whether admin
            **kwargs: Fields to update

        Returns:
            Updated TimeEntry

        Raises:
            TimeEntryNotFoundError: If not found
            TimeEntryError: If entry is not editable
        """
        entry = await self.get_entry(entry_id, org_id, user_id, is_admin)

        # Can only edit draft or rejected entries
        if entry.status not in [
            TimeEntryStatus.DRAFT.value,
            TimeEntryStatus.REJECTED.value,
        ]:
            raise TimeEntryError(
                message="Cannot edit submitted or approved entries",
                entry_id=entry_id,
                status=entry.status,
            )

        # If rejected and being edited, reset to draft
        if entry.status == TimeEntryStatus.REJECTED.value:
            entry.status = TimeEntryStatus.DRAFT.value
            entry.rejection_reason = None

        updated = await self.entry_dao.update_entry(entry_id, org_id, **kwargs)
        return updated

    async def delete_entry(
        self,
        entry_id: int,
        org_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> None:
        """
        Delete a time entry.

        WHAT: Removes a time entry.

        WHY: Clean up incorrect entries.

        Args:
            entry_id: Entry ID
            org_id: Organization ID
            user_id: Requesting user
            is_admin: Whether admin

        Raises:
            TimeEntryNotFoundError: If not found
            TimeEntryAlreadyInvoicedError: If invoiced
        """
        entry = await self.get_entry(entry_id, org_id, user_id, is_admin)

        if entry.invoice_id:
            raise TimeEntryAlreadyInvoicedError(
                message="Cannot delete invoiced entries",
                entry_id=entry_id,
                invoice_id=entry.invoice_id,
            )

        if entry.status == TimeEntryStatus.INVOICED.value:
            raise TimeEntryError(
                message="Cannot delete invoiced entries",
                entry_id=entry_id,
            )

        await self.entry_dao.delete(entry_id)

    async def start_timer(
        self,
        org_id: int,
        user_id: int,
        entry_id: Optional[int] = None,
        project_id: Optional[int] = None,
        ticket_id: Optional[int] = None,
        description: str = "Timer session",
    ) -> TimeEntry:
        """
        Start a timer.

        WHAT: Starts time tracking.

        WHY: Real-time time capture.

        Args:
            org_id: Organization ID
            user_id: User ID
            entry_id: Existing entry to start timer on
            project_id: Project for new entry
            ticket_id: Ticket for new entry
            description: Description for new entry

        Returns:
            Entry with running timer

        Raises:
            TimeEntryOverlapError: If timer already running
        """
        # Check if user already has a running timer
        existing = await self.entry_dao.get_running_timer(user_id, org_id)
        if existing:
            raise TimeEntryOverlapError(
                message="You already have a timer running",
                existing_entry_id=existing.id,
            )

        if entry_id:
            # Start timer on existing entry
            entry = await self.entry_dao.get_by_id_and_org(entry_id, org_id)
            if not entry:
                raise TimeEntryNotFoundError(
                    message="Time entry not found",
                    entry_id=entry_id,
                )
            if entry.user_id != user_id:
                raise AuthorizationError(
                    message="Cannot start timer on another user's entry",
                )
            return await self.entry_dao.start_timer(entry_id, org_id)
        else:
            # Create new entry with timer
            entry = await self.create_entry(
                org_id=org_id,
                user_id=user_id,
                entry_date=date.today(),
                description=description,
                project_id=project_id,
                ticket_id=ticket_id,
            )
            return await self.entry_dao.start_timer(entry.id, org_id)

    async def stop_timer(
        self,
        org_id: int,
        user_id: int,
        entry_id: Optional[int] = None,
    ) -> Optional[TimeEntry]:
        """
        Stop the running timer.

        WHAT: Stops time tracking.

        WHY: Captures elapsed time.

        Args:
            org_id: Organization ID
            user_id: User ID
            entry_id: Specific entry (or find running)

        Returns:
            Updated entry or None
        """
        if entry_id:
            entry = await self.entry_dao.get_by_id_and_org(entry_id, org_id)
            if entry and entry.user_id == user_id and entry.is_running:
                return await self.entry_dao.stop_timer(entry_id, org_id)
        else:
            # Find and stop running timer
            running = await self.entry_dao.get_running_timer(user_id, org_id)
            if running:
                return await self.entry_dao.stop_timer(running.id, org_id)

        return None

    async def get_running_timer(
        self,
        org_id: int,
        user_id: int,
    ) -> Optional[TimeEntry]:
        """
        Get user's currently running timer.

        Args:
            org_id: Organization ID
            user_id: User ID

        Returns:
            Running entry or None
        """
        return await self.entry_dao.get_running_timer(user_id, org_id)

    async def submit_entry(
        self,
        entry_id: int,
        org_id: int,
        user_id: int,
    ) -> TimeEntry:
        """
        Submit entry for approval.

        WHAT: Changes status to SUBMITTED.

        WHY: Approval workflow.

        Args:
            entry_id: Entry ID
            org_id: Organization ID
            user_id: User submitting

        Returns:
            Updated entry

        Raises:
            TimeEntryError: If cannot submit
        """
        entry = await self.entry_dao.get_by_id_and_org(entry_id, org_id)
        if not entry:
            raise TimeEntryNotFoundError(
                message="Time entry not found",
                entry_id=entry_id,
            )

        if entry.user_id != user_id:
            raise AuthorizationError(
                message="Can only submit your own entries",
            )

        if entry.status != TimeEntryStatus.DRAFT.value:
            raise TimeEntryError(
                message="Entry must be in draft status to submit",
                entry_id=entry_id,
                status=entry.status,
            )

        if entry.is_running:
            raise TimeEntryError(
                message="Stop the timer before submitting",
                entry_id=entry_id,
            )

        if entry.duration_minutes == 0:
            raise ValidationError(
                message="Cannot submit entry with zero duration",
            )

        return await self.entry_dao.submit_entry(entry_id, org_id)

    async def approve_entry(
        self,
        entry_id: int,
        org_id: int,
        approver_id: int,
    ) -> TimeEntry:
        """
        Approve a submitted entry.

        WHAT: Changes status to APPROVED.

        WHY: Manager approval for billing.

        Args:
            entry_id: Entry ID
            org_id: Organization ID
            approver_id: Approving user

        Returns:
            Updated entry

        Raises:
            TimeEntryError: If cannot approve
        """
        entry = await self.entry_dao.get_by_id_and_org(entry_id, org_id)
        if not entry:
            raise TimeEntryNotFoundError(
                message="Time entry not found",
                entry_id=entry_id,
            )

        if entry.status != TimeEntryStatus.SUBMITTED.value:
            raise TimeEntryError(
                message="Entry must be submitted before approval",
                entry_id=entry_id,
                status=entry.status,
            )

        return await self.entry_dao.approve_entry(entry_id, org_id, approver_id)

    async def reject_entry(
        self,
        entry_id: int,
        org_id: int,
        reason: str,
    ) -> TimeEntry:
        """
        Reject a submitted entry.

        WHAT: Changes status to REJECTED.

        WHY: Send back for revision.

        Args:
            entry_id: Entry ID
            org_id: Organization ID
            reason: Rejection reason

        Returns:
            Updated entry

        Raises:
            TimeEntryError: If cannot reject
        """
        entry = await self.entry_dao.get_by_id_and_org(entry_id, org_id)
        if not entry:
            raise TimeEntryNotFoundError(
                message="Time entry not found",
                entry_id=entry_id,
            )

        if entry.status != TimeEntryStatus.SUBMITTED.value:
            raise TimeEntryError(
                message="Entry must be submitted to reject",
                entry_id=entry_id,
                status=entry.status,
            )

        return await self.entry_dao.reject_entry(entry_id, org_id, reason)

    async def bulk_approve(
        self,
        entry_ids: List[int],
        org_id: int,
        approver_id: int,
    ) -> Dict[str, Any]:
        """
        Bulk approve entries.

        WHAT: Approves multiple entries.

        WHY: Efficient approval workflow.

        Args:
            entry_ids: List of entry IDs
            org_id: Organization ID
            approver_id: Approving user

        Returns:
            Results dict
        """
        approved = []
        failed = []

        for entry_id in entry_ids:
            try:
                entry = await self.approve_entry(entry_id, org_id, approver_id)
                approved.append(entry_id)
            except Exception as e:
                failed.append({"id": entry_id, "error": str(e)})

        return {
            "approved_count": len(approved),
            "approved_ids": approved,
            "failed_count": len(failed),
            "failed": failed,
        }

    async def link_to_invoice(
        self,
        entry_ids: List[int],
        invoice_id: int,
        org_id: int,
    ) -> int:
        """
        Link entries to an invoice.

        WHAT: Associates entries with billing.

        WHY: Tracks invoiced time.

        Args:
            entry_ids: Entry IDs
            invoice_id: Invoice ID
            org_id: Organization ID

        Returns:
            Number of entries linked
        """
        return await self.entry_dao.link_to_invoice(entry_ids, invoice_id, org_id)

    async def get_user_entries(
        self,
        user_id: int,
        org_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TimeEntry]:
        """
        Get entries for a user.

        Args:
            user_id: User ID
            org_id: Organization ID
            start_date: Start filter
            end_date: End filter
            skip: Offset
            limit: Limit

        Returns:
            List of entries
        """
        return await self.entry_dao.get_by_user(
            user_id, org_id, start_date, end_date, skip, limit
        )

    async def get_project_entries(
        self,
        project_id: int,
        org_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TimeEntry]:
        """
        Get entries for a project.

        Args:
            project_id: Project ID
            org_id: Organization ID
            start_date: Start filter
            end_date: End filter
            skip: Offset
            limit: Limit

        Returns:
            List of entries
        """
        return await self.entry_dao.get_by_project(
            project_id, org_id, start_date, end_date, skip, limit
        )

    async def get_uninvoiced_entries(
        self,
        org_id: int,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> List[TimeEntry]:
        """
        Get entries ready for invoicing.

        Args:
            org_id: Organization ID
            project_id: Optional project filter
            user_id: Optional user filter

        Returns:
            List of uninvoiced entries
        """
        return await self.entry_dao.get_uninvoiced_entries(
            org_id, project_id, user_id
        )

    async def get_user_summary(
        self,
        user_id: int,
        org_id: int,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get time summary for a user.

        Args:
            user_id: User ID
            org_id: Organization ID
            start_date: Start date
            end_date: End date

        Returns:
            Summary dict
        """
        return await self.entry_dao.get_user_summary(
            user_id, org_id, start_date, end_date
        )

    async def get_project_summary(
        self,
        project_id: int,
        org_id: int,
    ) -> Dict[str, Any]:
        """
        Get time summary for a project.

        Args:
            project_id: Project ID
            org_id: Organization ID

        Returns:
            Summary dict
        """
        return await self.entry_dao.get_project_summary(project_id, org_id)

    async def get_daily_breakdown(
        self,
        org_id: int,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get daily time breakdown.

        Args:
            org_id: Organization ID
            user_id: Optional user filter
            project_id: Optional project filter
            start_date: Start date
            end_date: End date

        Returns:
            List of daily summaries
        """
        return await self.entry_dao.get_daily_breakdown(
            org_id, user_id, project_id, start_date, end_date
        )
