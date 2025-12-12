"""
Push Subscription Data Access Object (DAO).

WHAT: Database operations for push subscription model.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for subscription operations
3. Enforces org-scoping for multi-tenancy
4. Handles subscription lifecycle

HOW: Extends BaseDAO with subscription-specific queries:
- Subscription CRUD
- User subscription management
- Batch operations for notifications
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.push_subscription import PushSubscription


class PushSubscriptionDAO(BaseDAO[PushSubscription]):
    """
    Data Access Object for PushSubscription model.

    WHAT: Provides operations for push subscriptions.

    WHY: Centralizes subscription management.

    HOW: Extends BaseDAO with push-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize PushSubscriptionDAO."""
        super().__init__(PushSubscription, session)

    async def get_by_endpoint(
        self,
        endpoint: str,
    ) -> Optional[PushSubscription]:
        """
        Get subscription by endpoint.

        WHAT: Finds subscription by unique endpoint URL.

        WHY: Endpoints uniquely identify subscriptions.

        Args:
            endpoint: Subscription endpoint URL

        Returns:
            PushSubscription if found
        """
        result = await self.session.execute(
            select(PushSubscription).where(
                PushSubscription.endpoint == endpoint,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_subscriptions(
        self,
        user_id: int,
        active_only: bool = True,
    ) -> List[PushSubscription]:
        """
        Get all subscriptions for a user.

        WHAT: Lists user's push subscriptions.

        WHY: Users may have multiple devices.

        Args:
            user_id: User ID
            active_only: Only return active subscriptions

        Returns:
            List of subscriptions
        """
        query = select(PushSubscription).where(
            PushSubscription.user_id == user_id,
        )

        if active_only:
            query = query.where(PushSubscription.is_active == True)

        query = query.order_by(PushSubscription.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_org_subscriptions(
        self,
        org_id: int,
        active_only: bool = True,
    ) -> List[PushSubscription]:
        """
        Get all subscriptions for an organization.

        WHAT: Lists org's push subscriptions.

        WHY: Broadcast notifications to entire org.

        Args:
            org_id: Organization ID
            active_only: Only return active subscriptions

        Returns:
            List of subscriptions
        """
        query = select(PushSubscription).where(
            PushSubscription.org_id == org_id,
        )

        if active_only:
            query = query.where(PushSubscription.is_active == True)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_or_update(
        self,
        user_id: int,
        org_id: int,
        subscription: Dict[str, Any],
        user_agent: Optional[str] = None,
    ) -> PushSubscription:
        """
        Create or update a subscription.

        WHAT: Upserts subscription by endpoint.

        WHY: Same device may re-subscribe.

        Args:
            user_id: User ID
            org_id: Organization ID
            subscription: Web Push subscription JSON
            user_agent: Browser user agent

        Returns:
            Created or updated subscription
        """
        endpoint = subscription.get("endpoint")
        if not endpoint:
            raise ValueError("Subscription must have endpoint")

        # Check for existing subscription
        existing = await self.get_by_endpoint(endpoint)

        if existing:
            # Update existing
            keys = subscription.get("keys", {})
            existing.p256dh_key = keys.get("p256dh", existing.p256dh_key)
            existing.auth_key = keys.get("auth", existing.auth_key)
            existing.subscription_info = subscription
            existing.user_agent = user_agent or existing.user_agent
            existing.is_active = True
            existing.failed_count = 0

            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        # Create new
        sub = PushSubscription.from_subscription_json(
            user_id=user_id,
            org_id=org_id,
            subscription=subscription,
            user_agent=user_agent,
        )

        self.session.add(sub)
        await self.session.flush()
        await self.session.refresh(sub)
        return sub

    async def deactivate_by_endpoint(
        self,
        endpoint: str,
    ) -> bool:
        """
        Deactivate a subscription by endpoint.

        WHAT: Marks subscription as inactive.

        WHY: User unsubscribed or subscription expired.

        Args:
            endpoint: Subscription endpoint URL

        Returns:
            Whether subscription was found and deactivated
        """
        result = await self.session.execute(
            update(PushSubscription)
            .where(PushSubscription.endpoint == endpoint)
            .values(is_active=False)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def delete_by_endpoint(
        self,
        endpoint: str,
    ) -> bool:
        """
        Delete a subscription by endpoint.

        WHAT: Permanently removes subscription.

        WHY: Complete removal requested.

        Args:
            endpoint: Subscription endpoint URL

        Returns:
            Whether subscription was deleted
        """
        result = await self.session.execute(
            delete(PushSubscription).where(
                PushSubscription.endpoint == endpoint,
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def delete_user_subscriptions(
        self,
        user_id: int,
    ) -> int:
        """
        Delete all subscriptions for a user.

        WHAT: Removes all user subscriptions.

        WHY: User account deletion or logout from all.

        Args:
            user_id: User ID

        Returns:
            Number of deleted subscriptions
        """
        result = await self.session.execute(
            delete(PushSubscription).where(
                PushSubscription.user_id == user_id,
            )
        )
        await self.session.flush()
        return result.rowcount

    async def record_success(
        self,
        subscription_id: int,
    ) -> None:
        """
        Record successful notification delivery.

        WHAT: Updates last used timestamp.

        WHY: Track subscription activity.

        Args:
            subscription_id: Subscription ID
        """
        await self.session.execute(
            update(PushSubscription)
            .where(PushSubscription.id == subscription_id)
            .values(
                last_used_at=datetime.utcnow(),
                failed_count=0,
            )
        )
        await self.session.flush()

    async def record_failure(
        self,
        subscription_id: int,
    ) -> int:
        """
        Record failed notification delivery.

        WHAT: Increments failure count.

        WHY: Track and cleanup dead subscriptions.

        Args:
            subscription_id: Subscription ID

        Returns:
            New failure count
        """
        sub = await self.get_by_id(subscription_id)
        if not sub:
            return 0

        sub.failed_count += 1

        # Deactivate after 3 consecutive failures
        if sub.failed_count >= 3:
            sub.is_active = False

        await self.session.flush()
        return sub.failed_count

    async def cleanup_inactive(
        self,
        days_inactive: int = 30,
    ) -> int:
        """
        Remove old inactive subscriptions.

        WHAT: Deletes stale subscriptions.

        WHY: Prevent database bloat.

        Args:
            days_inactive: Days since last use

        Returns:
            Number of deleted subscriptions
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days_inactive)

        result = await self.session.execute(
            delete(PushSubscription).where(
                and_(
                    PushSubscription.is_active == False,
                    PushSubscription.updated_at < cutoff,
                )
            )
        )
        await self.session.flush()
        return result.rowcount
