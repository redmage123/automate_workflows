"""
Push Notification API endpoints.

WHAT: REST API for web push notification management.

WHY: Enables frontend to:
1. Subscribe to push notifications
2. Unsubscribe from push notifications
3. Manage notification preferences
4. Test notifications

HOW: FastAPI router with subscription endpoints
that integrate with PushNotificationService.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Request, Header

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.push_notification_service import PushNotificationService
from pydantic import BaseModel, Field


router = APIRouter(prefix="/push", tags=["push-notifications"])


# =============================================================================
# Request/Response Schemas
# =============================================================================


class PushSubscriptionRequest(BaseModel):
    """
    Request schema for push subscription.

    WHAT: Web Push subscription from browser.

    WHY: Contains all needed info for push delivery.
    """

    endpoint: str = Field(..., description="Push service endpoint URL")
    expirationTime: Optional[int] = Field(None, description="Subscription expiration")
    keys: Dict[str, str] = Field(..., description="Encryption keys (p256dh, auth)")


class UnsubscribeRequest(BaseModel):
    """Request schema for unsubscribing."""

    endpoint: str = Field(..., description="Subscription endpoint to remove")


class TestNotificationRequest(BaseModel):
    """Request schema for testing notifications."""

    title: str = Field(default="Test Notification", description="Notification title")
    body: str = Field(default="This is a test notification.", description="Body text")


class SubscriptionResponse(BaseModel):
    """Response schema for subscription status."""

    subscribed: bool = Field(..., description="Whether subscription is active")
    endpoint: Optional[str] = Field(None, description="Subscription endpoint")


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/subscribe",
    response_model=SubscriptionResponse,
    summary="Subscribe to push notifications",
    description="Register a push subscription for the current user.",
)
async def subscribe(
    subscription: PushSubscriptionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_agent: Optional[str] = Header(None),
) -> SubscriptionResponse:
    """
    Subscribe to push notifications.

    WHAT: Creates push subscription for user.

    WHY: Required to receive push notifications.

    Args:
        subscription: Web Push subscription from browser
        request: HTTP request
        db: Database session
        current_user: Authenticated user
        user_agent: Browser user agent

    Returns:
        Subscription status
    """
    service = PushNotificationService(db)

    sub = await service.subscribe(
        user_id=current_user.id,
        org_id=current_user.org_id,
        subscription=subscription.model_dump(),
        user_agent=user_agent,
    )

    await db.commit()

    return SubscriptionResponse(
        subscribed=True,
        endpoint=sub.endpoint,
    )


@router.post(
    "/unsubscribe",
    response_model=SubscriptionResponse,
    summary="Unsubscribe from push notifications",
    description="Remove a push subscription.",
)
async def unsubscribe(
    request_body: UnsubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionResponse:
    """
    Unsubscribe from push notifications.

    WHAT: Removes push subscription.

    WHY: User wants to stop receiving notifications.

    Args:
        request_body: Unsubscribe request with endpoint
        db: Database session
        current_user: Authenticated user

    Returns:
        Subscription status
    """
    service = PushNotificationService(db)

    await service.unsubscribe(endpoint=request_body.endpoint)
    await db.commit()

    return SubscriptionResponse(
        subscribed=False,
        endpoint=None,
    )


@router.get(
    "/status",
    response_model=SubscriptionResponse,
    summary="Get subscription status",
    description="Check if user has active push subscriptions.",
)
async def get_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionResponse:
    """
    Get push subscription status.

    WHAT: Checks if user has active subscriptions.

    WHY: UI needs to know current state.

    Args:
        db: Database session
        current_user: Authenticated user

    Returns:
        Subscription status
    """
    service = PushNotificationService(db)

    subscriptions = await service.get_user_subscriptions(user_id=current_user.id)

    if subscriptions:
        return SubscriptionResponse(
            subscribed=True,
            endpoint=subscriptions[0].endpoint,
        )

    return SubscriptionResponse(
        subscribed=False,
        endpoint=None,
    )


@router.post(
    "/test",
    summary="Send test notification",
    description="Send a test push notification to the current user.",
)
async def test_notification(
    request_body: TestNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Send test notification.

    WHAT: Sends test push to verify setup.

    WHY: Helps users confirm notifications work.

    Args:
        request_body: Test notification content
        db: Database session
        current_user: Authenticated user

    Returns:
        Result status
    """
    service = PushNotificationService(db)

    count = await service.send_to_user(
        user_id=current_user.id,
        title=request_body.title,
        body=request_body.body,
        tag="test-notification",
        data={"type": "test"},
    )

    await db.commit()

    return {
        "success": count > 0,
        "sent_count": count,
        "message": f"Test notification sent to {count} device(s)",
    }
