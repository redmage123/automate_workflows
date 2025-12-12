"""
Push Subscription Model.

WHAT: SQLAlchemy model for web push subscriptions.

WHY: Push subscriptions enable:
1. Real-time notifications to users
2. Engagement even when app is closed
3. Cross-device notification delivery
4. Persistent subscription storage

HOW: Stores Web Push API subscription data
linked to users for targeting notifications.
"""

from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.organization import Organization


class PushSubscription(Base):
    """
    Web Push subscription record.

    WHAT: Stores push notification subscription data.

    WHY: Enables sending push notifications to users:
    - Browser-based push for web users
    - Works even when browser is closed
    - Per-user targeting

    HOW: Stores Web Push API subscription object
    with endpoint and encryption keys.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Subscription endpoint (unique URL for this subscription)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Encryption keys for secure messaging
    p256dh_key: Mapped[str] = mapped_column(Text, nullable=False)
    auth_key: Mapped[str] = mapped_column(Text, nullable=False)

    # Full subscription object for convenience
    subscription_info: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Device/browser info for debugging
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="push_subscriptions")
    organization: Mapped["Organization"] = relationship("Organization")

    # Indexes
    __table_args__ = (
        Index("ix_push_subscriptions_user_id", "user_id"),
        Index("ix_push_subscriptions_org_id", "org_id"),
        Index("ix_push_subscriptions_is_active", "is_active"),
        Index("ix_push_subscriptions_endpoint", "endpoint", unique=True),
    )

    def __repr__(self) -> str:
        return f"<PushSubscription(id={self.id}, user_id={self.user_id})>"

    @classmethod
    def from_subscription_json(
        cls,
        user_id: int,
        org_id: int,
        subscription: Dict[str, Any],
        user_agent: Optional[str] = None,
    ) -> "PushSubscription":
        """
        Create subscription from Web Push API JSON.

        WHAT: Factory method to create from browser subscription.

        WHY: Simplifies parsing subscription object.

        Args:
            user_id: User ID
            org_id: Organization ID
            subscription: Web Push subscription JSON
            user_agent: Browser user agent string

        Returns:
            PushSubscription instance
        """
        keys = subscription.get("keys", {})

        # Detect device type from user agent
        device_type = "unknown"
        if user_agent:
            ua_lower = user_agent.lower()
            if "mobile" in ua_lower or "android" in ua_lower:
                device_type = "mobile"
            elif "tablet" in ua_lower or "ipad" in ua_lower:
                device_type = "tablet"
            else:
                device_type = "desktop"

        return cls(
            user_id=user_id,
            org_id=org_id,
            endpoint=subscription["endpoint"],
            p256dh_key=keys.get("p256dh", ""),
            auth_key=keys.get("auth", ""),
            subscription_info=subscription,
            user_agent=user_agent,
            device_type=device_type,
        )

    def to_webpush_info(self) -> Dict[str, Any]:
        """
        Convert to format expected by webpush library.

        WHAT: Returns subscription in webpush format.

        WHY: Compatible with pywebpush library.

        Returns:
            Subscription dict for webpush
        """
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh_key,
                "auth": self.auth_key,
            },
        }
