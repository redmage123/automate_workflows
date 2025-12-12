"""
Unit tests for Integration Services.

WHAT: Tests for CalendarIntegrationService and WebhookService.

WHY: Verifies that:
1. Calendar OAuth flow generates correct URLs
2. Calendar sync operations update status correctly
3. Webhook payload signing works correctly
4. Webhook delivery and retry logic work
5. Event triggering sends to correct endpoints

HOW: Uses pytest-asyncio with mocked external dependencies.
"""

import pytest
import hmac
import hashlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.integration_service import (
    CalendarIntegrationService,
    WebhookService,
    IntegrationError,
    CalendarIntegrationError,
    OAuthError,
    WebhookDeliveryError,
)
from app.models.integration import (
    CalendarProvider,
    WebhookEventType,
)
from tests.factories import (
    OrganizationFactory,
    UserFactory,
    CalendarIntegrationFactory,
    WebhookEndpointFactory,
    WebhookDeliveryFactory,
)


# ============================================================================
# Calendar Integration Service Tests
# ============================================================================


class TestCalendarIntegrationServiceOAuth:
    """Tests for OAuth flow operations."""

    @pytest.mark.asyncio
    async def test_get_oauth_url_google(self, db_session, test_org, test_user, monkeypatch):
        """Test generating Google OAuth URL."""
        # Mock settings
        monkeypatch.setattr(
            "app.services.integration_service.settings",
            MagicMock(GOOGLE_CALENDAR_CLIENT_ID="test_client_id"),
        )

        service = CalendarIntegrationService(db_session)
        url = await service.get_oauth_url(
            provider=CalendarProvider.GOOGLE.value,
            user_id=test_user.id,
            org_id=test_org.id,
            redirect_uri="https://example.com/callback",
        )

        assert "accounts.google.com" in url
        assert "client_id=test_client_id" in url
        assert "redirect_uri=https://example.com/callback" in url
        assert "scope" in url
        assert "state=" in url

    @pytest.mark.asyncio
    async def test_get_oauth_url_invalid_provider(self, db_session, test_org, test_user):
        """Test that invalid provider raises error."""
        service = CalendarIntegrationService(db_session)

        with pytest.raises(Exception) as exc_info:
            await service.get_oauth_url(
                provider="invalid_provider",
                user_id=test_user.id,
                org_id=test_org.id,
                redirect_uri="https://example.com/callback",
            )

        assert "Unsupported calendar provider" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_state_encoding_decoding(self, db_session):
        """Test state parameter encoding and decoding."""
        service = CalendarIntegrationService(db_session)

        state = service._encode_state(user_id=123, org_id=456, provider="google")
        user_id, org_id, provider = service._decode_state(state)

        assert user_id == 123
        assert org_id == 456
        assert provider == "google"


class TestCalendarIntegrationServiceCRUD:
    """Tests for calendar integration CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_user_integrations(self, db_session, test_org, test_user):
        """Test getting all integrations for a user."""
        await CalendarIntegrationFactory.create(
            db_session,
            user=test_user,
            organization=test_org,
            provider=CalendarProvider.GOOGLE.value,
        )
        await CalendarIntegrationFactory.create(
            db_session,
            user=test_user,
            organization=test_org,
            provider=CalendarProvider.OUTLOOK.value,
        )

        service = CalendarIntegrationService(db_session)
        integrations = await service.get_user_integrations(test_user.id, test_org.id)

        assert len(integrations) == 2

    @pytest.mark.asyncio
    async def test_get_integration_success(self, db_session, test_org, test_user):
        """Test getting a specific integration."""
        integration = await CalendarIntegrationFactory.create(
            db_session, user=test_user, organization=test_org
        )

        service = CalendarIntegrationService(db_session)
        found = await service.get_integration(integration.id, test_user.id)

        assert found.id == integration.id

    @pytest.mark.asyncio
    async def test_get_integration_wrong_user(self, db_session, test_org, test_user):
        """Test getting integration owned by different user fails."""
        other_user = await UserFactory.create(
            db_session, email="other@test.com", organization=test_org
        )
        integration = await CalendarIntegrationFactory.create(
            db_session, user=other_user, organization=test_org
        )

        service = CalendarIntegrationService(db_session)

        with pytest.raises(Exception):  # NotFoundError
            await service.get_integration(integration.id, test_user.id)

    @pytest.mark.asyncio
    async def test_delete_integration(self, db_session, test_org, test_user):
        """Test deleting an integration."""
        integration = await CalendarIntegrationFactory.create(
            db_session, user=test_user, organization=test_org
        )

        service = CalendarIntegrationService(db_session)
        await service.delete_integration(integration.id, test_user.id)
        await db_session.commit()

        # Verify deleted
        found = await service.dao.get_by_id(integration.id)
        assert found is None


class TestCalendarIntegrationServiceSync:
    """Tests for calendar sync operations."""

    @pytest.mark.asyncio
    async def test_sync_calendar_updates_status(self, db_session, test_org, test_user):
        """Test that sync updates last_sync_at."""
        integration = await CalendarIntegrationFactory.create(
            db_session,
            user=test_user,
            organization=test_org,
            token_expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        assert integration.last_sync_at is None

        service = CalendarIntegrationService(db_session)
        result = await service.sync_calendar(
            integration_id=integration.id,
            user_id=test_user.id,
        )

        assert result["status"] == "success"

        # Refresh and check
        updated = await service.dao.get_by_id(integration.id)
        assert updated.last_sync_at is not None


# ============================================================================
# Webhook Service Tests
# ============================================================================


class TestWebhookServiceEndpoints:
    """Tests for webhook endpoint management."""

    @pytest.mark.asyncio
    async def test_create_endpoint_generates_secret(self, db_session, test_org, test_admin):
        """Test that creating endpoint generates signing secret."""
        from app.schemas.integration import WebhookEndpointCreate

        service = WebhookService(db_session)
        endpoint = await service.create_endpoint(
            org_id=test_org.id,
            data=WebhookEndpointCreate(
                name="Test Webhook",
                url="https://example.com/webhook",
                events=["ticket.created"],
            ),
            created_by_id=test_admin.id,
        )

        assert endpoint.secret.startswith("whsec_")
        assert len(endpoint.secret) > 40

    @pytest.mark.asyncio
    async def test_get_endpoints(self, db_session, test_org):
        """Test listing endpoints for an org."""
        await WebhookEndpointFactory.create(
            db_session, name="Webhook 1", organization=test_org
        )
        await WebhookEndpointFactory.create(
            db_session, name="Webhook 2", organization=test_org
        )

        service = WebhookService(db_session)
        endpoints = await service.get_endpoints(test_org.id)

        assert len(endpoints) == 2

    @pytest.mark.asyncio
    async def test_regenerate_secret(self, db_session, test_org):
        """Test regenerating webhook secret."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )
        old_secret = endpoint.secret

        service = WebhookService(db_session)
        updated = await service.regenerate_secret(endpoint.id, test_org.id)

        assert updated.secret != old_secret
        assert updated.secret.startswith("whsec_")


class TestWebhookServiceSigning:
    """Tests for payload signing."""

    def test_sign_payload(self, db_session):
        """Test HMAC-SHA256 payload signing."""
        service = WebhookService(db_session)

        payload = '{"event": "test"}'
        secret = "whsec_test123"

        signature = service._sign_payload(payload, secret)

        assert signature.startswith("sha256=")

        # Verify signature
        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        assert signature == f"sha256={expected}"


class TestWebhookServiceDelivery:
    """Tests for webhook delivery."""

    @pytest.mark.asyncio
    async def test_trigger_event_finds_subscribed_endpoints(self, db_session, test_org):
        """Test that event triggering finds correct endpoints."""
        # Create endpoint subscribed to ticket events
        await WebhookEndpointFactory.create(
            db_session,
            name="Ticket Webhook",
            organization=test_org,
            events=["ticket.created"],
        )

        # Create endpoint subscribed to project events (should not receive)
        await WebhookEndpointFactory.create(
            db_session,
            name="Project Webhook",
            organization=test_org,
            events=["project.created"],
        )

        service = WebhookService(db_session)

        # Mock HTTP client
        with patch("app.services.integration_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = '{"ok": true}'
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            deliveries = await service.trigger_event(
                org_id=test_org.id,
                event_type=WebhookEventType.TICKET_CREATED.value,
                data={"ticket_id": 123},
            )

        # Should only deliver to ticket webhook
        assert len(deliveries) == 1

    @pytest.mark.asyncio
    async def test_trigger_event_no_subscribers(self, db_session, test_org):
        """Test triggering event with no subscribers."""
        await WebhookEndpointFactory.create(
            db_session,
            organization=test_org,
            events=["project.created"],
        )

        service = WebhookService(db_session)
        deliveries = await service.trigger_event(
            org_id=test_org.id,
            event_type=WebhookEventType.TICKET_CREATED.value,
            data={"ticket_id": 123},
        )

        assert len(deliveries) == 0

    @pytest.mark.asyncio
    async def test_test_endpoint(self, db_session, test_org):
        """Test sending test event to endpoint."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        service = WebhookService(db_session)

        with patch("app.services.integration_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.text = '{"received": true}'
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            delivery = await service.test_endpoint(
                endpoint_id=endpoint.id,
                org_id=test_org.id,
            )

        assert delivery.event_type == "test.ping"
        assert delivery.delivered is True
        assert delivery.response_status == 200


class TestWebhookServiceRetry:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_retry_failed_deliveries(self, db_session, test_org):
        """Test retrying failed deliveries."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org, retry_enabled=True
        )
        await WebhookDeliveryFactory.create_pending_retry(
            db_session, endpoint=endpoint
        )

        service = WebhookService(db_session)

        with patch("app.services.integration_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = '{"ok": true}'
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            retry_count = await service.retry_failed_deliveries()

        assert retry_count == 1


class TestWebhookServiceDeliveryHistory:
    """Tests for delivery history."""

    @pytest.mark.asyncio
    async def test_get_deliveries(self, db_session, test_org):
        """Test getting delivery history."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )
        await WebhookDeliveryFactory.create_successful(db_session, endpoint=endpoint)
        await WebhookDeliveryFactory.create_failed(db_session, endpoint=endpoint)

        service = WebhookService(db_session)
        deliveries = await service.get_deliveries(
            endpoint_id=endpoint.id,
            org_id=test_org.id,
        )

        assert len(deliveries) == 2

    @pytest.mark.asyncio
    async def test_get_delivery_stats(self, db_session, test_org):
        """Test getting delivery statistics."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )
        await WebhookDeliveryFactory.create_successful(db_session, endpoint=endpoint)
        await WebhookDeliveryFactory.create_successful(db_session, endpoint=endpoint)
        await WebhookDeliveryFactory.create_failed(db_session, endpoint=endpoint)

        service = WebhookService(db_session)
        stats = await service.get_delivery_stats(
            endpoint_id=endpoint.id,
            org_id=test_org.id,
            days=7,
        )

        assert stats["total_deliveries"] == 3
        assert stats["successful_deliveries"] == 2
        assert stats["failed_deliveries"] == 1
        assert "success_rate" in stats


class TestWebhookServiceMultiTenancy:
    """Tests for multi-tenancy isolation."""

    @pytest.mark.asyncio
    async def test_get_endpoint_wrong_org(self, db_session):
        """Test getting endpoint from wrong org fails."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=org1
        )

        service = WebhookService(db_session)

        with pytest.raises(Exception):  # NotFoundError
            await service.get_endpoint(endpoint.id, org2.id)


# ============================================================================
# Exception Tests
# ============================================================================


class TestIntegrationExceptions:
    """Tests for custom exceptions."""

    def test_integration_error(self):
        """Test IntegrationError."""
        error = IntegrationError(
            message="Test error",
            details={"key": "value"},
        )
        assert error.message == "Test error"
        assert error.details["key"] == "value"
        assert error.status_code == 500

    def test_calendar_integration_error(self):
        """Test CalendarIntegrationError."""
        error = CalendarIntegrationError(
            message="Calendar error",
            provider="google",
            details={"reason": "token_expired"},
        )
        assert "google" in error.details["provider"]

    def test_oauth_error(self):
        """Test OAuthError."""
        error = OAuthError(
            message="OAuth failed",
            provider="google",
        )
        assert error.status_code == 401

    def test_webhook_delivery_error(self):
        """Test WebhookDeliveryError."""
        error = WebhookDeliveryError(
            message="Delivery failed",
            endpoint_id=123,
            status_code=500,
            retryable=True,
        )
        assert error.retryable is True
        assert error.details["endpoint_id"] == 123
