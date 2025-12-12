"""
Time Entry models.

WHAT: SQLAlchemy models for time tracking and billing.

WHY: Time tracking is essential for:
1. Billing clients based on hours worked
2. Project budget management
3. Team productivity insights
4. Invoice generation

HOW: Uses SQLAlchemy 2.0 with:
- User and project associations
- Billable/non-billable distinction
- Invoice linking for billing
- Timer support with start/stop
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Numeric,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.project import Project
    from app.models.ticket import Ticket
    from app.models.invoice import Invoice


class TimeEntryStatus(str, Enum):
    """
    Time entry status.

    WHAT: Tracks the state of a time entry.

    WHY: Status determines what actions can be taken:
    - DRAFT: Can be edited/deleted
    - SUBMITTED: Awaiting approval
    - APPROVED: Ready for invoicing
    - INVOICED: Linked to an invoice
    - REJECTED: Sent back for revision
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    INVOICED = "invoiced"
    REJECTED = "rejected"


class TimeEntry(Base):
    """
    Time tracking entry.

    WHAT: Records time spent on projects/tickets.

    WHY: Time tracking enables:
    - Accurate billing based on hours
    - Project budget tracking
    - Team workload analysis
    - Client transparency

    HOW: Each entry has:
    - Duration (calculated from start/end or manual)
    - Association to project and/or ticket
    - Billable flag and rate
    - Invoice linking for billing
    """

    __tablename__ = "time_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Project/ticket association
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True
    )
    ticket_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tickets.id"), nullable=True
    )

    # Time tracking
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Description
    description: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Billing
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hourly_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Status and workflow
    status: Mapped[TimeEntryStatus] = mapped_column(
        String(20), default=TimeEntryStatus.DRAFT.value, nullable=False
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Invoice linking
    invoice_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("invoices.id"), nullable=True
    )

    # Timer support (for active timers)
    timer_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_running: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by])
    project: Mapped[Optional["Project"]] = relationship("Project")
    ticket: Mapped[Optional["Ticket"]] = relationship("Ticket")
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice")

    # Indexes and constraints
    __table_args__ = (
        Index("ix_time_entries_org_id", "org_id"),
        Index("ix_time_entries_user_id", "user_id"),
        Index("ix_time_entries_project_id", "project_id"),
        Index("ix_time_entries_ticket_id", "ticket_id"),
        Index("ix_time_entries_date", "date"),
        Index("ix_time_entries_status", "status"),
        Index("ix_time_entries_invoice_id", "invoice_id"),
        CheckConstraint(
            "duration_minutes >= 0",
            name="ck_time_entries_positive_duration",
        ),
        CheckConstraint(
            "end_time IS NULL OR start_time IS NULL OR end_time >= start_time",
            name="ck_time_entries_valid_time_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<TimeEntry(id={self.id}, "
            f"user_id={self.user_id}, "
            f"date={self.date}, "
            f"minutes={self.duration_minutes})>"
        )

    @property
    def duration_hours(self) -> float:
        """Get duration in hours."""
        return self.duration_minutes / 60.0

    @property
    def is_invoiced(self) -> bool:
        """Check if entry has been invoiced."""
        return self.invoice_id is not None

    @property
    def calculated_amount(self) -> Optional[Decimal]:
        """
        Calculate the billable amount.

        WHAT: Computes amount based on hours and rate.

        WHY: Automatic calculation ensures consistency.
        """
        if not self.is_billable or not self.hourly_rate:
            return None
        hours = Decimal(str(self.duration_minutes)) / Decimal("60")
        return (hours * self.hourly_rate).quantize(Decimal("0.01"))

    def start_timer(self) -> None:
        """
        Start the timer for this entry.

        WHAT: Records current time as timer start.

        WHY: Supports real-time time tracking.
        """
        if not self.is_running:
            self.timer_started_at = datetime.utcnow()
            self.is_running = True

    def stop_timer(self) -> int:
        """
        Stop the timer and calculate duration.

        WHAT: Stops timer and adds elapsed minutes.

        WHY: Captures time worked in real-time.

        Returns:
            Minutes elapsed during this timer session
        """
        if self.is_running and self.timer_started_at:
            elapsed = datetime.utcnow() - self.timer_started_at
            elapsed_minutes = int(elapsed.total_seconds() / 60)
            self.duration_minutes += elapsed_minutes
            self.timer_started_at = None
            self.is_running = False
            return elapsed_minutes
        return 0


class TimeSummary(Base):
    """
    Aggregated time summary (materialized view-like).

    WHAT: Pre-calculated time summaries for reporting.

    WHY: Speeds up dashboard and report queries by
    pre-aggregating time data by user/project/date.

    HOW: Updated periodically or on-demand when
    time entries change.
    """

    __tablename__ = "time_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Aggregation keys
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True
    )
    summary_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary_week: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    summary_month: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Aggregated values
    total_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    billable_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    non_billable_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    billable_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), nullable=False
    )
    entry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Last updated
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Indexes
    __table_args__ = (
        Index("ix_time_summaries_org_date", "org_id", "summary_date"),
        Index("ix_time_summaries_user_date", "user_id", "summary_date"),
        Index("ix_time_summaries_project_date", "project_id", "summary_date"),
        Index(
            "ix_time_summaries_unique",
            "org_id",
            "user_id",
            "project_id",
            "summary_date",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<TimeSummary(id={self.id}, "
            f"date={self.summary_date}, "
            f"minutes={self.total_minutes})>"
        )

    @property
    def total_hours(self) -> float:
        """Get total hours."""
        return self.total_minutes / 60.0

    @property
    def billable_hours(self) -> float:
        """Get billable hours."""
        return self.billable_minutes / 60.0
