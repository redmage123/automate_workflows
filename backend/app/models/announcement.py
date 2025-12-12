"""
Announcement models.

WHAT: SQLAlchemy models for organization announcements.

WHY: Announcements enable:
1. Broadcasting important updates to all users
2. Scheduled communication
3. Targeted messaging (by role, user group)
4. Acknowledgment tracking

HOW: Uses SQLAlchemy 2.0 with:
- Scheduling support
- Targeting rules
- Read/acknowledgment tracking
- Priority and type classification
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class AnnouncementType(str, Enum):
    """
    Announcement types.

    WHAT: Categorizes announcements.

    WHY: Different types have different visual treatment:
    - INFO: General information
    - UPDATE: Product/service updates
    - ALERT: Important warnings
    - MAINTENANCE: Scheduled maintenance
    - PROMOTION: Marketing/promotional
    """

    INFO = "info"
    UPDATE = "update"
    ALERT = "alert"
    MAINTENANCE = "maintenance"
    PROMOTION = "promotion"


class AnnouncementPriority(str, Enum):
    """
    Announcement priority levels.

    WHAT: Determines urgency/visibility.

    WHY: Higher priority announcements are more prominent.
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AnnouncementStatus(str, Enum):
    """
    Announcement status.

    WHAT: Lifecycle status.

    WHY: Controls visibility and editing.
    """

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class Announcement(Base):
    """
    Announcement model.

    WHAT: A broadcast message to users.

    WHY: Announcements provide:
    - Organization-wide communication
    - Scheduled messaging
    - Targeted delivery
    - Acknowledgment tracking

    HOW: Supports scheduling, targeting, and tracking.
    """

    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Type and priority
    type: Mapped[str] = mapped_column(
        String(20), default=AnnouncementType.INFO.value, nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(20), default=AnnouncementPriority.NORMAL.value, nullable=False
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default=AnnouncementStatus.DRAFT.value, nullable=False
    )

    # Scheduling
    publish_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expire_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Targeting
    target_all: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    target_roles: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )
    target_user_ids: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer), nullable=True
    )

    # Display options
    is_dismissible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    require_acknowledgment: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    show_banner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Link (optional CTA)
    action_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    action_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Metadata
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Creator
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    reads: Mapped[List["AnnouncementRead"]] = relationship(
        "AnnouncementRead", back_populates="announcement", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_announcements_org_id", "org_id"),
        Index("ix_announcements_status", "status"),
        Index("ix_announcements_publish_at", "publish_at"),
        Index("ix_announcements_expire_at", "expire_at"),
        Index("ix_announcements_created_by", "created_by"),
    )

    def __repr__(self) -> str:
        return f"<Announcement(id={self.id}, title='{self.title}', status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Check if announcement is currently active."""
        if self.status != AnnouncementStatus.ACTIVE.value:
            return False
        now = datetime.utcnow()
        if self.publish_at and now < self.publish_at:
            return False
        if self.expire_at and now > self.expire_at:
            return False
        return True


class AnnouncementRead(Base):
    """
    Announcement read/acknowledgment tracking.

    WHAT: Tracks who has seen/acknowledged announcements.

    WHY: Enables:
    - Read status tracking
    - Acknowledgment for important announcements
    - Analytics on reach

    HOW: Links users to announcements they've interacted with.
    """

    __tablename__ = "announcement_reads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    announcement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Interaction type
    is_read: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    read_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement", back_populates="reads"
    )
    user: Mapped["User"] = relationship("User")

    # Indexes
    __table_args__ = (
        Index("ix_announcement_reads_announcement_id", "announcement_id"),
        Index("ix_announcement_reads_user_id", "user_id"),
        Index(
            "ix_announcement_reads_unique",
            "announcement_id",
            "user_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AnnouncementRead(announcement_id={self.announcement_id}, "
            f"user_id={self.user_id})>"
        )
