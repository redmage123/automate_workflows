"""
Activity Feed Data Access Object (DAO).

WHAT: Database operations for activity feed models.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for activity operations
3. Enforces org-scoping for multi-tenancy
4. Handles activity queries and filtering

HOW: Extends BaseDAO with activity-specific queries:
- Event creation and retrieval
- Subscription management
- Feed generation
- Analytics aggregation
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.activity import ActivityEvent, ActivityType, ActivitySubscription


class ActivityEventDAO(BaseDAO[ActivityEvent]):
    """
    Data Access Object for ActivityEvent model.

    WHAT: Provides operations for activity events.

    WHY: Centralizes activity event management.

    HOW: Extends BaseDAO with activity-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize ActivityEventDAO."""
        super().__init__(ActivityEvent, session)

    async def create_event(
        self,
        org_id: int,
        actor_id: int,
        event_type: str,
        entity_type: str,
        entity_id: int,
        description: str,
        entity_name: Optional[str] = None,
        parent_entity_type: Optional[str] = None,
        parent_entity_id: Optional[int] = None,
        description_html: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_public: bool = True,
    ) -> ActivityEvent:
        """
        Create a new activity event.

        WHAT: Records an activity event.

        WHY: Track actions in the system.

        Args:
            org_id: Organization ID
            actor_id: User who performed action
            event_type: Type of event
            entity_type: Type of entity acted upon
            entity_id: ID of entity acted upon
            description: Human-readable description
            entity_name: Optional entity name for display
            parent_entity_type: Optional parent entity type
            parent_entity_id: Optional parent entity ID
            description_html: Optional HTML description
            metadata: Optional event-specific data
            is_public: Whether visible to non-admins

        Returns:
            Created ActivityEvent
        """
        return await self.create(
            org_id=org_id,
            actor_id=actor_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            description=description,
            description_html=description_html,
            metadata=metadata,
            is_public=is_public,
        )

    async def get_org_feed(
        self,
        org_id: int,
        event_types: Optional[List[str]] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        actor_id: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        include_private: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ActivityEvent]:
        """
        Get activity feed for an organization.

        WHAT: Retrieves recent activities.

        WHY: Display organization activity feed.

        Args:
            org_id: Organization ID
            event_types: Optional list of event types to filter
            entity_type: Optional entity type filter
            entity_id: Optional entity ID filter
            actor_id: Optional actor filter
            since: Optional start time
            until: Optional end time
            include_private: Include private events
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of activities
        """
        query = (
            select(ActivityEvent)
            .where(ActivityEvent.org_id == org_id)
            .options(selectinload(ActivityEvent.actor))
        )

        if event_types:
            query = query.where(ActivityEvent.event_type.in_(event_types))

        if entity_type:
            query = query.where(ActivityEvent.entity_type == entity_type)

        if entity_id:
            query = query.where(ActivityEvent.entity_id == entity_id)

        if actor_id:
            query = query.where(ActivityEvent.actor_id == actor_id)

        if since:
            query = query.where(ActivityEvent.created_at >= since)

        if until:
            query = query.where(ActivityEvent.created_at <= until)

        if not include_private:
            query = query.where(ActivityEvent.is_public == True)

        query = query.order_by(ActivityEvent.created_at.desc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_entity_feed(
        self,
        entity_type: str,
        entity_id: int,
        org_id: int,
        include_children: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ActivityEvent]:
        """
        Get activity feed for a specific entity.

        WHAT: Retrieves entity-specific activities.

        WHY: Display activity timeline for a project/ticket/etc.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            org_id: Organization ID
            include_children: Include child entity activities
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of activities
        """
        conditions = [
            ActivityEvent.org_id == org_id,
            or_(
                and_(
                    ActivityEvent.entity_type == entity_type,
                    ActivityEvent.entity_id == entity_id,
                ),
                and_(
                    ActivityEvent.parent_entity_type == entity_type,
                    ActivityEvent.parent_entity_id == entity_id,
                ) if include_children else False,
            ),
        ]

        query = (
            select(ActivityEvent)
            .where(*conditions)
            .options(selectinload(ActivityEvent.actor))
            .order_by(ActivityEvent.created_at.desc())
        )

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_user_feed(
        self,
        user_id: int,
        org_id: int,
        include_own_actions: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ActivityEvent]:
        """
        Get personalized feed for a user.

        WHAT: Gets activities relevant to a user.

        WHY: Shows user's personalized activity timeline.

        Args:
            user_id: User ID
            org_id: Organization ID
            include_own_actions: Include user's own actions
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of activities
        """
        # Get subscribed entities
        sub_result = await self.session.execute(
            select(ActivitySubscription).where(
                ActivitySubscription.user_id == user_id,
                ActivitySubscription.org_id == org_id,
            )
        )
        subscriptions = list(sub_result.scalars().all())

        # Build conditions for subscribed entities
        sub_conditions = [
            and_(
                ActivityEvent.entity_type == sub.entity_type,
                ActivityEvent.entity_id == sub.entity_id,
            )
            for sub in subscriptions
        ]

        # Base query
        query = (
            select(ActivityEvent)
            .where(
                ActivityEvent.org_id == org_id,
                ActivityEvent.is_public == True,
            )
            .options(selectinload(ActivityEvent.actor))
        )

        if sub_conditions:
            query = query.where(or_(*sub_conditions))

        if not include_own_actions:
            query = query.where(ActivityEvent.actor_id != user_id)

        query = query.order_by(ActivityEvent.created_at.desc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def count_by_type(
        self,
        org_id: int,
        since: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Count activities by type.

        WHAT: Aggregates activity counts.

        WHY: Analytics and dashboards.

        Args:
            org_id: Organization ID
            since: Optional start time

        Returns:
            Dict of event_type -> count
        """
        query = (
            select(
                ActivityEvent.event_type,
                func.count(ActivityEvent.id).label("count"),
            )
            .where(ActivityEvent.org_id == org_id)
            .group_by(ActivityEvent.event_type)
        )

        if since:
            query = query.where(ActivityEvent.created_at >= since)

        result = await self.session.execute(query)
        return {row.event_type: row.count for row in result}

    async def get_recent_actors(
        self,
        org_id: int,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get recent active users.

        WHAT: Lists most active users.

        WHY: Team activity insights.

        Args:
            org_id: Organization ID
            entity_type: Optional entity filter
            entity_id: Optional entity filter
            limit: Max users

        Returns:
            List of actor activity summaries
        """
        query = (
            select(
                ActivityEvent.actor_id,
                func.count(ActivityEvent.id).label("activity_count"),
                func.max(ActivityEvent.created_at).label("last_activity"),
            )
            .where(
                ActivityEvent.org_id == org_id,
                ActivityEvent.created_at >= datetime.utcnow() - timedelta(days=7),
            )
            .group_by(ActivityEvent.actor_id)
            .order_by(func.count(ActivityEvent.id).desc())
            .limit(limit)
        )

        if entity_type:
            query = query.where(ActivityEvent.entity_type == entity_type)
        if entity_id:
            query = query.where(ActivityEvent.entity_id == entity_id)

        result = await self.session.execute(query)
        return [
            {
                "actor_id": row.actor_id,
                "activity_count": row.activity_count,
                "last_activity": row.last_activity,
            }
            for row in result
        ]


class ActivitySubscriptionDAO(BaseDAO[ActivitySubscription]):
    """
    Data Access Object for ActivitySubscription.

    WHAT: Manages activity subscriptions.

    WHY: Controls what users follow.
    """

    def __init__(self, session: AsyncSession):
        """Initialize ActivitySubscriptionDAO."""
        super().__init__(ActivitySubscription, session)

    async def subscribe(
        self,
        user_id: int,
        org_id: int,
        entity_type: str,
        entity_id: int,
        notify_in_app: bool = True,
        notify_email: bool = False,
    ) -> ActivitySubscription:
        """
        Subscribe user to entity activities.

        WHAT: Creates or updates subscription.

        WHY: Follow entities for updates.

        Args:
            user_id: User ID
            org_id: Organization ID
            entity_type: Entity type
            entity_id: Entity ID
            notify_in_app: In-app notifications
            notify_email: Email notifications

        Returns:
            Subscription
        """
        # Check if already subscribed
        result = await self.session.execute(
            select(ActivitySubscription).where(
                ActivitySubscription.user_id == user_id,
                ActivitySubscription.entity_type == entity_type,
                ActivitySubscription.entity_id == entity_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.notify_in_app = notify_in_app
            existing.notify_email = notify_email
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        return await self.create(
            user_id=user_id,
            org_id=org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            notify_in_app=notify_in_app,
            notify_email=notify_email,
        )

    async def unsubscribe(
        self,
        user_id: int,
        entity_type: str,
        entity_id: int,
    ) -> bool:
        """
        Unsubscribe user from entity.

        WHAT: Removes subscription.

        WHY: Stop following entity.

        Args:
            user_id: User ID
            entity_type: Entity type
            entity_id: Entity ID

        Returns:
            True if unsubscribed
        """
        result = await self.session.execute(
            delete(ActivitySubscription).where(
                ActivitySubscription.user_id == user_id,
                ActivitySubscription.entity_type == entity_type,
                ActivitySubscription.entity_id == entity_id,
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def get_user_subscriptions(
        self,
        user_id: int,
        org_id: int,
        entity_type: Optional[str] = None,
    ) -> List[ActivitySubscription]:
        """
        Get user's subscriptions.

        WHAT: Lists followed entities.

        WHY: Manage subscriptions.

        Args:
            user_id: User ID
            org_id: Organization ID
            entity_type: Optional type filter

        Returns:
            List of subscriptions
        """
        query = select(ActivitySubscription).where(
            ActivitySubscription.user_id == user_id,
            ActivitySubscription.org_id == org_id,
        )

        if entity_type:
            query = query.where(ActivitySubscription.entity_type == entity_type)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_entity_subscribers(
        self,
        entity_type: str,
        entity_id: int,
        org_id: int,
        notify_in_app: Optional[bool] = None,
        notify_email: Optional[bool] = None,
    ) -> List[ActivitySubscription]:
        """
        Get subscribers for an entity.

        WHAT: Lists users following entity.

        WHY: Notification targeting.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            org_id: Organization ID
            notify_in_app: Filter by in-app preference
            notify_email: Filter by email preference

        Returns:
            List of subscriptions
        """
        query = select(ActivitySubscription).where(
            ActivitySubscription.entity_type == entity_type,
            ActivitySubscription.entity_id == entity_id,
            ActivitySubscription.org_id == org_id,
        )

        if notify_in_app is not None:
            query = query.where(ActivitySubscription.notify_in_app == notify_in_app)

        if notify_email is not None:
            query = query.where(ActivitySubscription.notify_email == notify_email)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def is_subscribed(
        self,
        user_id: int,
        entity_type: str,
        entity_id: int,
    ) -> bool:
        """
        Check if user is subscribed.

        WHAT: Validates subscription.

        WHY: UI state.

        Args:
            user_id: User ID
            entity_type: Entity type
            entity_id: Entity ID

        Returns:
            True if subscribed
        """
        result = await self.session.execute(
            select(ActivitySubscription).where(
                ActivitySubscription.user_id == user_id,
                ActivitySubscription.entity_type == entity_type,
                ActivitySubscription.entity_id == entity_id,
            )
        )
        return result.scalar_one_or_none() is not None
