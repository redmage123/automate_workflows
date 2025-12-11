"""
Unit tests for SlackService.

WHAT: Tests Slack webhook integration.

WHY: Ensures notifications are sent correctly and errors
are handled gracefully.

HOW: Uses mocked HTTP client to verify webhook calls.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.slack_service import (
    SlackService,
    build_header_block,
    build_section_block,
    build_fields_block,
    build_context_block,
    build_divider_block,
    build_actions_block,
    build_ticket_created_message,
    build_sla_warning_message,
    build_sla_breach_message,
    build_payment_received_message,
    build_proposal_status_message,
)
from app.core.exceptions import SlackNotificationError


class TestSlackService:
    """Tests for SlackService class."""

    @pytest.fixture
    def slack_service(self):
        """Create SlackService with test configuration."""
        return SlackService(
            webhook_url="https://hooks.slack.com/services/test/test/test",
            enabled=True,
        )

    @pytest.fixture
    def disabled_service(self):
        """Create disabled SlackService."""
        return SlackService(
            webhook_url="https://hooks.slack.com/services/test/test/test",
            enabled=False,
        )

    @pytest.mark.asyncio
    async def test_send_message_success(self, slack_service):
        """Test successful message sending."""
        with patch("app.services.slack_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "ok"
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await slack_service.send_message("Test message")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_message_disabled(self, disabled_service):
        """Test message not sent when disabled."""
        result = await disabled_service.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_no_webhook_url(self):
        """Test message not sent when no webhook URL."""
        service = SlackService(webhook_url=None, enabled=True)
        result = await service.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_with_blocks(self, slack_service):
        """Test message sending with Block Kit blocks."""
        blocks = [
            build_header_block("Test Header"),
            build_section_block("Test content"),
        ]

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "ok"
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            result = await slack_service.send_message("Test", blocks=blocks)

            assert result is True
            # Verify blocks were included in payload
            call_args = mock_post.call_args
            assert "blocks" in call_args.kwargs["json"]
            assert len(call_args.kwargs["json"]["blocks"]) == 2

    @pytest.mark.asyncio
    async def test_send_message_error_response(self, slack_service):
        """Test error handling for non-200 response."""
        with patch("app.services.slack_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "invalid_payload"
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(SlackNotificationError):
                await slack_service.send_message("Test message")

    @pytest.mark.asyncio
    async def test_send_message_timeout(self, slack_service):
        """Test error handling for timeout."""
        import httpx

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            with pytest.raises(SlackNotificationError) as exc_info:
                await slack_service.send_message("Test message")

            assert "timed out" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_send_message_connection_error(self, slack_service):
        """Test error handling for connection error."""
        import httpx

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )

            with pytest.raises(SlackNotificationError) as exc_info:
                await slack_service.send_message("Test message")

            assert "Failed to connect" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_send_message_safe_success(self, slack_service):
        """Test safe message sending succeeds."""
        with patch("app.services.slack_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "ok"
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await slack_service.send_message_safe("Test message")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_message_safe_catches_errors(self, slack_service):
        """Test safe message sending catches errors."""
        import httpx

        with patch("app.services.slack_service.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            # Should not raise, returns False
            result = await slack_service.send_message_safe("Test message")

            assert result is False


class TestBlockKitBuilders:
    """Tests for Block Kit builder functions."""

    def test_build_header_block(self):
        """Test header block creation."""
        block = build_header_block("Test Header")
        assert block["type"] == "header"
        assert block["text"]["type"] == "plain_text"
        assert block["text"]["text"] == "Test Header"

    def test_build_header_block_truncates_long_text(self):
        """Test header block truncates text over 150 chars."""
        long_text = "x" * 200
        block = build_header_block(long_text)
        assert len(block["text"]["text"]) == 150

    def test_build_section_block(self):
        """Test section block creation."""
        block = build_section_block("Test content")
        assert block["type"] == "section"
        assert block["text"]["type"] == "mrkdwn"
        assert block["text"]["text"] == "Test content"

    def test_build_section_block_with_fields(self):
        """Test section block with fields."""
        fields = [
            {"label": "Status", "value": "Open"},
            {"label": "Priority", "value": "High"},
        ]
        block = build_section_block("Content", fields=fields)
        assert "fields" in block
        assert len(block["fields"]) == 2
        assert "*Status:*" in block["fields"][0]["text"]

    def test_build_fields_block(self):
        """Test fields-only section block."""
        fields = [
            {"label": "Key1", "value": "Value1"},
            {"label": "Key2", "value": "Value2"},
        ]
        block = build_fields_block(fields)
        assert block["type"] == "section"
        assert "text" not in block
        assert len(block["fields"]) == 2

    def test_build_context_block(self):
        """Test context block creation."""
        block = build_context_block("Context text")
        assert block["type"] == "context"
        assert block["elements"][0]["text"] == "Context text"

    def test_build_divider_block(self):
        """Test divider block creation."""
        block = build_divider_block()
        assert block["type"] == "divider"

    def test_build_actions_block(self):
        """Test actions block with buttons."""
        buttons = [
            {"text": "View", "url": "https://example.com"},
            {"text": "Edit", "url": "https://example.com/edit"},
        ]
        block = build_actions_block(buttons)
        assert block["type"] == "actions"
        assert len(block["elements"]) == 2
        assert block["elements"][0]["text"]["text"] == "View"
        assert block["elements"][0]["url"] == "https://example.com"


class TestMessageTemplates:
    """Tests for pre-built message templates."""

    def test_build_ticket_created_message(self):
        """Test ticket created message template."""
        text, blocks = build_ticket_created_message(
            ticket_id=123,
            subject="Test ticket",
            priority="high",
            category="bug",
            created_by="John Doe",
            org_name="Acme Inc",
            ticket_url="https://app.example.com/tickets/123",
        )

        assert "123" in text
        assert "Test ticket" in text
        assert len(blocks) == 6  # header, section, fields, context, divider, actions
        assert blocks[0]["type"] == "header"

    def test_build_ticket_created_message_priority_emoji(self):
        """Test priority emoji mapping in ticket message."""
        text, blocks = build_ticket_created_message(
            ticket_id=1,
            subject="Urgent issue",
            priority="urgent",
            category="bug",
            created_by="User",
            org_name="Org",
            ticket_url="https://example.com",
        )

        # Check header contains emoji for urgent priority
        header_text = blocks[0]["text"]["text"]
        assert "" in header_text

    def test_build_sla_warning_message(self):
        """Test SLA warning message template."""
        text, blocks = build_sla_warning_message(
            ticket_id=123,
            subject="Test ticket",
            priority="high",
            sla_type="response",
            time_remaining="2 hours",
            assigned_to="Jane Doe",
            ticket_url="https://app.example.com/tickets/123",
        )

        assert "Warning" in text or "warning" in text.lower()
        assert "response" in text.lower()
        assert len(blocks) >= 5

    def test_build_sla_breach_message(self):
        """Test SLA breach message template."""
        text, blocks = build_sla_breach_message(
            ticket_id=123,
            subject="Test ticket",
            priority="urgent",
            sla_type="resolution",
            assigned_to=None,  # Unassigned
            ticket_url="https://app.example.com/tickets/123",
        )

        assert "BREACH" in text.upper()
        # Check for unassigned handling
        assert len(blocks) >= 5

    def test_build_payment_received_message(self):
        """Test payment received message template."""
        text, blocks = build_payment_received_message(
            amount=499.99,
            currency="USD",
            invoice_id=1001,
            org_name="Acme Inc",
            payment_method="card",
            invoice_url="https://app.example.com/invoices/1001",
        )

        assert "499.99" in text or "$499.99" in text
        assert "Acme Inc" in text
        assert len(blocks) >= 4

    def test_build_proposal_status_message(self):
        """Test proposal status message template."""
        text, blocks = build_proposal_status_message(
            proposal_id=42,
            project_name="Website Redesign",
            org_name="Client Corp",
            status="approved",
            total_amount=15000.00,
            proposal_url="https://app.example.com/proposals/42",
        )

        assert "42" in text
        assert "approved" in text.lower()
        # Check for approval emoji in header
        header_text = blocks[0]["text"]["text"]
        assert "" in header_text or "Approved" in header_text
