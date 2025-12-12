"""
Subscription Data Access Object (DAO).

WHAT: DAO for managing subscription records in the database.

WHY: Subscriptions are critical for:
1. Enforcing plan limits (projects, workflows, users)
2. Tracking billing status with Stripe
3. Managing trial periods and cancellations
4. Determining feature access

HOW: Extends BaseDAO with subscription-specific queries like
getting subscription by org_id, Stripe subscription ID, and
updating subscription status from webhooks.
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.dao.base import BaseDAO
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus


class SubscriptionDAO(BaseDAO[Subscription]):
    """
    Data Access Object for Subscription model.

    WHAT: Handles all database operations for subscriptions.

    WHY: Centralizes subscription queries for:
    - Plan limit enforcement
    - Stripe webhook processing
    - Subscription lifecycle management

    HOW: Extends BaseDAO with subscription-specific methods for
    common query patterns like org lookups and Stripe ID lookups.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize SubscriptionDAO.

        WHY: Simplified constructor since model is always Subscription.

        Args:
            session: Async database session
        """
        super().__init__(Subscription, session)

    async def get_by_org_id(self, org_id: int) -> Optional[Subscription]:
        """
        Get subscription for an organization.

        WHAT: Retrieves the subscription record for a specific organization.

        WHY: Primary method for checking plan limits and subscription status.
        Each organization has exactly one subscription (1:1 relationship).

        HOW: Simple query by org_id with unique constraint guaranteeing
        at most one result.

        Args:
            org_id: Organization ID

        Returns:
            Subscription if found, None otherwise
        """
        result = await self.session.execute(
            select(Subscription).where(Subscription.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_stripe_subscription_id(
        self, stripe_subscription_id: str
    ) -> Optional[Subscription]:
        """
        Get subscription by Stripe subscription ID.

        WHAT: Looks up a subscription using the Stripe subscription ID.

        WHY: Essential for webhook processing. When Stripe sends events,
        we need to find the corresponding subscription in our database.

        HOW: Direct lookup by stripe_subscription_id which is unique.

        Args:
            stripe_subscription_id: Stripe subscription ID (sub_xxx)

        Returns:
            Subscription if found, None otherwise
        """
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_stripe_subscription_id_with_org(
        self, stripe_subscription_id: str
    ) -> Optional[Subscription]:
        """
        Get subscription with organization eagerly loaded.

        WHAT: Retrieves subscription with organization data in single query.

        WHY: Webhook handlers often need org data (e.g., to send notifications).
        Eager loading prevents N+1 query issues.

        HOW: Uses joinedload to fetch organization in the same query.

        Args:
            stripe_subscription_id: Stripe subscription ID (sub_xxx)

        Returns:
            Subscription with organization loaded, or None
        """
        result = await self.session.execute(
            select(Subscription)
            .options(joinedload(Subscription.organization))
            .where(Subscription.stripe_subscription_id == stripe_subscription_id)
        )
        return result.scalar_one_or_none()

    async def create_for_org(
        self,
        org_id: int,
        plan: SubscriptionPlan = SubscriptionPlan.FREE,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    ) -> Subscription:
        """
        Create a subscription for an organization.

        WHAT: Creates a new subscription record.

        WHY: Called when:
        1. Organization is created (default FREE plan)
        2. Organization upgrades from no subscription

        HOW: Creates subscription with org_id, defaulting to FREE plan.

        Args:
            org_id: Organization ID
            plan: Subscription plan (default FREE)
            status: Subscription status (default ACTIVE)

        Returns:
            Created Subscription instance

        Raises:
            IntegrityError: If org already has a subscription
        """
        return await self.create(
            org_id=org_id,
            plan=plan,
            status=status,
        )

    async def update_from_stripe_event(
        self,
        stripe_subscription_id: str,
        status: Optional[SubscriptionStatus] = None,
        plan: Optional[SubscriptionPlan] = None,
        stripe_price_id: Optional[str] = None,
        current_period_start: Optional[datetime] = None,
        current_period_end: Optional[datetime] = None,
        trial_start: Optional[datetime] = None,
        trial_end: Optional[datetime] = None,
        cancel_at_period_end: Optional[bool] = None,
        canceled_at: Optional[datetime] = None,
    ) -> Optional[Subscription]:
        """
        Update subscription from Stripe webhook event.

        WHAT: Updates subscription state based on Stripe event data.

        WHY: Stripe webhooks are the source of truth for subscription state.
        This method handles all the fields that can be updated from webhooks.

        HOW: Finds subscription by Stripe ID and updates only provided fields.

        Args:
            stripe_subscription_id: Stripe subscription ID
            status: New subscription status
            plan: New subscription plan
            stripe_price_id: New Stripe price ID
            current_period_start: Start of current billing period
            current_period_end: End of current billing period
            trial_start: Trial start date
            trial_end: Trial end date
            cancel_at_period_end: Whether subscription cancels at period end
            canceled_at: When cancellation was requested

        Returns:
            Updated Subscription or None if not found
        """
        subscription = await self.get_by_stripe_subscription_id(stripe_subscription_id)
        if not subscription:
            return None

        # Build update dict with only provided values
        update_data = {}
        if status is not None:
            update_data["status"] = status
        if plan is not None:
            update_data["plan"] = plan
        if stripe_price_id is not None:
            update_data["stripe_price_id"] = stripe_price_id
        if current_period_start is not None:
            update_data["current_period_start"] = current_period_start
        if current_period_end is not None:
            update_data["current_period_end"] = current_period_end
        if trial_start is not None:
            update_data["trial_start"] = trial_start
        if trial_end is not None:
            update_data["trial_end"] = trial_end
        if cancel_at_period_end is not None:
            update_data["cancel_at_period_end"] = cancel_at_period_end
        if canceled_at is not None:
            update_data["canceled_at"] = canceled_at

        if update_data:
            return await self.update(subscription.id, **update_data)

        return subscription

    async def link_stripe_subscription(
        self,
        org_id: int,
        stripe_subscription_id: str,
        stripe_price_id: str,
        plan: SubscriptionPlan,
        status: SubscriptionStatus,
        current_period_start: Optional[datetime] = None,
        current_period_end: Optional[datetime] = None,
        trial_start: Optional[datetime] = None,
        trial_end: Optional[datetime] = None,
    ) -> Optional[Subscription]:
        """
        Link a Stripe subscription to an organization's subscription.

        WHAT: Updates an existing subscription with Stripe details.

        WHY: Called after successful Stripe checkout to link the
        Stripe subscription to our database record.

        HOW: Finds subscription by org_id and updates with Stripe data.

        Args:
            org_id: Organization ID
            stripe_subscription_id: Stripe subscription ID
            stripe_price_id: Stripe price ID for the plan
            plan: Subscription plan
            status: Subscription status
            current_period_start: Start of current billing period
            current_period_end: End of current billing period
            trial_start: Trial start date (if applicable)
            trial_end: Trial end date (if applicable)

        Returns:
            Updated Subscription or None if not found
        """
        subscription = await self.get_by_org_id(org_id)
        if not subscription:
            return None

        return await self.update(
            subscription.id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_price_id=stripe_price_id,
            plan=plan,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            trial_start=trial_start,
            trial_end=trial_end,
        )

    async def cancel_subscription(
        self,
        org_id: int,
        cancel_at_period_end: bool = True,
    ) -> Optional[Subscription]:
        """
        Cancel a subscription.

        WHAT: Marks a subscription as pending cancellation.

        WHY: Supports both immediate cancellation and cancel-at-period-end.
        Usually we want cancel_at_period_end=True to honor paid time.

        HOW: Updates cancel_at_period_end flag and canceled_at timestamp.

        Args:
            org_id: Organization ID
            cancel_at_period_end: If True, access continues until period end

        Returns:
            Updated Subscription or None if not found
        """
        subscription = await self.get_by_org_id(org_id)
        if not subscription:
            return None

        update_data = {
            "cancel_at_period_end": cancel_at_period_end,
            "canceled_at": datetime.utcnow(),
        }

        # If immediate cancellation, set status to canceled
        if not cancel_at_period_end:
            update_data["status"] = SubscriptionStatus.CANCELED

        return await self.update(subscription.id, **update_data)

    async def reactivate_subscription(
        self,
        org_id: int,
    ) -> Optional[Subscription]:
        """
        Reactivate a canceled subscription.

        WHAT: Clears cancellation flags on a subscription.

        WHY: Allows users to undo cancellation before period end.

        HOW: Clears cancel_at_period_end and canceled_at fields.

        Args:
            org_id: Organization ID

        Returns:
            Updated Subscription or None if not found
        """
        subscription = await self.get_by_org_id(org_id)
        if not subscription:
            return None

        return await self.update(
            subscription.id,
            cancel_at_period_end=False,
            canceled_at=None,
        )

    async def downgrade_to_free(
        self,
        org_id: int,
    ) -> Optional[Subscription]:
        """
        Downgrade subscription to FREE plan.

        WHAT: Resets subscription to FREE plan.

        WHY: Called when:
        1. Subscription expires without renewal
        2. Payment fails permanently
        3. User explicitly downgrades

        HOW: Sets plan to FREE, clears Stripe IDs and billing info.

        Args:
            org_id: Organization ID

        Returns:
            Updated Subscription or None if not found
        """
        subscription = await self.get_by_org_id(org_id)
        if not subscription:
            return None

        return await self.update(
            subscription.id,
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id=None,
            stripe_price_id=None,
            current_period_start=None,
            current_period_end=None,
            trial_start=None,
            trial_end=None,
            cancel_at_period_end=False,
            canceled_at=None,
        )

    async def get_expiring_trials(
        self,
        days: int = 3,
    ) -> List[Subscription]:
        """
        Get subscriptions with trials expiring soon.

        WHAT: Finds subscriptions in trial that expire within specified days.

        WHY: Used for sending trial expiration reminders to users.

        HOW: Queries for trialing subscriptions with trial_end within range.

        Args:
            days: Number of days to look ahead

        Returns:
            List of subscriptions with expiring trials
        """
        from datetime import timedelta

        now = datetime.utcnow()
        cutoff = now + timedelta(days=days)

        result = await self.session.execute(
            select(Subscription)
            .options(joinedload(Subscription.organization))
            .where(
                and_(
                    Subscription.status == SubscriptionStatus.TRIALING,
                    Subscription.trial_end.isnot(None),
                    Subscription.trial_end >= now,
                    Subscription.trial_end <= cutoff,
                )
            )
        )
        return list(result.scalars().all())

    async def get_past_due_subscriptions(self) -> List[Subscription]:
        """
        Get all subscriptions in past_due status.

        WHAT: Finds subscriptions with failed payments.

        WHY: Used for:
        1. Sending payment failure notifications
        2. Admin dashboard monitoring
        3. Automated retry logic

        HOW: Simple query for past_due status.

        Returns:
            List of past_due subscriptions
        """
        result = await self.session.execute(
            select(Subscription)
            .options(joinedload(Subscription.organization))
            .where(Subscription.status == SubscriptionStatus.PAST_DUE)
        )
        return list(result.scalars().all())

    async def get_subscriptions_by_plan(
        self,
        plan: SubscriptionPlan,
    ) -> List[Subscription]:
        """
        Get all subscriptions for a specific plan.

        WHAT: Finds all subscriptions on a given plan.

        WHY: Useful for:
        1. Analytics and reporting
        2. Plan migration (e.g., deprecating a plan)
        3. Feature rollout by plan tier

        HOW: Simple query by plan field.

        Args:
            plan: Subscription plan to filter by

        Returns:
            List of subscriptions on the plan
        """
        result = await self.session.execute(
            select(Subscription)
            .options(joinedload(Subscription.organization))
            .where(Subscription.plan == plan)
        )
        return list(result.scalars().all())

    async def count_by_plan(self) -> dict:
        """
        Count subscriptions by plan.

        WHAT: Returns counts for each subscription plan.

        WHY: Admin analytics to understand plan distribution.

        HOW: Groups subscriptions by plan and counts.

        Returns:
            Dict mapping plan name to count
        """
        counts = {}
        for plan in SubscriptionPlan:
            result = await self.session.execute(
                select(Subscription).where(Subscription.plan == plan)
            )
            counts[plan.value] = len(list(result.scalars().all()))
        return counts

    async def count_by_status(self) -> dict:
        """
        Count subscriptions by status.

        WHAT: Returns counts for each subscription status.

        WHY: Admin analytics to monitor subscription health:
        - High past_due → payment issues
        - High canceled → churn problem

        HOW: Groups subscriptions by status and counts.

        Returns:
            Dict mapping status name to count
        """
        counts = {}
        for status in SubscriptionStatus:
            result = await self.session.execute(
                select(Subscription).where(Subscription.status == status)
            )
            counts[status.value] = len(list(result.scalars().all()))
        return counts
