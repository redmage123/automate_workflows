"""
Integration tests for Integrations API endpoints.

WHAT: Tests for calendar and webhook API endpoints.

WHY: Verifies that:
1. Calendar integration endpoints work correctly
2. Webhook endpoint management works correctly
3. Authentication and authorization are enforced
4. Response formats are correct

HOW: Uses pytest-asyncio with test HTTP client for integration testing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.user import UserRole
from app.core.auth import create_access_token
from tests.factories import (
    OrganizationFactory,
    UserFactory,
    CalendarIntegrationFactory,
    WebhookEndpointFactory,
    WebhookDeliveryFactory,
)


# ============================================================================
# Helper Fixtures
# ============================================================================


@pytest.fixture
def auth_headers(test_user):
    """Create auth headers for test user."""
    token = create_access_token(test_user.id, test_user.org_id, test_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_admin):
    """Create auth headers for admin user."""
    token = create_access_token(test_admin.id, test_admin.org_id, test_admin.role.value)
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Calendar Integration API Tests
# ============================================================================


class TestCalendarIntegrationListAPI:
    """Tests for listing calendar integrations."""

    @pytest.mark.asyncio
    async def test_list_integrations_empty(self, client, auth_headers):
        """Test listing integrations when none exist."""
        response = await client.get(
            "/api/integrations/calendar",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_integrations_with_data(
        self, client, db_session, test_org, test_user, auth_headers
    ):
        """Test listing integrations with existing data."""
        await CalendarIntegrationFactory.create(
            db_session, user=test_user, organization=test_org
        )

        response = await client.get(
            "/api/integrations/calendar",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_integrations_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        response = await client.get("/api/integrations/calendar")

        assert response.status_code == 401


class TestCalendarIntegrationConnectAPI:
    """Tests for initiating OAuth flow."""

    @pytest.mark.asyncio
    async def test_connect_returns_oauth_url(
        self, client, auth_headers, monkeypatch
    ):
        """Test that connect returns OAuth authorization URL."""
        # Mock settings
        from app.core import config
        monkeypatch.setattr(config.settings, "GOOGLE_CALENDAR_CLIENT_ID", "test_client_id")

        response = await client.post(
            "/api/integrations/calendar/connect",
            headers=auth_headers,
            json={"provider": "google"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "accounts.google.com" in data["authorization_url"]

    @pytest.mark.asyncio
    async def test_connect_invalid_provider(self, client, auth_headers):
        """Test that invalid provider is rejected."""
        response = await client.post(
            "/api/integrations/calendar/connect",
            headers=auth_headers,
            json={"provider": "invalid"},
        )

        assert response.status_code == 422  # Validation error


class TestCalendarIntegrationGetAPI:
    """Tests for getting specific integration."""

    @pytest.mark.asyncio
    async def test_get_integration_success(
        self, client, db_session, test_org, test_user, auth_headers
    ):
        """Test getting an integration by ID."""
        integration = await CalendarIntegrationFactory.create(
            db_session, user=test_user, organization=test_org
        )

        response = await client.get(
            f"/api/integrations/calendar/{integration.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == integration.id
        assert data["provider"] == "google"
        # Tokens should not be in response
        assert "access_token" not in data
        assert "refresh_token" not in data

    @pytest.mark.asyncio
    async def test_get_integration_not_found(self, client, auth_headers):
        """Test getting non-existent integration."""
        response = await client.get(
            "/api/integrations/calendar/99999",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestCalendarIntegrationUpdateAPI:
    """Tests for updating integration."""

    @pytest.mark.asyncio
    async def test_update_integration_success(
        self, client, db_session, test_org, test_user, auth_headers
    ):
        """Test updating integration settings."""
        integration = await CalendarIntegrationFactory.create(
            db_session,
            user=test_user,
            organization=test_org,
            sync_projects=True,
            sync_tickets=False,
        )

        response = await client.patch(
            f"/api/integrations/calendar/{integration.id}",
            headers=auth_headers,
            json={
                "sync_tickets": True,
                "calendar_name": "Work Calendar",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sync_tickets"] is True
        assert data["calendar_name"] == "Work Calendar"


class TestCalendarIntegrationDeleteAPI:
    """Tests for deleting integration."""

    @pytest.mark.asyncio
    async def test_delete_integration_success(
        self, client, db_session, test_org, test_user, auth_headers
    ):
        """Test deleting an integration."""
        integration = await CalendarIntegrationFactory.create(
            db_session, user=test_user, organization=test_org
        )

        response = await client.delete(
            f"/api/integrations/calendar/{integration.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_integration_wrong_user(
        self, client, db_session, test_org, test_user, auth_headers
    ):
        """Test that user cannot delete another user's integration."""
        other_user = await UserFactory.create(
            db_session, email="other@test.com", organization=test_org
        )
        integration = await CalendarIntegrationFactory.create(
            db_session, user=other_user, organization=test_org
        )

        response = await client.delete(
            f"/api/integrations/calendar/{integration.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404


# ============================================================================
# Webhook Endpoint API Tests
# ============================================================================


class TestWebhookEndpointListAPI:
    """Tests for listing webhook endpoints."""

    @pytest.mark.asyncio
    async def test_list_webhooks_admin_only(self, client, auth_headers):
        """Test that non-admins cannot list webhooks."""
        response = await client.get(
            "/api/integrations/webhooks",
            headers=auth_headers,  # CLIENT role
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_webhooks_success(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test listing webhooks as admin."""
        await WebhookEndpointFactory.create(
            db_session, name="Webhook 1", organization=test_org
        )
        await WebhookEndpointFactory.create(
            db_session, name="Webhook 2", organization=test_org
        )

        response = await client.get(
            "/api/integrations/webhooks",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2


class TestWebhookEndpointCreateAPI:
    """Tests for creating webhook endpoints."""

    @pytest.mark.asyncio
    async def test_create_webhook_success(
        self, client, admin_auth_headers
    ):
        """Test creating a webhook endpoint."""
        response = await client.post(
            "/api/integrations/webhooks",
            headers=admin_auth_headers,
            json={
                "name": "Slack Notifications",
                "url": "https://hooks.slack.com/services/xxx",
                "events": ["ticket.created", "ticket.updated"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Slack Notifications"
        assert "ticket.created" in data["events"]
        # Secret should be in creation response
        assert "secret" in data
        assert data["secret"].startswith("whsec_")

    @pytest.mark.asyncio
    async def test_create_webhook_requires_https(
        self, client, admin_auth_headers
    ):
        """Test that HTTP URLs are rejected."""
        response = await client.post(
            "/api/integrations/webhooks",
            headers=admin_auth_headers,
            json={
                "name": "Test Webhook",
                "url": "http://example.com/webhook",  # HTTP not HTTPS
                "events": ["ticket.created"],
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_webhook_admin_only(self, client, auth_headers):
        """Test that non-admins cannot create webhooks."""
        response = await client.post(
            "/api/integrations/webhooks",
            headers=auth_headers,  # CLIENT role
            json={
                "name": "Test",
                "url": "https://example.com/webhook",
                "events": ["ticket.created"],
            },
        )

        assert response.status_code == 403


class TestWebhookEndpointGetAPI:
    """Tests for getting webhook endpoints."""

    @pytest.mark.asyncio
    async def test_get_webhook_success(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test getting a webhook endpoint."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        response = await client.get(
            f"/api/integrations/webhooks/{endpoint.id}",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == endpoint.id
        # Secret should NOT be in regular response
        assert "secret" not in data

    @pytest.mark.asyncio
    async def test_get_webhook_with_secret(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test getting webhook with secret."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        response = await client.get(
            f"/api/integrations/webhooks/{endpoint.id}/secret",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "secret" in data


class TestWebhookEndpointUpdateAPI:
    """Tests for updating webhook endpoints."""

    @pytest.mark.asyncio
    async def test_update_webhook_success(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test updating a webhook endpoint."""
        endpoint = await WebhookEndpointFactory.create(
            db_session,
            name="Original Name",
            organization=test_org,
        )

        response = await client.patch(
            f"/api/integrations/webhooks/{endpoint.id}",
            headers=admin_auth_headers,
            json={
                "name": "Updated Name",
                "events": ["ticket.*"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert "ticket.*" in data["events"]


class TestWebhookEndpointDeleteAPI:
    """Tests for deleting webhook endpoints."""

    @pytest.mark.asyncio
    async def test_delete_webhook_success(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test deleting a webhook endpoint."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        response = await client.delete(
            f"/api/integrations/webhooks/{endpoint.id}",
            headers=admin_auth_headers,
        )

        assert response.status_code == 204


class TestWebhookEndpointActivationAPI:
    """Tests for activating/deactivating webhooks."""

    @pytest.mark.asyncio
    async def test_deactivate_webhook(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test deactivating a webhook."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org, is_active=True
        )

        response = await client.post(
            f"/api/integrations/webhooks/{endpoint.id}/deactivate",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_activate_webhook(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test activating a webhook."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org, is_active=False
        )

        response = await client.post(
            f"/api/integrations/webhooks/{endpoint.id}/activate",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True


class TestWebhookEndpointRegenerateSecretAPI:
    """Tests for regenerating webhook secret."""

    @pytest.mark.asyncio
    async def test_regenerate_secret(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test regenerating webhook secret."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )
        old_secret = endpoint.secret

        response = await client.post(
            f"/api/integrations/webhooks/{endpoint.id}/regenerate-secret",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["secret"] != old_secret
        assert data["secret"].startswith("whsec_")


class TestWebhookEndpointTestAPI:
    """Tests for testing webhook endpoints."""

    @pytest.mark.asyncio
    async def test_test_webhook(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test sending test event to webhook."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        with patch("app.services.integration_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.text = '{"received": true}'
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            response = await client.post(
                f"/api/integrations/webhooks/{endpoint.id}/test",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "test.ping"
        assert data["delivered"] is True


# ============================================================================
# Webhook Delivery API Tests
# ============================================================================


class TestWebhookDeliveryListAPI:
    """Tests for listing webhook deliveries."""

    @pytest.mark.asyncio
    async def test_list_deliveries(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test listing deliveries for an endpoint."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )
        await WebhookDeliveryFactory.create_successful(
            db_session, endpoint=endpoint
        )
        await WebhookDeliveryFactory.create_failed(
            db_session, endpoint=endpoint
        )

        response = await client.get(
            f"/api/integrations/webhooks/{endpoint.id}/deliveries",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2


class TestWebhookDeliveryStatsAPI:
    """Tests for delivery statistics."""

    @pytest.mark.asyncio
    async def test_get_delivery_stats(
        self, client, db_session, test_org, admin_auth_headers
    ):
        """Test getting delivery statistics."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )
        await WebhookDeliveryFactory.create_successful(
            db_session, endpoint=endpoint
        )
        await WebhookDeliveryFactory.create_successful(
            db_session, endpoint=endpoint
        )
        await WebhookDeliveryFactory.create_failed(
            db_session, endpoint=endpoint
        )

        response = await client.get(
            f"/api/integrations/webhooks/{endpoint.id}/stats",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_deliveries"] == 3
        assert data["successful_deliveries"] == 2
        assert data["failed_deliveries"] == 1


class TestWebhookAvailableEventsAPI:
    """Tests for available events endpoint."""

    @pytest.mark.asyncio
    async def test_list_available_events(self, client, auth_headers):
        """Test listing available webhook events."""
        response = await client.get(
            "/api/integrations/webhooks/events/available",
            headers=auth_headers,  # Any authenticated user can view
        )

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "wildcards" in data
        assert "ticket" in data["events"]


# ============================================================================
# Multi-Tenancy Tests
# ============================================================================


class TestIntegrationMultiTenancy:
    """Tests for multi-tenancy isolation."""

    @pytest.mark.asyncio
    async def test_cannot_access_other_org_webhook(
        self, client, db_session
    ):
        """Test that webhooks from other orgs are not accessible."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        admin1 = await UserFactory.create_admin(
            db_session, email="admin1@test.com", organization=org1
        )
        admin2 = await UserFactory.create_admin(
            db_session, email="admin2@test.com", organization=org2
        )

        # Create webhook in org1
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=org1
        )

        # Try to access from org2
        token = create_access_token(admin2.id, admin2.org_id, admin2.role.value)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get(
            f"/api/integrations/webhooks/{endpoint.id}",
            headers=headers,
        )

        assert response.status_code == 404
