"""
Integration Service.

WHAT: Business logic for external integrations.

WHY: External integrations require:
1. Calendar OAuth flow management
2. Calendar sync operations
3. Webhook event delivery
4. Retry logic and error handling

HOW: Implements:
- OAuth token exchange and refresh
- Calendar sync with external APIs
- Webhook payload signing and delivery
- Background job support for retries
"""

import uuid
import hmac
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, TYPE_CHECKING

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    NotFoundError,
    ValidationError,
    ExternalServiceError,
)
from app.dao.integration import (
    CalendarIntegrationDAO,
    WebhookEndpointDAO,
    WebhookDeliveryDAO,
)
from app.models.integration import (
    CalendarIntegration,
    WebhookEndpoint,
    WebhookDelivery,
    CalendarProvider,
    WebhookEventType,
)
from app.schemas.integration import (
    CalendarIntegrationCreate,
    CalendarIntegrationUpdate,
    WebhookEndpointCreate,
    WebhookEndpointUpdate,
    WebhookPayload,
)

if TYPE_CHECKING:
    from app.models.user import User

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exceptions
# ============================================================================


class IntegrationError(AppException):
    """
    Base exception for integration errors.

    WHAT: Parent class for all integration-related errors.

    WHY: Allows catching all integration errors with a single
    except clause while providing specific error types.
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            status_code=500,
            error_code="INTEGRATION_ERROR",
            details=details,
            original_exception=original_exception,
        )


class CalendarIntegrationError(IntegrationError):
    """
    Exception for calendar integration errors.

    WHAT: Errors specific to calendar operations.

    WHY: Calendar errors may require different handling,
    such as prompting re-authentication.
    """

    def __init__(
        self,
        message: str,
        provider: str,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            details={**(details or {}), "provider": provider},
            original_exception=original_exception,
        )
        self.error_code = "CALENDAR_INTEGRATION_ERROR"


class OAuthError(CalendarIntegrationError):
    """
    Exception for OAuth flow errors.

    WHAT: Errors during OAuth authorization or token refresh.

    WHY: OAuth errors typically require user intervention
    to re-authorize the integration.
    """

    def __init__(
        self,
        message: str,
        provider: str,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            details=details,
            original_exception=original_exception,
        )
        self.error_code = "OAUTH_ERROR"
        self.status_code = 401


class WebhookDeliveryError(IntegrationError):
    """
    Exception for webhook delivery errors.

    WHAT: Errors during webhook payload delivery.

    WHY: Delivery errors may be retryable (network issues)
    or permanent (invalid URL, 4xx responses).
    """

    def __init__(
        self,
        message: str,
        endpoint_id: int,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        retryable: bool = True,
    ):
        super().__init__(
            message=message,
            details={
                **(details or {}),
                "endpoint_id": endpoint_id,
                "response_status": status_code,
            },
            original_exception=original_exception,
        )
        self.error_code = "WEBHOOK_DELIVERY_ERROR"
        self.retryable = retryable


# ============================================================================
# Calendar Integration Service
# ============================================================================


class CalendarIntegrationService:
    """
    Service for calendar integration management.

    WHAT: Handles calendar OAuth and sync operations.

    WHY: Calendar integration enables:
    - Syncing project milestones to user calendars
    - Deadline reminders via calendar events
    - Meeting scheduling integration

    HOW: Uses OAuth 2.0 for authorization, provider-specific
    APIs for calendar operations.
    """

    # OAuth configuration per provider
    OAUTH_CONFIG = {
        CalendarProvider.GOOGLE.value: {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scope": "https://www.googleapis.com/auth/calendar",
            "api_base": "https://www.googleapis.com/calendar/v3",
        },
        CalendarProvider.OUTLOOK.value: {
            "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "scope": "https://graph.microsoft.com/Calendars.ReadWrite offline_access",
            "api_base": "https://graph.microsoft.com/v1.0",
        },
    }

    def __init__(self, session: AsyncSession):
        """
        Initialize CalendarIntegrationService.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.dao = CalendarIntegrationDAO(session)

    async def get_oauth_url(
        self,
        provider: str,
        user_id: int,
        org_id: int,
        redirect_uri: str,
    ) -> str:
        """
        Generate OAuth authorization URL.

        WHAT: Creates URL for user to authorize calendar access.

        WHY: OAuth requires redirecting user to provider's
        authorization page to grant access.

        Args:
            provider: Calendar provider
            user_id: User requesting authorization
            org_id: Organization ID
            redirect_uri: URL to redirect after authorization

        Returns:
            OAuth authorization URL
        """
        config = self.OAUTH_CONFIG.get(provider)
        if not config:
            raise ValidationError(
                message=f"Unsupported calendar provider: {provider}",
                details={"provider": provider},
            )

        # Generate state token for CSRF protection
        # State encodes user context for callback handling
        state = self._encode_state(user_id, org_id, provider)

        # Get client credentials from settings
        client_id = getattr(settings, f"{provider.upper()}_CALENDAR_CLIENT_ID", None)
        if not client_id:
            raise ValidationError(
                message=f"Calendar provider {provider} is not configured",
                details={"provider": provider},
            )

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": config["scope"],
            "state": state,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Always show consent screen
        }

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{config['auth_url']}?{query_string}"

    async def handle_oauth_callback(
        self,
        code: str,
        state: str,
        redirect_uri: str,
    ) -> CalendarIntegration:
        """
        Handle OAuth callback and create integration.

        WHAT: Exchanges authorization code for tokens.

        WHY: OAuth callback provides one-time code that
        must be exchanged for access/refresh tokens.

        Args:
            code: Authorization code from callback
            state: State parameter for verification
            redirect_uri: Same redirect_uri used in auth request

        Returns:
            Created or updated CalendarIntegration
        """
        # Decode and verify state
        user_id, org_id, provider = self._decode_state(state)

        config = self.OAUTH_CONFIG.get(provider)
        if not config:
            raise OAuthError(
                message="Invalid provider in state",
                provider=provider,
            )

        # Get client credentials
        client_id = getattr(settings, f"{provider.upper()}_CALENDAR_CLIENT_ID", None)
        client_secret = getattr(
            settings, f"{provider.upper()}_CALENDAR_CLIENT_SECRET", None
        )

        if not client_id or not client_secret:
            raise OAuthError(
                message="OAuth credentials not configured",
                provider=provider,
            )

        # Exchange code for tokens
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config["token_url"],
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
                response.raise_for_status()
                tokens = response.json()
        except httpx.HTTPStatusError as e:
            raise OAuthError(
                message="Failed to exchange authorization code",
                provider=provider,
                details={"status_code": e.response.status_code},
                original_exception=e,
            )
        except Exception as e:
            raise OAuthError(
                message="OAuth token exchange failed",
                provider=provider,
                original_exception=e,
            )

        # Calculate token expiration
        expires_in = tokens.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Get user email from provider
        provider_email = await self._get_provider_email(
            provider, tokens["access_token"]
        )

        # Check for existing integration
        existing = await self.dao.get_by_user_and_provider(user_id, provider)

        if existing:
            # Update existing integration
            return await self.dao.update_tokens(
                integration_id=existing.id,
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                expires_at=expires_at,
            )
        else:
            # Create new integration
            integration = CalendarIntegration(
                user_id=user_id,
                org_id=org_id,
                provider=provider,
                provider_email=provider_email,
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                token_expires_at=expires_at,
                is_active=True,
                sync_enabled=True,
            )
            return await self.dao.create(integration)

    async def refresh_token(
        self,
        integration_id: int,
    ) -> CalendarIntegration:
        """
        Refresh OAuth access token.

        WHAT: Uses refresh token to get new access token.

        WHY: Access tokens expire. Refresh tokens allow
        getting new access tokens without user interaction.

        Args:
            integration_id: Integration to refresh

        Returns:
            Updated integration with new tokens
        """
        integration = await self.dao.get_by_id(integration_id)
        if not integration:
            raise NotFoundError(
                message="Calendar integration not found",
                resource_type="CalendarIntegration",
                resource_id=str(integration_id),
            )

        if not integration.refresh_token:
            raise OAuthError(
                message="No refresh token available",
                provider=integration.provider,
            )

        config = self.OAUTH_CONFIG.get(integration.provider)
        client_id = getattr(
            settings, f"{integration.provider.upper()}_CALENDAR_CLIENT_ID", None
        )
        client_secret = getattr(
            settings, f"{integration.provider.upper()}_CALENDAR_CLIENT_SECRET", None
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config["token_url"],
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": integration.refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                response.raise_for_status()
                tokens = response.json()
        except httpx.HTTPStatusError as e:
            # Mark integration as inactive if refresh fails
            await self.dao.deactivate(
                integration_id,
                error_message="Token refresh failed - please reconnect",
            )
            raise OAuthError(
                message="Failed to refresh access token",
                provider=integration.provider,
                details={"status_code": e.response.status_code},
                original_exception=e,
            )

        expires_in = tokens.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        return await self.dao.update_tokens(
            integration_id=integration_id,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_at=expires_at,
        )

    async def get_user_integrations(
        self,
        user_id: int,
        org_id: int,
    ) -> List[CalendarIntegration]:
        """
        Get all calendar integrations for a user.

        Args:
            user_id: User ID
            org_id: Organization ID

        Returns:
            List of calendar integrations
        """
        return list(await self.dao.get_user_integrations(user_id, org_id))

    async def get_integration(
        self,
        integration_id: int,
        user_id: int,
    ) -> CalendarIntegration:
        """
        Get a specific calendar integration.

        Args:
            integration_id: Integration ID
            user_id: User ID (for ownership verification)

        Returns:
            Calendar integration
        """
        integration = await self.dao.get_by_id(integration_id)
        if not integration:
            raise NotFoundError(
                message="Calendar integration not found",
                resource_type="CalendarIntegration",
                resource_id=str(integration_id),
            )
        if integration.user_id != user_id:
            raise NotFoundError(
                message="Calendar integration not found",
                resource_type="CalendarIntegration",
                resource_id=str(integration_id),
            )
        return integration

    async def update_integration(
        self,
        integration_id: int,
        user_id: int,
        update_data: CalendarIntegrationUpdate,
    ) -> CalendarIntegration:
        """
        Update calendar integration settings.

        Args:
            integration_id: Integration ID
            user_id: User ID (for ownership verification)
            update_data: Fields to update

        Returns:
            Updated integration
        """
        integration = await self.get_integration(integration_id, user_id)
        update_dict = update_data.model_dump(exclude_unset=True)
        return await self.dao.update(integration.id, update_dict)

    async def delete_integration(
        self,
        integration_id: int,
        user_id: int,
    ) -> None:
        """
        Delete a calendar integration.

        Args:
            integration_id: Integration ID
            user_id: User ID (for ownership verification)
        """
        integration = await self.get_integration(integration_id, user_id)
        await self.dao.delete(integration.id)

    async def sync_calendar(
        self,
        integration_id: int,
        user_id: int,
        full_sync: bool = False,
    ) -> Dict[str, Any]:
        """
        Sync calendar with platform data.

        WHAT: Pushes platform events to external calendar.

        WHY: Calendar sync keeps user's external calendar
        updated with project milestones and deadlines.

        Args:
            integration_id: Integration ID
            user_id: User ID
            full_sync: Whether to do full sync vs incremental

        Returns:
            Sync results summary
        """
        integration = await self.get_integration(integration_id, user_id)

        # Ensure token is valid
        if (
            integration.token_expires_at
            and integration.token_expires_at <= datetime.utcnow()
        ):
            integration = await self.refresh_token(integration_id)

        # TODO: Implement actual calendar sync logic
        # This would:
        # 1. Fetch projects/tickets with due dates
        # 2. Map to calendar events
        # 3. Create/update/delete events via provider API

        # For now, update sync status
        await self.dao.update_sync_status(
            integration_id=integration_id,
            last_sync_at=datetime.utcnow(),
        )

        return {
            "status": "success",
            "events_created": 0,
            "events_updated": 0,
            "events_deleted": 0,
            "sync_type": "full" if full_sync else "incremental",
        }

    def _encode_state(self, user_id: int, org_id: int, provider: str) -> str:
        """Encode state parameter for OAuth."""
        import base64

        data = f"{user_id}:{org_id}:{provider}:{uuid.uuid4().hex[:8]}"
        return base64.urlsafe_b64encode(data.encode()).decode()

    def _decode_state(self, state: str) -> tuple:
        """Decode state parameter from OAuth."""
        import base64

        try:
            data = base64.urlsafe_b64decode(state.encode()).decode()
            parts = data.split(":")
            return int(parts[0]), int(parts[1]), parts[2]
        except Exception as e:
            raise OAuthError(
                message="Invalid OAuth state parameter",
                provider="unknown",
                original_exception=e,
            )

    async def _get_provider_email(self, provider: str, access_token: str) -> str:
        """Get user email from calendar provider."""
        try:
            async with httpx.AsyncClient() as client:
                if provider == CalendarProvider.GOOGLE.value:
                    response = await client.get(
                        "https://www.googleapis.com/oauth2/v2/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    response.raise_for_status()
                    return response.json().get("email", "")
                elif provider == CalendarProvider.OUTLOOK.value:
                    response = await client.get(
                        "https://graph.microsoft.com/v1.0/me",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    response.raise_for_status()
                    return response.json().get("mail", "")
        except Exception as e:
            logger.warning(f"Failed to get provider email: {e}")
        return ""


# ============================================================================
# Webhook Service
# ============================================================================


class WebhookService:
    """
    Service for webhook management and delivery.

    WHAT: Handles webhook endpoint CRUD and event delivery.

    WHY: Webhooks enable:
    - Real-time notifications to external systems
    - Integration with third-party applications
    - Custom automation triggers

    HOW: Signs payloads with HMAC, delivers via HTTP,
    handles retries with exponential backoff.
    """

    # HTTP timeout for webhook delivery
    DELIVERY_TIMEOUT = 30.0

    def __init__(self, session: AsyncSession):
        """
        Initialize WebhookService.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.endpoint_dao = WebhookEndpointDAO(session)
        self.delivery_dao = WebhookDeliveryDAO(session)

    async def create_endpoint(
        self,
        org_id: int,
        data: WebhookEndpointCreate,
        created_by_id: int,
    ) -> WebhookEndpoint:
        """
        Create a new webhook endpoint.

        WHAT: Creates webhook endpoint with generated secret.

        WHY: Each endpoint needs a unique secret for
        payload signature verification by the receiver.

        Args:
            org_id: Organization ID
            data: Endpoint configuration
            created_by_id: User creating the endpoint

        Returns:
            Created webhook endpoint
        """
        # Generate signing secret
        secret = self._generate_secret()

        endpoint = WebhookEndpoint(
            org_id=org_id,
            name=data.name,
            description=data.description,
            url=data.url,
            secret=secret,
            events=data.events,
            headers=data.headers,
            retry_enabled=data.retry_enabled,
            max_retries=data.max_retries,
            created_by_id=created_by_id,
            is_active=True,
        )

        return await self.endpoint_dao.create(endpoint)

    async def get_endpoint(
        self,
        endpoint_id: int,
        org_id: int,
    ) -> WebhookEndpoint:
        """
        Get a webhook endpoint.

        Args:
            endpoint_id: Endpoint ID
            org_id: Organization ID (for access control)

        Returns:
            Webhook endpoint
        """
        endpoint = await self.endpoint_dao.get_by_id(endpoint_id)
        if not endpoint or endpoint.org_id != org_id:
            raise NotFoundError(
                message="Webhook endpoint not found",
                resource_type="WebhookEndpoint",
                resource_id=str(endpoint_id),
            )
        return endpoint

    async def get_endpoints(
        self,
        org_id: int,
        include_inactive: bool = False,
    ) -> List[WebhookEndpoint]:
        """
        Get all webhook endpoints for an organization.

        Args:
            org_id: Organization ID
            include_inactive: Include inactive endpoints

        Returns:
            List of webhook endpoints
        """
        return list(
            await self.endpoint_dao.get_by_org(org_id, include_inactive=include_inactive)
        )

    async def update_endpoint(
        self,
        endpoint_id: int,
        org_id: int,
        data: WebhookEndpointUpdate,
    ) -> WebhookEndpoint:
        """
        Update a webhook endpoint.

        Args:
            endpoint_id: Endpoint ID
            org_id: Organization ID
            data: Fields to update

        Returns:
            Updated endpoint
        """
        endpoint = await self.get_endpoint(endpoint_id, org_id)
        update_dict = data.model_dump(exclude_unset=True)
        return await self.endpoint_dao.update(endpoint.id, update_dict)

    async def delete_endpoint(
        self,
        endpoint_id: int,
        org_id: int,
    ) -> None:
        """
        Delete a webhook endpoint.

        Args:
            endpoint_id: Endpoint ID
            org_id: Organization ID
        """
        endpoint = await self.get_endpoint(endpoint_id, org_id)
        await self.endpoint_dao.delete(endpoint.id)

    async def regenerate_secret(
        self,
        endpoint_id: int,
        org_id: int,
    ) -> WebhookEndpoint:
        """
        Regenerate webhook signing secret.

        WHAT: Creates new signing secret for endpoint.

        WHY: If a secret is compromised, users need to
        regenerate it without recreating the endpoint.

        Args:
            endpoint_id: Endpoint ID
            org_id: Organization ID

        Returns:
            Updated endpoint with new secret
        """
        endpoint = await self.get_endpoint(endpoint_id, org_id)
        new_secret = self._generate_secret()
        return await self.endpoint_dao.update(endpoint.id, {"secret": new_secret})

    async def trigger_event(
        self,
        org_id: int,
        event_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[WebhookDelivery]:
        """
        Trigger a webhook event.

        WHAT: Delivers event to all subscribed endpoints.

        WHY: When platform events occur (ticket created, etc.),
        they need to be delivered to all relevant webhooks.

        Args:
            org_id: Organization where event occurred
            event_type: Type of event
            data: Event-specific data
            metadata: Additional metadata

        Returns:
            List of delivery records
        """
        # Find subscribed endpoints
        endpoints = await self.endpoint_dao.get_endpoints_for_event(org_id, event_type)

        if not endpoints:
            logger.debug(f"No endpoints subscribed to {event_type} for org {org_id}")
            return []

        # Generate event ID
        event_id = str(uuid.uuid4())

        # Create payload
        payload = WebhookPayload(
            event_type=event_type,
            event_id=event_id,
            timestamp=datetime.utcnow(),
            org_id=org_id,
            data=data,
            metadata=metadata,
        )

        # Deliver to each endpoint
        deliveries = []
        for endpoint in endpoints:
            delivery = await self._deliver_to_endpoint(endpoint, payload)
            deliveries.append(delivery)

        return deliveries

    async def _deliver_to_endpoint(
        self,
        endpoint: WebhookEndpoint,
        payload: WebhookPayload,
    ) -> WebhookDelivery:
        """
        Deliver payload to a specific endpoint.

        WHAT: Sends HTTP request with signed payload.

        WHY: Each endpoint receives its own delivery with
        proper signing and response tracking.

        Args:
            endpoint: Target endpoint
            payload: Payload to deliver

        Returns:
            Delivery record
        """
        # Serialize payload
        payload_json = payload.model_dump_json()
        payload_dict = json.loads(payload_json)

        # Sign payload
        signature = self._sign_payload(payload_json, endpoint.secret)

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": payload.event_type,
            "X-Webhook-ID": payload.event_id,
            "User-Agent": "AutomationPlatform-Webhook/1.0",
        }
        if endpoint.headers:
            headers.update(endpoint.headers)

        # Create delivery record
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            event_type=payload.event_type,
            event_id=payload.event_id,
            request_url=endpoint.url,
            request_headers={k: v for k, v in headers.items() if k != "Authorization"},
            request_body=payload_dict,
            delivered=False,
            attempt_count=0,
        )
        delivery = await self.delivery_dao.create(delivery)

        # Attempt delivery
        start_time = datetime.utcnow()
        try:
            async with httpx.AsyncClient(timeout=self.DELIVERY_TIMEOUT) as client:
                response = await client.post(
                    endpoint.url,
                    content=payload_json,
                    headers=headers,
                )

                duration_ms = int(
                    (datetime.utcnow() - start_time).total_seconds() * 1000
                )

                # Consider 2xx successful
                delivered = 200 <= response.status_code < 300

                delivery = await self.delivery_dao.record_attempt(
                    delivery_id=delivery.id,
                    response_status=response.status_code,
                    response_headers=dict(response.headers),
                    response_body=response.text[:10000],
                    delivered=delivered,
                    duration_ms=duration_ms,
                    error_message=None if delivered else f"HTTP {response.status_code}",
                )

                # Update endpoint stats
                await self.endpoint_dao.update_stats(endpoint.id, delivered)

                if not delivered:
                    logger.warning(
                        f"Webhook delivery failed: {endpoint.url} "
                        f"returned {response.status_code}"
                    )

        except httpx.TimeoutException as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            delivery = await self.delivery_dao.record_attempt(
                delivery_id=delivery.id,
                response_status=None,
                response_headers=None,
                response_body=None,
                delivered=False,
                duration_ms=duration_ms,
                error_message="Request timeout",
            )
            await self.endpoint_dao.update_stats(endpoint.id, False)
            logger.warning(f"Webhook delivery timeout: {endpoint.url}")

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            delivery = await self.delivery_dao.record_attempt(
                delivery_id=delivery.id,
                response_status=None,
                response_headers=None,
                response_body=None,
                delivered=False,
                duration_ms=duration_ms,
                error_message=str(e),
            )
            await self.endpoint_dao.update_stats(endpoint.id, False)
            logger.error(f"Webhook delivery error: {endpoint.url} - {e}")

        return delivery

    async def retry_failed_deliveries(self) -> int:
        """
        Retry failed webhook deliveries.

        WHAT: Processes pending retries from all endpoints.

        WHY: Background job calls this to handle retries
        with exponential backoff timing.

        Returns:
            Number of retries attempted
        """
        pending = await self.delivery_dao.get_pending_retries()
        count = 0

        for delivery in pending:
            endpoint = await self.endpoint_dao.get_by_id(delivery.endpoint_id)
            if not endpoint or not endpoint.is_active:
                continue

            if not endpoint.retry_enabled:
                continue

            if delivery.attempt_count >= endpoint.max_retries:
                continue

            # Recreate payload from stored data
            payload = WebhookPayload(
                event_type=delivery.event_type,
                event_id=delivery.event_id,
                timestamp=delivery.triggered_at,
                org_id=endpoint.org_id,
                data=delivery.request_body.get("data", {}),
                metadata=delivery.request_body.get("metadata"),
            )

            await self._deliver_retry(endpoint, delivery, payload)
            count += 1

        return count

    async def _deliver_retry(
        self,
        endpoint: WebhookEndpoint,
        delivery: WebhookDelivery,
        payload: WebhookPayload,
    ) -> WebhookDelivery:
        """Retry a failed delivery."""
        payload_json = payload.model_dump_json()
        signature = self._sign_payload(payload_json, endpoint.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": payload.event_type,
            "X-Webhook-ID": payload.event_id,
            "X-Webhook-Retry": str(delivery.attempt_count),
            "User-Agent": "AutomationPlatform-Webhook/1.0",
        }
        if endpoint.headers:
            headers.update(endpoint.headers)

        start_time = datetime.utcnow()
        try:
            async with httpx.AsyncClient(timeout=self.DELIVERY_TIMEOUT) as client:
                response = await client.post(
                    endpoint.url,
                    content=payload_json,
                    headers=headers,
                )

                duration_ms = int(
                    (datetime.utcnow() - start_time).total_seconds() * 1000
                )
                delivered = 200 <= response.status_code < 300

                delivery = await self.delivery_dao.record_attempt(
                    delivery_id=delivery.id,
                    response_status=response.status_code,
                    response_headers=dict(response.headers),
                    response_body=response.text[:10000],
                    delivered=delivered,
                    duration_ms=duration_ms,
                    error_message=None if delivered else f"HTTP {response.status_code}",
                )
                await self.endpoint_dao.update_stats(endpoint.id, delivered)

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            delivery = await self.delivery_dao.record_attempt(
                delivery_id=delivery.id,
                response_status=None,
                response_headers=None,
                response_body=None,
                delivered=False,
                duration_ms=duration_ms,
                error_message=str(e),
            )
            await self.endpoint_dao.update_stats(endpoint.id, False)

        return delivery

    async def test_endpoint(
        self,
        endpoint_id: int,
        org_id: int,
        event_type: str = "test.ping",
        custom_payload: Optional[Dict[str, Any]] = None,
    ) -> WebhookDelivery:
        """
        Send a test event to a webhook endpoint.

        WHAT: Sends test payload for verification.

        WHY: Users need to verify their webhook URL works
        and can properly receive and validate payloads.

        Args:
            endpoint_id: Endpoint to test
            org_id: Organization ID
            event_type: Event type for test
            custom_payload: Optional custom payload

        Returns:
            Delivery record with results
        """
        endpoint = await self.get_endpoint(endpoint_id, org_id)

        payload = WebhookPayload(
            event_type=event_type,
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            org_id=org_id,
            data=custom_payload
            or {
                "message": "This is a test webhook from Automation Platform",
                "test": True,
            },
            metadata={"triggered_by": "test"},
        )

        return await self._deliver_to_endpoint(endpoint, payload)

    async def get_deliveries(
        self,
        endpoint_id: int,
        org_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[WebhookDelivery]:
        """
        Get delivery history for an endpoint.

        Args:
            endpoint_id: Endpoint ID
            org_id: Organization ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of deliveries
        """
        # Verify endpoint access
        await self.get_endpoint(endpoint_id, org_id)
        return list(
            await self.delivery_dao.get_by_endpoint(endpoint_id, limit, offset)
        )

    async def get_delivery_stats(
        self,
        endpoint_id: int,
        org_id: int,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get delivery statistics for an endpoint.

        Args:
            endpoint_id: Endpoint ID
            org_id: Organization ID
            days: Number of days to include

        Returns:
            Delivery statistics
        """
        await self.get_endpoint(endpoint_id, org_id)
        since = datetime.utcnow() - timedelta(days=days)
        stats = await self.delivery_dao.get_stats(endpoint_id, since)
        stats["period_start"] = since
        stats["period_end"] = datetime.utcnow()
        return stats

    def _generate_secret(self) -> str:
        """Generate a webhook signing secret."""
        import secrets

        return f"whsec_{secrets.token_urlsafe(32)}"

    def _sign_payload(self, payload: str, secret: str) -> str:
        """
        Sign webhook payload with HMAC-SHA256.

        WHAT: Creates signature for payload verification.

        WHY: Signature allows webhook receivers to verify
        the payload came from us and wasn't tampered with.

        Args:
            payload: JSON payload string
            secret: Signing secret

        Returns:
            Signature in format "sha256=..."
        """
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"


# ============================================================================
# Webhook Event Helpers
# ============================================================================


async def trigger_ticket_created(
    session: AsyncSession,
    org_id: int,
    ticket_data: Dict[str, Any],
) -> List[WebhookDelivery]:
    """Helper to trigger ticket.created event."""
    service = WebhookService(session)
    return await service.trigger_event(
        org_id=org_id,
        event_type=WebhookEventType.TICKET_CREATED.value,
        data=ticket_data,
    )


async def trigger_ticket_updated(
    session: AsyncSession,
    org_id: int,
    ticket_data: Dict[str, Any],
    changes: Dict[str, Any],
) -> List[WebhookDelivery]:
    """Helper to trigger ticket.updated event."""
    service = WebhookService(session)
    return await service.trigger_event(
        org_id=org_id,
        event_type=WebhookEventType.TICKET_UPDATED.value,
        data=ticket_data,
        metadata={"changes": changes},
    )


async def trigger_project_created(
    session: AsyncSession,
    org_id: int,
    project_data: Dict[str, Any],
) -> List[WebhookDelivery]:
    """Helper to trigger project.created event."""
    service = WebhookService(session)
    return await service.trigger_event(
        org_id=org_id,
        event_type=WebhookEventType.PROJECT_CREATED.value,
        data=project_data,
    )


async def trigger_invoice_paid(
    session: AsyncSession,
    org_id: int,
    invoice_data: Dict[str, Any],
) -> List[WebhookDelivery]:
    """Helper to trigger invoice.paid event."""
    service = WebhookService(session)
    return await service.trigger_event(
        org_id=org_id,
        event_type=WebhookEventType.INVOICE_PAID.value,
        data=invoice_data,
    )
