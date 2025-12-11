"""
Slack Webhook Integration Service.

WHAT: Sends messages to Slack channels via incoming webhooks.

WHY: Real-time team visibility into platform events (tickets, proposals,
payments, SLA breaches) without requiring manual monitoring.

HOW: Uses Slack's Incoming Webhooks API to post messages with Block Kit
formatting for rich, structured notifications.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import SlackNotificationError

logger = logging.getLogger(__name__)


class SlackService:
    """
    Service for sending messages to Slack via webhooks.

    WHAT: Handles communication with Slack's Incoming Webhooks API.

    WHY: Centralizes Slack integration logic including error handling,
    retry logic, and message formatting.

    HOW: Uses httpx async client to POST messages to the webhook URL.
    Messages can be plain text or Block Kit formatted for rich display.

    Attributes:
        webhook_url: Slack Incoming Webhook URL
        enabled: Whether Slack notifications are enabled
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        enabled: Optional[bool] = None,
        timeout: float = 10.0,
    ):
        """
        Initialize SlackService.

        WHAT: Sets up the service with webhook configuration.

        WHY: Allows injection of config for testing while defaulting
        to environment settings in production.

        Args:
            webhook_url: Slack webhook URL (defaults to settings)
            enabled: Whether notifications are enabled (defaults to settings)
            timeout: HTTP request timeout in seconds
        """
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL
        self.enabled = enabled if enabled is not None else settings.SLACK_WEBHOOK_ENABLED
        self.timeout = timeout

    async def send_message(
        self,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Send a message to Slack.

        WHAT: Posts a message to the configured Slack webhook.

        WHY: Enables real-time notifications to team channels for
        important platform events.

        HOW: Constructs a payload with text and optional Block Kit
        blocks, then POSTs to the webhook URL.

        Args:
            text: Plain text message (also used as fallback for blocks)
            blocks: Optional Block Kit blocks for rich formatting
            attachments: Optional legacy attachments

        Returns:
            True if message was sent successfully

        Raises:
            SlackNotificationError: If the webhook call fails
        """
        if not self.enabled:
            logger.debug("Slack notifications disabled, skipping message")
            return False

        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False

        payload: Dict[str, Any] = {"text": text}

        if blocks:
            payload["blocks"] = blocks

        if attachments:
            payload["attachments"] = attachments

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                )

                # Slack returns "ok" for successful messages
                if response.status_code == 200 and response.text == "ok":
                    logger.info("Slack message sent successfully")
                    return True

                # Handle error responses
                logger.error(
                    f"Slack webhook returned error: {response.status_code} - {response.text}"
                )
                raise SlackNotificationError(
                    message="Slack webhook returned an error",
                    status_code=response.status_code,
                    response_text=response.text,
                )

        except httpx.TimeoutException as e:
            logger.error(f"Slack webhook timeout: {e}")
            raise SlackNotificationError(
                message="Slack webhook request timed out",
                timeout=self.timeout,
            ) from e

        except httpx.RequestError as e:
            logger.error(f"Slack webhook request error: {e}")
            raise SlackNotificationError(
                message="Failed to connect to Slack webhook",
                error=str(e),
            ) from e

    async def send_message_safe(
        self,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Send a message to Slack without raising exceptions.

        WHAT: Fire-and-forget message sending that logs but doesn't fail.

        WHY: Notification failures should not block main operations.
        This method is for cases where notifications are supplementary.

        HOW: Wraps send_message and catches all exceptions.

        Args:
            text: Plain text message
            blocks: Optional Block Kit blocks
            attachments: Optional legacy attachments

        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            return await self.send_message(text, blocks, attachments)
        except SlackNotificationError as e:
            logger.error(f"Failed to send Slack notification: {e.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Slack notification: {e}")
            return False


# ============================================================================
# Block Kit Builders
# ============================================================================


def build_header_block(text: str) -> Dict[str, Any]:
    """
    Build a header block for Slack message.

    WHAT: Creates a header block with large, bold text.

    WHY: Headers visually distinguish notification types and
    draw attention to important messages.

    Args:
        text: Header text (max 150 chars)

    Returns:
        Block Kit header block
    """
    return {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": text[:150],  # Slack header limit
            "emoji": True,
        },
    }


def build_section_block(
    text: str,
    fields: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Build a section block for Slack message.

    WHAT: Creates a text section with optional key-value fields.

    WHY: Sections provide the main content of notifications with
    support for markdown formatting.

    Args:
        text: Main section text (markdown supported)
        fields: Optional list of field dictionaries

    Returns:
        Block Kit section block
    """
    block: Dict[str, Any] = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": text,
        },
    }

    if fields:
        block["fields"] = [
            {"type": "mrkdwn", "text": f"*{f['label']}:*\n{f['value']}"}
            for f in fields
        ]

    return block


def build_fields_block(fields: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Build a section block with only fields (no text).

    WHAT: Creates a two-column layout of key-value pairs.

    WHY: Displays structured data compactly (priority, status, etc.).

    Args:
        fields: List of dicts with 'label' and 'value' keys

    Returns:
        Block Kit section block with fields
    """
    return {
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*{f['label']}:*\n{f['value']}"}
            for f in fields
        ],
    }


def build_context_block(text: str) -> Dict[str, Any]:
    """
    Build a context block for Slack message.

    WHAT: Creates small, muted text for metadata.

    WHY: Provides additional context (timestamps, IDs) without
    cluttering the main message.

    Args:
        text: Context text

    Returns:
        Block Kit context block
    """
    return {
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": text},
        ],
    }


def build_divider_block() -> Dict[str, Any]:
    """
    Build a divider block.

    WHAT: Creates a horizontal line between sections.

    WHY: Visually separates different parts of a notification.

    Returns:
        Block Kit divider block
    """
    return {"type": "divider"}


def build_actions_block(buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Build an actions block with buttons.

    WHAT: Creates clickable buttons for user actions.

    WHY: Direct links to view/action items (View Ticket, etc.)
    improve workflow efficiency.

    Args:
        buttons: List of dicts with 'text' and 'url' keys

    Returns:
        Block Kit actions block
    """
    return {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": btn["text"], "emoji": True},
                "url": btn["url"],
                "action_id": f"button_{i}",
            }
            for i, btn in enumerate(buttons)
        ],
    }


# ============================================================================
# Pre-built Message Templates
# ============================================================================


def build_ticket_created_message(
    ticket_id: int,
    subject: str,
    priority: str,
    category: str,
    created_by: str,
    org_name: str,
    ticket_url: str,
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Build Slack message for new ticket creation.

    WHAT: Formats a ticket creation notification.

    WHY: Immediate visibility for support team when tickets are created.

    Args:
        ticket_id: Ticket ID
        subject: Ticket subject line
        priority: Ticket priority (low, medium, high, urgent)
        category: Ticket category (bug, feature, support, etc.)
        created_by: User who created the ticket
        org_name: Organization name
        ticket_url: Direct link to ticket

    Returns:
        Tuple of (fallback text, Block Kit blocks)
    """
    # Priority emoji mapping
    priority_emoji = {
        "low": "",
        "medium": "",
        "high": "",
        "urgent": "",
    }.get(priority.lower(), "")

    text = f"New ticket #{ticket_id}: {subject}"

    blocks = [
        build_header_block(f"{priority_emoji} New Support Ticket"),
        build_section_block(f"*{subject}*"),
        build_fields_block([
            {"label": "Ticket", "value": f"#{ticket_id}"},
            {"label": "Priority", "value": priority.capitalize()},
            {"label": "Category", "value": category.capitalize()},
            {"label": "Organization", "value": org_name},
        ]),
        build_context_block(f"Created by {created_by}"),
        build_divider_block(),
        build_actions_block([{"text": "View Ticket", "url": ticket_url}]),
    ]

    return text, blocks


def build_sla_warning_message(
    ticket_id: int,
    subject: str,
    priority: str,
    sla_type: str,  # "response" or "resolution"
    time_remaining: str,
    assigned_to: Optional[str],
    ticket_url: str,
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Build Slack message for SLA warning.

    WHAT: Formats an SLA warning notification (75% threshold).

    WHY: Proactive alerts help prevent SLA breaches.

    Args:
        ticket_id: Ticket ID
        subject: Ticket subject
        priority: Ticket priority
        sla_type: Type of SLA ("response" or "resolution")
        time_remaining: Human-readable time remaining
        assigned_to: Assigned user (if any)
        ticket_url: Direct link to ticket

    Returns:
        Tuple of (fallback text, Block Kit blocks)
    """
    text = f"SLA Warning: Ticket #{ticket_id} - {sla_type} SLA approaching"

    assignee = assigned_to or "Unassigned"

    blocks = [
        build_header_block(f" SLA Warning"),
        build_section_block(
            f"Ticket *#{ticket_id}* {sla_type} SLA is approaching the deadline."
        ),
        build_fields_block([
            {"label": "Subject", "value": subject},
            {"label": "Priority", "value": priority.capitalize()},
            {"label": "Time Remaining", "value": time_remaining},
            {"label": "Assigned To", "value": assignee},
        ]),
        build_divider_block(),
        build_actions_block([{"text": "View Ticket", "url": ticket_url}]),
    ]

    return text, blocks


def build_sla_breach_message(
    ticket_id: int,
    subject: str,
    priority: str,
    sla_type: str,
    assigned_to: Optional[str],
    ticket_url: str,
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Build Slack message for SLA breach.

    WHAT: Formats an SLA breach notification (100% threshold).

    WHY: Immediate escalation for SLA breaches requiring urgent attention.

    Args:
        ticket_id: Ticket ID
        subject: Ticket subject
        priority: Ticket priority
        sla_type: Type of SLA ("response" or "resolution")
        assigned_to: Assigned user (if any)
        ticket_url: Direct link to ticket

    Returns:
        Tuple of (fallback text, Block Kit blocks)
    """
    text = f"SLA BREACH: Ticket #{ticket_id} - {sla_type} SLA breached!"

    assignee = assigned_to or "Unassigned"

    blocks = [
        build_header_block(f" SLA BREACH"),
        build_section_block(
            f"Ticket *#{ticket_id}* has breached the *{sla_type}* SLA!"
        ),
        build_fields_block([
            {"label": "Subject", "value": subject},
            {"label": "Priority", "value": priority.capitalize()},
            {"label": "SLA Type", "value": sla_type.capitalize()},
            {"label": "Assigned To", "value": assignee},
        ]),
        build_context_block("Immediate attention required!"),
        build_divider_block(),
        build_actions_block([{"text": "View Ticket Now", "url": ticket_url}]),
    ]

    return text, blocks


def build_payment_received_message(
    amount: float,
    currency: str,
    invoice_id: int,
    org_name: str,
    payment_method: str,
    invoice_url: str,
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Build Slack message for payment received.

    WHAT: Formats a payment confirmation notification.

    WHY: Finance team visibility for incoming payments.

    Args:
        amount: Payment amount
        currency: Currency code (USD, etc.)
        invoice_id: Invoice ID
        org_name: Organization name
        payment_method: Payment method (card, bank transfer, etc.)
        invoice_url: Direct link to invoice

    Returns:
        Tuple of (fallback text, Block Kit blocks)
    """
    text = f"Payment received: ${amount:.2f} from {org_name}"

    blocks = [
        build_header_block(f" Payment Received"),
        build_section_block(f"*${amount:,.2f} {currency.upper()}*"),
        build_fields_block([
            {"label": "Organization", "value": org_name},
            {"label": "Invoice", "value": f"#{invoice_id}"},
            {"label": "Method", "value": payment_method},
        ]),
        build_divider_block(),
        build_actions_block([{"text": "View Invoice", "url": invoice_url}]),
    ]

    return text, blocks


def build_proposal_status_message(
    proposal_id: int,
    project_name: str,
    org_name: str,
    status: str,
    total_amount: float,
    proposal_url: str,
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Build Slack message for proposal status change.

    WHAT: Formats a proposal status notification.

    WHY: Sales team visibility for proposal workflow.

    Args:
        proposal_id: Proposal ID
        project_name: Project name
        org_name: Organization name
        status: New status (sent, approved, rejected)
        total_amount: Proposal total
        proposal_url: Direct link to proposal

    Returns:
        Tuple of (fallback text, Block Kit blocks)
    """
    # Status emoji mapping
    status_emoji = {
        "sent": "",
        "approved": "",
        "rejected": "",
        "draft": "",
    }.get(status.lower(), "")

    text = f"Proposal #{proposal_id} {status}: {project_name}"

    blocks = [
        build_header_block(f"{status_emoji} Proposal {status.capitalize()}"),
        build_section_block(f"*{project_name}*"),
        build_fields_block([
            {"label": "Proposal", "value": f"#{proposal_id}"},
            {"label": "Organization", "value": org_name},
            {"label": "Status", "value": status.capitalize()},
            {"label": "Amount", "value": f"${total_amount:,.2f}"},
        ]),
        build_divider_block(),
        build_actions_block([{"text": "View Proposal", "url": proposal_url}]),
    ]

    return text, blocks
