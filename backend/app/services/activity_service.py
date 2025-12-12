"""
Activity Feed Service.

WHAT: Business logic for activity feed operations.

WHY: The service layer:
1. Encapsulates activity feed business logic
2. Coordinates between DAOs
3. Provides unified API for recording activities
4. Handles subscription management

HOW: Orchestrates ActivityEventDAO and ActivitySubscriptionDAO
while providing helper methods for common activity patterns.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.activity import ActivityEventDAO, ActivitySubscriptionDAO
from app.dao.user import UserDAO
from app.models.activity import (
    ActivityEvent,
    ActivityType,
    ActivitySubscription,
)
from app.core.exceptions import ValidationError, ActivityEventError


class ActivityService:
    """
    Service for activity feed operations.

    WHAT: Provides business logic for activities.

    WHY: Activity feeds enable:
    - Real-time visibility into project/organization activity
    - Better team collaboration and awareness
    - Audit trail for non-admin users
    - Context for decisions and changes

    HOW: Coordinates DAOs and provides helper methods.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize ActivityService.

        Args:
            session: Async database session
        """
        self.session = session
        self.event_dao = ActivityEventDAO(session)
        self.subscription_dao = ActivitySubscriptionDAO(session)
        self.user_dao = UserDAO(session)

    # =========================================================================
    # Activity Recording
    # =========================================================================

    async def record_activity(
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
        Record a new activity event.

        WHAT: Creates an activity record.

        WHY: Tracks actions for visibility and audit.

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
        return await self.event_dao.create_event(
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

    # =========================================================================
    # Helper Methods for Common Activities
    # =========================================================================

    async def record_project_activity(
        self,
        org_id: int,
        actor_id: int,
        project_id: int,
        project_name: str,
        event_type: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ActivityEvent:
        """
        Record project-related activity.

        WHAT: Convenience method for project events.

        WHY: Consistent project activity recording.
        """
        return await self.record_activity(
            org_id=org_id,
            actor_id=actor_id,
            event_type=event_type,
            entity_type="project",
            entity_id=project_id,
            entity_name=project_name,
            description=description,
            metadata=metadata,
        )

    async def record_ticket_activity(
        self,
        org_id: int,
        actor_id: int,
        ticket_id: int,
        ticket_subject: str,
        event_type: str,
        description: str,
        project_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ActivityEvent:
        """
        Record ticket-related activity.

        WHAT: Convenience method for ticket events.

        WHY: Consistent ticket activity recording.
        """
        return await self.record_activity(
            org_id=org_id,
            actor_id=actor_id,
            event_type=event_type,
            entity_type="ticket",
            entity_id=ticket_id,
            entity_name=ticket_subject,
            parent_entity_type="project" if project_id else None,
            parent_entity_id=project_id,
            description=description,
            metadata=metadata,
        )

    async def record_document_activity(
        self,
        org_id: int,
        actor_id: int,
        document_id: int,
        document_name: str,
        event_type: str,
        description: str,
        parent_entity_type: Optional[str] = None,
        parent_entity_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ActivityEvent:
        """
        Record document-related activity.

        WHAT: Convenience method for document events.

        WHY: Consistent document activity recording.
        """
        return await self.record_activity(
            org_id=org_id,
            actor_id=actor_id,
            event_type=event_type,
            entity_type="document",
            entity_id=document_id,
            entity_name=document_name,
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            description=description,
            metadata=metadata,
        )

    async def record_workflow_activity(
        self,
        org_id: int,
        actor_id: int,
        workflow_id: int,
        workflow_name: str,
        event_type: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ActivityEvent:
        """
        Record workflow-related activity.

        WHAT: Convenience method for workflow events.

        WHY: Consistent workflow activity recording.
        """
        return await self.record_activity(
            org_id=org_id,
            actor_id=actor_id,
            event_type=event_type,
            entity_type="workflow",
            entity_id=workflow_id,
            entity_name=workflow_name,
            description=description,
            metadata=metadata,
        )

    # =========================================================================
    # Feed Retrieval
    # =========================================================================

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
    ) -> Dict[str, Any]:
        """
        Get organization activity feed.

        WHAT: Retrieves recent organization activities.

        WHY: Display activity feed for organization.

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
            Dict with activities and pagination
        """
        activities = await self.event_dao.get_org_feed(
            org_id=org_id,
            event_types=event_types,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            since=since,
            until=until,
            include_private=include_private,
            skip=skip,
            limit=limit + 1,  # Get one extra to check for more
        )

        has_more = len(activities) > limit
        if has_more:
            activities = activities[:limit]

        return {
            "items": activities,
            "total": len(activities),
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        }

    async def get_entity_feed(
        self,
        entity_type: str,
        entity_id: int,
        org_id: int,
        include_children: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get activity feed for a specific entity.

        WHAT: Retrieves entity-specific activities.

        WHY: Display activity timeline for project/ticket/etc.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            org_id: Organization ID
            include_children: Include child entity activities
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dict with activities and pagination
        """
        activities = await self.event_dao.get_entity_feed(
            entity_type=entity_type,
            entity_id=entity_id,
            org_id=org_id,
            include_children=include_children,
            skip=skip,
            limit=limit + 1,
        )

        has_more = len(activities) > limit
        if has_more:
            activities = activities[:limit]

        return {
            "items": activities,
            "total": len(activities),
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        }

    async def get_user_feed(
        self,
        user_id: int,
        org_id: int,
        include_own_actions: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
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
            Dict with activities and pagination
        """
        activities = await self.event_dao.get_user_feed(
            user_id=user_id,
            org_id=org_id,
            include_own_actions=include_own_actions,
            skip=skip,
            limit=limit + 1,
        )

        has_more = len(activities) > limit
        if has_more:
            activities = activities[:limit]

        return {
            "items": activities,
            "total": len(activities),
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        }

    # =========================================================================
    # Subscription Management
    # =========================================================================

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

        WHAT: Creates subscription.

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
        return await self.subscription_dao.subscribe(
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
        return await self.subscription_dao.unsubscribe(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    async def get_user_subscriptions(
        self,
        user_id: int,
        org_id: int,
        entity_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get user's subscriptions.

        WHAT: Lists followed entities.

        WHY: Manage subscriptions.

        Args:
            user_id: User ID
            org_id: Organization ID
            entity_type: Optional type filter

        Returns:
            Dict with subscriptions
        """
        subscriptions = await self.subscription_dao.get_user_subscriptions(
            user_id=user_id,
            org_id=org_id,
            entity_type=entity_type,
        )

        return {
            "items": subscriptions,
            "total": len(subscriptions),
        }

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
        return await self.subscription_dao.is_subscribed(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    async def get_entity_subscribers(
        self,
        entity_type: str,
        entity_id: int,
        org_id: int,
    ) -> List[ActivitySubscription]:
        """
        Get subscribers for an entity.

        WHAT: Lists users following entity.

        WHY: Notification targeting.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            org_id: Organization ID

        Returns:
            List of subscriptions
        """
        return await self.subscription_dao.get_entity_subscribers(
            entity_type=entity_type,
            entity_id=entity_id,
            org_id=org_id,
        )

    # =========================================================================
    # Analytics
    # =========================================================================

    async def get_activity_summary(
        self,
        org_id: int,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get activity summary for organization.

        WHAT: Aggregated activity statistics.

        WHY: Dashboard widgets.

        Args:
            org_id: Organization ID
            days: Period in days

        Returns:
            Summary dict
        """
        since = datetime.utcnow() - timedelta(days=days)
        counts = await self.event_dao.count_by_type(org_id, since)

        return {
            "counts_by_type": counts,
            "total_events": sum(counts.values()),
            "period_start": since,
            "period_end": datetime.utcnow(),
        }

    async def get_active_users(
        self,
        org_id: int,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Get most active users.

        WHAT: Lists recent active users.

        WHY: Team activity insights.

        Args:
            org_id: Organization ID
            entity_type: Optional entity filter
            entity_id: Optional entity filter
            limit: Max users

        Returns:
            Active users summary
        """
        actors = await self.event_dao.get_recent_actors(
            org_id=org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        )

        # Enrich with user names
        for actor in actors:
            user = await self.user_dao.get_by_id(actor["actor_id"])
            actor["actor_name"] = user.name if user else None

        return {
            "items": actors,
            "period_days": 7,
        }
