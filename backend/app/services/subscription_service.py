"""
Subscription service for managing SaaS subscriptions.

WHAT: Provides business logic for subscription management including
plan changes, Stripe Checkout integration, and webhook processing.

WHY: Subscriptions enable:
1. Recurring revenue via Stripe Billing
2. Tiered feature access based on plan (Free, Pro, Enterprise)
3. Self-service billing via Stripe Customer Portal
4. Usage limits enforcement

HOW: Integrates with:
- SubscriptionDAO for database operations
- Stripe API for billing operations
- Webhook handlers for async status updates

Design decisions:
- Stripe Checkout for subscriptions: Secure, hosted payment page
- Customer Portal for self-service: Reduces support burden
- Webhook-first status updates: Source of truth for billing state
- Prorated upgrades: Fair billing for mid-cycle changes
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

import stripe

from app.core.config import settings
from app.core.exceptions import (
    StripeError,
    ValidationError,
    ResourceNotFoundError,
    AppException,
)
from app.dao.subscription import SubscriptionDAO
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus, PLAN_LIMITS
from app.models.organization import Organization
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============================================================================
# Stripe Configuration
# ============================================================================


def configure_stripe() -> None:
    """
    Configure Stripe SDK with API key from settings.

    WHAT: Sets up the Stripe SDK with the secret key.

    WHY: Must be called before any Stripe API operations.
    Centralized configuration ensures consistent setup.
    """
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = "2023-10-16"


# Initialize Stripe on module load
configure_stripe()


# ============================================================================
# Exceptions
# ============================================================================


class SubscriptionError(AppException):
    """Base exception for subscription errors."""

    status_code = 400
    default_message = "Subscription operation failed"


class SubscriptionNotFoundError(ResourceNotFoundError):
    """Subscription not found."""

    default_message = "Subscription not found"


class PlanNotConfiguredError(SubscriptionError):
    """Plan price not configured in Stripe."""

    default_message = "Plan pricing not configured"


class SubscriptionAlreadyExistsError(SubscriptionError):
    """Organization already has a paid subscription."""

    default_message = "Organization already has an active subscription"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class SubscriptionCheckoutSession:
    """
    Represents a Stripe Checkout Session for subscription.

    WHAT: Data container for subscription checkout session.

    WHY: Structured data for consistent handling of checkout info.
    """

    id: str
    url: str
    customer_id: Optional[str] = None


@dataclass
class CustomerPortalSession:
    """
    Represents a Stripe Customer Portal session.

    WHAT: Data container for customer portal session.

    WHY: Provides URL for self-service billing management.
    """

    id: str
    url: str


# ============================================================================
# Plan Configuration
# ============================================================================


# Map plan + interval to Stripe price ID
def get_stripe_price_id(plan: SubscriptionPlan, interval: str = "monthly") -> Optional[str]:
    """
    Get Stripe price ID for a plan and billing interval.

    WHAT: Maps our plan enum to Stripe price IDs.

    WHY: Price IDs are configured in Stripe Dashboard and stored in settings.
    This mapping allows changing prices without code changes.

    Args:
        plan: Subscription plan
        interval: Billing interval ('monthly' or 'yearly')

    Returns:
        Stripe price ID or None if not configured
    """
    price_map = {
        (SubscriptionPlan.PRO, "monthly"): settings.STRIPE_PRICE_PRO_MONTHLY,
        (SubscriptionPlan.PRO, "yearly"): settings.STRIPE_PRICE_PRO_YEARLY,
        (SubscriptionPlan.ENTERPRISE, "monthly"): settings.STRIPE_PRICE_ENTERPRISE_MONTHLY,
        (SubscriptionPlan.ENTERPRISE, "yearly"): settings.STRIPE_PRICE_ENTERPRISE_YEARLY,
    }
    return price_map.get((plan, interval))


# Plan pricing for display (in USD)
PLAN_PRICING = {
    SubscriptionPlan.FREE: {
        "monthly": 0,
        "yearly": 0,
    },
    SubscriptionPlan.PRO: {
        "monthly": 29.00,
        "yearly": 290.00,  # 2 months free
    },
    SubscriptionPlan.ENTERPRISE: {
        "monthly": 99.00,
        "yearly": 990.00,  # 2 months free
    },
}


# Plan descriptions
PLAN_DESCRIPTIONS = {
    SubscriptionPlan.FREE: "Basic features for small projects",
    SubscriptionPlan.PRO: "Advanced features for growing teams",
    SubscriptionPlan.ENTERPRISE: "Unlimited features for large organizations",
}


# Plan feature lists
PLAN_FEATURES = {
    SubscriptionPlan.FREE: [
        "Up to 3 projects",
        "Up to 5 workflows",
        "2 team members",
        "1 GB storage",
        "Community support",
    ],
    SubscriptionPlan.PRO: [
        "Up to 20 projects",
        "Up to 50 workflows",
        "10 team members",
        "50 GB storage",
        "Email support",
        "Priority workflow execution",
        "Custom branding",
    ],
    SubscriptionPlan.ENTERPRISE: [
        "Unlimited projects",
        "Unlimited workflows",
        "Unlimited team members",
        "Unlimited storage",
        "Priority support",
        "Dedicated account manager",
        "SLA guarantees",
        "SSO & SAML",
        "Audit logs",
    ],
}


# ============================================================================
# Subscription Service
# ============================================================================


class SubscriptionService:
    """
    Service for subscription management.

    WHAT: High-level interface for subscription operations.

    WHY: Centralizes subscription business logic:
    - Plan information and pricing
    - Stripe Checkout integration
    - Customer Portal access
    - Webhook processing
    - Usage tracking

    HOW: Coordinates between SubscriptionDAO and Stripe API.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize subscription service.

        Args:
            db: Async database session
        """
        self.db = db
        self.dao = SubscriptionDAO(db)

    # ========================================================================
    # Plan Information
    # ========================================================================

    def get_all_plans(self) -> list:
        """
        Get information about all available plans.

        WHAT: Returns detailed info for all subscription plans.

        WHY: Frontend needs this for:
        - Pricing page
        - Upgrade modal
        - Feature comparison

        Returns:
            List of plan info dictionaries
        """
        plans = []
        for plan in SubscriptionPlan:
            limits = PLAN_LIMITS[plan]
            plans.append({
                "plan": plan.value,
                "name": plan.value.title(),
                "description": PLAN_DESCRIPTIONS[plan],
                "price_monthly": PLAN_PRICING[plan]["monthly"],
                "price_yearly": PLAN_PRICING[plan]["yearly"],
                "limits": {
                    "projects_limit": limits["projects_limit"],
                    "workflows_limit": limits["workflows_limit"],
                    "users_limit": limits["users_limit"],
                    "storage_gb": limits["storage_gb"],
                    "support_level": limits["support_level"],
                },
                "features": PLAN_FEATURES[plan],
                "stripe_price_id_monthly": get_stripe_price_id(plan, "monthly"),
                "stripe_price_id_yearly": get_stripe_price_id(plan, "yearly"),
            })
        return plans

    # ========================================================================
    # Subscription Management
    # ========================================================================

    async def get_subscription(self, org_id: int) -> Optional[Subscription]:
        """
        Get subscription for an organization.

        WHAT: Retrieves the subscription record.

        WHY: Primary method for checking plan and status.

        Args:
            org_id: Organization ID

        Returns:
            Subscription or None
        """
        return await self.dao.get_by_org_id(org_id)

    async def get_subscription_or_create_free(self, org_id: int) -> Subscription:
        """
        Get subscription or create a FREE subscription.

        WHAT: Ensures organization has a subscription.

        WHY: All organizations should have a subscription record,
        even if on the FREE plan.

        Args:
            org_id: Organization ID

        Returns:
            Subscription (existing or newly created)
        """
        subscription = await self.dao.get_by_org_id(org_id)
        if subscription:
            return subscription

        # Create FREE subscription
        return await self.dao.create_for_org(
            org_id=org_id,
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.ACTIVE,
        )

    async def ensure_subscription_exists(self, org_id: int) -> Subscription:
        """
        Ensure organization has a subscription record.

        WHAT: Creates FREE subscription if none exists.

        WHY: Called during organization creation or first access.

        Args:
            org_id: Organization ID

        Returns:
            Subscription
        """
        return await self.get_subscription_or_create_free(org_id)

    # ========================================================================
    # Stripe Checkout
    # ========================================================================

    async def create_checkout_session(
        self,
        org: Organization,
        plan: SubscriptionPlan,
        billing_interval: str,
        success_url: str,
        cancel_url: str,
    ) -> SubscriptionCheckoutSession:
        """
        Create a Stripe Checkout Session for subscription.

        WHAT: Initiates subscription checkout flow.

        WHY: Stripe Checkout provides:
        - PCI-compliant hosted payment page
        - Subscription setup with payment method
        - Free trial support
        - Automatic tax collection

        HOW: Creates Checkout Session with subscription mode.

        Args:
            org: Organization subscribing
            plan: Target subscription plan
            billing_interval: 'monthly' or 'yearly'
            success_url: Redirect URL after success
            cancel_url: Redirect URL if cancelled

        Returns:
            SubscriptionCheckoutSession with checkout URL

        Raises:
            PlanNotConfiguredError: If Stripe price not configured
            SubscriptionAlreadyExistsError: If already has paid subscription
            StripeError: If Stripe API fails
        """
        # Validate plan has pricing
        if plan == SubscriptionPlan.FREE:
            raise ValidationError(
                message="Cannot checkout for FREE plan",
                details={"plan": plan.value},
            )

        price_id = get_stripe_price_id(plan, billing_interval)
        if not price_id:
            raise PlanNotConfiguredError(
                message=f"Stripe price not configured for {plan.value} {billing_interval}",
                details={"plan": plan.value, "interval": billing_interval},
            )

        # Check existing subscription
        subscription = await self.dao.get_by_org_id(org.id)
        if subscription and subscription.stripe_subscription_id:
            if subscription.is_active and not subscription.is_canceled:
                raise SubscriptionAlreadyExistsError(
                    message="Organization already has an active subscription",
                    details={"org_id": org.id, "current_plan": subscription.plan.value},
                )

        try:
            # Get or create Stripe customer
            customer_id = org.stripe_customer_id
            if not customer_id:
                customer = stripe.Customer.create(
                    name=org.name,
                    metadata={
                        "org_id": str(org.id),
                        "source": "automation_platform",
                    },
                )
                customer_id = customer["id"]
                # Note: Caller should update org.stripe_customer_id

            # Create checkout session
            session_params = {
                "mode": "subscription",
                "customer": customer_id,
                "line_items": [
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                "metadata": {
                    "org_id": str(org.id),
                    "plan": plan.value,
                    "interval": billing_interval,
                },
                "success_url": success_url,
                "cancel_url": cancel_url,
                "subscription_data": {
                    "metadata": {
                        "org_id": str(org.id),
                        "plan": plan.value,
                    },
                },
            }

            # Add trial period if configured
            if settings.STRIPE_TRIAL_DAYS > 0:
                session_params["subscription_data"]["trial_period_days"] = settings.STRIPE_TRIAL_DAYS

            session = stripe.checkout.Session.create(**session_params)

            logger.info(
                f"Created subscription checkout session {session['id']} for org {org.id}",
                extra={
                    "checkout_session_id": session["id"],
                    "org_id": org.id,
                    "plan": plan.value,
                    "interval": billing_interval,
                },
            )

            return SubscriptionCheckoutSession(
                id=session["id"],
                url=session["url"],
                customer_id=customer_id,
            )

        except stripe.StripeError as e:
            logger.error(f"Stripe checkout error: {e}", extra={"org_id": org.id})
            raise StripeError(
                message="Failed to create subscription checkout",
                stripe_error=str(e),
                org_id=org.id,
            )

    async def create_customer_portal_session(
        self,
        org: Organization,
        return_url: str,
    ) -> CustomerPortalSession:
        """
        Create a Stripe Customer Portal session.

        WHAT: Creates a session for self-service billing management.

        WHY: Customer Portal allows users to:
        - Update payment method
        - View invoices and receipts
        - Cancel subscription
        - Change plan (if configured)

        Args:
            org: Organization
            return_url: URL to redirect after portal session

        Returns:
            CustomerPortalSession with portal URL

        Raises:
            SubscriptionNotFoundError: If no Stripe customer
            StripeError: If Stripe API fails
        """
        if not org.stripe_customer_id:
            raise SubscriptionNotFoundError(
                message="No billing information found for organization",
                details={"org_id": org.id},
            )

        try:
            session = stripe.billing_portal.Session.create(
                customer=org.stripe_customer_id,
                return_url=return_url,
            )

            logger.info(
                f"Created customer portal session for org {org.id}",
                extra={
                    "org_id": org.id,
                    "customer_id": org.stripe_customer_id,
                },
            )

            return CustomerPortalSession(
                id=session["id"],
                url=session["url"],
            )

        except stripe.StripeError as e:
            logger.error(f"Stripe portal error: {e}", extra={"org_id": org.id})
            raise StripeError(
                message="Failed to create customer portal session",
                stripe_error=str(e),
                org_id=org.id,
            )

    # ========================================================================
    # Subscription Changes
    # ========================================================================

    async def cancel_subscription(
        self,
        org_id: int,
        cancel_immediately: bool = False,
        reason: Optional[str] = None,
    ) -> Subscription:
        """
        Cancel a subscription.

        WHAT: Cancels the subscription with Stripe and updates database.

        WHY: Supports two cancellation modes:
        - cancel_immediately=False: Cancel at period end (default)
        - cancel_immediately=True: Cancel now, access revoked

        Args:
            org_id: Organization ID
            cancel_immediately: If True, cancel now; if False, at period end
            reason: Optional cancellation reason for analytics

        Returns:
            Updated Subscription

        Raises:
            SubscriptionNotFoundError: If subscription not found
            StripeError: If Stripe API fails
        """
        subscription = await self.dao.get_by_org_id(org_id)
        if not subscription:
            raise SubscriptionNotFoundError(
                message="Subscription not found",
                details={"org_id": org_id},
            )

        if not subscription.stripe_subscription_id:
            # FREE plan, just mark as canceled
            return await self.dao.cancel_subscription(
                org_id=org_id,
                cancel_at_period_end=not cancel_immediately,
            )

        try:
            if cancel_immediately:
                # Cancel immediately
                stripe.Subscription.cancel(subscription.stripe_subscription_id)
            else:
                # Cancel at period end
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True,
                    metadata={
                        "cancellation_reason": reason or "user_requested",
                    },
                )

            logger.info(
                f"Cancelled subscription for org {org_id}",
                extra={
                    "org_id": org_id,
                    "immediately": cancel_immediately,
                    "reason": reason,
                },
            )

            # Update database (webhook will also update, but sync for response)
            return await self.dao.cancel_subscription(
                org_id=org_id,
                cancel_at_period_end=not cancel_immediately,
            )

        except stripe.StripeError as e:
            logger.error(f"Stripe cancellation error: {e}", extra={"org_id": org_id})
            raise StripeError(
                message="Failed to cancel subscription",
                stripe_error=str(e),
                org_id=org_id,
            )

    async def reactivate_subscription(self, org_id: int) -> Subscription:
        """
        Reactivate a subscription pending cancellation.

        WHAT: Removes the cancellation request.

        WHY: Allows users to undo cancellation before period ends.

        Args:
            org_id: Organization ID

        Returns:
            Updated Subscription

        Raises:
            SubscriptionNotFoundError: If subscription not found
            ValidationError: If subscription not pending cancellation
            StripeError: If Stripe API fails
        """
        subscription = await self.dao.get_by_org_id(org_id)
        if not subscription:
            raise SubscriptionNotFoundError(
                message="Subscription not found",
                details={"org_id": org_id},
            )

        if not subscription.cancel_at_period_end:
            raise ValidationError(
                message="Subscription is not pending cancellation",
                details={"org_id": org_id},
            )

        if subscription.stripe_subscription_id:
            try:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False,
                )
            except stripe.StripeError as e:
                logger.error(f"Stripe reactivation error: {e}", extra={"org_id": org_id})
                raise StripeError(
                    message="Failed to reactivate subscription",
                    stripe_error=str(e),
                    org_id=org_id,
                )

        logger.info(f"Reactivated subscription for org {org_id}", extra={"org_id": org_id})

        return await self.dao.reactivate_subscription(org_id)

    # ========================================================================
    # Usage Tracking
    # ========================================================================

    async def get_usage_stats(
        self,
        org_id: int,
        projects_count: int,
        workflows_count: int,
        users_count: int,
    ) -> dict:
        """
        Get usage statistics for an organization.

        WHAT: Calculates current usage vs plan limits.

        WHY: Shows users their resource consumption for:
        - Progress bars in UI
        - Upgrade prompts
        - Limit enforcement

        Args:
            org_id: Organization ID
            projects_count: Current project count
            workflows_count: Current workflow count
            users_count: Current user count

        Returns:
            Dict with usage stats and percentages
        """
        subscription = await self.get_subscription_or_create_free(org_id)

        def calc_percentage(count: int, limit: Optional[int]) -> Optional[float]:
            if limit is None:
                return None
            return min(100.0, (count / limit) * 100)

        return {
            "projects_count": projects_count,
            "projects_limit": subscription.projects_limit,
            "projects_percentage": calc_percentage(projects_count, subscription.projects_limit),
            "workflows_count": workflows_count,
            "workflows_limit": subscription.workflows_limit,
            "workflows_percentage": calc_percentage(workflows_count, subscription.workflows_limit),
            "users_count": users_count,
            "users_limit": subscription.users_limit,
            "users_percentage": calc_percentage(users_count, subscription.users_limit),
        }

    async def check_can_add_project(self, org_id: int, current_count: int) -> Tuple[bool, Optional[str]]:
        """
        Check if organization can add another project.

        WHAT: Validates project creation against plan limits.

        WHY: Enforces plan limits at the service layer.

        Args:
            org_id: Organization ID
            current_count: Current number of projects

        Returns:
            Tuple of (can_add: bool, reason: str if cannot add)
        """
        subscription = await self.get_subscription_or_create_free(org_id)

        if subscription.can_add_project(current_count):
            return True, None

        return False, f"Project limit reached ({subscription.projects_limit} projects). Upgrade to add more."

    async def check_can_add_workflow(self, org_id: int, current_count: int) -> Tuple[bool, Optional[str]]:
        """
        Check if organization can add another workflow.

        Args:
            org_id: Organization ID
            current_count: Current number of workflows

        Returns:
            Tuple of (can_add: bool, reason: str if cannot add)
        """
        subscription = await self.get_subscription_or_create_free(org_id)

        if subscription.can_add_workflow(current_count):
            return True, None

        return False, f"Workflow limit reached ({subscription.workflows_limit} workflows). Upgrade to add more."

    async def check_can_add_user(self, org_id: int, current_count: int) -> Tuple[bool, Optional[str]]:
        """
        Check if organization can add another user.

        Args:
            org_id: Organization ID
            current_count: Current number of users

        Returns:
            Tuple of (can_add: bool, reason: str if cannot add)
        """
        subscription = await self.get_subscription_or_create_free(org_id)

        if subscription.can_add_user(current_count):
            return True, None

        return False, f"User limit reached ({subscription.users_limit} users). Upgrade to add more."

    # ========================================================================
    # Webhook Handling
    # ========================================================================

    async def handle_subscription_created(
        self,
        stripe_subscription: Dict[str, Any],
    ) -> Optional[Subscription]:
        """
        Handle customer.subscription.created webhook.

        WHAT: Links new Stripe subscription to organization.

        WHY: Called when checkout completes or subscription created via API.

        Args:
            stripe_subscription: Stripe subscription object from webhook

        Returns:
            Updated Subscription or None if org not found
        """
        org_id = stripe_subscription.get("metadata", {}).get("org_id")
        if not org_id:
            logger.warning("Subscription created webhook missing org_id metadata")
            return None

        org_id = int(org_id)
        plan_str = stripe_subscription.get("metadata", {}).get("plan", "pro")

        try:
            plan = SubscriptionPlan(plan_str)
        except ValueError:
            plan = SubscriptionPlan.PRO

        # Determine status
        status_map = {
            "trialing": SubscriptionStatus.TRIALING,
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "unpaid": SubscriptionStatus.UNPAID,
            "incomplete": SubscriptionStatus.INCOMPLETE,
            "incomplete_expired": SubscriptionStatus.INCOMPLETE_EXPIRED,
            "paused": SubscriptionStatus.PAUSED,
        }
        status = status_map.get(
            stripe_subscription.get("status"),
            SubscriptionStatus.ACTIVE,
        )

        # Parse dates
        def parse_timestamp(ts: Optional[int]) -> Optional[datetime]:
            if ts:
                return datetime.fromtimestamp(ts)
            return None

        return await self.dao.link_stripe_subscription(
            org_id=org_id,
            stripe_subscription_id=stripe_subscription["id"],
            stripe_price_id=stripe_subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id"),
            plan=plan,
            status=status,
            current_period_start=parse_timestamp(stripe_subscription.get("current_period_start")),
            current_period_end=parse_timestamp(stripe_subscription.get("current_period_end")),
            trial_start=parse_timestamp(stripe_subscription.get("trial_start")),
            trial_end=parse_timestamp(stripe_subscription.get("trial_end")),
        )

    async def handle_subscription_updated(
        self,
        stripe_subscription: Dict[str, Any],
    ) -> Optional[Subscription]:
        """
        Handle customer.subscription.updated webhook.

        WHAT: Updates subscription status from Stripe event.

        WHY: Handles:
        - Status changes (trialing → active, active → past_due)
        - Plan changes
        - Cancellation/reactivation
        - Period changes

        Args:
            stripe_subscription: Stripe subscription object from webhook

        Returns:
            Updated Subscription or None if not found
        """
        stripe_subscription_id = stripe_subscription["id"]

        # Map Stripe status to our status
        status_map = {
            "trialing": SubscriptionStatus.TRIALING,
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "unpaid": SubscriptionStatus.UNPAID,
            "incomplete": SubscriptionStatus.INCOMPLETE,
            "incomplete_expired": SubscriptionStatus.INCOMPLETE_EXPIRED,
            "paused": SubscriptionStatus.PAUSED,
        }
        status = status_map.get(
            stripe_subscription.get("status"),
            SubscriptionStatus.ACTIVE,
        )

        # Parse dates
        def parse_timestamp(ts: Optional[int]) -> Optional[datetime]:
            if ts:
                return datetime.fromtimestamp(ts)
            return None

        return await self.dao.update_from_stripe_event(
            stripe_subscription_id=stripe_subscription_id,
            status=status,
            stripe_price_id=stripe_subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id"),
            current_period_start=parse_timestamp(stripe_subscription.get("current_period_start")),
            current_period_end=parse_timestamp(stripe_subscription.get("current_period_end")),
            trial_start=parse_timestamp(stripe_subscription.get("trial_start")),
            trial_end=parse_timestamp(stripe_subscription.get("trial_end")),
            cancel_at_period_end=stripe_subscription.get("cancel_at_period_end", False),
            canceled_at=parse_timestamp(stripe_subscription.get("canceled_at")),
        )

    async def handle_subscription_deleted(
        self,
        stripe_subscription: Dict[str, Any],
    ) -> Optional[Subscription]:
        """
        Handle customer.subscription.deleted webhook.

        WHAT: Downgrades subscription to FREE after deletion.

        WHY: When subscription is fully canceled (not just cancel_at_period_end),
        revert to FREE plan.

        Args:
            stripe_subscription: Stripe subscription object from webhook

        Returns:
            Updated Subscription or None if not found
        """
        subscription = await self.dao.get_by_stripe_subscription_id(
            stripe_subscription["id"]
        )
        if not subscription:
            logger.warning(
                f"Subscription deleted webhook for unknown subscription: {stripe_subscription['id']}"
            )
            return None

        logger.info(
            f"Subscription deleted for org {subscription.org_id}, downgrading to FREE",
            extra={"org_id": subscription.org_id},
        )

        return await self.dao.downgrade_to_free(subscription.org_id)

    # ========================================================================
    # Admin Operations
    # ========================================================================

    async def admin_update_subscription(
        self,
        org_id: int,
        plan: Optional[SubscriptionPlan] = None,
        status: Optional[SubscriptionStatus] = None,
        trial_end: Optional[datetime] = None,
        current_period_end: Optional[datetime] = None,
    ) -> Subscription:
        """
        Admin override for subscription settings.

        WHAT: Allows admins to manually update subscription.

        WHY: Needed for:
        - Partner/VIP accounts
        - Issue resolution
        - Trial extensions
        - Manual plan assignment

        Args:
            org_id: Organization ID
            plan: Optional new plan
            status: Optional new status
            trial_end: Optional new trial end date
            current_period_end: Optional new period end date

        Returns:
            Updated Subscription

        Raises:
            SubscriptionNotFoundError: If subscription not found
        """
        subscription = await self.dao.get_by_org_id(org_id)
        if not subscription:
            raise SubscriptionNotFoundError(
                message="Subscription not found",
                details={"org_id": org_id},
            )

        update_data = {}
        if plan is not None:
            update_data["plan"] = plan
        if status is not None:
            update_data["status"] = status
        if trial_end is not None:
            update_data["trial_end"] = trial_end
        if current_period_end is not None:
            update_data["current_period_end"] = current_period_end

        if update_data:
            return await self.dao.update(subscription.id, **update_data)

        return subscription

    async def get_subscription_stats(self) -> dict:
        """
        Get aggregate subscription statistics.

        WHAT: Returns counts and metrics for admin dashboard.

        WHY: Provides business metrics:
        - Plan distribution
        - Status distribution
        - Trial metrics
        - Revenue indicators

        Returns:
            Dict with subscription statistics
        """
        by_plan = await self.dao.count_by_plan()
        by_status = await self.dao.count_by_status()
        expiring_trials = await self.dao.get_expiring_trials(days=7)
        past_due = await self.dao.get_past_due_subscriptions()

        # Calculate MRR estimate
        mrr = 0.0
        for plan, count in by_plan.items():
            if plan != "free":
                mrr += PLAN_PRICING.get(SubscriptionPlan(plan), {}).get("monthly", 0) * count

        total = sum(by_plan.values())

        return {
            "total_subscriptions": total,
            "by_plan": by_plan,
            "by_status": by_status,
            "active_trials": by_status.get("trialing", 0),
            "expiring_trials_7_days": len(expiring_trials),
            "past_due_count": len(past_due),
            "mrr_estimate": mrr,
        }
