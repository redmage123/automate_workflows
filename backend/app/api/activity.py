"""
Activity Feed API Routes.

WHAT: REST API endpoints for activity feed operations.

WHY: Activity feeds enable:
1. Real-time visibility into project/organization activity
2. Better team collaboration and awareness
3. Audit trail for non-admin users
4. Context for decisions and changes

HOW: Uses FastAPI with dependency injection for auth/db.
All routes require authentication and enforce org-scoping.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_admin
from app.models.user import User, UserRole
from app.services.activity_service import ActivityService
from app.schemas.activity import (
    ActivityType,
    ActivityFilterRequest,
    SubscribeRequest,
    UpdateSubscriptionRequest,
    ActorResponse,
    ActivityEventResponse,
    ActivityFeedResponse,
    SubscriptionResponse,
    SubscriptionListResponse,
    ActivitySummaryResponse,
    ActiveUserResponse,
    ActiveUsersResponse,
)


router = APIRouter(prefix="/activity", tags=["activity"])


def _event_to_response(event) -> ActivityEventResponse:
    """
    Convert ActivityEvent model to response schema.

    WHAT: Maps model fields to response.

    WHY: Consistent response formatting.
    """
    actor = None
    if event.actor:
        actor = ActorResponse(
            id=event.actor.id,
            name=event.actor.name,
            email=event.actor.email,
        )

    return ActivityEventResponse(
        id=event.id,
        org_id=event.org_id,
        event_type=ActivityType(event.event_type),
        actor_id=event.actor_id,
        actor=actor,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        entity_name=event.entity_name,
        parent_entity_type=event.parent_entity_type,
        parent_entity_id=event.parent_entity_id,
        description=event.description,
        description_html=event.description_html,
        metadata=event.metadata,
        is_public=event.is_public,
        created_at=event.created_at,
    )


def _subscription_to_response(sub) -> SubscriptionResponse:
    """
    Convert ActivitySubscription to response schema.

    WHAT: Maps model fields to response.

    WHY: Consistent response formatting.
    """
    return SubscriptionResponse(
        id=sub.id,
        user_id=sub.user_id,
        entity_type=sub.entity_type,
        entity_id=sub.entity_id,
        notify_in_app=sub.notify_in_app,
        notify_email=sub.notify_email,
        created_at=sub.created_at,
    )


# ============================================================================
# Feed Endpoints
# ============================================================================


@router.get("/feed", response_model=ActivityFeedResponse)
async def get_organization_feed(
    event_type: Optional[ActivityType] = Query(None, description="Filter by type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    actor_id: Optional[int] = Query(None, description="Filter by actor"),
    since: Optional[datetime] = Query(None, description="Start time"),
    until: Optional[datetime] = Query(None, description="End time"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get organization activity feed.

    WHAT: Lists recent activities in the organization.

    WHY: Provides visibility into what's happening.
    """
    service = ActivityService(session)
    is_admin = current_user.role == UserRole.ADMIN

    event_types = [event_type.value] if event_type else None

    result = await service.get_org_feed(
        org_id=current_user.org_id,
        event_types=event_types,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        since=since,
        until=until,
        include_private=is_admin,
        skip=skip,
        limit=limit,
    )

    return ActivityFeedResponse(
        items=[_event_to_response(e) for e in result["items"]],
        total=result["total"],
        skip=result["skip"],
        limit=result["limit"],
        has_more=result["has_more"],
    )


@router.get("/feed/my", response_model=ActivityFeedResponse)
async def get_my_feed(
    include_own_actions: bool = Query(True, description="Include own actions"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get personalized activity feed.

    WHAT: Shows activities from subscribed entities.

    WHY: Personalized view of relevant activities.
    """
    service = ActivityService(session)

    result = await service.get_user_feed(
        user_id=current_user.id,
        org_id=current_user.org_id,
        include_own_actions=include_own_actions,
        skip=skip,
        limit=limit,
    )

    return ActivityFeedResponse(
        items=[_event_to_response(e) for e in result["items"]],
        total=result["total"],
        skip=result["skip"],
        limit=result["limit"],
        has_more=result["has_more"],
    )


@router.get("/entity/{entity_type}/{entity_id}", response_model=ActivityFeedResponse)
async def get_entity_feed(
    entity_type: str,
    entity_id: int,
    include_children: bool = Query(True, description="Include child entities"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get activity feed for a specific entity.

    WHAT: Shows activities for project/ticket/etc.

    WHY: Context-aware activity timeline.
    """
    service = ActivityService(session)

    result = await service.get_entity_feed(
        entity_type=entity_type,
        entity_id=entity_id,
        org_id=current_user.org_id,
        include_children=include_children,
        skip=skip,
        limit=limit,
    )

    return ActivityFeedResponse(
        items=[_event_to_response(e) for e in result["items"]],
        total=result["total"],
        skip=result["skip"],
        limit=result["limit"],
        has_more=result["has_more"],
    )


# ============================================================================
# Subscription Endpoints
# ============================================================================


@router.post("/subscriptions", response_model=SubscriptionResponse)
async def subscribe_to_entity(
    request: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Subscribe to entity activities.

    WHAT: Follow an entity for updates.

    WHY: Get notified about changes.
    """
    service = ActivityService(session)

    subscription = await service.subscribe(
        user_id=current_user.id,
        org_id=current_user.org_id,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        notify_in_app=request.notify_in_app,
        notify_email=request.notify_email,
    )

    await session.commit()
    return _subscription_to_response(subscription)


@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def get_my_subscriptions(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get current user's subscriptions.

    WHAT: Lists followed entities.

    WHY: Manage what you're following.
    """
    service = ActivityService(session)

    result = await service.get_user_subscriptions(
        user_id=current_user.id,
        org_id=current_user.org_id,
        entity_type=entity_type,
    )

    return SubscriptionListResponse(
        items=[_subscription_to_response(s) for s in result["items"]],
        total=result["total"],
    )


@router.get("/subscriptions/check", response_model=bool)
async def check_subscription(
    entity_type: str = Query(..., description="Entity type"),
    entity_id: int = Query(..., description="Entity ID"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Check if subscribed to an entity.

    WHAT: Returns subscription status.

    WHY: UI state for follow/unfollow button.
    """
    service = ActivityService(session)

    return await service.is_subscribed(
        user_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
    )


@router.delete("/subscriptions/{entity_type}/{entity_id}")
async def unsubscribe_from_entity(
    entity_type: str,
    entity_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Unsubscribe from entity activities.

    WHAT: Stop following an entity.

    WHY: No longer interested in updates.
    """
    service = ActivityService(session)

    await service.unsubscribe(
        user_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    await session.commit()
    return {"message": "Unsubscribed"}


# ============================================================================
# Analytics Endpoints
# ============================================================================


@router.get("/summary", response_model=ActivitySummaryResponse)
async def get_activity_summary(
    days: int = Query(7, ge=1, le=90, description="Period in days"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get activity summary statistics.

    WHAT: Aggregated activity counts.

    WHY: Dashboard widgets.
    """
    service = ActivityService(session)

    summary = await service.get_activity_summary(
        org_id=current_user.org_id,
        days=days,
    )

    return ActivitySummaryResponse(
        counts_by_type=summary["counts_by_type"],
        total_events=summary["total_events"],
        period_start=summary["period_start"],
        period_end=summary["period_end"],
    )


@router.get("/active-users", response_model=ActiveUsersResponse)
async def get_active_users(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get most active users.

    WHAT: Lists users by activity count.

    WHY: Team engagement insights.
    """
    service = ActivityService(session)

    result = await service.get_active_users(
        org_id=current_user.org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )

    return ActiveUsersResponse(
        items=[
            ActiveUserResponse(
                actor_id=a["actor_id"],
                actor_name=a.get("actor_name"),
                activity_count=a["activity_count"],
                last_activity=a["last_activity"],
            )
            for a in result["items"]
        ],
        period_days=result["period_days"],
    )
