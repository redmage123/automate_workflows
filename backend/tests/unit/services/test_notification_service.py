"""
Unit tests for NotificationService.

WHAT: Tests notification orchestration across channels.

WHY: Ensures notifications are sent for platform events
with correct formatting.

HOW: Uses mocked SlackService to verify notification calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.notification_service import NotificationService
from app.services.slack_service import SlackService
from app.models.ticket import (
    Ticket,
    TicketComment,
    TicketStatus,
    TicketPriority,
    TicketCategory,
)


class TestNotificationService:
    """Tests for NotificationService class."""

    @pytest.fixture
    def mock_slack_service(self):
        """Create a mocked SlackService."""
        mock = MagicMock(spec=SlackService)
        mock.send_message_safe = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def notification_service(self, mock_slack_service):
        """Create NotificationService with mocked Slack."""
        return NotificationService(
            slack_service=mock_slack_service,
            base_url="https://app.example.com",
        )

    @pytest.fixture
    def sample_ticket(self):
        """Create a sample ticket for testing."""
        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.subject = "Test ticket subject"
        ticket.description = "Test description"
        ticket.status = TicketStatus.OPEN
        ticket.priority = TicketPriority.HIGH
        ticket.category = TicketCategory.BUG
        ticket.org_id = 1
        ticket.created_at = datetime.utcnow()
        return ticket

    @pytest.fixture
    def sample_comment(self):
        """Create a sample comment for testing."""
        comment = MagicMock(spec=TicketComment)
        comment.id = 456
        comment.ticket_id = 123
        comment.content = "This is a test comment"
        comment.is_internal = False
        comment.created_at = datetime.utcnow()
        return comment


class TestTicketNotifications(TestNotificationService):
    """Tests for ticket-related notifications."""

    @pytest.mark.asyncio
    async def test_notify_ticket_created(
        self, notification_service, mock_slack_service, sample_ticket
    ):
        """Test ticket created notification is sent."""
        result = await notification_service.notify_ticket_created(
            ticket=sample_ticket,
            org_name="Acme Inc",
            created_by_name="John Doe",
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()

        # Verify message content
        call_args = mock_slack_service.send_message_safe.call_args
        text = call_args[0][0]
        blocks = call_args[0][1]

        assert "123" in text
        assert sample_ticket.subject in text
        assert len(blocks) >= 4

    @pytest.mark.asyncio
    async def test_notify_ticket_created_includes_url(
        self, notification_service, mock_slack_service, sample_ticket
    ):
        """Test ticket notification includes correct URL."""
        await notification_service.notify_ticket_created(
            ticket=sample_ticket,
            org_name="Acme Inc",
            created_by_name="John Doe",
        )

        call_args = mock_slack_service.send_message_safe.call_args
        blocks = call_args[0][1]

        # Find the actions block with URL
        actions_block = next(
            (b for b in blocks if b.get("type") == "actions"),
            None
        )
        assert actions_block is not None
        assert "https://app.example.com/tickets/123" in str(actions_block)

    @pytest.mark.asyncio
    async def test_notify_sla_warning(
        self, notification_service, mock_slack_service, sample_ticket
    ):
        """Test SLA warning notification is sent."""
        result = await notification_service.notify_sla_warning(
            ticket=sample_ticket,
            sla_type="response",
            time_remaining="2 hours",
            assigned_to_name="Jane Doe",
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()

        call_args = mock_slack_service.send_message_safe.call_args
        text = call_args[0][0]

        assert "response" in text.lower()
        assert "Warning" in text or "warning" in text.lower()

    @pytest.mark.asyncio
    async def test_notify_sla_breach(
        self, notification_service, mock_slack_service, sample_ticket
    ):
        """Test SLA breach notification is sent."""
        result = await notification_service.notify_sla_breach(
            ticket=sample_ticket,
            sla_type="resolution",
            assigned_to_name=None,  # Unassigned
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()

        call_args = mock_slack_service.send_message_safe.call_args
        text = call_args[0][0]

        assert "BREACH" in text.upper()
        assert "resolution" in text.lower()

    @pytest.mark.asyncio
    async def test_notify_ticket_assigned(
        self, notification_service, mock_slack_service, sample_ticket
    ):
        """Test ticket assignment notification is sent."""
        result = await notification_service.notify_ticket_assigned(
            ticket=sample_ticket,
            assigned_to_name="Jane Doe",
            assigned_by_name="Admin User",
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()

        call_args = mock_slack_service.send_message_safe.call_args
        text = call_args[0][0]

        assert "Jane Doe" in text
        assert "assigned" in text.lower()

    @pytest.mark.asyncio
    async def test_notify_comment_added(
        self, notification_service, mock_slack_service, sample_ticket, sample_comment
    ):
        """Test comment notification is sent."""
        result = await notification_service.notify_comment_added(
            ticket=sample_ticket,
            comment=sample_comment,
            commenter_name="John Doe",
            is_internal=False,
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_comment_skips_internal_notes(
        self, notification_service, mock_slack_service, sample_ticket, sample_comment
    ):
        """Test internal notes don't trigger notifications."""
        result = await notification_service.notify_comment_added(
            ticket=sample_ticket,
            comment=sample_comment,
            commenter_name="Admin",
            is_internal=True,
        )

        assert result is False
        mock_slack_service.send_message_safe.assert_not_called()


class TestPaymentNotifications(TestNotificationService):
    """Tests for payment-related notifications."""

    @pytest.mark.asyncio
    async def test_notify_payment_received(
        self, notification_service, mock_slack_service
    ):
        """Test payment notification is sent."""
        result = await notification_service.notify_payment_received(
            amount=499.99,
            currency="USD",
            invoice_id=1001,
            org_name="Acme Inc",
            payment_method="card",
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()

        call_args = mock_slack_service.send_message_safe.call_args
        text = call_args[0][0]

        assert "499.99" in text or "$499.99" in text
        assert "Acme Inc" in text

    @pytest.mark.asyncio
    async def test_notify_payment_includes_invoice_url(
        self, notification_service, mock_slack_service
    ):
        """Test payment notification includes invoice URL."""
        await notification_service.notify_payment_received(
            amount=100.00,
            currency="USD",
            invoice_id=2002,
            org_name="Test Corp",
            payment_method="bank_transfer",
        )

        call_args = mock_slack_service.send_message_safe.call_args
        blocks = call_args[0][1]

        # Find URL in actions block
        actions_block = next(
            (b for b in blocks if b.get("type") == "actions"),
            None
        )
        assert actions_block is not None
        assert "https://app.example.com/invoices/2002" in str(actions_block)


class TestProposalNotifications(TestNotificationService):
    """Tests for proposal-related notifications."""

    @pytest.mark.asyncio
    async def test_notify_proposal_sent(
        self, notification_service, mock_slack_service
    ):
        """Test proposal sent notification is sent."""
        result = await notification_service.notify_proposal_sent(
            proposal_id=42,
            project_name="Website Redesign",
            org_name="Client Corp",
            total_amount=15000.00,
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()

        call_args = mock_slack_service.send_message_safe.call_args
        text = call_args[0][0]

        assert "42" in text
        assert "sent" in text.lower()

    @pytest.mark.asyncio
    async def test_notify_proposal_approved(
        self, notification_service, mock_slack_service
    ):
        """Test proposal approved notification is sent."""
        result = await notification_service.notify_proposal_approved(
            proposal_id=42,
            project_name="Website Redesign",
            org_name="Client Corp",
            total_amount=15000.00,
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()

        call_args = mock_slack_service.send_message_safe.call_args
        text = call_args[0][0]

        assert "approved" in text.lower()

    @pytest.mark.asyncio
    async def test_notify_proposal_rejected(
        self, notification_service, mock_slack_service
    ):
        """Test proposal rejected notification is sent."""
        result = await notification_service.notify_proposal_rejected(
            proposal_id=42,
            project_name="Website Redesign",
            org_name="Client Corp",
            total_amount=15000.00,
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()

        call_args = mock_slack_service.send_message_safe.call_args
        text = call_args[0][0]

        assert "rejected" in text.lower()


class TestOrganizationNotifications(TestNotificationService):
    """Tests for organization-related notifications."""

    @pytest.mark.asyncio
    async def test_notify_new_client_signup(
        self, notification_service, mock_slack_service
    ):
        """Test new client notification is sent."""
        result = await notification_service.notify_new_client_signup(
            org_name="New Client Inc",
            contact_email="contact@newclient.com",
            plan_name="Professional",
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()

        call_args = mock_slack_service.send_message_safe.call_args
        text = call_args[0][0]

        assert "New Client Inc" in text

    @pytest.mark.asyncio
    async def test_notify_new_client_without_plan(
        self, notification_service, mock_slack_service
    ):
        """Test new client notification works without plan."""
        result = await notification_service.notify_new_client_signup(
            org_name="Free User Inc",
            contact_email="free@user.com",
            plan_name=None,
        )

        assert result is True
        mock_slack_service.send_message_safe.assert_called_once()


class TestNotificationURLBuilding(TestNotificationService):
    """Tests for URL building functions."""

    def test_build_ticket_url(self, notification_service):
        """Test ticket URL building."""
        url = notification_service._build_ticket_url(123)
        assert url == "https://app.example.com/tickets/123"

    def test_build_invoice_url(self, notification_service):
        """Test invoice URL building."""
        url = notification_service._build_invoice_url(456)
        assert url == "https://app.example.com/invoices/456"

    def test_build_proposal_url(self, notification_service):
        """Test proposal URL building."""
        url = notification_service._build_proposal_url(789)
        assert url == "https://app.example.com/proposals/789"


class TestNotificationServiceErrorHandling(TestNotificationService):
    """Tests for error handling in NotificationService."""

    @pytest.mark.asyncio
    async def test_slack_failure_returns_false(
        self, notification_service, mock_slack_service, sample_ticket
    ):
        """Test that Slack failures return False without raising."""
        mock_slack_service.send_message_safe = AsyncMock(return_value=False)

        result = await notification_service.notify_ticket_created(
            ticket=sample_ticket,
            org_name="Test Org",
            created_by_name="User",
        )

        assert result is False
