"""
Activity Feed models.

WHAT: SQLAlchemy models for activity feed functionality.

WHY: An activity feed enables:
1. Real-time visibility into project/organization activity
2. Better team collaboration and awareness
3. Audit trail for non-admin users
4. Context for decisions and changes

HOW: Uses SQLAlchemy 2.0 with:
- Polymorphic entity references
- Actor tracking (who did it)
- Flexible JSON metadata
- Efficient indexing for queries
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    Boolean,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class ActivityType(str, Enum):
    """
    Activity event types.

    WHAT: Categorizes activities by type.

    WHY: Different types enable:
    - Filtering by activity category
    - Type-specific rendering
    - Aggregation and analytics
    """

    # Project activities
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    PROJECT_STATUS_CHANGED = "project.status_changed"
    PROJECT_ASSIGNED = "project.assigned"

    # Proposal activities
    PROPOSAL_CREATED = "proposal.created"
    PROPOSAL_SENT = "proposal.sent"
    PROPOSAL_APPROVED = "proposal.approved"
    PROPOSAL_REJECTED = "proposal.rejected"

    # Invoice activities
    INVOICE_CREATED = "invoice.created"
    INVOICE_SENT = "invoice.sent"
    INVOICE_PAID = "invoice.paid"
    INVOICE_OVERDUE = "invoice.overdue"

    # Ticket activities
    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_STATUS_CHANGED = "ticket.status_changed"
    TICKET_ASSIGNED = "ticket.assigned"
    TICKET_COMMENTED = "ticket.commented"

    # Workflow activities
    WORKFLOW_CREATED = "workflow.created"
    WORKFLOW_EXECUTED = "workflow.executed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_COMPLETED = "workflow.completed"

    # Document activities
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_SHARED = "document.shared"
    DOCUMENT_DOWNLOADED = "document.downloaded"
    DOCUMENT_DELETED = "document.deleted"

    # Time tracking activities
    TIME_ENTRY_SUBMITTED = "time_entry.submitted"
    TIME_ENTRY_APPROVED = "time_entry.approved"
    TIME_ENTRY_REJECTED = "time_entry.rejected"

    # User activities
    USER_JOINED = "user.joined"
    USER_INVITED = "user.invited"

    # Message activities
    CONVERSATION_CREATED = "conversation.created"
    MESSAGE_SENT = "message.sent"

    # General
    COMMENT_ADDED = "comment.added"
    NOTE_ADDED = "note.added"


class ActivityEvent(Base):
    """
    Activity feed event model.

    WHAT: Records a single activity event.

    WHY: Activity events provide:
    - Timeline of actions
    - Context for decisions
    - Team awareness
    - Non-admin audit view

    HOW: Captures who did what to which entity and when,
    with flexible metadata for type-specific details.
    """

    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Actor (who did it)
    actor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Event type
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Target entity (polymorphic)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Parent entity (for hierarchical contexts, e.g., comment on ticket)
    parent_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    parent_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Description
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata (type-specific details)
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Visibility
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    actor: Mapped["User"] = relationship("User", foreign_keys=[actor_id])

    # Indexes
    __table_args__ = (
        Index("ix_activity_events_org_id", "org_id"),
        Index("ix_activity_events_actor_id", "actor_id"),
        Index("ix_activity_events_entity", "entity_type", "entity_id"),
        Index("ix_activity_events_parent_entity", "parent_entity_type", "parent_entity_id"),
        Index("ix_activity_events_event_type", "event_type"),
        Index("ix_activity_events_created_at", "created_at"),
        Index("ix_activity_events_org_created", "org_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityEvent(id={self.id}, "
            f"type={self.event_type}, "
            f"entity={self.entity_type}:{self.entity_id})>"
        )


class ActivitySubscription(Base):
    """
    Activity subscription model.

    WHAT: Tracks user subscriptions to entity activities.

    WHY: Subscriptions enable:
    - Personalized activity feeds
    - "Following" entities for updates
    - Notification targeting

    HOW: Links users to entities they want to follow.
    """

    __tablename__ = "activity_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Subscribed entity
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Notification preferences for this subscription
    notify_in_app: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")

    # Indexes
    __table_args__ = (
        Index("ix_activity_subs_user_id", "user_id"),
        Index("ix_activity_subs_entity", "entity_type", "entity_id"),
        Index(
            "ix_activity_subs_unique",
            "user_id",
            "entity_type",
            "entity_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ActivitySubscription(user_id={self.user_id}, "
            f"entity={self.entity_type}:{self.entity_id})>"
        )
