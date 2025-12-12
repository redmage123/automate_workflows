"""
Subscription schemas for API request/response validation.

WHAT: Pydantic schemas for subscription data validation.

WHY: Schemas provide:
1. Type-safe request/response handling
2. Automatic validation with clear error messages
3. OpenAPI documentation generation
4. Data serialization/deserialization

HOW: Uses Pydantic v2 with Field validators and model_config.
Mirrors the Subscription model enums and provides schemas for
subscription management, Stripe checkout, and webhook processing.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Enums (matching model enums for API)
# ============================================================================


class SubscriptionPlan(str, Enum):
    """
    Available subscription plans.

    WHY: String enum for clean JSON serialization
    matching the model's SubscriptionPlan.
    """

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """
    Subscription status values.

    WHY: String enum for clean JSON serialization
    matching the model's SubscriptionStatus (mirrors Stripe).
    """

    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAUSED = "paused"


# ============================================================================
# Plan Information Schemas
# ============================================================================


class PlanLimits(BaseModel):
    """
    Plan limit configuration.

    WHY: Exposes plan limits to frontend for:
    - Displaying current limits
    - Upgrade prompts when approaching limits
    - Feature gating
    """

    projects_limit: Optional[int] = Field(
        description="Maximum projects allowed (null = unlimited)"
    )
    workflows_limit: Optional[int] = Field(
        description="Maximum workflows allowed (null = unlimited)"
    )
    users_limit: Optional[int] = Field(
        description="Maximum users allowed (null = unlimited)"
    )
    storage_gb: Optional[int] = Field(
        description="Storage limit in GB (null = unlimited)"
    )
    support_level: str = Field(
        description="Support level (community, email, priority)"
    )


class PlanInfo(BaseModel):
    """
    Plan information for pricing display.

    WHY: Frontend needs plan details for:
    - Pricing page
    - Upgrade modal
    - Feature comparison
    """

    plan: SubscriptionPlan
    name: str = Field(description="Display name for the plan")
    description: str = Field(description="Short description of the plan")
    price_monthly: Optional[float] = Field(
        description="Monthly price in USD (null for Enterprise)"
    )
    price_yearly: Optional[float] = Field(
        description="Yearly price in USD (null for Enterprise)"
    )
    limits: PlanLimits
    features: List[str] = Field(description="List of feature descriptions")
    stripe_price_id_monthly: Optional[str] = Field(
        default=None,
        description="Stripe price ID for monthly billing"
    )
    stripe_price_id_yearly: Optional[str] = Field(
        default=None,
        description="Stripe price ID for yearly billing"
    )


class PlansResponse(BaseModel):
    """
    Response for listing available plans.

    WHY: Provides all plan info for pricing page.
    """

    plans: List[PlanInfo]


# ============================================================================
# Subscription Response Schemas
# ============================================================================


class SubscriptionResponse(BaseModel):
    """
    Schema for subscription response data.

    WHY: Complete subscription data for display including:
    - Current plan and status
    - Billing period info
    - Trial status
    - Cancellation status
    - Plan limits
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int

    # Plan and status
    plan: SubscriptionPlan
    status: SubscriptionStatus

    # Stripe references
    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None

    # Billing period
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None

    # Trial info
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None

    # Cancellation
    cancel_at_period_end: bool
    canceled_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Computed properties (from model)
    is_active: bool
    is_trialing: bool
    is_canceled: bool

    # Plan limits
    projects_limit: Optional[int] = None
    workflows_limit: Optional[int] = None
    users_limit: Optional[int] = None
    storage_gb: Optional[int] = None
    support_level: str

    # Days remaining
    days_until_period_end: Optional[int] = None
    days_until_trial_end: Optional[int] = None


class SubscriptionSummary(BaseModel):
    """
    Lightweight subscription summary for headers/sidebars.

    WHY: Minimal data for frequent display without full details.
    """

    plan: SubscriptionPlan
    status: SubscriptionStatus
    is_active: bool
    is_trialing: bool
    days_until_trial_end: Optional[int] = None


# ============================================================================
# Usage Schemas
# ============================================================================


class UsageStats(BaseModel):
    """
    Current resource usage vs limits.

    WHY: Shows users their current usage to:
    - Track resource consumption
    - Prompt upgrades before hitting limits
    - Display progress bars in UI
    """

    projects_count: int = Field(description="Current number of projects")
    projects_limit: Optional[int] = Field(description="Projects limit (null = unlimited)")
    projects_percentage: Optional[float] = Field(
        description="Percentage of projects used (null if unlimited)"
    )

    workflows_count: int = Field(description="Current number of workflows")
    workflows_limit: Optional[int] = Field(description="Workflows limit (null = unlimited)")
    workflows_percentage: Optional[float] = Field(
        description="Percentage of workflows used (null if unlimited)"
    )

    users_count: int = Field(description="Current number of users")
    users_limit: Optional[int] = Field(description="Users limit (null = unlimited)")
    users_percentage: Optional[float] = Field(
        description="Percentage of users used (null if unlimited)"
    )


class UsageResponse(BaseModel):
    """
    Response combining subscription and usage.

    WHY: Single endpoint for subscription status page showing
    both current plan and resource usage.
    """

    subscription: SubscriptionResponse
    usage: UsageStats


# ============================================================================
# Checkout Schemas
# ============================================================================


class SubscriptionCheckoutRequest(BaseModel):
    """
    Request to create a subscription checkout session.

    WHY: Initiates Stripe Checkout for subscription:
    - Specifies target plan
    - Provides redirect URLs
    - Optionally specifies billing interval
    """

    plan: SubscriptionPlan = Field(
        description="Plan to subscribe to"
    )
    billing_interval: str = Field(
        default="monthly",
        description="Billing interval: 'monthly' or 'yearly'"
    )
    success_url: str = Field(
        description="URL to redirect after successful checkout"
    )
    cancel_url: str = Field(
        description="URL to redirect if checkout is cancelled"
    )


class SubscriptionCheckoutResponse(BaseModel):
    """
    Response for subscription checkout session creation.

    WHY: Provides client with:
    - Checkout URL for redirect
    - Session ID for status checks
    """

    checkout_session_id: str = Field(description="Stripe Checkout Session ID")
    checkout_url: str = Field(description="URL to redirect user to")


class CustomerPortalRequest(BaseModel):
    """
    Request to create a Stripe Customer Portal session.

    WHY: Customer Portal allows self-service:
    - Update payment method
    - View invoices
    - Cancel subscription
    """

    return_url: str = Field(
        description="URL to redirect after portal session"
    )


class CustomerPortalResponse(BaseModel):
    """
    Response for customer portal session creation.

    WHY: Provides redirect URL to Stripe's hosted portal.
    """

    portal_url: str = Field(description="URL to redirect user to")


# ============================================================================
# Subscription Management Schemas
# ============================================================================


class SubscriptionCancelRequest(BaseModel):
    """
    Request to cancel a subscription.

    WHY: Supports both cancellation types:
    - Immediate: Access revoked now
    - At period end: Access until paid period expires
    """

    cancel_immediately: bool = Field(
        default=False,
        description="If true, cancel immediately. If false, cancel at period end."
    )
    cancellation_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional reason for cancellation (for analytics)"
    )


class SubscriptionCancelResponse(BaseModel):
    """
    Response for subscription cancellation.

    WHY: Confirms cancellation and provides access end date.
    """

    message: str
    subscription: SubscriptionResponse
    access_until: Optional[datetime] = Field(
        description="When access will be revoked (null if immediate)"
    )


class SubscriptionReactivateResponse(BaseModel):
    """
    Response for subscription reactivation.

    WHY: Confirms cancellation was undone.
    """

    message: str
    subscription: SubscriptionResponse


class PlanChangeRequest(BaseModel):
    """
    Request to change subscription plan.

    WHY: Supports upgrades and downgrades:
    - Upgrades: Immediate access to new features, prorated
    - Downgrades: Takes effect at period end
    """

    new_plan: SubscriptionPlan = Field(
        description="Plan to change to"
    )
    billing_interval: Optional[str] = Field(
        default=None,
        description="New billing interval (monthly/yearly), or None to keep current"
    )


class PlanChangeResponse(BaseModel):
    """
    Response for plan change.

    WHY: Confirms change and indicates when it takes effect.
    """

    message: str
    subscription: SubscriptionResponse
    prorated_amount: Optional[float] = Field(
        description="Amount charged/credited for proration (null if downgrade)"
    )
    effective_date: datetime = Field(
        description="When the new plan takes effect"
    )


# ============================================================================
# Admin Schemas
# ============================================================================


class AdminSubscriptionUpdate(BaseModel):
    """
    Admin-only schema for updating subscriptions.

    WHY: Allows admins to:
    - Override plan (e.g., for partners)
    - Fix billing issues
    - Extend trials
    """

    plan: Optional[SubscriptionPlan] = Field(
        default=None,
        description="Override plan"
    )
    status: Optional[SubscriptionStatus] = Field(
        default=None,
        description="Override status"
    )
    trial_end: Optional[datetime] = Field(
        default=None,
        description="Extend or set trial end date"
    )
    current_period_end: Optional[datetime] = Field(
        default=None,
        description="Extend current period"
    )


class SubscriptionStats(BaseModel):
    """
    Subscription statistics for admin dashboard.

    WHY: Provides metrics for:
    - Revenue tracking
    - Churn analysis
    - Plan distribution
    """

    total_subscriptions: int
    by_plan: Dict[str, int] = Field(
        description="Count of subscriptions per plan"
    )
    by_status: Dict[str, int] = Field(
        description="Count of subscriptions per status"
    )
    active_trials: int
    expiring_trials_7_days: int
    past_due_count: int
    mrr_estimate: float = Field(
        description="Monthly Recurring Revenue estimate"
    )


# ============================================================================
# Webhook Schemas
# ============================================================================


class StripeWebhookPayload(BaseModel):
    """
    Schema for Stripe webhook event payload.

    WHY: Validates webhook structure before processing.
    Note: Actual signature verification happens in endpoint.
    """

    id: str = Field(description="Event ID")
    type: str = Field(description="Event type (e.g., customer.subscription.updated)")
    data: Dict[str, Any] = Field(description="Event data object")
    created: int = Field(description="Event creation timestamp")


class WebhookResponse(BaseModel):
    """
    Response for webhook processing.

    WHY: Confirms webhook was received and processed.
    """

    received: bool = True
    message: str = "Webhook processed successfully"
