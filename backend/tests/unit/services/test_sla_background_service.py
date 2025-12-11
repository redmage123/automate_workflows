"""
Unit tests for SLA Background Service.

WHAT: Tests for the SLA breach check job.

WHY: Verifies that:
1. Tickets in warning zone trigger warnings
2. Breached tickets trigger breach notifications
3. Notifications are not duplicated
4. Only active tickets are checked
5. Correct recipients receive notifications

HOW: Uses pytest-asyncio with mocked dependencies.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.sla_background_service import SLABackgroundService
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketCategory
from app.models.user import User, UserRole


class TestSLABackgroundServiceCheckLogic:
    """Tests for SLA check logic."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return SLABackgroundService()

    @pytest.fixture
    def mock_ticket_open(self):
        """Create a mock open ticket."""
        ticket = MagicMock(spec=Ticket)
        ticket.id = 1
        ticket.org_id = 100
        ticket.status = TicketStatus.OPEN
        ticket.priority = TicketPriority.HIGH
        ticket.subject = "Test Ticket"
        ticket.first_response_at = None
        ticket.created_at = datetime.utcnow() - timedelta(hours=3)
        ticket.sla_response_due_at = datetime.utcnow() + timedelta(hours=1)
        ticket.sla_resolution_due_at = datetime.utcnow() + timedelta(hours=21)
        ticket.sla_response_warning_sent_at = None
        ticket.sla_response_breach_sent_at = None
        ticket.sla_resolution_warning_sent_at = None
        ticket.sla_resolution_breach_sent_at = None
        ticket.is_sla_response_breached = False
        ticket.is_sla_resolution_breached = False
        ticket.is_sla_response_warning_zone = True  # 75% elapsed
        ticket.is_sla_resolution_warning_zone = False
        ticket.sla_response_remaining_seconds = 3600  # 1 hour
        ticket.sla_resolution_remaining_seconds = 75600  # 21 hours
        ticket.created_by = MagicMock()
        ticket.created_by.name = "Test Customer"
        ticket.assigned_to = None
        ticket.assigned_to_user_id = None
        return ticket

    @pytest.fixture
    def mock_breached_ticket(self):
        """Create a mock breached ticket."""
        ticket = MagicMock(spec=Ticket)
        ticket.id = 2
        ticket.org_id = 100
        ticket.status = TicketStatus.OPEN
        ticket.priority = TicketPriority.URGENT
        ticket.subject = "Urgent Breached Ticket"
        ticket.first_response_at = None
        ticket.created_at = datetime.utcnow() - timedelta(hours=2)
        ticket.sla_response_due_at = datetime.utcnow() - timedelta(minutes=30)
        ticket.sla_resolution_due_at = datetime.utcnow() + timedelta(hours=2)
        ticket.sla_response_warning_sent_at = datetime.utcnow() - timedelta(hours=1)
        ticket.sla_response_breach_sent_at = None
        ticket.sla_resolution_warning_sent_at = None
        ticket.sla_resolution_breach_sent_at = None
        ticket.is_sla_response_breached = True
        ticket.is_sla_resolution_breached = False
        ticket.is_sla_response_warning_zone = False
        ticket.is_sla_resolution_warning_zone = False
        ticket.sla_response_remaining_seconds = 0
        ticket.sla_resolution_remaining_seconds = 7200
        ticket.created_by = MagicMock()
        ticket.created_by.name = "Urgent Customer"
        ticket.assigned_to = MagicMock()
        ticket.assigned_to.name = "Agent Smith"
        ticket.assigned_to_user_id = 5
        return ticket

    @pytest.fixture
    def mock_user(self):
        """Create mock user recipient."""
        user = MagicMock(spec=User)
        user.id = 10
        user.email = "admin@test.com"
        user.name = "Test Admin"
        user.role = UserRole.ADMIN
        user.is_active = True
        return user

    @pytest.mark.asyncio
    async def test_check_response_sla_warning(self, service, mock_ticket_open):
        """Test that warning is sent when in warning zone."""
        mock_session = AsyncMock()

        with patch.object(
            service, "_send_sla_warning_notification", new_callable=AsyncMock
        ) as mock_send:
            result = await service._check_response_sla(mock_session, mock_ticket_open)

            assert result == "warning"
            mock_send.assert_called_once_with(mock_session, mock_ticket_open, "response")

    @pytest.mark.asyncio
    async def test_check_response_sla_breach(self, service, mock_breached_ticket):
        """Test that breach is sent when SLA is breached."""
        mock_session = AsyncMock()

        with patch.object(
            service, "_send_sla_breach_notification", new_callable=AsyncMock
        ) as mock_send:
            result = await service._check_response_sla(mock_session, mock_breached_ticket)

            assert result == "breach"
            mock_send.assert_called_once_with(mock_session, mock_breached_ticket, "response")

    @pytest.mark.asyncio
    async def test_no_duplicate_warning(self, service, mock_ticket_open):
        """Test that warning is not sent twice."""
        mock_session = AsyncMock()
        # Already sent warning
        mock_ticket_open.sla_response_warning_sent_at = datetime.utcnow() - timedelta(minutes=30)

        with patch.object(
            service, "_send_sla_warning_notification", new_callable=AsyncMock
        ) as mock_send:
            result = await service._check_response_sla(mock_session, mock_ticket_open)

            assert result is None
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_duplicate_breach(self, service, mock_breached_ticket):
        """Test that breach is not sent twice."""
        mock_session = AsyncMock()
        # Already sent breach
        mock_breached_ticket.sla_response_breach_sent_at = datetime.utcnow() - timedelta(minutes=30)

        with patch.object(
            service, "_send_sla_breach_notification", new_callable=AsyncMock
        ) as mock_send:
            result = await service._check_response_sla(mock_session, mock_breached_ticket)

            assert result is None
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_responded_ticket(self, service, mock_ticket_open):
        """Test that tickets with first response are skipped."""
        mock_session = AsyncMock()
        mock_ticket_open.first_response_at = datetime.utcnow()

        with patch.object(
            service, "_send_sla_warning_notification", new_callable=AsyncMock
        ) as mock_send:
            result = await service._check_response_sla(mock_session, mock_ticket_open)

            assert result is None
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_resolution_sla_warning(self, service):
        """Test resolution SLA warning check."""
        mock_session = AsyncMock()
        ticket = MagicMock()
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.sla_resolution_due_at = datetime.utcnow() + timedelta(hours=1)
        ticket.is_sla_resolution_breached = False
        ticket.is_sla_resolution_warning_zone = True
        ticket.sla_resolution_warning_sent_at = None
        ticket.sla_resolution_remaining_seconds = 3600

        with patch.object(
            service, "_send_sla_warning_notification", new_callable=AsyncMock
        ) as mock_send:
            result = await service._check_resolution_sla(mock_session, ticket)

            assert result == "warning"
            mock_send.assert_called_once_with(mock_session, ticket, "resolution")

    @pytest.mark.asyncio
    async def test_skip_resolved_ticket_for_resolution_sla(self, service):
        """Test that resolved tickets are skipped for resolution SLA."""
        mock_session = AsyncMock()
        ticket = MagicMock()
        ticket.status = TicketStatus.RESOLVED

        result = await service._check_resolution_sla(mock_session, ticket)

        assert result is None


class TestSLABackgroundServiceRecipients:
    """Tests for notification recipient logic."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return SLABackgroundService()

    @pytest.mark.asyncio
    async def test_get_recipients_includes_assignee(self, service):
        """Test that assigned user is included in recipients."""
        mock_session = AsyncMock()

        # Mock assignee
        assignee = MagicMock()
        assignee.id = 5
        assignee.email = "assignee@test.com"
        assignee.is_active = True

        # Mock ticket
        ticket = MagicMock()
        ticket.org_id = 100
        ticket.assigned_to_user_id = 5

        # Mock user_dao.get_by_id
        mock_user_dao = MagicMock()
        mock_user_dao.get_by_id = AsyncMock(return_value=assignee)

        # Mock admin query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.sla_background_service.UserDAO", return_value=mock_user_dao):
            recipients = await service._get_notification_recipients(mock_session, ticket)

            assert len(recipients) == 1
            assert recipients[0].email == "assignee@test.com"

    @pytest.mark.asyncio
    async def test_get_recipients_includes_admins(self, service):
        """Test that org admins are included in recipients."""
        mock_session = AsyncMock()

        # Mock admin users
        admin1 = MagicMock()
        admin1.id = 10
        admin1.email = "admin1@test.com"
        admin1.is_active = True

        admin2 = MagicMock()
        admin2.id = 11
        admin2.email = "admin2@test.com"
        admin2.is_active = True

        # Mock ticket without assignee
        ticket = MagicMock()
        ticket.org_id = 100
        ticket.assigned_to_user_id = None

        # Mock user_dao
        mock_user_dao = MagicMock()
        mock_user_dao.get_by_id = AsyncMock(return_value=None)

        # Mock admin query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [admin1, admin2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.sla_background_service.UserDAO", return_value=mock_user_dao):
            recipients = await service._get_notification_recipients(mock_session, ticket)

            assert len(recipients) == 2
            emails = [r.email for r in recipients]
            assert "admin1@test.com" in emails
            assert "admin2@test.com" in emails


class TestSLABackgroundServiceIntegration:
    """Integration-style tests with mocked database."""

    @pytest.fixture
    def service(self):
        """Create service instance with mocked session factory."""
        mock_session = AsyncMock()
        service = SLABackgroundService(session_factory=lambda: mock_session)
        service._mock_session = mock_session
        return service

    @pytest.mark.asyncio
    async def test_check_all_returns_stats(self, service):
        """Test that check_all_sla_breaches returns statistics."""
        # Mock _get_active_tickets to return empty list
        with patch.object(
            service, "_get_active_tickets", new_callable=AsyncMock, return_value=[]
        ):
            stats = await service.check_all_sla_breaches()

            assert isinstance(stats, dict)
            assert "response_warnings" in stats
            assert "response_breaches" in stats
            assert "resolution_warnings" in stats
            assert "resolution_breaches" in stats
            assert "errors" in stats

    @pytest.mark.asyncio
    async def test_check_all_processes_tickets(self, service):
        """Test that all active tickets are processed."""
        # Create mock tickets
        ticket1 = MagicMock()
        ticket1.id = 1
        ticket2 = MagicMock()
        ticket2.id = 2

        with patch.object(
            service, "_get_active_tickets", new_callable=AsyncMock, return_value=[ticket1, ticket2]
        ), patch.object(
            service, "_check_response_sla", new_callable=AsyncMock, return_value="warning"
        ) as mock_response, patch.object(
            service, "_check_resolution_sla", new_callable=AsyncMock, return_value=None
        ) as mock_resolution:
            stats = await service.check_all_sla_breaches()

            # Both tickets should be checked
            assert mock_response.call_count == 2
            assert mock_resolution.call_count == 2
            assert stats["response_warnings"] == 2
