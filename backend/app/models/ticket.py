"""
Ticket models for support ticketing system.

WHAT: SQLAlchemy models for tickets, comments, and attachments.

WHY: Provides structured support request management with:
1. Priority-based SLA tracking
2. Status workflow (open → in_progress → waiting → resolved → closed)
3. Comment threading with internal notes
4. File attachment support
5. Project linking for context

HOW: Uses SQLAlchemy 2.0 with:
- Enums for status and priority fields
- Foreign keys to users, organizations, and projects
- Computed properties for SLA status
- Proper indexing for common queries
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.project import Project
    from app.models.user import User


# ============================================================================
# Enums
# ============================================================================


class TicketStatus(str, Enum):
    """
    Ticket status values.

    WHAT: Tracks the lifecycle of a support ticket.

    WHY: Status determines workflow and SLA timer behavior:
    - OPEN: New ticket, SLA timer running
    - IN_PROGRESS: Being worked on, SLA timer running
    - WAITING: Waiting for client response, SLA timer paused
    - RESOLVED: Issue addressed, awaiting confirmation
    - CLOSED: Ticket completed, no further action
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """
    Ticket priority levels.

    WHAT: Determines SLA response and resolution times.

    WHY: Priority-based SLA ensures critical issues get faster attention:
    - URGENT: 1h response, 4h resolution
    - HIGH: 4h response, 24h resolution
    - MEDIUM: 8h response, 72h resolution
    - LOW: 24h response, 168h resolution
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketCategory(str, Enum):
    """
    Ticket category for classification.

    WHAT: Categorizes the type of support request.

    WHY: Helps with routing, reporting, and analytics.
    """

    GENERAL = "general"
    BUG = "bug"
    FEATURE = "feature"
    QUESTION = "question"
    SUPPORT = "support"


# ============================================================================
# SLA Configuration
# ============================================================================

# SLA times in hours for each priority level
SLA_CONFIG = {
    TicketPriority.URGENT: {"response_hours": 1, "resolution_hours": 4},
    TicketPriority.HIGH: {"response_hours": 4, "resolution_hours": 24},
    TicketPriority.MEDIUM: {"response_hours": 8, "resolution_hours": 72},
    TicketPriority.LOW: {"response_hours": 24, "resolution_hours": 168},
}


# ============================================================================
# Ticket Model
# ============================================================================


class Ticket(Base):
    """
    Support ticket for client requests.

    WHAT: Represents a support request or issue.

    WHY: Enables structured support workflow with:
    - Priority-based SLA tracking
    - Status workflow management
    - Project linking for context
    - Assignment to team members

    Security: Org-scoped, clients only see their org's tickets.
    """

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    # Ticket details
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification
    status: Mapped[TicketStatus] = mapped_column(
        SQLEnum(TicketStatus, name="ticketstatus"),
        default=TicketStatus.OPEN,
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SQLEnum(TicketPriority, name="ticketpriority"),
        default=TicketPriority.MEDIUM,
        nullable=False,
    )
    category: Mapped[TicketCategory] = mapped_column(
        SQLEnum(TicketCategory, name="ticketcategory"),
        default=TicketCategory.SUPPORT,
        nullable=False,
    )

    # SLA tracking
    sla_response_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    sla_resolution_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    first_response_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Status timestamps
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # SLA notification tracking (to prevent duplicate notifications)
    sla_response_warning_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    """Timestamp when response SLA warning notification was sent (75% elapsed)."""

    sla_response_breach_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    """Timestamp when response SLA breach notification was sent."""

    sla_resolution_warning_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    """Timestamp when resolution SLA warning notification was sent (75% elapsed)."""

    sla_resolution_breach_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    """Timestamp when resolution SLA breach notification was sent."""

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="tickets"
    )
    project: Mapped[Optional["Project"]] = relationship(
        "Project", back_populates="tickets"
    )
    created_by: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by_user_id], back_populates="created_tickets"
    )
    assigned_to: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_to_user_id], back_populates="assigned_tickets"
    )
    comments: Mapped[List["TicketComment"]] = relationship(
        "TicketComment", back_populates="ticket", cascade="all, delete-orphan"
    )
    attachments: Mapped[List["TicketAttachment"]] = relationship(
        "TicketAttachment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        foreign_keys="TicketAttachment.ticket_id",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_tickets_org_id", "org_id"),
        Index("ix_tickets_project_id", "project_id"),
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_priority", "priority"),
        Index("ix_tickets_assigned_to", "assigned_to_user_id"),
        Index("ix_tickets_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Ticket(id={self.id}, subject='{self.subject[:30]}...', status={self.status.value})>"

    @property
    def is_open(self) -> bool:
        """Check if ticket is still open (not closed)."""
        return self.status != TicketStatus.CLOSED

    @property
    def is_sla_response_breached(self) -> bool:
        """
        Check if first response SLA is breached.

        WHY: Enables SLA monitoring and alerting.
        """
        if self.first_response_at is not None:
            return False  # Already responded
        if self.sla_response_due_at is None:
            return False
        return datetime.utcnow() > self.sla_response_due_at

    @property
    def is_sla_resolution_breached(self) -> bool:
        """
        Check if resolution SLA is breached.

        WHY: Enables SLA monitoring and alerting.
        """
        if self.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            return False  # Already resolved
        if self.sla_resolution_due_at is None:
            return False
        return datetime.utcnow() > self.sla_resolution_due_at

    @property
    def sla_response_remaining_seconds(self) -> Optional[float]:
        """Get remaining seconds until response SLA breach."""
        if self.first_response_at is not None:
            return None  # Already responded
        if self.sla_response_due_at is None:
            return None
        remaining = (self.sla_response_due_at - datetime.utcnow()).total_seconds()
        return max(0, remaining)

    @property
    def sla_resolution_remaining_seconds(self) -> Optional[float]:
        """Get remaining seconds until resolution SLA breach."""
        if self.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            return None  # Already resolved
        if self.sla_resolution_due_at is None:
            return None
        remaining = (self.sla_resolution_due_at - datetime.utcnow()).total_seconds()
        return max(0, remaining)

    def calculate_sla_due_dates(self) -> None:
        """
        Calculate SLA due dates based on priority.

        WHAT: Sets response and resolution due dates.

        WHY: Enforces SLA commitments based on ticket priority.

        HOW: Uses SLA_CONFIG to determine hours, adds to created_at.
        """
        config = SLA_CONFIG.get(self.priority)
        if config:
            self.sla_response_due_at = self.created_at + timedelta(
                hours=config["response_hours"]
            )
            self.sla_resolution_due_at = self.created_at + timedelta(
                hours=config["resolution_hours"]
            )

    @property
    def is_sla_response_warning_zone(self) -> bool:
        """
        Check if response SLA is in warning zone (75% elapsed).

        WHY: Allows proactive notification before breach occurs.

        Returns:
            True if 75% or more of response SLA time has elapsed
            but not yet breached.
        """
        if self.first_response_at is not None:
            return False  # Already responded
        if self.sla_response_due_at is None:
            return False

        now = datetime.utcnow()
        if now >= self.sla_response_due_at:
            return False  # Already breached, not warning

        total_time = (self.sla_response_due_at - self.created_at).total_seconds()
        elapsed_time = (now - self.created_at).total_seconds()
        elapsed_percent = elapsed_time / total_time if total_time > 0 else 0

        return elapsed_percent >= 0.75

    @property
    def is_sla_resolution_warning_zone(self) -> bool:
        """
        Check if resolution SLA is in warning zone (75% elapsed).

        WHY: Allows proactive notification before breach occurs.

        Returns:
            True if 75% or more of resolution SLA time has elapsed
            but not yet breached.
        """
        if self.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            return False  # Already resolved
        if self.sla_resolution_due_at is None:
            return False

        now = datetime.utcnow()
        if now >= self.sla_resolution_due_at:
            return False  # Already breached, not warning

        total_time = (self.sla_resolution_due_at - self.created_at).total_seconds()
        elapsed_time = (now - self.created_at).total_seconds()
        elapsed_percent = elapsed_time / total_time if total_time > 0 else 0

        return elapsed_percent >= 0.75

    @property
    def sla_response_elapsed_percent(self) -> Optional[float]:
        """Get percentage of response SLA time elapsed."""
        if self.first_response_at is not None:
            return None  # Already responded
        if self.sla_response_due_at is None or self.created_at is None:
            return None

        total_time = (self.sla_response_due_at - self.created_at).total_seconds()
        if total_time <= 0:
            return 100.0

        elapsed_time = (datetime.utcnow() - self.created_at).total_seconds()
        return min(100.0, (elapsed_time / total_time) * 100)

    @property
    def sla_resolution_elapsed_percent(self) -> Optional[float]:
        """Get percentage of resolution SLA time elapsed."""
        if self.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            return None  # Already resolved
        if self.sla_resolution_due_at is None or self.created_at is None:
            return None

        total_time = (self.sla_resolution_due_at - self.created_at).total_seconds()
        if total_time <= 0:
            return 100.0

        elapsed_time = (datetime.utcnow() - self.created_at).total_seconds()
        return min(100.0, (elapsed_time / total_time) * 100)


# ============================================================================
# TicketComment Model
# ============================================================================


class TicketComment(Base):
    """
    Comment on a ticket.

    WHAT: Represents a reply or note on a ticket.

    WHY: Enables conversation threading with:
    - Public comments visible to all participants
    - Internal notes visible only to admins
    - Edit history tracking

    Security: is_internal notes are hidden from clients.
    """

    __tablename__ = "ticket_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Comment content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Internal note flag
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="comments")
    user: Mapped["User"] = relationship("User", back_populates="ticket_comments")
    attachments: Mapped[List["TicketAttachment"]] = relationship(
        "TicketAttachment",
        back_populates="comment",
        foreign_keys="TicketAttachment.comment_id",
    )

    # Indexes
    __table_args__ = (
        Index("ix_ticket_comments_ticket_id", "ticket_id"),
        Index("ix_ticket_comments_user_id", "user_id"),
        Index("ix_ticket_comments_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TicketComment(id={self.id}, ticket_id={self.ticket_id}, is_internal={self.is_internal})>"

    @property
    def is_edited(self) -> bool:
        """Check if comment has been edited."""
        return self.updated_at is not None


# ============================================================================
# TicketAttachment Model
# ============================================================================


class TicketAttachment(Base):
    """
    File attachment on a ticket or comment.

    WHAT: Represents an uploaded file.

    WHY: Enables file sharing for:
    - Screenshots of issues
    - Log files
    - Documentation

    Security: Files are validated for type and size.
    """

    __tablename__ = "ticket_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id"), nullable=False
    )
    comment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ticket_comments.id"), nullable=True
    )
    uploaded_by_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # File details
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    ticket: Mapped["Ticket"] = relationship(
        "Ticket",
        back_populates="attachments",
        foreign_keys=[ticket_id],
    )
    comment: Mapped[Optional["TicketComment"]] = relationship(
        "TicketComment",
        back_populates="attachments",
        foreign_keys=[comment_id],
    )
    uploaded_by: Mapped["User"] = relationship(
        "User", back_populates="ticket_attachments"
    )

    # Indexes
    __table_args__ = (
        Index("ix_ticket_attachments_ticket_id", "ticket_id"),
        Index("ix_ticket_attachments_comment_id", "comment_id"),
    )

    def __repr__(self) -> str:
        return f"<TicketAttachment(id={self.id}, filename='{self.filename}')>"

    @property
    def file_size_kb(self) -> float:
        """Get file size in kilobytes."""
        return self.file_size / 1024

    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return self.file_size / (1024 * 1024)
