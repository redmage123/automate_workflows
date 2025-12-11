"""
Notification Preference Model.

WHAT: SQLAlchemy model for user notification preferences.

WHY: Notification preferences allow users to:
- Control which notifications they receive
- Choose notification channels (email, Slack, in-app)
- Set notification frequency preferences
- Comply with email marketing regulations

HOW: Per-user, per-category preferences stored in database.
Security category cannot be disabled (password changes, etc.)
"""

import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, PrimaryKeyMixin


class NotificationCategory(str, enum.Enum):
    """
    Categories of notifications.

    WHY: Grouping notifications by category allows users to make
    meaningful choices about what they want to receive.
    """

    SECURITY = "security"
    """Password changes, login alerts, security events. CANNOT be disabled."""

    TICKETS = "tickets"
    """Ticket creation, updates, comments, SLA alerts."""

    PROPOSALS = "proposals"
    """Proposal sent, approved, rejected notifications."""

    INVOICES = "invoices"
    """Invoice creation, payment confirmations."""

    PROJECTS = "projects"
    """Project status changes, updates."""

    WORKFLOWS = "workflows"
    """Workflow execution results, failures."""

    SYSTEM = "system"
    """System announcements, maintenance notices."""


class NotificationChannel(str, enum.Enum):
    """
    Notification delivery channels.

    WHY: Different users prefer different channels for different
    types of notifications. Some want email, others prefer Slack.
    """

    EMAIL = "email"
    """Email notifications via configured email provider."""

    SLACK = "slack"
    """Slack notifications via webhook."""

    IN_APP = "in_app"
    """In-application notifications (stored for UI display)."""


class NotificationFrequency(str, enum.Enum):
    """
    Notification delivery frequency.

    WHY: Some notifications should be immediate, others can be batched
    to reduce notification fatigue.
    """

    IMMEDIATE = "immediate"
    """Send notification immediately when event occurs."""

    DAILY_DIGEST = "daily_digest"
    """Batch and send daily summary email."""

    WEEKLY_DIGEST = "weekly_digest"
    """Batch and send weekly summary email."""

    NONE = "none"
    """Don't send this category (except security which is always sent)."""


class NotificationPreference(Base, PrimaryKeyMixin, TimestampMixin):
    """
    User notification preferences by category.

    WHAT: Stores per-user, per-category notification settings.

    WHY: Allows users to customize notification behavior:
    - Which categories they want notifications for
    - Which channels (email, Slack, in-app)
    - How frequently (immediate, digest, none)

    HOW: One row per user per category. If no row exists, defaults apply.
    Security category preferences are enforced to always email.

    Example:
        # User wants ticket notifications via email immediately
        pref = NotificationPreference(
            user_id=1,
            category=NotificationCategory.TICKETS,
            channel_email=True,
            channel_slack=False,
            channel_in_app=True,
            frequency=NotificationFrequency.IMMEDIATE,
        )
    """

    __tablename__ = "notification_preferences"

    # User association
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    """User who owns this preference. Indexed for fast lookup."""

    # Category this preference applies to
    category = Column(
        Enum(NotificationCategory),
        nullable=False,
    )
    """Notification category this preference controls."""

    # Channel preferences
    channel_email = Column(Boolean, default=True, nullable=False)
    """Whether to send email notifications. Default: enabled."""

    channel_slack = Column(Boolean, default=False, nullable=False)
    """Whether to send Slack notifications. Default: disabled."""

    channel_in_app = Column(Boolean, default=True, nullable=False)
    """Whether to create in-app notifications. Default: enabled."""

    # Frequency
    frequency = Column(
        Enum(NotificationFrequency),
        default=NotificationFrequency.IMMEDIATE,
        nullable=False,
    )
    """How frequently to send notifications."""

    # Overall enabled flag
    is_enabled = Column(Boolean, default=True, nullable=False)
    """Master switch for this category. If False, no notifications sent."""

    # Relationships
    user = relationship("User", backref="notification_preferences")

    # Ensure one preference per user per category
    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uix_user_category"),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationPreference(user_id={self.user_id}, "
            f"category={self.category.value}, enabled={self.is_enabled})>"
        )

    @property
    def is_security_category(self) -> bool:
        """
        Check if this is the security category.

        WHY: Security notifications cannot be disabled.
        """
        return self.category == NotificationCategory.SECURITY

    def should_send_email(self) -> bool:
        """
        Determine if email should be sent for this preference.

        WHY: Combines enabled, channel, and frequency checks.
        Security category always sends email.

        Returns:
            True if email notification should be sent
        """
        if self.is_security_category:
            return True  # Always send security emails

        if not self.is_enabled:
            return False

        if self.frequency == NotificationFrequency.NONE:
            return False

        return self.channel_email

    def should_send_slack(self) -> bool:
        """
        Determine if Slack notification should be sent.

        Returns:
            True if Slack notification should be sent
        """
        if not self.is_enabled:
            return False

        if self.frequency == NotificationFrequency.NONE:
            return False

        return self.channel_slack

    def should_send_in_app(self) -> bool:
        """
        Determine if in-app notification should be created.

        Returns:
            True if in-app notification should be created
        """
        if not self.is_enabled:
            return False

        if self.frequency == NotificationFrequency.NONE:
            return False

        return self.channel_in_app


# Default preferences for new users
DEFAULT_PREFERENCES = {
    NotificationCategory.SECURITY: {
        "channel_email": True,
        "channel_slack": False,
        "channel_in_app": True,
        "frequency": NotificationFrequency.IMMEDIATE,
        "is_enabled": True,  # Cannot be disabled
    },
    NotificationCategory.TICKETS: {
        "channel_email": True,
        "channel_slack": False,
        "channel_in_app": True,
        "frequency": NotificationFrequency.IMMEDIATE,
        "is_enabled": True,
    },
    NotificationCategory.PROPOSALS: {
        "channel_email": True,
        "channel_slack": False,
        "channel_in_app": True,
        "frequency": NotificationFrequency.IMMEDIATE,
        "is_enabled": True,
    },
    NotificationCategory.INVOICES: {
        "channel_email": True,
        "channel_slack": False,
        "channel_in_app": True,
        "frequency": NotificationFrequency.IMMEDIATE,
        "is_enabled": True,
    },
    NotificationCategory.PROJECTS: {
        "channel_email": True,
        "channel_slack": False,
        "channel_in_app": True,
        "frequency": NotificationFrequency.IMMEDIATE,
        "is_enabled": True,
    },
    NotificationCategory.WORKFLOWS: {
        "channel_email": True,
        "channel_slack": False,
        "channel_in_app": True,
        "frequency": NotificationFrequency.IMMEDIATE,
        "is_enabled": True,
    },
    NotificationCategory.SYSTEM: {
        "channel_email": True,
        "channel_slack": False,
        "channel_in_app": True,
        "frequency": NotificationFrequency.DAILY_DIGEST,
        "is_enabled": True,
    },
}
