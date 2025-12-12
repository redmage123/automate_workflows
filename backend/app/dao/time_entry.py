"""
Time Entry Data Access Object (DAO).

WHAT: Database operations for TimeEntry and TimeSummary models.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for time operations
3. Enforces org-scoping for multi-tenancy
4. Handles complex time aggregations

HOW: Extends BaseDAO with time-specific queries:
- Date range filtering
- User/project aggregation
- Timer management
- Invoice linking
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.time_entry import TimeEntry, TimeEntryStatus, TimeSummary


class TimeEntryDAO(BaseDAO[TimeEntry]):
    """
    Data Access Object for TimeEntry model.

    WHAT: Provides CRUD and query operations for time entries.

    WHY: Centralizes all time tracking database operations:
    - Enforces org_id scoping for security
    - Handles timer operations
    - Provides aggregation for reports

    HOW: Extends BaseDAO with time-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize TimeEntryDAO.

        Args:
            session: Async database session
        """
        super().__init__(TimeEntry, session)

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

        WHY: Records time spent on work for billing and tracking.

        Args:
            org_id: Organization ID
            user_id: User who worked
            entry_date: Date of work
            description: Description of work done
            duration_minutes: Time spent in minutes
            project_id: Optional project ID
            ticket_id: Optional ticket ID
            task_type: Type of task (development, meeting, etc.)
            is_billable: Whether this time is billable
            hourly_rate: Hourly rate for billing
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Created TimeEntry
        """
        # Calculate amount if billable with rate
        amount = None
        if is_billable and hourly_rate and duration_minutes > 0:
            hours = Decimal(str(duration_minutes)) / Decimal("60")
            amount = (hours * hourly_rate).quantize(Decimal("0.01"))

        return await self.create(
            org_id=org_id,
            user_id=user_id,
            date=entry_date,
            description=description,
            duration_minutes=duration_minutes,
            project_id=project_id,
            ticket_id=ticket_id,
            task_type=task_type,
            is_billable=is_billable,
            hourly_rate=hourly_rate,
            amount=amount,
            start_time=start_time,
            end_time=end_time,
            status=TimeEntryStatus.DRAFT.value,
        )

    async def get_by_user(
        self,
        user_id: int,
        org_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TimeEntry]:
        """
        Get time entries for a user.

        WHAT: Retrieves user's time entries with optional date filter.

        WHY: Shows individual time history.

        Args:
            user_id: User ID
            org_id: Organization ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of time entries
        """
        query = select(TimeEntry).where(
            TimeEntry.org_id == org_id,
            TimeEntry.user_id == user_id,
        )

        if start_date:
            query = query.where(TimeEntry.date >= start_date)
        if end_date:
            query = query.where(TimeEntry.date <= end_date)

        result = await self.session.execute(
            query.order_by(TimeEntry.date.desc(), TimeEntry.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_project(
        self,
        project_id: int,
        org_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TimeEntry]:
        """
        Get time entries for a project.

        WHAT: Retrieves project's time entries.

        WHY: Shows all time logged to a project.

        Args:
            project_id: Project ID
            org_id: Organization ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of time entries
        """
        query = select(TimeEntry).where(
            TimeEntry.org_id == org_id,
            TimeEntry.project_id == project_id,
        )

        if start_date:
            query = query.where(TimeEntry.date >= start_date)
        if end_date:
            query = query.where(TimeEntry.date <= end_date)

        result = await self.session.execute(
            query.order_by(TimeEntry.date.desc(), TimeEntry.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_ticket(
        self,
        ticket_id: int,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TimeEntry]:
        """
        Get time entries for a ticket.

        WHAT: Retrieves ticket's time entries.

        WHY: Shows all time logged to a ticket.

        Args:
            ticket_id: Ticket ID
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of time entries
        """
        result = await self.session.execute(
            select(TimeEntry)
            .where(
                TimeEntry.org_id == org_id,
                TimeEntry.ticket_id == ticket_id,
            )
            .order_by(TimeEntry.date.desc(), TimeEntry.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_uninvoiced_entries(
        self,
        org_id: int,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
        billable_only: bool = True,
    ) -> List[TimeEntry]:
        """
        Get approved entries that haven't been invoiced.

        WHAT: Retrieves entries ready for invoicing.

        WHY: Enables batch invoicing of time.

        Args:
            org_id: Organization ID
            project_id: Optional project filter
            user_id: Optional user filter
            billable_only: Only include billable entries

        Returns:
            List of uninvoiced entries
        """
        query = select(TimeEntry).where(
            TimeEntry.org_id == org_id,
            TimeEntry.invoice_id.is_(None),
            TimeEntry.status == TimeEntryStatus.APPROVED.value,
        )

        if project_id:
            query = query.where(TimeEntry.project_id == project_id)
        if user_id:
            query = query.where(TimeEntry.user_id == user_id)
        if billable_only:
            query = query.where(TimeEntry.is_billable == True)

        result = await self.session.execute(
            query.order_by(TimeEntry.date.asc())
        )
        return list(result.scalars().all())

    async def start_timer(
        self,
        entry_id: int,
        org_id: int,
    ) -> Optional[TimeEntry]:
        """
        Start the timer for an entry.

        WHAT: Records current time as timer start.

        WHY: Real-time time tracking.

        Args:
            entry_id: Time entry ID
            org_id: Organization ID

        Returns:
            Updated entry or None
        """
        entry = await self.get_by_id_and_org(entry_id, org_id)
        if not entry:
            return None

        if entry.is_running:
            return entry  # Already running

        entry.timer_started_at = datetime.utcnow()
        entry.is_running = True
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def stop_timer(
        self,
        entry_id: int,
        org_id: int,
    ) -> Optional[TimeEntry]:
        """
        Stop the timer and add elapsed time.

        WHAT: Stops timer and calculates duration.

        WHY: Captures tracked time.

        Args:
            entry_id: Time entry ID
            org_id: Organization ID

        Returns:
            Updated entry or None
        """
        entry = await self.get_by_id_and_org(entry_id, org_id)
        if not entry or not entry.is_running:
            return entry

        # Calculate elapsed time
        if entry.timer_started_at:
            elapsed = datetime.utcnow() - entry.timer_started_at
            elapsed_minutes = int(elapsed.total_seconds() / 60)
            entry.duration_minutes += elapsed_minutes

            # Recalculate amount
            if entry.is_billable and entry.hourly_rate:
                hours = Decimal(str(entry.duration_minutes)) / Decimal("60")
                entry.amount = (hours * entry.hourly_rate).quantize(Decimal("0.01"))

        entry.timer_started_at = None
        entry.is_running = False
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def get_running_timer(
        self,
        user_id: int,
        org_id: int,
    ) -> Optional[TimeEntry]:
        """
        Get the currently running timer for a user.

        WHAT: Finds active timer if any.

        WHY: User should only have one running timer.

        Args:
            user_id: User ID
            org_id: Organization ID

        Returns:
            Running entry or None
        """
        result = await self.session.execute(
            select(TimeEntry).where(
                TimeEntry.org_id == org_id,
                TimeEntry.user_id == user_id,
                TimeEntry.is_running == True,
            )
        )
        return result.scalar_one_or_none()

    async def submit_entry(
        self,
        entry_id: int,
        org_id: int,
    ) -> Optional[TimeEntry]:
        """
        Submit entry for approval.

        WHAT: Changes status to SUBMITTED.

        WHY: Workflow state transition for approval.

        Args:
            entry_id: Time entry ID
            org_id: Organization ID

        Returns:
            Updated entry or None
        """
        entry = await self.get_by_id_and_org(entry_id, org_id)
        if not entry or entry.status != TimeEntryStatus.DRAFT.value:
            return None

        entry.status = TimeEntryStatus.SUBMITTED.value
        entry.submitted_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def approve_entry(
        self,
        entry_id: int,
        org_id: int,
        approver_id: int,
    ) -> Optional[TimeEntry]:
        """
        Approve a submitted entry.

        WHAT: Changes status to APPROVED.

        WHY: Manager approval before invoicing.

        Args:
            entry_id: Time entry ID
            org_id: Organization ID
            approver_id: User who approved

        Returns:
            Updated entry or None
        """
        entry = await self.get_by_id_and_org(entry_id, org_id)
        if not entry or entry.status != TimeEntryStatus.SUBMITTED.value:
            return None

        entry.status = TimeEntryStatus.APPROVED.value
        entry.approved_at = datetime.utcnow()
        entry.approved_by = approver_id
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def reject_entry(
        self,
        entry_id: int,
        org_id: int,
        reason: str,
    ) -> Optional[TimeEntry]:
        """
        Reject a submitted entry.

        WHAT: Changes status to REJECTED.

        WHY: Allows revision of incorrect entries.

        Args:
            entry_id: Time entry ID
            org_id: Organization ID
            reason: Rejection reason

        Returns:
            Updated entry or None
        """
        entry = await self.get_by_id_and_org(entry_id, org_id)
        if not entry or entry.status != TimeEntryStatus.SUBMITTED.value:
            return None

        entry.status = TimeEntryStatus.REJECTED.value
        entry.rejection_reason = reason
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def link_to_invoice(
        self,
        entry_ids: List[int],
        invoice_id: int,
        org_id: int,
    ) -> int:
        """
        Link entries to an invoice.

        WHAT: Associates entries with an invoice.

        WHY: Tracks which entries have been billed.

        Args:
            entry_ids: List of entry IDs
            invoice_id: Invoice ID
            org_id: Organization ID

        Returns:
            Number of entries linked
        """
        result = await self.session.execute(
            update(TimeEntry)
            .where(
                TimeEntry.id.in_(entry_ids),
                TimeEntry.org_id == org_id,
                TimeEntry.status == TimeEntryStatus.APPROVED.value,
                TimeEntry.invoice_id.is_(None),
            )
            .values(
                invoice_id=invoice_id,
                status=TimeEntryStatus.INVOICED.value,
            )
        )
        await self.session.flush()
        return result.rowcount

    async def get_user_summary(
        self,
        user_id: int,
        org_id: int,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get time summary for a user.

        WHAT: Aggregates time data for a user.

        WHY: Dashboard and reporting.

        Args:
            user_id: User ID
            org_id: Organization ID
            start_date: Start date
            end_date: End date

        Returns:
            Summary dict with totals
        """
        result = await self.session.execute(
            select(
                func.sum(TimeEntry.duration_minutes).label("total_minutes"),
                func.sum(
                    func.case(
                        (TimeEntry.is_billable == True, TimeEntry.duration_minutes),
                        else_=0,
                    )
                ).label("billable_minutes"),
                func.sum(
                    func.case(
                        (TimeEntry.is_billable == True, TimeEntry.amount),
                        else_=Decimal("0"),
                    )
                ).label("billable_amount"),
                func.count(TimeEntry.id).label("entry_count"),
            ).where(
                TimeEntry.org_id == org_id,
                TimeEntry.user_id == user_id,
                TimeEntry.date >= start_date,
                TimeEntry.date <= end_date,
            )
        )
        row = result.one()

        return {
            "total_minutes": row.total_minutes or 0,
            "total_hours": (row.total_minutes or 0) / 60.0,
            "billable_minutes": row.billable_minutes or 0,
            "billable_hours": (row.billable_minutes or 0) / 60.0,
            "billable_amount": row.billable_amount or Decimal("0"),
            "entry_count": row.entry_count or 0,
        }

    async def get_project_summary(
        self,
        project_id: int,
        org_id: int,
    ) -> Dict[str, Any]:
        """
        Get time summary for a project.

        WHAT: Aggregates time data for a project.

        WHY: Project budget tracking.

        Args:
            project_id: Project ID
            org_id: Organization ID

        Returns:
            Summary dict with totals
        """
        result = await self.session.execute(
            select(
                func.sum(TimeEntry.duration_minutes).label("total_minutes"),
                func.sum(
                    func.case(
                        (TimeEntry.is_billable == True, TimeEntry.duration_minutes),
                        else_=0,
                    )
                ).label("billable_minutes"),
                func.sum(
                    func.case(
                        (TimeEntry.is_billable == True, TimeEntry.amount),
                        else_=Decimal("0"),
                    )
                ).label("billable_amount"),
                func.sum(
                    func.case(
                        (TimeEntry.status == TimeEntryStatus.INVOICED.value, TimeEntry.amount),
                        else_=Decimal("0"),
                    )
                ).label("invoiced_amount"),
                func.count(TimeEntry.id).label("entry_count"),
            ).where(
                TimeEntry.org_id == org_id,
                TimeEntry.project_id == project_id,
            )
        )
        row = result.one()

        return {
            "total_minutes": row.total_minutes or 0,
            "total_hours": (row.total_minutes or 0) / 60.0,
            "billable_minutes": row.billable_minutes or 0,
            "billable_hours": (row.billable_minutes or 0) / 60.0,
            "billable_amount": row.billable_amount or Decimal("0"),
            "invoiced_amount": row.invoiced_amount or Decimal("0"),
            "entry_count": row.entry_count or 0,
        }

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

        WHAT: Groups time by date.

        WHY: Shows daily work patterns.

        Args:
            org_id: Organization ID
            user_id: Optional user filter
            project_id: Optional project filter
            start_date: Start date
            end_date: End date

        Returns:
            List of daily summaries
        """
        query = (
            select(
                TimeEntry.date,
                func.sum(TimeEntry.duration_minutes).label("total_minutes"),
                func.sum(
                    func.case(
                        (TimeEntry.is_billable == True, TimeEntry.duration_minutes),
                        else_=0,
                    )
                ).label("billable_minutes"),
                func.count(TimeEntry.id).label("entry_count"),
            )
            .where(TimeEntry.org_id == org_id)
            .group_by(TimeEntry.date)
            .order_by(TimeEntry.date.desc())
        )

        if user_id:
            query = query.where(TimeEntry.user_id == user_id)
        if project_id:
            query = query.where(TimeEntry.project_id == project_id)
        if start_date:
            query = query.where(TimeEntry.date >= start_date)
        if end_date:
            query = query.where(TimeEntry.date <= end_date)

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "date": row.date,
                "total_minutes": row.total_minutes or 0,
                "total_hours": (row.total_minutes or 0) / 60.0,
                "billable_minutes": row.billable_minutes or 0,
                "billable_hours": (row.billable_minutes or 0) / 60.0,
                "entry_count": row.entry_count or 0,
            }
            for row in rows
        ]

    async def update_entry(
        self,
        entry_id: int,
        org_id: int,
        **kwargs,
    ) -> Optional[TimeEntry]:
        """
        Update a time entry.

        WHAT: Updates entry fields.

        WHY: Allows editing draft entries.

        Args:
            entry_id: Time entry ID
            org_id: Organization ID
            **kwargs: Fields to update

        Returns:
            Updated entry or None
        """
        entry = await self.get_by_id_and_org(entry_id, org_id)
        if not entry:
            return None

        # Only allow editing draft entries
        if entry.status != TimeEntryStatus.DRAFT.value:
            return entry

        for key, value in kwargs.items():
            if hasattr(entry, key) and value is not None:
                setattr(entry, key, value)

        # Recalculate amount if needed
        if entry.is_billable and entry.hourly_rate and entry.duration_minutes > 0:
            hours = Decimal(str(entry.duration_minutes)) / Decimal("60")
            entry.amount = (hours * entry.hourly_rate).quantize(Decimal("0.01"))

        await self.session.flush()
        await self.session.refresh(entry)
        return entry


class TimeSummaryDAO(BaseDAO[TimeSummary]):
    """
    Data Access Object for TimeSummary model.

    WHAT: Provides operations for pre-aggregated time data.

    WHY: Optimizes reporting queries.

    HOW: Maintains materialized summaries for fast access.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize TimeSummaryDAO.

        Args:
            session: Async database session
        """
        super().__init__(TimeSummary, session)

    async def upsert_summary(
        self,
        org_id: int,
        summary_date: date,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        total_minutes: int = 0,
        billable_minutes: int = 0,
        non_billable_minutes: int = 0,
        billable_amount: Decimal = Decimal("0"),
        entry_count: int = 0,
    ) -> TimeSummary:
        """
        Create or update a time summary.

        WHAT: Upserts summary record.

        WHY: Keeps aggregated data current.

        Args:
            org_id: Organization ID
            summary_date: Date of summary
            user_id: Optional user ID
            project_id: Optional project ID
            total_minutes: Total minutes
            billable_minutes: Billable minutes
            non_billable_minutes: Non-billable minutes
            billable_amount: Billable amount
            entry_count: Number of entries

        Returns:
            Created or updated summary
        """
        # Try to find existing
        result = await self.session.execute(
            select(TimeSummary).where(
                TimeSummary.org_id == org_id,
                TimeSummary.summary_date == summary_date,
                TimeSummary.user_id == user_id if user_id else TimeSummary.user_id.is_(None),
                TimeSummary.project_id == project_id if project_id else TimeSummary.project_id.is_(None),
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.total_minutes = total_minutes
            existing.billable_minutes = billable_minutes
            existing.non_billable_minutes = non_billable_minutes
            existing.billable_amount = billable_amount
            existing.entry_count = entry_count
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        # Calculate week and month
        summary_week = summary_date - timedelta(days=summary_date.weekday())
        summary_month = summary_date.replace(day=1)

        return await self.create(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            summary_date=summary_date,
            summary_week=summary_week,
            summary_month=summary_month,
            total_minutes=total_minutes,
            billable_minutes=billable_minutes,
            non_billable_minutes=non_billable_minutes,
            billable_amount=billable_amount,
            entry_count=entry_count,
        )

    async def get_range_summary(
        self,
        org_id: int,
        start_date: date,
        end_date: date,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get summary for a date range.

        WHAT: Aggregates summaries over a range.

        WHY: Dashboard totals.

        Args:
            org_id: Organization ID
            start_date: Start date
            end_date: End date
            user_id: Optional user filter
            project_id: Optional project filter

        Returns:
            Aggregated summary
        """
        query = select(
            func.sum(TimeSummary.total_minutes).label("total_minutes"),
            func.sum(TimeSummary.billable_minutes).label("billable_minutes"),
            func.sum(TimeSummary.non_billable_minutes).label("non_billable_minutes"),
            func.sum(TimeSummary.billable_amount).label("billable_amount"),
            func.sum(TimeSummary.entry_count).label("entry_count"),
        ).where(
            TimeSummary.org_id == org_id,
            TimeSummary.summary_date >= start_date,
            TimeSummary.summary_date <= end_date,
        )

        if user_id:
            query = query.where(TimeSummary.user_id == user_id)
        if project_id:
            query = query.where(TimeSummary.project_id == project_id)

        result = await self.session.execute(query)
        row = result.one()

        return {
            "total_minutes": row.total_minutes or 0,
            "total_hours": (row.total_minutes or 0) / 60.0,
            "billable_minutes": row.billable_minutes or 0,
            "billable_hours": (row.billable_minutes or 0) / 60.0,
            "non_billable_minutes": row.non_billable_minutes or 0,
            "non_billable_hours": (row.non_billable_minutes or 0) / 60.0,
            "billable_amount": row.billable_amount or Decimal("0"),
            "entry_count": row.entry_count or 0,
        }
