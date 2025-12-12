"""
Subscription API endpoints for managing SaaS subscriptions.

WHAT: REST API endpoints for subscription management including:
1. GET /subscriptions - Get current subscription and usage
2. GET /subscriptions/plans - List available plans
3. POST /subscriptions/checkout - Create Stripe Checkout session
4. POST /subscriptions/portal - Create Stripe Customer Portal session
5. POST /subscriptions/cancel - Cancel subscription
6. POST /subscriptions/reactivate - Reactivate canceled subscription
7. POST /subscriptions/webhooks/stripe - Handle Stripe webhooks

WHY: Enables:
- Self-service subscription management
- Stripe integration for billing
- Usage tracking against plan limits
- Admin subscription management

SECURITY (OWASP):
- A01: Organization-scoped data access
- A02: Webhook signature verification
- A07: Authenticated endpoints only (except webhook)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

import stripe

from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.core.exceptions import StripeError
from app.db.session import get_db
from app.models.user import User
from app.schemas.subscription import (
    SubscriptionResponse,
    SubscriptionSummary,
    UsageResponse,
    UsageStats,
    PlansResponse,
    PlanInfo,
    PlanLimits,
    SubscriptionCheckoutRequest,
    SubscriptionCheckoutResponse,
    CustomerPortalRequest,
    CustomerPortalResponse,
    SubscriptionCancelRequest,
    SubscriptionCancelResponse,
    SubscriptionReactivateResponse,
    AdminSubscriptionUpdate,
    SubscriptionStats,
    SubscriptionPlan,
    SubscriptionStatus,
    WebhookResponse,
)
from app.services.subscription_service import (
    SubscriptionService,
    PLAN_PRICING,
    PLAN_DESCRIPTIONS,
    PLAN_FEATURES,
    get_stripe_price_id,
)
from app.dao.project import ProjectDAO
from app.dao.workflow_instance import WorkflowInstanceDAO
from app.dao.user import UserDAO
from app.models.project import Project
from app.models.workflow import WorkflowInstance
from app.models.subscription import PLAN_LIMITS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


# ============================================================================
# Plan Information
# ============================================================================


@router.get(
    "/plans",
    response_model=PlansResponse,
    summary="List available subscription plans",
    description="Returns all available subscription plans with pricing and features.",
)
async def list_plans():
    """
    List all available subscription plans.

    WHY: Frontend needs plan details for:
    - Pricing page
    - Upgrade modal
    - Feature comparison

    Returns:
        List of all plans with pricing and features
    """
    plans = []
    for plan in [SubscriptionPlan.FREE, SubscriptionPlan.PRO, SubscriptionPlan.ENTERPRISE]:
        model_plan = __import__(
            "app.models.subscription",
            fromlist=["SubscriptionPlan"]
        ).SubscriptionPlan(plan.value)

        limits = PLAN_LIMITS[model_plan]
        plans.append(
            PlanInfo(
                plan=plan,
                name=plan.value.title(),
                description=PLAN_DESCRIPTIONS.get(model_plan, ""),
                price_monthly=PLAN_PRICING.get(model_plan, {}).get("monthly"),
                price_yearly=PLAN_PRICING.get(model_plan, {}).get("yearly"),
                limits=PlanLimits(
                    projects_limit=limits["projects_limit"],
                    workflows_limit=limits["workflows_limit"],
                    users_limit=limits["users_limit"],
                    storage_gb=limits["storage_gb"],
                    support_level=limits["support_level"],
                ),
                features=PLAN_FEATURES.get(model_plan, []),
                stripe_price_id_monthly=get_stripe_price_id(model_plan, "monthly"),
                stripe_price_id_yearly=get_stripe_price_id(model_plan, "yearly"),
            )
        )

    return PlansResponse(plans=plans)


# ============================================================================
# Subscription Status
# ============================================================================


@router.get(
    "",
    response_model=UsageResponse,
    summary="Get current subscription and usage",
    description="Returns the organization's subscription details and current resource usage.",
)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current subscription and usage for user's organization.

    WHY: Primary endpoint for subscription status page showing:
    - Current plan and status
    - Billing period info
    - Resource usage vs limits

    Returns:
        Subscription details with usage statistics
    """
    service = SubscriptionService(db)

    # Get or create subscription
    subscription = await service.get_subscription_or_create_free(current_user.org_id)

    # Get current usage counts
    project_dao = ProjectDAO(Project, db)
    workflow_dao = WorkflowInstanceDAO(WorkflowInstance, db)
    user_dao = UserDAO(User, db)

    projects_count = await project_dao.count(org_id=current_user.org_id)
    workflows_count = await workflow_dao.count(org_id=current_user.org_id)
    users_count = await user_dao.count(org_id=current_user.org_id)

    # Get usage stats
    usage = await service.get_usage_stats(
        org_id=current_user.org_id,
        projects_count=projects_count,
        workflows_count=workflows_count,
        users_count=users_count,
    )

    return UsageResponse(
        subscription=SubscriptionResponse(
            id=subscription.id,
            org_id=subscription.org_id,
            plan=SubscriptionPlan(subscription.plan.value),
            status=SubscriptionStatus(subscription.status.value),
            stripe_subscription_id=subscription.stripe_subscription_id,
            stripe_price_id=subscription.stripe_price_id,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            trial_start=subscription.trial_start,
            trial_end=subscription.trial_end,
            cancel_at_period_end=subscription.cancel_at_period_end,
            canceled_at=subscription.canceled_at,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
            is_active=subscription.is_active,
            is_trialing=subscription.is_trialing,
            is_canceled=subscription.is_canceled,
            projects_limit=subscription.projects_limit,
            workflows_limit=subscription.workflows_limit,
            users_limit=subscription.users_limit,
            storage_gb=subscription.storage_gb,
            support_level=subscription.support_level,
            days_until_period_end=subscription.days_until_period_end(),
            days_until_trial_end=subscription.days_until_trial_end(),
        ),
        usage=UsageStats(**usage),
    )


@router.get(
    "/summary",
    response_model=SubscriptionSummary,
    summary="Get subscription summary",
    description="Returns a lightweight subscription summary for headers/navigation.",
)
async def get_subscription_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get lightweight subscription summary.

    WHY: Minimal data for frequent display in UI headers
    without full subscription details.

    Returns:
        Subscription summary with plan and status
    """
    service = SubscriptionService(db)
    subscription = await service.get_subscription_or_create_free(current_user.org_id)

    return SubscriptionSummary(
        plan=SubscriptionPlan(subscription.plan.value),
        status=SubscriptionStatus(subscription.status.value),
        is_active=subscription.is_active,
        is_trialing=subscription.is_trialing,
        days_until_trial_end=subscription.days_until_trial_end(),
    )


# ============================================================================
# Checkout & Portal
# ============================================================================


@router.post(
    "/checkout",
    response_model=SubscriptionCheckoutResponse,
    summary="Create subscription checkout session",
    description="Creates a Stripe Checkout session for subscribing to a plan.",
)
async def create_checkout(
    request: SubscriptionCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create Stripe Checkout session for subscription.

    WHY: Stripe Checkout provides:
    - Secure, hosted payment page
    - PCI compliance
    - Multiple payment method support
    - Trial period handling

    Args:
        request: Checkout request with plan and URLs

    Returns:
        Checkout session with redirect URL
    """
    from app.dao.base import BaseDAO
    from app.models.organization import Organization

    # Get organization
    org_dao = BaseDAO(Organization, db)
    org = await org_dao.get_by_id(current_user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    service = SubscriptionService(db)

    # Map schema plan to model plan
    model_plan = __import__(
        "app.models.subscription",
        fromlist=["SubscriptionPlan"]
    ).SubscriptionPlan(request.plan.value)

    checkout_session = await service.create_checkout_session(
        org=org,
        plan=model_plan,
        billing_interval=request.billing_interval,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
    )

    # Update org's Stripe customer ID if newly created
    if checkout_session.customer_id and not org.stripe_customer_id:
        await org_dao.update(org.id, stripe_customer_id=checkout_session.customer_id)
        await db.commit()

    return SubscriptionCheckoutResponse(
        checkout_session_id=checkout_session.id,
        checkout_url=checkout_session.url,
    )


@router.post(
    "/portal",
    response_model=CustomerPortalResponse,
    summary="Create customer portal session",
    description="Creates a Stripe Customer Portal session for billing management.",
)
async def create_portal_session(
    request: CustomerPortalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create Stripe Customer Portal session.

    WHY: Customer Portal enables self-service:
    - Update payment method
    - View invoices
    - Cancel subscription
    - Download receipts

    Args:
        request: Portal request with return URL

    Returns:
        Portal session with redirect URL
    """
    from app.dao.base import BaseDAO
    from app.models.organization import Organization

    # Get organization
    org_dao = BaseDAO(Organization, db)
    org = await org_dao.get_by_id(current_user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    service = SubscriptionService(db)

    portal_session = await service.create_customer_portal_session(
        org=org,
        return_url=request.return_url,
    )

    return CustomerPortalResponse(portal_url=portal_session.url)


# ============================================================================
# Subscription Management
# ============================================================================


@router.post(
    "/cancel",
    response_model=SubscriptionCancelResponse,
    summary="Cancel subscription",
    description="Cancels the organization's subscription.",
)
async def cancel_subscription(
    request: SubscriptionCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel the organization's subscription.

    WHY: Allows users to:
    - Cancel at period end (keep access until paid time expires)
    - Cancel immediately (revoke access now)

    Args:
        request: Cancellation options

    Returns:
        Updated subscription with access end date
    """
    service = SubscriptionService(db)

    subscription = await service.cancel_subscription(
        org_id=current_user.org_id,
        cancel_immediately=request.cancel_immediately,
        reason=request.cancellation_reason,
    )

    await db.commit()

    return SubscriptionCancelResponse(
        message="Subscription cancelled successfully",
        subscription=SubscriptionResponse(
            id=subscription.id,
            org_id=subscription.org_id,
            plan=SubscriptionPlan(subscription.plan.value),
            status=SubscriptionStatus(subscription.status.value),
            stripe_subscription_id=subscription.stripe_subscription_id,
            stripe_price_id=subscription.stripe_price_id,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            trial_start=subscription.trial_start,
            trial_end=subscription.trial_end,
            cancel_at_period_end=subscription.cancel_at_period_end,
            canceled_at=subscription.canceled_at,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
            is_active=subscription.is_active,
            is_trialing=subscription.is_trialing,
            is_canceled=subscription.is_canceled,
            projects_limit=subscription.projects_limit,
            workflows_limit=subscription.workflows_limit,
            users_limit=subscription.users_limit,
            storage_gb=subscription.storage_gb,
            support_level=subscription.support_level,
            days_until_period_end=subscription.days_until_period_end(),
            days_until_trial_end=subscription.days_until_trial_end(),
        ),
        access_until=subscription.current_period_end if not request.cancel_immediately else None,
    )


@router.post(
    "/reactivate",
    response_model=SubscriptionReactivateResponse,
    summary="Reactivate subscription",
    description="Reactivates a subscription that is pending cancellation.",
)
async def reactivate_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reactivate a subscription pending cancellation.

    WHY: Allows users to undo cancellation before period ends.

    Returns:
        Reactivated subscription
    """
    service = SubscriptionService(db)

    subscription = await service.reactivate_subscription(current_user.org_id)

    await db.commit()

    return SubscriptionReactivateResponse(
        message="Subscription reactivated successfully",
        subscription=SubscriptionResponse(
            id=subscription.id,
            org_id=subscription.org_id,
            plan=SubscriptionPlan(subscription.plan.value),
            status=SubscriptionStatus(subscription.status.value),
            stripe_subscription_id=subscription.stripe_subscription_id,
            stripe_price_id=subscription.stripe_price_id,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            trial_start=subscription.trial_start,
            trial_end=subscription.trial_end,
            cancel_at_period_end=subscription.cancel_at_period_end,
            canceled_at=subscription.canceled_at,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
            is_active=subscription.is_active,
            is_trialing=subscription.is_trialing,
            is_canceled=subscription.is_canceled,
            projects_limit=subscription.projects_limit,
            workflows_limit=subscription.workflows_limit,
            users_limit=subscription.users_limit,
            storage_gb=subscription.storage_gb,
            support_level=subscription.support_level,
            days_until_period_end=subscription.days_until_period_end(),
            days_until_trial_end=subscription.days_until_trial_end(),
        ),
    )


# ============================================================================
# Admin Endpoints
# ============================================================================


@router.get(
    "/admin/stats",
    response_model=SubscriptionStats,
    summary="Get subscription statistics",
    description="Returns aggregate subscription statistics (admin only).",
)
async def get_subscription_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Get subscription statistics for admin dashboard.

    WHY: Provides business metrics:
    - Plan distribution
    - Revenue indicators
    - Churn monitoring

    Returns:
        Aggregate subscription statistics
    """
    service = SubscriptionService(db)
    stats = await service.get_subscription_stats()

    return SubscriptionStats(**stats)


@router.patch(
    "/admin/{org_id}",
    response_model=SubscriptionResponse,
    summary="Admin update subscription",
    description="Admin-only endpoint to update subscription settings.",
)
async def admin_update_subscription(
    org_id: int,
    update: AdminSubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Admin override for subscription settings.

    WHY: Allows admins to:
    - Grant free upgrades to partners
    - Extend trials
    - Fix billing issues

    Args:
        org_id: Organization ID to update
        update: Fields to update

    Returns:
        Updated subscription
    """
    service = SubscriptionService(db)

    # Map schema enums to model enums if provided
    model_plan = None
    model_status = None

    if update.plan:
        model_plan = __import__(
            "app.models.subscription",
            fromlist=["SubscriptionPlan"]
        ).SubscriptionPlan(update.plan.value)

    if update.status:
        model_status = __import__(
            "app.models.subscription",
            fromlist=["SubscriptionStatus"]
        ).SubscriptionStatus(update.status.value)

    subscription = await service.admin_update_subscription(
        org_id=org_id,
        plan=model_plan,
        status=model_status,
        trial_end=update.trial_end,
        current_period_end=update.current_period_end,
    )

    await db.commit()

    return SubscriptionResponse(
        id=subscription.id,
        org_id=subscription.org_id,
        plan=SubscriptionPlan(subscription.plan.value),
        status=SubscriptionStatus(subscription.status.value),
        stripe_subscription_id=subscription.stripe_subscription_id,
        stripe_price_id=subscription.stripe_price_id,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_start=subscription.trial_start,
        trial_end=subscription.trial_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        canceled_at=subscription.canceled_at,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
        is_active=subscription.is_active,
        is_trialing=subscription.is_trialing,
        is_canceled=subscription.is_canceled,
        projects_limit=subscription.projects_limit,
        workflows_limit=subscription.workflows_limit,
        users_limit=subscription.users_limit,
        storage_gb=subscription.storage_gb,
        support_level=subscription.support_level,
        days_until_period_end=subscription.days_until_period_end(),
        days_until_trial_end=subscription.days_until_trial_end(),
    )


# ============================================================================
# Stripe Webhooks
# ============================================================================


# Create a separate router for webhooks (no auth required)
webhooks_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@webhooks_router.post(
    "/stripe/subscription",
    response_model=WebhookResponse,
    summary="Stripe subscription webhook",
    description="Handles Stripe subscription webhooks.",
)
async def stripe_subscription_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    """
    Handle Stripe subscription webhooks.

    WHY: Webhooks are the source of truth for subscription state:
    - subscription.created: New subscription
    - subscription.updated: Status changes, plan changes
    - subscription.deleted: Subscription ended

    SECURITY (OWASP A02):
    - Verifies webhook signature before processing
    - Prevents webhook forgery attacks

    Returns:
        Acknowledgment of webhook receipt
    """
    if not stripe_signature:
        logger.warning("Webhook received without Stripe-Signature header")
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    # Get raw body for signature verification
    payload = await request.body()

    try:
        # Verify signature
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except stripe.error.SignatureVerificationError as e:
        logger.warning(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing error")

    # Handle event
    service = SubscriptionService(db)
    event_type = event["type"]
    subscription_data = event["data"]["object"]

    logger.info(
        f"Processing subscription webhook: {event_type}",
        extra={
            "event_id": event["id"],
            "event_type": event_type,
        },
    )

    try:
        if event_type == "customer.subscription.created":
            await service.handle_subscription_created(subscription_data)
        elif event_type == "customer.subscription.updated":
            await service.handle_subscription_updated(subscription_data)
        elif event_type == "customer.subscription.deleted":
            await service.handle_subscription_deleted(subscription_data)
        else:
            logger.info(f"Unhandled subscription webhook event type: {event_type}")

        await db.commit()

    except Exception as e:
        logger.error(f"Error processing webhook {event_type}: {e}")
        await db.rollback()
        # Still return 200 to prevent Stripe retries for processing errors
        # Real errors should be monitored via logs

    return WebhookResponse(
        received=True,
        message=f"Webhook {event_type} processed",
    )
