"""
Unit tests for Integration DAOs.

WHAT: Tests for CalendarIntegrationDAO, WebhookEndpointDAO, WebhookDeliveryDAO.

WHY: Verifies that:
1. Calendar integration CRUD operations work correctly
2. Webhook endpoint management and event filtering work
3. Webhook delivery tracking and retry logic work
4. Org-scoping is enforced (multi-tenancy security)
5. Query methods filter and paginate correctly

HOW: Uses pytest-asyncio with PostgreSQL test database for isolation.
"""

import pytest
from datetime import datetime, timedelta

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
from tests.factories import (
    OrganizationFactory,
    UserFactory,
    CalendarIntegrationFactory,
    WebhookEndpointFactory,
    WebhookDeliveryFactory,
)


# ============================================================================
# Calendar Integration DAO Tests
# ============================================================================


class TestCalendarIntegrationDAOCreate:
    """Tests for calendar integration creation."""

    @pytest.mark.asyncio
    async def test_create_integration_success(self, db_session, test_org, test_user):
        """Test creating a calendar integration with all fields."""
        dao = CalendarIntegrationDAO(db_session)

        integration = CalendarIntegration(
            user_id=test_user.id,
            org_id=test_org.id,
            provider=CalendarProvider.GOOGLE.value,
            provider_email="test@google.com",
            access_token="access_token_123",
            refresh_token="refresh_token_456",
            token_expires_at=datetime.utcnow() + timedelta(hours=1),
            calendar_name="My Calendar",
            sync_enabled=True,
            sync_projects=True,
            is_active=True,
        )
        created = await dao.create(integration)

        assert created.id is not None
        assert created.user_id == test_user.id
        assert created.org_id == test_org.id
        assert created.provider == CalendarProvider.GOOGLE.value
        assert created.provider_email == "test@google.com"
        assert created.access_token == "access_token_123"
        assert created.is_active is True

    @pytest.mark.asyncio
    async def test_create_multiple_providers_same_user(self, db_session, test_org, test_user):
        """Test creating multiple integrations for same user with different providers."""
        dao = CalendarIntegrationDAO(db_session)

        # Create Google integration
        google = CalendarIntegration(
            user_id=test_user.id,
            org_id=test_org.id,
            provider=CalendarProvider.GOOGLE.value,
            access_token="google_token",
            is_active=True,
        )
        google = await dao.create(google)

        # Create Outlook integration
        outlook = CalendarIntegration(
            user_id=test_user.id,
            org_id=test_org.id,
            provider=CalendarProvider.OUTLOOK.value,
            access_token="outlook_token",
            is_active=True,
        )
        outlook = await dao.create(outlook)

        assert google.id != outlook.id
        assert google.provider == CalendarProvider.GOOGLE.value
        assert outlook.provider == CalendarProvider.OUTLOOK.value


class TestCalendarIntegrationDAORead:
    """Tests for calendar integration read operations."""

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session, test_org, test_user):
        """Test retrieving integration by ID."""
        integration = await CalendarIntegrationFactory.create(
            db_session, user=test_user, organization=test_org
        )

        dao = CalendarIntegrationDAO(db_session)
        found = await dao.get_by_id(integration.id)

        assert found is not None
        assert found.id == integration.id
        assert found.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_get_by_user_and_provider(self, db_session, test_org, test_user):
        """Test retrieving integration by user and provider."""
        await CalendarIntegrationFactory.create(
            db_session,
            user=test_user,
            organization=test_org,
            provider=CalendarProvider.GOOGLE.value,
        )

        dao = CalendarIntegrationDAO(db_session)
        found = await dao.get_by_user_and_provider(
            test_user.id, CalendarProvider.GOOGLE.value
        )

        assert found is not None
        assert found.provider == CalendarProvider.GOOGLE.value

    @pytest.mark.asyncio
    async def test_get_by_user_and_provider_not_found(self, db_session, test_org, test_user):
        """Test retrieving non-existent integration returns None."""
        await CalendarIntegrationFactory.create(
            db_session,
            user=test_user,
            organization=test_org,
            provider=CalendarProvider.GOOGLE.value,
        )

        dao = CalendarIntegrationDAO(db_session)
        found = await dao.get_by_user_and_provider(
            test_user.id, CalendarProvider.OUTLOOK.value
        )

        assert found is None

    @pytest.mark.asyncio
    async def test_get_user_integrations(self, db_session, test_org, test_user):
        """Test getting all integrations for a user."""
        # Create multiple integrations
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

        dao = CalendarIntegrationDAO(db_session)
        integrations = await dao.get_user_integrations(test_user.id, test_org.id)

        assert len(integrations) == 2


class TestCalendarIntegrationDAOTokenRefresh:
    """Tests for token refresh operations."""

    @pytest.mark.asyncio
    async def test_get_integrations_needing_refresh(self, db_session, test_org, test_user):
        """Test finding integrations with expiring tokens."""
        # Create integration with soon-expiring token
        await CalendarIntegrationFactory.create(
            db_session,
            user=test_user,
            organization=test_org,
            token_expires_at=datetime.utcnow() + timedelta(minutes=3),
        )

        # Create integration with valid token
        user2 = await UserFactory.create(
            db_session, email="user2@test.com", organization=test_org
        )
        await CalendarIntegrationFactory.create(
            db_session,
            user=user2,
            organization=test_org,
            token_expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        dao = CalendarIntegrationDAO(db_session)
        needing_refresh = await dao.get_integrations_needing_refresh(buffer_minutes=5)

        assert len(needing_refresh) == 1
        assert needing_refresh[0].user_id == test_user.id

    @pytest.mark.asyncio
    async def test_update_tokens(self, db_session, test_org, test_user):
        """Test updating OAuth tokens."""
        integration = await CalendarIntegrationFactory.create(
            db_session, user=test_user, organization=test_org
        )
        old_token = integration.access_token

        dao = CalendarIntegrationDAO(db_session)
        new_expires = datetime.utcnow() + timedelta(hours=2)
        updated = await dao.update_tokens(
            integration_id=integration.id,
            access_token="new_access_token",
            refresh_token="new_refresh_token",
            expires_at=new_expires,
        )

        assert updated.access_token == "new_access_token"
        assert updated.access_token != old_token
        assert updated.refresh_token == "new_refresh_token"


class TestCalendarIntegrationDAOSync:
    """Tests for sync-related operations."""

    @pytest.mark.asyncio
    async def test_get_active_integrations(self, db_session, test_org, test_user):
        """Test getting active integrations for an org."""
        # Create active integration
        await CalendarIntegrationFactory.create(
            db_session,
            user=test_user,
            organization=test_org,
            is_active=True,
            sync_enabled=True,
        )

        # Create inactive integration
        user2 = await UserFactory.create(
            db_session, email="inactive@test.com", organization=test_org
        )
        await CalendarIntegrationFactory.create(
            db_session,
            user=user2,
            organization=test_org,
            is_active=False,
            sync_enabled=True,
        )

        dao = CalendarIntegrationDAO(db_session)
        active = await dao.get_active_integrations(test_org.id)

        assert len(active) == 1
        assert active[0].is_active is True

    @pytest.mark.asyncio
    async def test_update_sync_status(self, db_session, test_org, test_user):
        """Test updating sync status."""
        integration = await CalendarIntegrationFactory.create(
            db_session, user=test_user, organization=test_org
        )
        assert integration.last_sync_at is None

        dao = CalendarIntegrationDAO(db_session)
        sync_time = datetime.utcnow()
        updated = await dao.update_sync_status(
            integration_id=integration.id,
            last_sync_at=sync_time,
        )

        assert updated.last_sync_at is not None

    @pytest.mark.asyncio
    async def test_deactivate_integration(self, db_session, test_org, test_user):
        """Test deactivating an integration."""
        integration = await CalendarIntegrationFactory.create(
            db_session, user=test_user, organization=test_org, is_active=True
        )

        dao = CalendarIntegrationDAO(db_session)
        deactivated = await dao.deactivate(
            integration.id, error_message="OAuth revoked"
        )

        assert deactivated.is_active is False
        assert deactivated.error_message == "OAuth revoked"


class TestCalendarIntegrationDAOMultiTenancy:
    """Tests for multi-tenancy isolation."""

    @pytest.mark.asyncio
    async def test_integrations_isolated_by_org(self, db_session):
        """Test that integrations from different orgs are isolated."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")
        user1 = await UserFactory.create(
            db_session, email="user1@org1.com", organization=org1
        )
        user2 = await UserFactory.create(
            db_session, email="user2@org2.com", organization=org2
        )

        await CalendarIntegrationFactory.create(
            db_session, user=user1, organization=org1
        )
        await CalendarIntegrationFactory.create(
            db_session, user=user2, organization=org2
        )

        dao = CalendarIntegrationDAO(db_session)

        org1_integrations = await dao.get_user_integrations(user1.id, org1.id)
        org2_integrations = await dao.get_user_integrations(user2.id, org2.id)

        assert len(org1_integrations) == 1
        assert len(org2_integrations) == 1
        assert org1_integrations[0].org_id == org1.id
        assert org2_integrations[0].org_id == org2.id


# ============================================================================
# Webhook Endpoint DAO Tests
# ============================================================================


class TestWebhookEndpointDAOCreate:
    """Tests for webhook endpoint creation."""

    @pytest.mark.asyncio
    async def test_create_endpoint_success(self, db_session, test_org, test_admin):
        """Test creating a webhook endpoint."""
        dao = WebhookEndpointDAO(db_session)

        endpoint = WebhookEndpoint(
            org_id=test_org.id,
            name="Slack Notifications",
            description="Send notifications to Slack",
            url="https://hooks.slack.com/services/xxx",
            secret="whsec_test123",
            events=["ticket.created", "ticket.updated"],
            is_active=True,
            created_by_id=test_admin.id,
        )
        created = await dao.create(endpoint)

        assert created.id is not None
        assert created.name == "Slack Notifications"
        assert created.url == "https://hooks.slack.com/services/xxx"
        assert "ticket.created" in created.events
        assert created.is_active is True

    @pytest.mark.asyncio
    async def test_create_endpoint_with_headers(self, db_session, test_org):
        """Test creating endpoint with custom headers."""
        dao = WebhookEndpointDAO(db_session)

        endpoint = WebhookEndpoint(
            org_id=test_org.id,
            name="Custom API",
            url="https://api.example.com/webhook",
            secret="whsec_test",
            events=["*"],
            headers={"X-Custom-Header": "value"},
            is_active=True,
        )
        created = await dao.create(endpoint)

        assert created.headers == {"X-Custom-Header": "value"}


class TestWebhookEndpointDAORead:
    """Tests for webhook endpoint read operations."""

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session, test_org):
        """Test retrieving endpoint by ID."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        dao = WebhookEndpointDAO(db_session)
        found = await dao.get_by_id(endpoint.id)

        assert found is not None
        assert found.id == endpoint.id

    @pytest.mark.asyncio
    async def test_get_by_org(self, db_session, test_org):
        """Test listing endpoints by organization."""
        await WebhookEndpointFactory.create(
            db_session, name="Webhook 1", organization=test_org
        )
        await WebhookEndpointFactory.create(
            db_session, name="Webhook 2", organization=test_org
        )
        await WebhookEndpointFactory.create(
            db_session, name="Inactive", organization=test_org, is_active=False
        )

        dao = WebhookEndpointDAO(db_session)

        # Active only
        active = await dao.get_by_org(test_org.id, include_inactive=False)
        assert len(active) == 2

        # Include inactive
        all_endpoints = await dao.get_by_org(test_org.id, include_inactive=True)
        assert len(all_endpoints) == 3


class TestWebhookEndpointDAOEventFiltering:
    """Tests for event subscription filtering."""

    @pytest.mark.asyncio
    async def test_get_endpoints_for_event_exact_match(self, db_session, test_org):
        """Test getting endpoints subscribed to exact event."""
        await WebhookEndpointFactory.create(
            db_session,
            name="Ticket Webhook",
            organization=test_org,
            events=[WebhookEventType.TICKET_CREATED.value],
        )
        await WebhookEndpointFactory.create(
            db_session,
            name="Project Webhook",
            organization=test_org,
            events=[WebhookEventType.PROJECT_CREATED.value],
        )

        dao = WebhookEndpointDAO(db_session)
        endpoints = await dao.get_endpoints_for_event(
            test_org.id, WebhookEventType.TICKET_CREATED.value
        )

        assert len(endpoints) == 1
        assert endpoints[0].name == "Ticket Webhook"

    @pytest.mark.asyncio
    async def test_get_endpoints_for_event_wildcard(self, db_session, test_org):
        """Test getting endpoints with wildcard subscriptions."""
        await WebhookEndpointFactory.create(
            db_session,
            name="All Tickets",
            organization=test_org,
            events=["ticket.*"],
        )
        await WebhookEndpointFactory.create(
            db_session,
            name="All Events",
            organization=test_org,
            events=["*"],
        )

        dao = WebhookEndpointDAO(db_session)
        endpoints = await dao.get_endpoints_for_event(
            test_org.id, WebhookEventType.TICKET_UPDATED.value
        )

        assert len(endpoints) == 2

    @pytest.mark.asyncio
    async def test_subscribes_to_method(self, db_session, test_org):
        """Test the subscribes_to method on WebhookEndpoint."""
        endpoint = await WebhookEndpointFactory.create(
            db_session,
            organization=test_org,
            events=["ticket.*", "invoice.paid"],
        )

        assert endpoint.subscribes_to("ticket.created") is True
        assert endpoint.subscribes_to("ticket.updated") is True
        assert endpoint.subscribes_to("invoice.paid") is True
        assert endpoint.subscribes_to("invoice.created") is False
        assert endpoint.subscribes_to("project.created") is False


class TestWebhookEndpointDAOStats:
    """Tests for delivery statistics."""

    @pytest.mark.asyncio
    async def test_update_stats_success(self, db_session, test_org):
        """Test updating stats after successful delivery."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )
        assert endpoint.delivery_count == 0

        dao = WebhookEndpointDAO(db_session)
        updated = await dao.update_stats(endpoint.id, delivered=True)

        assert updated.delivery_count == 1
        assert updated.success_count == 1
        assert updated.failure_count == 0
        assert updated.last_success_at is not None

    @pytest.mark.asyncio
    async def test_update_stats_failure(self, db_session, test_org):
        """Test updating stats after failed delivery."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        dao = WebhookEndpointDAO(db_session)
        updated = await dao.update_stats(endpoint.id, delivered=False)

        assert updated.delivery_count == 1
        assert updated.success_count == 0
        assert updated.failure_count == 1
        assert updated.last_failure_at is not None


class TestWebhookEndpointDAOActivation:
    """Tests for endpoint activation/deactivation."""

    @pytest.mark.asyncio
    async def test_deactivate_endpoint(self, db_session, test_org):
        """Test deactivating an endpoint."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org, is_active=True
        )

        dao = WebhookEndpointDAO(db_session)
        deactivated = await dao.deactivate(endpoint.id)

        assert deactivated.is_active is False

    @pytest.mark.asyncio
    async def test_activate_endpoint(self, db_session, test_org):
        """Test activating an endpoint."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org, is_active=False
        )

        dao = WebhookEndpointDAO(db_session)
        activated = await dao.activate(endpoint.id)

        assert activated.is_active is True


class TestWebhookEndpointDAOMultiTenancy:
    """Tests for multi-tenancy isolation."""

    @pytest.mark.asyncio
    async def test_endpoints_isolated_by_org(self, db_session):
        """Test that endpoints from different orgs are isolated."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        await WebhookEndpointFactory.create(
            db_session, name="Org1 Webhook", organization=org1
        )
        await WebhookEndpointFactory.create(
            db_session, name="Org2 Webhook", organization=org2
        )

        dao = WebhookEndpointDAO(db_session)

        org1_endpoints = await dao.get_by_org(org1.id)
        org2_endpoints = await dao.get_by_org(org2.id)

        assert len(org1_endpoints) == 1
        assert len(org2_endpoints) == 1
        assert org1_endpoints[0].org_id == org1.id
        assert org2_endpoints[0].org_id == org2.id


# ============================================================================
# Webhook Delivery DAO Tests
# ============================================================================


class TestWebhookDeliveryDAOCreate:
    """Tests for webhook delivery creation."""

    @pytest.mark.asyncio
    async def test_create_delivery_success(self, db_session, test_org):
        """Test creating a delivery record."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        dao = WebhookDeliveryDAO(db_session)
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            event_type=WebhookEventType.TICKET_CREATED.value,
            event_id="evt_12345",
            request_url=endpoint.url,
            request_body={"test": "data"},
        )
        created = await dao.create(delivery)

        assert created.id is not None
        assert created.event_type == WebhookEventType.TICKET_CREATED.value
        assert created.event_id == "evt_12345"
        assert created.delivered is False


class TestWebhookDeliveryDAORead:
    """Tests for webhook delivery read operations."""

    @pytest.mark.asyncio
    async def test_get_by_endpoint(self, db_session, test_org):
        """Test listing deliveries for an endpoint."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        await WebhookDeliveryFactory.create_successful(db_session, endpoint=endpoint)
        await WebhookDeliveryFactory.create_failed(db_session, endpoint=endpoint)
        await WebhookDeliveryFactory.create(db_session, endpoint=endpoint)

        dao = WebhookDeliveryDAO(db_session)
        deliveries = await dao.get_by_endpoint(endpoint.id)

        assert len(deliveries) == 3

    @pytest.mark.asyncio
    async def test_get_by_endpoint_pagination(self, db_session, test_org):
        """Test pagination for delivery listing."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        for i in range(5):
            await WebhookDeliveryFactory.create(db_session, endpoint=endpoint)

        dao = WebhookDeliveryDAO(db_session)

        page1 = await dao.get_by_endpoint(endpoint.id, limit=2, offset=0)
        page2 = await dao.get_by_endpoint(endpoint.id, limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2


class TestWebhookDeliveryDAORetry:
    """Tests for retry-related operations."""

    @pytest.mark.asyncio
    async def test_get_pending_retries(self, db_session, test_org):
        """Test finding deliveries needing retry."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        # Create pending retry
        await WebhookDeliveryFactory.create_pending_retry(
            db_session, endpoint=endpoint
        )

        # Create successful delivery (should not be retried)
        await WebhookDeliveryFactory.create_successful(db_session, endpoint=endpoint)

        dao = WebhookDeliveryDAO(db_session)
        pending = await dao.get_pending_retries()

        assert len(pending) == 1
        assert pending[0].delivered is False

    @pytest.mark.asyncio
    async def test_record_attempt_success(self, db_session, test_org):
        """Test recording a successful delivery attempt."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )
        delivery = await WebhookDeliveryFactory.create(db_session, endpoint=endpoint)

        dao = WebhookDeliveryDAO(db_session)
        updated = await dao.record_attempt(
            delivery_id=delivery.id,
            response_status=200,
            response_headers={"Content-Type": "application/json"},
            response_body='{"ok": true}',
            delivered=True,
            duration_ms=150,
        )

        assert updated.delivered is True
        assert updated.response_status == 200
        assert updated.duration_ms == 150
        assert updated.delivered_at is not None
        assert updated.next_retry_at is None

    @pytest.mark.asyncio
    async def test_record_attempt_failure_with_retry(self, db_session, test_org):
        """Test recording a failed attempt schedules retry."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )
        delivery = await WebhookDeliveryFactory.create(
            db_session, endpoint=endpoint, attempt_count=0
        )

        dao = WebhookDeliveryDAO(db_session)
        updated = await dao.record_attempt(
            delivery_id=delivery.id,
            response_status=500,
            response_headers={},
            response_body="Internal Server Error",
            delivered=False,
            duration_ms=5000,
            error_message="HTTP 500",
        )

        assert updated.delivered is False
        assert updated.response_status == 500
        assert updated.error_message == "HTTP 500"
        assert updated.attempt_count == 1
        assert updated.next_retry_at is not None


class TestWebhookDeliveryDAOStats:
    """Tests for delivery statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, db_session, test_org):
        """Test getting delivery statistics."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        # Create mixed deliveries
        await WebhookDeliveryFactory.create_successful(db_session, endpoint=endpoint)
        await WebhookDeliveryFactory.create_successful(db_session, endpoint=endpoint)
        await WebhookDeliveryFactory.create_failed(db_session, endpoint=endpoint)

        dao = WebhookDeliveryDAO(db_session)
        since = datetime.utcnow() - timedelta(days=1)
        stats = await dao.get_stats(endpoint.id, since)

        assert stats["total_deliveries"] == 3
        assert stats["successful_deliveries"] == 2
        assert stats["failed_deliveries"] == 1
        assert stats["success_rate"] == pytest.approx(66.67, rel=0.1)


class TestWebhookDeliveryDAOCleanup:
    """Tests for delivery cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_old_deliveries(self, db_session, test_org):
        """Test cleaning up old delivery records."""
        endpoint = await WebhookEndpointFactory.create(
            db_session, organization=test_org
        )

        # Create old delivery
        old_delivery = await WebhookDeliveryFactory.create(
            db_session, endpoint=endpoint
        )
        # Manually set old timestamp
        old_delivery.triggered_at = datetime.utcnow() - timedelta(days=60)
        await db_session.commit()

        # Create recent delivery
        await WebhookDeliveryFactory.create(db_session, endpoint=endpoint)

        dao = WebhookDeliveryDAO(db_session)
        deleted_count = await dao.cleanup_old_deliveries(days_to_keep=30)

        assert deleted_count == 1

        # Verify recent delivery still exists
        remaining = await dao.get_by_endpoint(endpoint.id)
        assert len(remaining) == 1
