"""
Notification Service for Platform Events.

WHAT: Orchestrates sending notifications across channels (Slack, email, etc.)
for platform events like ticket creation, SLA breaches, payments, etc.

WHY: Centralizes notification logic to ensure consistent messaging and
easy addition of new notification channels.

HOW: Event-specific methods format data and delegate to channel services
(SlackService, future EmailService). Uses fire-and-forget pattern to
avoid blocking main operations.
"""

import logging
from typing import Optional

from app.core.config import settings
from app.models.ticket import Ticket, TicketComment
from app.services.slack_service import (
    SlackService,
    build_ticket_created_message,
    build_sla_warning_message,
    build_sla_breach_message,
    build_payment_received_message,
    build_proposal_status_message,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Orchestrates notifications across multiple channels.

    WHAT: Handles formatting and sending notifications for platform events.

    WHY: Separates notification logic from business logic, making it easy
    to add new channels (email, SMS) or modify notification content.

    HOW: Event methods receive domain objects, extract relevant data,
    format messages, and send via channel services.

    Attributes:
        slack_service: Service for Slack webhook notifications
        base_url: Base URL for generating action links
    """

    def __init__(
        self,
        slack_service: Optional[SlackService] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize NotificationService.

        WHAT: Sets up notification channels.

        WHY: Allows dependency injection for testing while defaulting
        to production services.

        Args:
            slack_service: SlackService instance (defaults to new instance)
            base_url: Base URL for action links (defaults to settings)
        """
        self.slack_service = slack_service or SlackService()
        self.base_url = base_url or settings.FRONTEND_URL

    def _build_ticket_url(self, ticket_id: int) -> str:
        """
        Build URL to ticket detail page.

        Args:
            ticket_id: Ticket ID

        Returns:
            Full URL to ticket page
        """
        return f"{self.base_url}/tickets/{ticket_id}"

    def _build_invoice_url(self, invoice_id: int) -> str:
        """
        Build URL to invoice detail page.

        Args:
            invoice_id: Invoice ID

        Returns:
            Full URL to invoice page
        """
        return f"{self.base_url}/invoices/{invoice_id}"

    def _build_proposal_url(self, proposal_id: int) -> str:
        """
        Build URL to proposal detail page.

        Args:
            proposal_id: Proposal ID

        Returns:
            Full URL to proposal page
        """
        return f"{self.base_url}/proposals/{proposal_id}"

    # =========================================================================
    # Ticket Notifications
    # =========================================================================

    async def notify_ticket_created(
        self,
        ticket: Ticket,
        org_name: str,
        created_by_name: str,
    ) -> bool:
        """
        Send notification when a new ticket is created.

        WHAT: Notifies support team of new ticket.

        WHY: Immediate visibility for incoming support requests.

        Args:
            ticket: The created Ticket object
            org_name: Organization name
            created_by_name: Name of user who created the ticket

        Returns:
            True if notification was sent successfully
        """
        logger.info(f"Sending ticket created notification for ticket #{ticket.id}")

        text, blocks = build_ticket_created_message(
            ticket_id=ticket.id,
            subject=ticket.subject,
            priority=ticket.priority.value,
            category=ticket.category.value,
            created_by=created_by_name,
            org_name=org_name,
            ticket_url=self._build_ticket_url(ticket.id),
        )

        return await self.slack_service.send_message_safe(text, blocks)

    async def notify_sla_warning(
        self,
        ticket: Ticket,
        sla_type: str,
        time_remaining: str,
        assigned_to_name: Optional[str] = None,
    ) -> bool:
        """
        Send notification when SLA is approaching (75% threshold).

        WHAT: Warns support team that SLA deadline is near.

        WHY: Proactive alerts help prevent SLA breaches.

        Args:
            ticket: The Ticket object
            sla_type: "response" or "resolution"
            time_remaining: Human-readable time remaining
            assigned_to_name: Name of assigned user (if any)

        Returns:
            True if notification was sent successfully
        """
        logger.info(
            f"Sending SLA warning notification for ticket #{ticket.id} ({sla_type})"
        )

        text, blocks = build_sla_warning_message(
            ticket_id=ticket.id,
            subject=ticket.subject,
            priority=ticket.priority.value,
            sla_type=sla_type,
            time_remaining=time_remaining,
            assigned_to=assigned_to_name,
            ticket_url=self._build_ticket_url(ticket.id),
        )

        return await self.slack_service.send_message_safe(text, blocks)

    async def notify_sla_breach(
        self,
        ticket: Ticket,
        sla_type: str,
        assigned_to_name: Optional[str] = None,
    ) -> bool:
        """
        Send notification when SLA is breached (100% threshold).

        WHAT: Alerts support team that SLA has been breached.

        WHY: Immediate escalation for breached SLAs.

        Args:
            ticket: The Ticket object
            sla_type: "response" or "resolution"
            assigned_to_name: Name of assigned user (if any)

        Returns:
            True if notification was sent successfully
        """
        logger.warning(
            f"Sending SLA breach notification for ticket #{ticket.id} ({sla_type})"
        )

        text, blocks = build_sla_breach_message(
            ticket_id=ticket.id,
            subject=ticket.subject,
            priority=ticket.priority.value,
            sla_type=sla_type,
            assigned_to=assigned_to_name,
            ticket_url=self._build_ticket_url(ticket.id),
        )

        return await self.slack_service.send_message_safe(text, blocks)

    async def notify_ticket_assigned(
        self,
        ticket: Ticket,
        assigned_to_name: str,
        assigned_by_name: str,
    ) -> bool:
        """
        Send notification when a ticket is assigned.

        WHAT: Notifies assignee about their new ticket.

        WHY: Ensures assigned users are aware of their responsibilities.

        Args:
            ticket: The Ticket object
            assigned_to_name: Name of newly assigned user
            assigned_by_name: Name of user who made the assignment

        Returns:
            True if notification was sent successfully
        """
        logger.info(
            f"Sending ticket assignment notification for ticket #{ticket.id}"
        )

        text = f"Ticket #{ticket.id} assigned to {assigned_to_name}"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": " Ticket Assigned", "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{ticket.subject}*"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Ticket:*\n#{ticket.id}"},
                    {"type": "mrkdwn", "text": f"*Priority:*\n{ticket.priority.value.capitalize()}"},
                    {"type": "mrkdwn", "text": f"*Assigned To:*\n{assigned_to_name}"},
                    {"type": "mrkdwn", "text": f"*Assigned By:*\n{assigned_by_name}"},
                ],
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Ticket", "emoji": True},
                        "url": self._build_ticket_url(ticket.id),
                        "action_id": "view_ticket",
                    },
                ],
            },
        ]

        return await self.slack_service.send_message_safe(text, blocks)

    async def notify_comment_added(
        self,
        ticket: Ticket,
        comment: TicketComment,
        commenter_name: str,
        is_internal: bool = False,
    ) -> bool:
        """
        Send notification when a comment is added to a ticket.

        WHAT: Notifies about new ticket comments.

        WHY: Keeps team informed of ticket activity.

        Args:
            ticket: The Ticket object
            comment: The TicketComment object
            commenter_name: Name of user who commented
            is_internal: Whether this is an internal note

        Returns:
            True if notification was sent successfully
        """
        # Don't notify for internal notes to avoid spam
        if is_internal:
            logger.debug("Skipping notification for internal note")
            return False

        logger.info(f"Sending comment notification for ticket #{ticket.id}")

        note_type = "Internal Note" if is_internal else "Comment"
        text = f"New {note_type.lower()} on ticket #{ticket.id}"

        # Truncate comment content for preview
        preview = comment.content[:200] + "..." if len(comment.content) > 200 else comment.content

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f" New {note_type}", "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Ticket #{ticket.id}:* {ticket.subject}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f">{preview}"},
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"By {commenter_name}"}],
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Ticket", "emoji": True},
                        "url": self._build_ticket_url(ticket.id),
                        "action_id": "view_ticket",
                    },
                ],
            },
        ]

        return await self.slack_service.send_message_safe(text, blocks)

    # =========================================================================
    # Payment Notifications
    # =========================================================================

    async def notify_payment_received(
        self,
        amount: float,
        currency: str,
        invoice_id: int,
        org_name: str,
        payment_method: str = "card",
    ) -> bool:
        """
        Send notification when a payment is received.

        WHAT: Notifies finance team of incoming payment.

        WHY: Real-time visibility for cash flow tracking.

        Args:
            amount: Payment amount
            currency: Currency code
            invoice_id: Invoice ID
            org_name: Organization name
            payment_method: Payment method used

        Returns:
            True if notification was sent successfully
        """
        logger.info(f"Sending payment notification for invoice #{invoice_id}")

        text, blocks = build_payment_received_message(
            amount=amount,
            currency=currency,
            invoice_id=invoice_id,
            org_name=org_name,
            payment_method=payment_method,
            invoice_url=self._build_invoice_url(invoice_id),
        )

        return await self.slack_service.send_message_safe(text, blocks)

    # =========================================================================
    # Proposal Notifications
    # =========================================================================

    async def notify_proposal_sent(
        self,
        proposal_id: int,
        project_name: str,
        org_name: str,
        total_amount: float,
    ) -> bool:
        """
        Send notification when a proposal is sent to client.

        WHAT: Notifies sales team of proposal submission.

        WHY: Visibility for proposal workflow tracking.

        Args:
            proposal_id: Proposal ID
            project_name: Project name
            org_name: Organization name
            total_amount: Proposal total

        Returns:
            True if notification was sent successfully
        """
        logger.info(f"Sending proposal sent notification for proposal #{proposal_id}")

        text, blocks = build_proposal_status_message(
            proposal_id=proposal_id,
            project_name=project_name,
            org_name=org_name,
            status="sent",
            total_amount=total_amount,
            proposal_url=self._build_proposal_url(proposal_id),
        )

        return await self.slack_service.send_message_safe(text, blocks)

    async def notify_proposal_approved(
        self,
        proposal_id: int,
        project_name: str,
        org_name: str,
        total_amount: float,
    ) -> bool:
        """
        Send notification when a proposal is approved by client.

        WHAT: Notifies sales team of proposal approval.

        WHY: Celebrate wins and trigger project kickoff workflows.

        Args:
            proposal_id: Proposal ID
            project_name: Project name
            org_name: Organization name
            total_amount: Proposal total

        Returns:
            True if notification was sent successfully
        """
        logger.info(f"Sending proposal approved notification for proposal #{proposal_id}")

        text, blocks = build_proposal_status_message(
            proposal_id=proposal_id,
            project_name=project_name,
            org_name=org_name,
            status="approved",
            total_amount=total_amount,
            proposal_url=self._build_proposal_url(proposal_id),
        )

        return await self.slack_service.send_message_safe(text, blocks)

    async def notify_proposal_rejected(
        self,
        proposal_id: int,
        project_name: str,
        org_name: str,
        total_amount: float,
    ) -> bool:
        """
        Send notification when a proposal is rejected by client.

        WHAT: Notifies sales team of proposal rejection.

        WHY: Learn from rejections and update pipeline.

        Args:
            proposal_id: Proposal ID
            project_name: Project name
            org_name: Organization name
            total_amount: Proposal total

        Returns:
            True if notification was sent successfully
        """
        logger.info(f"Sending proposal rejected notification for proposal #{proposal_id}")

        text, blocks = build_proposal_status_message(
            proposal_id=proposal_id,
            project_name=project_name,
            org_name=org_name,
            status="rejected",
            total_amount=total_amount,
            proposal_url=self._build_proposal_url(proposal_id),
        )

        return await self.slack_service.send_message_safe(text, blocks)

    # =========================================================================
    # Organization Notifications
    # =========================================================================

    async def notify_new_client_signup(
        self,
        org_name: str,
        contact_email: str,
        plan_name: Optional[str] = None,
    ) -> bool:
        """
        Send notification when a new client signs up.

        WHAT: Notifies team of new client registration.

        WHY: Celebrate new clients and trigger onboarding workflows.

        Args:
            org_name: Organization name
            contact_email: Primary contact email
            plan_name: Subscription plan (if applicable)

        Returns:
            True if notification was sent successfully
        """
        logger.info(f"Sending new client notification for {org_name}")

        text = f"New client signup: {org_name}"

        fields = [
            {"type": "mrkdwn", "text": f"*Organization:*\n{org_name}"},
            {"type": "mrkdwn", "text": f"*Contact:*\n{contact_email}"},
        ]
        if plan_name:
            fields.append({"type": "mrkdwn", "text": f"*Plan:*\n{plan_name}"})

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": " New Client!", "emoji": True},
            },
            {"type": "section", "fields": fields},
        ]

        return await self.slack_service.send_message_safe(text, blocks)
