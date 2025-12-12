"""
Integration API Endpoints.

WHAT: REST API for external integrations (calendar, webhooks).

WHY: Provides endpoints for:
1. Calendar OAuth flow and management
2. Webhook endpoint CRUD
3. Webhook testing and delivery logs

HOW: Uses FastAPI router with dependency injection
for authentication and authorization.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, get_current_admin_user
from app.core.exceptions import NotFoundError, ValidationError
from app.models.user import User, UserRole
from app.services.integration_service import (
    CalendarIntegrationService,
    WebhookService,
)
from app.schemas.integration import (
    CalendarIntegrationCreate,
    CalendarIntegrationUpdate,
    CalendarIntegrationResponse,
    CalendarIntegrationList,
    CalendarOAuthCallback,
    CalendarSyncRequest,
    WebhookEndpointCreate,
    WebhookEndpointUpdate,
    WebhookEndpointResponse,
    WebhookEndpointWithSecret,
    WebhookEndpointList,
    WebhookTestRequest,
    WebhookDeliveryResponse,
    WebhookDeliveryList,
    WebhookDeliveryStats,
)

# ============================================================================
# Calendar Integration Routes
# ============================================================================

calendar_router = APIRouter(
    prefix="/integrations/calendar",
    tags=["integrations-calendar"],
)


@calendar_router.get(
    "",
    response_model=CalendarIntegrationList,
    summary="List calendar integrations",
)
async def list_calendar_integrations(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CalendarIntegrationList:
    """
    List all calendar integrations for the current user.

    WHAT: Returns user's connected calendar accounts.

    WHY: Users need to see which calendars are connected
    and their sync status.
    """
    service = CalendarIntegrationService(session)
    integrations = await service.get_user_integrations(
        user_id=current_user.id,
        org_id=current_user.org_id,
    )
    return CalendarIntegrationList(
        items=[CalendarIntegrationResponse.model_validate(i) for i in integrations],
        total=len(integrations),
    )


@calendar_router.post(
    "/connect",
    response_model=dict,
    summary="Start calendar OAuth flow",
)
async def start_calendar_oauth(
    request: Request,
    data: CalendarIntegrationCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Start OAuth flow to connect a calendar.

    WHAT: Returns OAuth authorization URL.

    WHY: OAuth requires redirecting user to provider's
    authorization page to grant calendar access.

    Returns:
        Dictionary with authorization URL
    """
    service = CalendarIntegrationService(session)

    # Build redirect URI from request
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/integrations/calendar/callback"

    oauth_url = await service.get_oauth_url(
        provider=data.provider,
        user_id=current_user.id,
        org_id=current_user.org_id,
        redirect_uri=redirect_uri,
    )

    return {"authorization_url": oauth_url}


@calendar_router.get(
    "/callback",
    summary="Handle OAuth callback",
)
async def handle_calendar_oauth_callback(
    request: Request,
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """
    Handle OAuth callback from calendar provider.

    WHAT: Exchanges authorization code for tokens.

    WHY: OAuth callback provides one-time code that
    must be exchanged for access tokens.

    Note: This endpoint does not require authentication
    because it's called by the OAuth provider redirect.
    """
    service = CalendarIntegrationService(session)

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/integrations/calendar/callback"

    await service.handle_oauth_callback(
        code=code,
        state=state,
        redirect_uri=redirect_uri,
    )

    await session.commit()

    # Redirect to frontend settings page
    frontend_url = base_url.replace(":8000", ":3000")  # Adjust port for frontend
    return Response(
        status_code=302,
        headers={"Location": f"{frontend_url}/settings/integrations?connected=calendar"},
    )


@calendar_router.get(
    "/{integration_id}",
    response_model=CalendarIntegrationResponse,
    summary="Get calendar integration",
)
async def get_calendar_integration(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CalendarIntegrationResponse:
    """
    Get details of a specific calendar integration.

    WHAT: Returns integration configuration and status.

    WHY: Users need to view their integration settings
    and check sync status.
    """
    service = CalendarIntegrationService(session)
    integration = await service.get_integration(integration_id, current_user.id)
    return CalendarIntegrationResponse.model_validate(integration)


@calendar_router.patch(
    "/{integration_id}",
    response_model=CalendarIntegrationResponse,
    summary="Update calendar integration",
)
async def update_calendar_integration(
    integration_id: int,
    data: CalendarIntegrationUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CalendarIntegrationResponse:
    """
    Update calendar integration settings.

    WHAT: Modifies sync preferences and settings.

    WHY: Users may want to change which items sync
    or select a different calendar.
    """
    service = CalendarIntegrationService(session)
    integration = await service.update_integration(
        integration_id=integration_id,
        user_id=current_user.id,
        update_data=data,
    )
    await session.commit()
    return CalendarIntegrationResponse.model_validate(integration)


@calendar_router.delete(
    "/{integration_id}",
    status_code=204,
    summary="Delete calendar integration",
)
async def delete_calendar_integration(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """
    Disconnect a calendar integration.

    WHAT: Removes calendar connection and stored tokens.

    WHY: Users may want to disconnect a calendar
    or remove access to their calendar data.
    """
    service = CalendarIntegrationService(session)
    await service.delete_integration(integration_id, current_user.id)
    await session.commit()


@calendar_router.post(
    "/{integration_id}/sync",
    response_model=dict,
    summary="Trigger calendar sync",
)
async def sync_calendar(
    integration_id: int,
    data: CalendarSyncRequest = CalendarSyncRequest(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Trigger manual calendar sync.

    WHAT: Syncs platform data to external calendar.

    WHY: Users may want immediate sync without waiting
    for scheduled sync interval.
    """
    service = CalendarIntegrationService(session)
    result = await service.sync_calendar(
        integration_id=integration_id,
        user_id=current_user.id,
        full_sync=data.full_sync,
    )
    await session.commit()
    return result


# ============================================================================
# Webhook Endpoint Routes
# ============================================================================

webhook_router = APIRouter(
    prefix="/integrations/webhooks",
    tags=["integrations-webhooks"],
)


@webhook_router.get(
    "",
    response_model=WebhookEndpointList,
    summary="List webhook endpoints",
)
async def list_webhook_endpoints(
    include_inactive: bool = Query(False, description="Include inactive endpoints"),
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookEndpointList:
    """
    List all webhook endpoints for the organization.

    WHAT: Returns configured webhook endpoints.

    WHY: Admins need to view and manage webhook
    configurations for their organization.

    Note: Requires ADMIN role.
    """
    service = WebhookService(session)
    endpoints = await service.get_endpoints(
        org_id=current_user.org_id,
        include_inactive=include_inactive,
    )
    return WebhookEndpointList(
        items=[WebhookEndpointResponse.model_validate(e) for e in endpoints],
        total=len(endpoints),
    )


@webhook_router.post(
    "",
    response_model=WebhookEndpointWithSecret,
    status_code=201,
    summary="Create webhook endpoint",
)
async def create_webhook_endpoint(
    data: WebhookEndpointCreate,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookEndpointWithSecret:
    """
    Create a new webhook endpoint.

    WHAT: Creates webhook with generated signing secret.

    WHY: Webhooks enable real-time notifications to
    external systems when platform events occur.

    Note: The signing secret is only shown once in this response.
    Store it securely for payload verification.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    endpoint = await service.create_endpoint(
        org_id=current_user.org_id,
        data=data,
        created_by_id=current_user.id,
    )
    await session.commit()
    return WebhookEndpointWithSecret.model_validate(endpoint)


@webhook_router.get(
    "/{endpoint_id}",
    response_model=WebhookEndpointResponse,
    summary="Get webhook endpoint",
)
async def get_webhook_endpoint(
    endpoint_id: int,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookEndpointResponse:
    """
    Get details of a specific webhook endpoint.

    WHAT: Returns endpoint configuration and stats.

    WHY: Admins need to view endpoint settings and
    monitor delivery health.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    endpoint = await service.get_endpoint(endpoint_id, current_user.org_id)
    return WebhookEndpointResponse.model_validate(endpoint)


@webhook_router.get(
    "/{endpoint_id}/secret",
    response_model=WebhookEndpointWithSecret,
    summary="Get webhook endpoint with secret",
)
async def get_webhook_endpoint_with_secret(
    endpoint_id: int,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookEndpointWithSecret:
    """
    Get webhook endpoint details including signing secret.

    WHAT: Returns endpoint with secret exposed.

    WHY: Users may need to retrieve the secret if they
    didn't save it during creation.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    endpoint = await service.get_endpoint(endpoint_id, current_user.org_id)
    return WebhookEndpointWithSecret.model_validate(endpoint)


@webhook_router.patch(
    "/{endpoint_id}",
    response_model=WebhookEndpointResponse,
    summary="Update webhook endpoint",
)
async def update_webhook_endpoint(
    endpoint_id: int,
    data: WebhookEndpointUpdate,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookEndpointResponse:
    """
    Update webhook endpoint configuration.

    WHAT: Modifies endpoint settings.

    WHY: Admins may need to update URL, events,
    or other webhook settings.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    endpoint = await service.update_endpoint(
        endpoint_id=endpoint_id,
        org_id=current_user.org_id,
        data=data,
    )
    await session.commit()
    return WebhookEndpointResponse.model_validate(endpoint)


@webhook_router.delete(
    "/{endpoint_id}",
    status_code=204,
    summary="Delete webhook endpoint",
)
async def delete_webhook_endpoint(
    endpoint_id: int,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a webhook endpoint.

    WHAT: Removes webhook and delivery history.

    WHY: Endpoints no longer needed should be removed
    to prevent unnecessary delivery attempts.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    await service.delete_endpoint(endpoint_id, current_user.org_id)
    await session.commit()


@webhook_router.post(
    "/{endpoint_id}/regenerate-secret",
    response_model=WebhookEndpointWithSecret,
    summary="Regenerate webhook secret",
)
async def regenerate_webhook_secret(
    endpoint_id: int,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookEndpointWithSecret:
    """
    Regenerate the signing secret for a webhook endpoint.

    WHAT: Creates new signing secret.

    WHY: If a secret is compromised, it can be regenerated
    without recreating the entire endpoint.

    Note: The new secret is only shown once. Store it securely.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    endpoint = await service.regenerate_secret(endpoint_id, current_user.org_id)
    await session.commit()
    return WebhookEndpointWithSecret.model_validate(endpoint)


@webhook_router.post(
    "/{endpoint_id}/test",
    response_model=WebhookDeliveryResponse,
    summary="Test webhook endpoint",
)
async def test_webhook_endpoint(
    endpoint_id: int,
    data: WebhookTestRequest = WebhookTestRequest(),
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookDeliveryResponse:
    """
    Send a test event to a webhook endpoint.

    WHAT: Delivers test payload for verification.

    WHY: Users need to verify their webhook URL works
    and can properly receive and validate payloads.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    delivery = await service.test_endpoint(
        endpoint_id=endpoint_id,
        org_id=current_user.org_id,
        event_type=data.event_type,
        custom_payload=data.payload,
    )
    await session.commit()
    return WebhookDeliveryResponse.model_validate(delivery)


@webhook_router.post(
    "/{endpoint_id}/activate",
    response_model=WebhookEndpointResponse,
    summary="Activate webhook endpoint",
)
async def activate_webhook_endpoint(
    endpoint_id: int,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookEndpointResponse:
    """
    Activate a disabled webhook endpoint.

    WHAT: Re-enables event delivery to endpoint.

    WHY: Users may want to re-enable previously
    disabled webhooks.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    endpoint = await service.get_endpoint(endpoint_id, current_user.org_id)
    updated = await service.endpoint_dao.activate(endpoint.id)
    await session.commit()
    return WebhookEndpointResponse.model_validate(updated)


@webhook_router.post(
    "/{endpoint_id}/deactivate",
    response_model=WebhookEndpointResponse,
    summary="Deactivate webhook endpoint",
)
async def deactivate_webhook_endpoint(
    endpoint_id: int,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookEndpointResponse:
    """
    Deactivate a webhook endpoint.

    WHAT: Temporarily disables event delivery.

    WHY: Users may want to pause webhooks without
    losing configuration.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    endpoint = await service.get_endpoint(endpoint_id, current_user.org_id)
    updated = await service.endpoint_dao.deactivate(endpoint.id)
    await session.commit()
    return WebhookEndpointResponse.model_validate(updated)


# ============================================================================
# Webhook Delivery Routes
# ============================================================================

@webhook_router.get(
    "/{endpoint_id}/deliveries",
    response_model=WebhookDeliveryList,
    summary="List webhook deliveries",
)
async def list_webhook_deliveries(
    endpoint_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookDeliveryList:
    """
    List delivery history for a webhook endpoint.

    WHAT: Returns delivery attempts and results.

    WHY: Users need to see delivery history for
    debugging failed webhooks.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    deliveries = await service.get_deliveries(
        endpoint_id=endpoint_id,
        org_id=current_user.org_id,
        limit=limit,
        offset=offset,
    )
    return WebhookDeliveryList(
        items=[WebhookDeliveryResponse.model_validate(d) for d in deliveries],
        total=len(deliveries),
        has_more=len(deliveries) == limit,
    )


@webhook_router.get(
    "/{endpoint_id}/stats",
    response_model=WebhookDeliveryStats,
    summary="Get webhook delivery statistics",
)
async def get_webhook_delivery_stats(
    endpoint_id: int,
    days: int = Query(7, ge=1, le=90, description="Number of days to include"),
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookDeliveryStats:
    """
    Get delivery statistics for a webhook endpoint.

    WHAT: Returns aggregated delivery metrics.

    WHY: Statistics help users monitor webhook reliability
    and identify problematic endpoints.

    Requires ADMIN role.
    """
    service = WebhookService(session)
    stats = await service.get_delivery_stats(
        endpoint_id=endpoint_id,
        org_id=current_user.org_id,
        days=days,
    )
    return WebhookDeliveryStats(**stats)


# ============================================================================
# Available Events Reference
# ============================================================================

@webhook_router.get(
    "/events/available",
    response_model=dict,
    summary="List available webhook events",
)
async def list_available_webhook_events(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    List all available webhook event types.

    WHAT: Returns list of subscribable event types.

    WHY: Users need to know which events they can
    subscribe to when creating webhooks.
    """
    from app.models.integration import WebhookEventType

    events = {}
    for event in WebhookEventType:
        category = event.value.split(".")[0]
        if category not in events:
            events[category] = []
        events[category].append({
            "type": event.value,
            "description": event.name.replace("_", " ").title(),
        })

    return {
        "events": events,
        "wildcards": [
            {"pattern": "*", "description": "Subscribe to all events"},
            {"pattern": "ticket.*", "description": "All ticket events"},
            {"pattern": "project.*", "description": "All project events"},
            {"pattern": "proposal.*", "description": "All proposal events"},
            {"pattern": "invoice.*", "description": "All invoice events"},
            {"pattern": "user.*", "description": "All user events"},
            {"pattern": "workflow.*", "description": "All workflow events"},
        ],
    }


# ============================================================================
# Combined Router
# ============================================================================

router = APIRouter()
router.include_router(calendar_router)
router.include_router(webhook_router)
