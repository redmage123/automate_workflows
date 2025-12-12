"""
Integration Data Access Objects.

WHAT: DAOs for managing external integration data (calendar, webhooks).

WHY: External integrations require:
1. Calendar OAuth token storage and retrieval
2. Webhook endpoint management
3. Delivery tracking and retry logic
4. Multi-tenant isolation

HOW: Uses BaseDAO pattern with specialized queries for:
- Calendar sync state management
- Webhook event filtering
- Delivery retry scheduling
"""

from datetime import datetime, timedelta
from typing import Optional, List, Sequence
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.integration import (
    CalendarIntegration,
    WebhookEndpoint,
    WebhookDelivery,
    CalendarProvider,
)


class CalendarIntegrationDAO(BaseDAO[CalendarIntegration]):
    """
    DAO for calendar integration management.

    WHAT: Handles CRUD and queries for calendar integrations.

    WHY: Calendar integrations require:
    - Per-user, per-provider uniqueness (one Google calendar per user)
    - Token refresh tracking
    - Sync state management
    - Multi-tenant isolation

    HOW: Extends BaseDAO with calendar-specific queries.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize CalendarIntegrationDAO.

        Args:
            session: SQLAlchemy async session
        """
        super().__init__(CalendarIntegration, session)

    async def get_by_user_and_provider(
        self,
        user_id: int,
        provider: str,
    ) -> Optional[CalendarIntegration]:
        """
        Get calendar integration by user and provider.

        WHAT: Retrieves a specific provider integration for a user.

        WHY: Users can have multiple calendar providers (Google + Outlook),
        but only one integration per provider. This enforces that constraint.

        Args:
            user_id: User ID
            provider: Calendar provider (google, outlook, etc.)

        Returns:
            CalendarIntegration if found, None otherwise
        """
        query = select(CalendarIntegration).where(
            and_(
                CalendarIntegration.user_id == user_id,
                CalendarIntegration.provider == provider,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_integrations(
        self,
        user_id: int,
        org_id: int,
    ) -> Sequence[CalendarIntegration]:
        """
        Get all calendar integrations for a user.

        WHAT: Retrieves all calendar integrations for a user.

        WHY: Users may have multiple calendar providers connected.
        Dashboard needs to show all connections and their status.

        Args:
            user_id: User ID
            org_id: Organization ID for tenant isolation

        Returns:
            List of calendar integrations
        """
        query = select(CalendarIntegration).where(
            and_(
                CalendarIntegration.user_id == user_id,
                CalendarIntegration.org_id == org_id,
            )
        ).order_by(CalendarIntegration.provider)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_active_integrations(
        self,
        org_id: int,
    ) -> Sequence[CalendarIntegration]:
        """
        Get all active calendar integrations for an organization.

        WHAT: Retrieves active integrations that need syncing.

        WHY: Background sync job needs all active integrations
        to process calendar updates across the organization.

        Args:
            org_id: Organization ID

        Returns:
            List of active calendar integrations
        """
        query = select(CalendarIntegration).where(
            and_(
                CalendarIntegration.org_id == org_id,
                CalendarIntegration.is_active == True,
                CalendarIntegration.sync_enabled == True,
            )
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_integrations_needing_refresh(
        self,
        buffer_minutes: int = 5,
    ) -> Sequence[CalendarIntegration]:
        """
        Get integrations with tokens expiring soon.

        WHAT: Finds integrations needing token refresh.

        WHY: OAuth tokens expire. We proactively refresh tokens
        before expiration to prevent sync interruptions.

        Args:
            buffer_minutes: Refresh tokens this many minutes before expiry

        Returns:
            List of integrations needing token refresh
        """
        threshold = datetime.utcnow() + timedelta(minutes=buffer_minutes)
        query = select(CalendarIntegration).where(
            and_(
                CalendarIntegration.is_active == True,
                CalendarIntegration.token_expires_at != None,
                CalendarIntegration.token_expires_at <= threshold,
                CalendarIntegration.refresh_token != None,
            )
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_tokens(
        self,
        integration_id: int,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: datetime,
    ) -> Optional[CalendarIntegration]:
        """
        Update OAuth tokens for an integration.

        WHAT: Updates the stored OAuth tokens.

        WHY: OAuth tokens are refreshed periodically. We must
        store the new tokens to maintain calendar access.

        Args:
            integration_id: Integration ID
            access_token: New access token
            refresh_token: New refresh token (if provided)
            expires_at: Token expiration time

        Returns:
            Updated integration
        """
        update_data = {
            "access_token": access_token,
            "token_expires_at": expires_at,
            "error_message": None,
        }
        if refresh_token:
            update_data["refresh_token"] = refresh_token

        stmt = (
            update(CalendarIntegration)
            .where(CalendarIntegration.id == integration_id)
            .values(**update_data)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(integration_id)

    async def update_sync_status(
        self,
        integration_id: int,
        last_sync_at: datetime,
        error_message: Optional[str] = None,
    ) -> Optional[CalendarIntegration]:
        """
        Update sync status after a sync attempt.

        WHAT: Records the last sync time and any errors.

        WHY: Tracking sync status helps users understand
        when their calendar was last updated and diagnose issues.

        Args:
            integration_id: Integration ID
            last_sync_at: When sync occurred
            error_message: Error if sync failed

        Returns:
            Updated integration
        """
        update_data = {
            "last_sync_at": last_sync_at,
            "error_message": error_message,
        }
        if error_message:
            update_data["is_active"] = False

        stmt = (
            update(CalendarIntegration)
            .where(CalendarIntegration.id == integration_id)
            .values(**update_data)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(integration_id)

    async def deactivate(
        self,
        integration_id: int,
        error_message: Optional[str] = None,
    ) -> Optional[CalendarIntegration]:
        """
        Deactivate a calendar integration.

        WHAT: Marks integration as inactive.

        WHY: When OAuth is revoked or errors persist,
        we deactivate to prevent repeated failures.

        Args:
            integration_id: Integration ID
            error_message: Reason for deactivation

        Returns:
            Updated integration
        """
        stmt = (
            update(CalendarIntegration)
            .where(CalendarIntegration.id == integration_id)
            .values(
                is_active=False,
                error_message=error_message,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(integration_id)


class WebhookEndpointDAO(BaseDAO[WebhookEndpoint]):
    """
    DAO for webhook endpoint management.

    WHAT: Handles CRUD and queries for webhook endpoints.

    WHY: Webhook endpoints require:
    - Event subscription filtering
    - Active/inactive state management
    - Delivery statistics tracking
    - Multi-tenant isolation

    HOW: Extends BaseDAO with webhook-specific queries.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize WebhookEndpointDAO.

        Args:
            session: SQLAlchemy async session
        """
        super().__init__(WebhookEndpoint, session)

    async def get_by_org(
        self,
        org_id: int,
        include_inactive: bool = False,
    ) -> Sequence[WebhookEndpoint]:
        """
        Get all webhook endpoints for an organization.

        WHAT: Retrieves webhook endpoints for an org.

        WHY: Organizations need to see and manage their
        configured webhook endpoints.

        Args:
            org_id: Organization ID
            include_inactive: Whether to include inactive endpoints

        Returns:
            List of webhook endpoints
        """
        conditions = [WebhookEndpoint.org_id == org_id]
        if not include_inactive:
            conditions.append(WebhookEndpoint.is_active == True)

        query = select(WebhookEndpoint).where(
            and_(*conditions)
        ).order_by(WebhookEndpoint.name)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_endpoints_for_event(
        self,
        org_id: int,
        event_type: str,
    ) -> Sequence[WebhookEndpoint]:
        """
        Get endpoints subscribed to a specific event type.

        WHAT: Finds endpoints that should receive an event.

        WHY: When an event occurs, we need to know which
        endpoints to deliver it to based on their subscriptions.

        Args:
            org_id: Organization ID
            event_type: Event type (e.g., "ticket.created")

        Returns:
            List of endpoints subscribed to the event
        """
        # Get all active endpoints for the org
        query = select(WebhookEndpoint).where(
            and_(
                WebhookEndpoint.org_id == org_id,
                WebhookEndpoint.is_active == True,
            )
        )
        result = await self.session.execute(query)
        endpoints = result.scalars().all()

        # Filter by event subscription (handles wildcards)
        return [ep for ep in endpoints if ep.subscribes_to(event_type)]

    async def update_stats(
        self,
        endpoint_id: int,
        delivered: bool,
    ) -> Optional[WebhookEndpoint]:
        """
        Update delivery statistics for an endpoint.

        WHAT: Increments delivery counters.

        WHY: Tracking delivery success/failure rates helps
        users identify problematic webhook configurations.

        Args:
            endpoint_id: Endpoint ID
            delivered: Whether delivery succeeded

        Returns:
            Updated endpoint
        """
        endpoint = await self.get_by_id(endpoint_id)
        if not endpoint:
            return None

        update_data = {
            "delivery_count": endpoint.delivery_count + 1,
            "last_triggered_at": datetime.utcnow(),
        }
        if delivered:
            update_data["success_count"] = endpoint.success_count + 1
            update_data["last_success_at"] = datetime.utcnow()
        else:
            update_data["failure_count"] = endpoint.failure_count + 1
            update_data["last_failure_at"] = datetime.utcnow()

        stmt = (
            update(WebhookEndpoint)
            .where(WebhookEndpoint.id == endpoint_id)
            .values(**update_data)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(endpoint_id)

    async def deactivate(
        self,
        endpoint_id: int,
    ) -> Optional[WebhookEndpoint]:
        """
        Deactivate a webhook endpoint.

        WHAT: Marks endpoint as inactive.

        WHY: Users may want to temporarily disable webhooks
        without losing their configuration.

        Args:
            endpoint_id: Endpoint ID

        Returns:
            Updated endpoint
        """
        stmt = (
            update(WebhookEndpoint)
            .where(WebhookEndpoint.id == endpoint_id)
            .values(is_active=False)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(endpoint_id)

    async def activate(
        self,
        endpoint_id: int,
    ) -> Optional[WebhookEndpoint]:
        """
        Activate a webhook endpoint.

        WHAT: Marks endpoint as active.

        WHY: Users may want to re-enable previously disabled webhooks.

        Args:
            endpoint_id: Endpoint ID

        Returns:
            Updated endpoint
        """
        stmt = (
            update(WebhookEndpoint)
            .where(WebhookEndpoint.id == endpoint_id)
            .values(is_active=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(endpoint_id)


class WebhookDeliveryDAO(BaseDAO[WebhookDelivery]):
    """
    DAO for webhook delivery tracking.

    WHAT: Handles CRUD and queries for webhook deliveries.

    WHY: Webhook deliveries require:
    - Delivery attempt logging
    - Retry scheduling
    - Debug information storage
    - Historical tracking

    HOW: Extends BaseDAO with delivery-specific queries.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize WebhookDeliveryDAO.

        Args:
            session: SQLAlchemy async session
        """
        super().__init__(WebhookDelivery, session)

    async def get_by_endpoint(
        self,
        endpoint_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[WebhookDelivery]:
        """
        Get deliveries for a specific endpoint.

        WHAT: Retrieves delivery history for an endpoint.

        WHY: Users need to see delivery attempts for debugging
        and verifying webhook functionality.

        Args:
            endpoint_id: Endpoint ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of deliveries
        """
        query = (
            select(WebhookDelivery)
            .where(WebhookDelivery.endpoint_id == endpoint_id)
            .order_by(WebhookDelivery.triggered_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_pending_retries(
        self,
        max_attempts: int = 3,
    ) -> Sequence[WebhookDelivery]:
        """
        Get deliveries that need to be retried.

        WHAT: Finds failed deliveries ready for retry.

        WHY: Webhooks may fail due to temporary issues.
        Retrying after a delay improves delivery reliability.

        Args:
            max_attempts: Maximum retry attempts

        Returns:
            List of deliveries needing retry
        """
        now = datetime.utcnow()
        query = select(WebhookDelivery).where(
            and_(
                WebhookDelivery.delivered == False,
                WebhookDelivery.attempt_count < max_attempts,
                WebhookDelivery.next_retry_at != None,
                WebhookDelivery.next_retry_at <= now,
            )
        ).order_by(WebhookDelivery.next_retry_at)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def record_attempt(
        self,
        delivery_id: int,
        response_status: Optional[int],
        response_headers: Optional[dict],
        response_body: Optional[str],
        delivered: bool,
        duration_ms: int,
        error_message: Optional[str] = None,
    ) -> Optional[WebhookDelivery]:
        """
        Record a delivery attempt result.

        WHAT: Updates delivery with attempt results.

        WHY: Each attempt's details are needed for:
        - Debugging failed deliveries
        - Calculating retry timing
        - User visibility into webhook issues

        Args:
            delivery_id: Delivery ID
            response_status: HTTP status code
            response_headers: Response headers
            response_body: Response body (truncated)
            delivered: Whether delivery succeeded
            duration_ms: Request duration in milliseconds
            error_message: Error if failed

        Returns:
            Updated delivery
        """
        delivery = await self.get_by_id(delivery_id)
        if not delivery:
            return None

        update_data = {
            "response_status": response_status,
            "response_headers": response_headers,
            "response_body": response_body[:10000] if response_body else None,
            "delivered": delivered,
            "duration_ms": duration_ms,
            "error_message": error_message,
            "attempt_count": delivery.attempt_count + 1,
        }

        if delivered:
            update_data["delivered_at"] = datetime.utcnow()
            update_data["next_retry_at"] = None
        else:
            # Exponential backoff: 1min, 5min, 15min
            backoff_minutes = [1, 5, 15]
            attempt = delivery.attempt_count
            if attempt < len(backoff_minutes):
                update_data["next_retry_at"] = datetime.utcnow() + timedelta(
                    minutes=backoff_minutes[attempt]
                )
            else:
                update_data["next_retry_at"] = None

        stmt = (
            update(WebhookDelivery)
            .where(WebhookDelivery.id == delivery_id)
            .values(**update_data)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(delivery_id)

    async def get_stats(
        self,
        endpoint_id: int,
        since: datetime,
    ) -> dict:
        """
        Get delivery statistics for an endpoint.

        WHAT: Calculates delivery success/failure rates.

        WHY: Statistics help users understand webhook reliability
        and identify problematic endpoints.

        Args:
            endpoint_id: Endpoint ID
            since: Start time for statistics

        Returns:
            Dictionary with delivery stats
        """
        # Total deliveries
        total_query = select(func.count(WebhookDelivery.id)).where(
            and_(
                WebhookDelivery.endpoint_id == endpoint_id,
                WebhookDelivery.triggered_at >= since,
            )
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0

        # Successful deliveries
        success_query = select(func.count(WebhookDelivery.id)).where(
            and_(
                WebhookDelivery.endpoint_id == endpoint_id,
                WebhookDelivery.triggered_at >= since,
                WebhookDelivery.delivered == True,
            )
        )
        success_result = await self.session.execute(success_query)
        success = success_result.scalar() or 0

        # Average duration
        duration_query = select(func.avg(WebhookDelivery.duration_ms)).where(
            and_(
                WebhookDelivery.endpoint_id == endpoint_id,
                WebhookDelivery.triggered_at >= since,
                WebhookDelivery.delivered == True,
            )
        )
        duration_result = await self.session.execute(duration_query)
        avg_duration = duration_result.scalar()

        return {
            "total_deliveries": total,
            "successful_deliveries": success,
            "failed_deliveries": total - success,
            "success_rate": (success / total * 100) if total > 0 else 0,
            "average_duration_ms": round(avg_duration) if avg_duration else None,
        }

    async def cleanup_old_deliveries(
        self,
        days_to_keep: int = 30,
    ) -> int:
        """
        Delete old delivery records.

        WHAT: Removes deliveries older than specified days.

        WHY: Delivery logs can accumulate quickly. Cleanup
        prevents database bloat while keeping recent history.

        Args:
            days_to_keep: Number of days to retain

        Returns:
            Number of deleted records
        """
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        query = select(WebhookDelivery).where(
            WebhookDelivery.triggered_at < cutoff
        )
        result = await self.session.execute(query)
        deliveries = result.scalars().all()
        count = len(deliveries)

        for delivery in deliveries:
            await self.session.delete(delivery)

        await self.session.flush()
        return count
