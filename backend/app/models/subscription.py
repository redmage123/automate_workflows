"""
Subscription model for managing SaaS subscription plans.

WHY: Subscriptions enable recurring revenue and tiered feature access:
1. Organizations subscribe to plans (Free, Pro, Enterprise)
2. Plans define limits (projects, workflows, users)
3. Stripe handles billing, we track subscription state
4. Webhook events keep subscription status in sync

SECURITY:
- Subscription status checked on every request requiring limits
- Webhook signatures verified before processing
- Stripe subscription ID used for verification, not client-provided data

ARCHITECTURE:
- One subscription per organization (1:1)
- Plan limits enforced at service layer
- Stripe Customer Portal for self-service billing
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    ForeignKey,
    DateTime,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, PrimaryKeyMixin


class SubscriptionPlan(str, enum.Enum):
    """
    Available subscription plans.

    WHY: Enum ensures only valid plans can be stored and provides
    type safety throughout the codebase.

    Plans:
    - FREE: Limited features, no payment required
    - PRO: Most popular, suitable for small teams
    - ENTERPRISE: Unlimited, for large organizations
    """

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    """
    Subscription status values (mirrors Stripe statuses).

    WHY: Tracking status allows for:
    - Enforcing access during active/trialing
    - Grace period during past_due
    - Disabling access when canceled/unpaid

    Statuses:
    - TRIALING: Free trial period (14 days default)
    - ACTIVE: Payment successful, full access
    - PAST_DUE: Payment failed, grace period
    - CANCELED: User canceled, access until period end
    - UNPAID: Multiple payment failures, access revoked
    - INCOMPLETE: Initial payment pending
    - INCOMPLETE_EXPIRED: Initial payment failed
    - PAUSED: Subscription paused by admin
    """

    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAUSED = "paused"


# Plan limits configuration
# WHY: Centralized limits make it easy to adjust pricing strategy
# None = unlimited
PLAN_LIMITS = {
    SubscriptionPlan.FREE: {
        "projects_limit": 3,
        "workflows_limit": 5,
        "users_limit": 2,
        "storage_gb": 1,
        "support_level": "community",
    },
    SubscriptionPlan.PRO: {
        "projects_limit": 20,
        "workflows_limit": 50,
        "users_limit": 10,
        "storage_gb": 50,
        "support_level": "email",
    },
    SubscriptionPlan.ENTERPRISE: {
        "projects_limit": None,  # Unlimited
        "workflows_limit": None,
        "users_limit": None,
        "storage_gb": None,
        "support_level": "priority",
    },
}


class Subscription(Base, PrimaryKeyMixin, TimestampMixin):
    """
    Subscription model for tracking organization billing.

    WHY: Subscriptions enable:
    1. Recurring revenue via Stripe Billing
    2. Tiered feature access based on plan
    3. Self-service billing via Customer Portal
    4. Usage limits enforcement

    RELATIONS:
    - One-to-one with Organization (each org has one subscription)
    - Linked to Stripe via stripe_subscription_id

    LIFECYCLE:
    1. Org created -> FREE plan (no Stripe subscription)
    2. User upgrades -> Stripe checkout -> subscription created
    3. Stripe webhooks update status
    4. User can cancel/upgrade via Customer Portal
    """

    __tablename__ = "subscriptions"

    # Foreign key to organization (1:1 relationship)
    # WHY: Each organization has exactly one subscription
    org_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Stripe identifiers
    # WHY: Link to Stripe for payment processing
    # stripe_subscription_id is null for FREE plan
    stripe_subscription_id = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        doc="Stripe subscription ID (sub_xxx)",
    )
    stripe_price_id = Column(
        String(255),
        nullable=True,
        doc="Stripe price ID for the current plan",
    )

    # Plan and status
    plan = Column(
        Enum(SubscriptionPlan),
        nullable=False,
        default=SubscriptionPlan.FREE,
        doc="Current subscription plan",
    )
    status = Column(
        Enum(SubscriptionStatus),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
        doc="Current subscription status",
    )

    # Billing period
    # WHY: Track current period for pro-rata calculations
    # and to know when access should be revoked after cancellation
    current_period_start = Column(
        DateTime,
        nullable=True,
        doc="Start of current billing period",
    )
    current_period_end = Column(
        DateTime,
        nullable=True,
        doc="End of current billing period",
    )

    # Trial information
    # WHY: Track trial separately from billing period
    trial_start = Column(
        DateTime,
        nullable=True,
        doc="When the trial started",
    )
    trial_end = Column(
        DateTime,
        nullable=True,
        doc="When the trial ends",
    )

    # Cancellation
    # WHY: cancel_at_period_end allows access until period ends
    # canceled_at records when the cancellation was requested
    cancel_at_period_end = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether subscription will cancel at period end",
    )
    canceled_at = Column(
        DateTime,
        nullable=True,
        doc="When the cancellation was requested",
    )

    # Relationship to Organization
    organization = relationship("Organization", back_populates="subscription")

    # Unique constraint: one subscription per org
    __table_args__ = (
        UniqueConstraint("org_id", name="uq_subscription_org"),
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<Subscription(id={self.id}, org_id={self.org_id}, "
            f"plan={self.plan.value}, status={self.status.value})>"
        )

    @property
    def is_active(self) -> bool:
        """
        Check if subscription grants access.

        WHY: Some statuses grant access (active, trialing, past_due)
        while others don't (canceled, unpaid, etc.).

        Returns:
            True if subscription grants feature access
        """
        return self.status in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.PAST_DUE,  # Grace period
        )

    @property
    def is_trialing(self) -> bool:
        """Check if subscription is in trial period."""
        return self.status == SubscriptionStatus.TRIALING

    @property
    def is_canceled(self) -> bool:
        """Check if subscription is canceled or pending cancellation."""
        return self.status == SubscriptionStatus.CANCELED or self.cancel_at_period_end

    @property
    def projects_limit(self) -> Optional[int]:
        """Get projects limit for current plan."""
        return PLAN_LIMITS[self.plan]["projects_limit"]

    @property
    def workflows_limit(self) -> Optional[int]:
        """Get workflows limit for current plan."""
        return PLAN_LIMITS[self.plan]["workflows_limit"]

    @property
    def users_limit(self) -> Optional[int]:
        """Get users limit for current plan."""
        return PLAN_LIMITS[self.plan]["users_limit"]

    @property
    def storage_gb(self) -> Optional[int]:
        """Get storage limit for current plan."""
        return PLAN_LIMITS[self.plan]["storage_gb"]

    @property
    def support_level(self) -> str:
        """Get support level for current plan."""
        return PLAN_LIMITS[self.plan]["support_level"]

    def can_add_project(self, current_count: int) -> bool:
        """
        Check if organization can add another project.

        WHY: Enforces plan limits at the model level.

        Args:
            current_count: Current number of projects

        Returns:
            True if under limit or unlimited
        """
        limit = self.projects_limit
        return limit is None or current_count < limit

    def can_add_workflow(self, current_count: int) -> bool:
        """Check if organization can add another workflow."""
        limit = self.workflows_limit
        return limit is None or current_count < limit

    def can_add_user(self, current_count: int) -> bool:
        """Check if organization can add another user."""
        limit = self.users_limit
        return limit is None or current_count < limit

    def days_until_period_end(self) -> Optional[int]:
        """
        Calculate days remaining in current billing period.

        WHY: Useful for displaying to users, especially when
        subscription is pending cancellation.

        Returns:
            Days until period end, or None if no period set
        """
        if not self.current_period_end:
            return None
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)

    def days_until_trial_end(self) -> Optional[int]:
        """
        Calculate days remaining in trial period.

        Returns:
            Days until trial end, or None if not trialing
        """
        if not self.trial_end or self.status != SubscriptionStatus.TRIALING:
            return None
        delta = self.trial_end - datetime.utcnow()
        return max(0, delta.days)
