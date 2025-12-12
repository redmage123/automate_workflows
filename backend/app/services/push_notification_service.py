"""
Push Notification Service.

WHAT: Business logic for web push notifications.

WHY: Push notifications enable:
1. Real-time alerts even when app is closed
2. Important event notifications (tickets, payments)
3. Improved user engagement
4. Timely SLA warnings

HOW: Uses pywebpush library for Web Push Protocol:
- VAPID authentication
- End-to-end encryption
- Subscription management
- Batched delivery
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.dao.push_subscription import PushSubscriptionDAO
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


class PushNotificationError(AppException):
    """
    Push notification specific error.

    WHAT: Base error for push notification operations.

    WHY: Provides specific context for push errors.
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        super().__init__(message=message, details=details, status_code=status_code)


class PushNotificationService:
    """
    Service for web push notifications.

    WHAT: Manages push subscriptions and sends notifications.

    WHY: Centralizes push notification logic for:
    - Subscription management
    - Notification delivery
    - Error handling and retry
    - Analytics tracking

    HOW: Uses pywebpush for Web Push Protocol delivery.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize PushNotificationService.

        WHAT: Sets up DAO and VAPID credentials.

        Args:
            session: Database session
        """
        self.session = session
        self.subscription_dao = PushSubscriptionDAO(session)

        # VAPID credentials for push authentication
        self.vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
        self.vapid_public_key = getattr(settings, "VAPID_PUBLIC_KEY", "")
        self.vapid_claims = {
            "sub": f"mailto:{getattr(settings, 'VAPID_MAILTO', 'admin@example.com')}",
        }

    # =========================================================================
    # Subscription Management
    # =========================================================================

    async def subscribe(
        self,
        user_id: int,
        org_id: int,
        subscription: Dict[str, Any],
        user_agent: Optional[str] = None,
    ) -> PushSubscription:
        """
        Subscribe a user to push notifications.

        WHAT: Creates or updates push subscription.

        WHY: Users need to subscribe to receive pushes.

        Args:
            user_id: User ID
            org_id: Organization ID
            subscription: Web Push subscription JSON from browser
            user_agent: Browser user agent string

        Returns:
            Created/updated subscription

        Raises:
            PushNotificationError: If subscription fails
        """
        try:
            sub = await self.subscription_dao.create_or_update(
                user_id=user_id,
                org_id=org_id,
                subscription=subscription,
                user_agent=user_agent,
            )
            return sub
        except Exception as e:
            logger.error(f"Failed to subscribe user {user_id}: {e}")
            raise PushNotificationError(
                message="Failed to create push subscription",
                details={"user_id": user_id, "error": str(e)},
            )

    async def unsubscribe(
        self,
        endpoint: str,
    ) -> bool:
        """
        Unsubscribe from push notifications.

        WHAT: Removes push subscription by endpoint.

        WHY: User requested to stop notifications.

        Args:
            endpoint: Subscription endpoint URL

        Returns:
            Whether unsubscribe succeeded
        """
        try:
            return await self.subscription_dao.delete_by_endpoint(endpoint)
        except Exception as e:
            logger.error(f"Failed to unsubscribe endpoint: {e}")
            return False

    async def get_user_subscriptions(
        self,
        user_id: int,
    ) -> List[PushSubscription]:
        """
        Get user's active subscriptions.

        WHAT: Lists user's push subscriptions.

        Args:
            user_id: User ID

        Returns:
            List of active subscriptions
        """
        return await self.subscription_dao.get_user_subscriptions(
            user_id=user_id,
            active_only=True,
        )

    # =========================================================================
    # Notification Sending
    # =========================================================================

    async def send_to_user(
        self,
        user_id: int,
        title: str,
        body: str,
        url: Optional[str] = None,
        icon: Optional[str] = None,
        tag: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        actions: Optional[List[Dict[str, str]]] = None,
        require_interaction: bool = False,
    ) -> int:
        """
        Send push notification to a user.

        WHAT: Delivers notification to all user's devices.

        WHY: Notify user about important events.

        Args:
            user_id: Target user ID
            title: Notification title
            body: Notification body text
            url: URL to open on click
            icon: Icon URL
            tag: Notification tag for grouping
            data: Additional data for the notification
            actions: Action buttons
            require_interaction: Whether user must interact

        Returns:
            Number of successfully sent notifications
        """
        subscriptions = await self.subscription_dao.get_user_subscriptions(
            user_id=user_id,
            active_only=True,
        )

        if not subscriptions:
            logger.debug(f"No active subscriptions for user {user_id}")
            return 0

        payload = self._build_payload(
            title=title,
            body=body,
            url=url,
            icon=icon,
            tag=tag,
            data=data,
            actions=actions,
            require_interaction=require_interaction,
        )

        success_count = 0
        for sub in subscriptions:
            success = await self._send_notification(sub, payload)
            if success:
                success_count += 1

        return success_count

    async def send_to_org(
        self,
        org_id: int,
        title: str,
        body: str,
        url: Optional[str] = None,
        icon: Optional[str] = None,
        tag: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> int:
        """
        Send push notification to entire organization.

        WHAT: Broadcasts notification to all org members.

        WHY: Org-wide announcements or alerts.

        Args:
            org_id: Organization ID
            title: Notification title
            body: Notification body text
            url: URL to open on click
            icon: Icon URL
            tag: Notification tag
            data: Additional data
            exclude_user_ids: Users to exclude

        Returns:
            Number of successfully sent notifications
        """
        subscriptions = await self.subscription_dao.get_org_subscriptions(
            org_id=org_id,
            active_only=True,
        )

        if exclude_user_ids:
            subscriptions = [
                s for s in subscriptions
                if s.user_id not in exclude_user_ids
            ]

        if not subscriptions:
            return 0

        payload = self._build_payload(
            title=title,
            body=body,
            url=url,
            icon=icon,
            tag=tag,
            data=data,
        )

        success_count = 0
        for sub in subscriptions:
            success = await self._send_notification(sub, payload)
            if success:
                success_count += 1

        return success_count

    async def send_to_users(
        self,
        user_ids: List[int],
        title: str,
        body: str,
        url: Optional[str] = None,
        icon: Optional[str] = None,
        tag: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Send push notification to multiple users.

        WHAT: Targeted notification to specific users.

        WHY: Group notifications for specific users.

        Args:
            user_ids: List of target user IDs
            title: Notification title
            body: Notification body text
            url: URL to open on click
            icon: Icon URL
            tag: Notification tag
            data: Additional data

        Returns:
            Number of successfully sent notifications
        """
        total_success = 0

        for user_id in user_ids:
            count = await self.send_to_user(
                user_id=user_id,
                title=title,
                body=body,
                url=url,
                icon=icon,
                tag=tag,
                data=data,
            )
            total_success += count

        return total_success

    # =========================================================================
    # Notification Types
    # =========================================================================

    async def notify_ticket_created(
        self,
        user_id: int,
        ticket_id: int,
        ticket_subject: str,
    ) -> int:
        """
        Send notification for new ticket.

        WHAT: Notifies assigned agents about new ticket.

        Args:
            user_id: User to notify
            ticket_id: Ticket ID
            ticket_subject: Ticket subject

        Returns:
            Number sent
        """
        return await self.send_to_user(
            user_id=user_id,
            title="New Ticket",
            body=f"#{ticket_id}: {ticket_subject}",
            url=f"/tickets/{ticket_id}",
            tag=f"ticket-{ticket_id}",
            icon="/icons/ticket-notification.png",
            data={"type": "ticket_created", "ticket_id": ticket_id},
            actions=[
                {"action": "view", "title": "View Ticket"},
            ],
        )

    async def notify_ticket_comment(
        self,
        user_id: int,
        ticket_id: int,
        commenter_name: str,
    ) -> int:
        """
        Send notification for ticket comment.

        WHAT: Notifies ticket participants about new comment.

        Args:
            user_id: User to notify
            ticket_id: Ticket ID
            commenter_name: Name of commenter

        Returns:
            Number sent
        """
        return await self.send_to_user(
            user_id=user_id,
            title="New Comment",
            body=f"{commenter_name} commented on ticket #{ticket_id}",
            url=f"/tickets/{ticket_id}",
            tag=f"ticket-comment-{ticket_id}",
            data={"type": "ticket_comment", "ticket_id": ticket_id},
        )

    async def notify_proposal_received(
        self,
        user_id: int,
        proposal_id: int,
        proposal_title: str,
    ) -> int:
        """
        Send notification for new proposal.

        WHAT: Notifies client about proposal.

        Args:
            user_id: Client user ID
            proposal_id: Proposal ID
            proposal_title: Proposal title

        Returns:
            Number sent
        """
        return await self.send_to_user(
            user_id=user_id,
            title="New Proposal",
            body=f"You have a new proposal: {proposal_title}",
            url=f"/proposals/{proposal_id}",
            tag=f"proposal-{proposal_id}",
            icon="/icons/proposal-notification.png",
            data={"type": "proposal_received", "proposal_id": proposal_id},
            actions=[
                {"action": "view", "title": "View Proposal"},
            ],
            require_interaction=True,
        )

    async def notify_payment_received(
        self,
        user_id: int,
        invoice_id: int,
        amount: str,
    ) -> int:
        """
        Send notification for payment received.

        WHAT: Notifies about successful payment.

        Args:
            user_id: User to notify
            invoice_id: Invoice ID
            amount: Formatted payment amount

        Returns:
            Number sent
        """
        return await self.send_to_user(
            user_id=user_id,
            title="Payment Received",
            body=f"Payment of {amount} received for invoice #{invoice_id}",
            url=f"/invoices/{invoice_id}",
            tag=f"payment-{invoice_id}",
            icon="/icons/payment-notification.png",
            data={"type": "payment_received", "invoice_id": invoice_id},
        )

    async def notify_sla_warning(
        self,
        user_id: int,
        ticket_id: int,
        sla_type: str,
        time_remaining: str,
    ) -> int:
        """
        Send SLA warning notification.

        WHAT: Alerts agents about SLA deadline.

        Args:
            user_id: Agent to notify
            ticket_id: Ticket ID
            sla_type: "response" or "resolution"
            time_remaining: Formatted time remaining

        Returns:
            Number sent
        """
        return await self.send_to_user(
            user_id=user_id,
            title=f"SLA Warning: Ticket #{ticket_id}",
            body=f"{sla_type.title()} SLA due in {time_remaining}",
            url=f"/tickets/{ticket_id}",
            tag=f"sla-warning-{ticket_id}",
            icon="/icons/warning-notification.png",
            data={
                "type": "sla_warning",
                "ticket_id": ticket_id,
                "sla_type": sla_type,
            },
            actions=[
                {"action": "view", "title": "View Ticket"},
            ],
            require_interaction=True,
        )

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _build_payload(
        self,
        title: str,
        body: str,
        url: Optional[str] = None,
        icon: Optional[str] = None,
        tag: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        actions: Optional[List[Dict[str, str]]] = None,
        require_interaction: bool = False,
    ) -> str:
        """
        Build notification payload.

        WHAT: Creates JSON payload for push.

        Args:
            title: Notification title
            body: Notification body
            url: Click URL
            icon: Icon URL
            tag: Notification tag
            data: Additional data
            actions: Action buttons
            require_interaction: Require interaction

        Returns:
            JSON string payload
        """
        payload = {
            "title": title,
            "body": body,
            "icon": icon or "/icons/icon-192x192.png",
            "badge": "/icons/badge-72x72.png",
            "tag": tag or "default",
            "requireInteraction": require_interaction,
            "data": {
                **(data or {}),
                "url": url or "/",
            },
        }

        if actions:
            payload["actions"] = actions

        return json.dumps(payload)

    async def _send_notification(
        self,
        subscription: PushSubscription,
        payload: str,
    ) -> bool:
        """
        Send notification to a subscription.

        WHAT: Delivers push to single subscription.

        HOW: Uses pywebpush library with VAPID auth.

        Args:
            subscription: Target subscription
            payload: JSON payload string

        Returns:
            Whether send succeeded
        """
        # Check if webpush is available
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            logger.warning("pywebpush not installed, using console mode")
            logger.info(f"Push notification (console): {payload}")
            return True

        # Check VAPID credentials
        if not self.vapid_private_key:
            logger.warning("VAPID credentials not configured")
            logger.info(f"Push notification (no credentials): {payload}")
            return True

        try:
            webpush(
                subscription_info=subscription.to_webpush_info(),
                data=payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims,
            )

            # Record success
            await self.subscription_dao.record_success(subscription.id)
            return True

        except WebPushException as e:
            logger.error(f"Push failed for subscription {subscription.id}: {e}")

            # Record failure
            failure_count = await self.subscription_dao.record_failure(subscription.id)

            # Check if subscription is gone (410 Gone)
            if e.response and e.response.status_code == 410:
                await self.subscription_dao.deactivate_by_endpoint(subscription.endpoint)
                logger.info(f"Deactivated expired subscription: {subscription.endpoint}")

            return False

        except Exception as e:
            logger.error(f"Unexpected push error: {e}")
            await self.subscription_dao.record_failure(subscription.id)
            return False
