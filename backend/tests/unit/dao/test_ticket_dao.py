"""
Unit tests for Ticket DAO.

WHAT: Tests for TicketDAO, TicketCommentDAO, and TicketAttachmentDAO.

WHY: Verifies that:
1. Ticket CRUD operations work correctly
2. Org-scoping is enforced (multi-tenancy security)
3. Status transitions follow valid workflow
4. SLA calculations are correct
5. Comments support internal notes filtering
6. Query methods filter and paginate correctly

HOW: Uses pytest-asyncio with in-memory SQLite database for isolation.
"""

import pytest
from datetime import datetime, timedelta

from app.dao.ticket import TicketDAO, TicketCommentDAO, TicketAttachmentDAO, VALID_STATUS_TRANSITIONS
from app.models.ticket import (
    Ticket,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    SLA_CONFIG,
)
from app.core.exceptions import ValidationError
from tests.factories import (
    OrganizationFactory,
    UserFactory,
    ProjectFactory,
    TicketFactory,
    TicketCommentFactory,
)


class TestTicketDAOCreate:
    """Tests for ticket creation."""

    @pytest.mark.asyncio
    async def test_create_ticket_success(self, db_session, test_org, test_user):
        """Test creating a ticket with all required fields."""
        ticket_dao = TicketDAO(db_session)

        ticket = await ticket_dao.create(
            org_id=test_org.id,
            created_by_user_id=test_user.id,
            subject="Test Ticket",
            description="Test description",
        )

        assert ticket.id is not None
        assert ticket.subject == "Test Ticket"
        assert ticket.description == "Test description"
        assert ticket.status == TicketStatus.OPEN
        assert ticket.priority == TicketPriority.MEDIUM
        assert ticket.category == TicketCategory.SUPPORT
        assert ticket.org_id == test_org.id
        assert ticket.created_by_user_id == test_user.id
        assert ticket.created_at is not None

    @pytest.mark.asyncio
    async def test_create_ticket_with_priority(self, db_session, test_org, test_user):
        """Test creating a ticket with custom priority."""
        ticket_dao = TicketDAO(db_session)

        ticket = await ticket_dao.create(
            org_id=test_org.id,
            created_by_user_id=test_user.id,
            subject="Urgent Ticket",
            description="Need help ASAP",
            priority=TicketPriority.URGENT,
        )

        assert ticket.priority == TicketPriority.URGENT

    @pytest.mark.asyncio
    async def test_create_ticket_sets_sla_due_dates(self, db_session, test_org, test_user):
        """Test that SLA due dates are calculated on creation."""
        ticket_dao = TicketDAO(db_session)

        ticket = await ticket_dao.create(
            org_id=test_org.id,
            created_by_user_id=test_user.id,
            subject="SLA Test",
            description="Testing SLA calculation",
            priority=TicketPriority.HIGH,
        )

        # HIGH priority: 4h response, 24h resolution
        assert ticket.sla_response_due_at is not None
        assert ticket.sla_resolution_due_at is not None

        # Verify SLA times are correct
        expected_response_delta = timedelta(hours=SLA_CONFIG[TicketPriority.HIGH]["response_hours"])
        expected_resolution_delta = timedelta(hours=SLA_CONFIG[TicketPriority.HIGH]["resolution_hours"])

        # Allow small time difference for test execution
        response_diff = abs((ticket.sla_response_due_at - ticket.created_at).total_seconds() - expected_response_delta.total_seconds())
        resolution_diff = abs((ticket.sla_resolution_due_at - ticket.created_at).total_seconds() - expected_resolution_delta.total_seconds())

        assert response_diff < 5  # Within 5 seconds
        assert resolution_diff < 5

    @pytest.mark.asyncio
    async def test_create_ticket_with_project(self, db_session, test_org, test_user):
        """Test creating a ticket linked to a project."""
        project = await ProjectFactory.create(db_session, organization=test_org)
        ticket_dao = TicketDAO(db_session)

        ticket = await ticket_dao.create(
            org_id=test_org.id,
            created_by_user_id=test_user.id,
            subject="Project Issue",
            description="Issue with project",
            project_id=project.id,
        )

        assert ticket.project_id == project.id


class TestTicketDAORead:
    """Tests for ticket read operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, db_session, test_org, test_user):
        """Test retrieving a ticket by ID."""
        ticket = await TicketFactory.create(
            db_session, subject="Findable", organization=test_org, created_by=test_user
        )

        ticket_dao = TicketDAO(db_session)
        found = await ticket_dao.get_by_id(ticket.id, test_org.id)

        assert found is not None
        assert found.id == ticket.id
        assert found.subject == "Findable"

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_org(self, db_session, test_user):
        """Test that org-scoping prevents cross-org access."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        ticket = await TicketFactory.create(
            db_session, subject="Org1 Ticket", organization=org1, created_by=test_user
        )

        ticket_dao = TicketDAO(db_session)
        # Try to access from wrong org
        found = await ticket_dao.get_by_id(ticket.id, org2.id)

        assert found is None  # Should not find ticket from other org

    @pytest.mark.asyncio
    async def test_get_by_org(self, db_session, test_org, test_user):
        """Test listing tickets by organization."""
        # Create multiple tickets
        await TicketFactory.create(db_session, subject="Ticket 1", organization=test_org, created_by=test_user)
        await TicketFactory.create(db_session, subject="Ticket 2", organization=test_org, created_by=test_user)
        await TicketFactory.create(db_session, subject="Ticket 3", organization=test_org, created_by=test_user)

        ticket_dao = TicketDAO(db_session)
        tickets, total = await ticket_dao.list(test_org.id)

        assert len(tickets) == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_get_by_org_pagination(self, db_session, test_org, test_user):
        """Test pagination for ticket listing."""
        # Create 5 tickets
        for i in range(5):
            await TicketFactory.create(
                db_session, subject=f"Ticket {i}", organization=test_org, created_by=test_user
            )

        ticket_dao = TicketDAO(db_session)

        # Get first page
        page1, total = await ticket_dao.list(test_org.id, skip=0, limit=2)
        assert len(page1) == 2
        assert total == 5

        # Get second page
        page2, _ = await ticket_dao.list(test_org.id, skip=2, limit=2)
        assert len(page2) == 2

        # Get remaining
        page3, _ = await ticket_dao.list(test_org.id, skip=4, limit=2)
        assert len(page3) == 1


class TestTicketDAOStatusFilters:
    """Tests for status-based filtering."""

    @pytest.mark.asyncio
    async def test_get_by_org_with_status_filter(self, db_session, test_org, test_user):
        """Test filtering tickets by status."""
        await TicketFactory.create(
            db_session, subject="Open", status=TicketStatus.OPEN, organization=test_org, created_by=test_user
        )
        await TicketFactory.create(
            db_session, subject="In Progress", status=TicketStatus.IN_PROGRESS, organization=test_org, created_by=test_user
        )
        await TicketFactory.create(
            db_session, subject="Resolved", status=TicketStatus.RESOLVED, organization=test_org, created_by=test_user
        )

        ticket_dao = TicketDAO(db_session)
        in_progress, total = await ticket_dao.list(test_org.id, status=TicketStatus.IN_PROGRESS)

        assert len(in_progress) == 1
        assert total == 1
        assert in_progress[0].subject == "In Progress"


class TestTicketDAOStatusTransitions:
    """Tests for status workflow transitions."""

    @pytest.mark.asyncio
    async def test_valid_status_transitions_defined(self):
        """Test that all statuses have defined transitions."""
        for status in TicketStatus:
            assert status in VALID_STATUS_TRANSITIONS
            assert isinstance(VALID_STATUS_TRANSITIONS[status], list)

    @pytest.mark.asyncio
    async def test_change_status_valid_transition(self, db_session, test_org, test_user):
        """Test valid status transitions work."""
        ticket = await TicketFactory.create(
            db_session, subject="Status Test", organization=test_org, created_by=test_user
        )
        assert ticket.status == TicketStatus.OPEN

        ticket_dao = TicketDAO(db_session)

        # OPEN -> IN_PROGRESS is valid
        ticket = await ticket_dao.change_status(ticket.id, test_org.id, TicketStatus.IN_PROGRESS)
        assert ticket.status == TicketStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_change_status_invalid_transition(self, db_session, test_org, test_user):
        """Test invalid status transitions are rejected."""
        ticket = await TicketFactory.create(
            db_session, subject="Invalid Transition", organization=test_org, created_by=test_user
        )
        assert ticket.status == TicketStatus.OPEN

        ticket_dao = TicketDAO(db_session)

        # OPEN -> RESOLVED is not valid (must go through IN_PROGRESS first)
        with pytest.raises(ValidationError) as exc_info:
            await ticket_dao.change_status(ticket.id, test_org.id, TicketStatus.RESOLVED)

        assert "Invalid status transition" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_change_status_to_resolved_sets_resolved_at(self, db_session, test_org, test_user):
        """Test that resolving a ticket sets resolved_at timestamp."""
        ticket = await TicketFactory.create(
            db_session, subject="To Resolve", status=TicketStatus.IN_PROGRESS,
            organization=test_org, created_by=test_user
        )
        assert ticket.resolved_at is None

        ticket_dao = TicketDAO(db_session)
        ticket = await ticket_dao.change_status(ticket.id, test_org.id, TicketStatus.RESOLVED)

        assert ticket.status == TicketStatus.RESOLVED
        assert ticket.resolved_at is not None

    @pytest.mark.asyncio
    async def test_change_status_to_closed_sets_closed_at(self, db_session, test_org, test_user):
        """Test that closing a ticket sets closed_at timestamp."""
        ticket = await TicketFactory.create(
            db_session, subject="To Close", status=TicketStatus.RESOLVED,
            organization=test_org, created_by=test_user
        )
        assert ticket.closed_at is None

        ticket_dao = TicketDAO(db_session)
        ticket = await ticket_dao.change_status(ticket.id, test_org.id, TicketStatus.CLOSED)

        assert ticket.status == TicketStatus.CLOSED
        assert ticket.closed_at is not None


class TestTicketDAOAssignment:
    """Tests for ticket assignment."""

    @pytest.mark.asyncio
    async def test_assign_ticket(self, db_session, test_org, test_user):
        """Test assigning a ticket to a user."""
        admin = await UserFactory.create_admin(
            db_session, email="admin@test.com", organization=test_org
        )
        ticket = await TicketFactory.create(
            db_session, subject="Assign Me", organization=test_org, created_by=test_user
        )
        assert ticket.assigned_to_user_id is None

        ticket_dao = TicketDAO(db_session)
        ticket = await ticket_dao.assign(ticket.id, test_org.id, admin.id)

        assert ticket.assigned_to_user_id == admin.id
        # Assignment should auto-transition to IN_PROGRESS
        assert ticket.status == TicketStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_unassign_ticket(self, db_session, test_org, test_user):
        """Test unassigning a ticket."""
        admin = await UserFactory.create_admin(
            db_session, email="admin2@test.com", organization=test_org
        )
        ticket = await TicketFactory.create(
            db_session, subject="Unassign Me", organization=test_org,
            created_by=test_user, assigned_to=admin
        )

        ticket_dao = TicketDAO(db_session)
        ticket = await ticket_dao.assign(ticket.id, test_org.id, None)

        assert ticket.assigned_to_user_id is None


class TestTicketDAOSLA:
    """Tests for SLA-related operations."""

    @pytest.mark.asyncio
    async def test_get_sla_breached_tickets(self, db_session, test_org, test_user):
        """Test getting tickets with breached SLA."""
        ticket_dao = TicketDAO(db_session)

        # Create a ticket and manually set breached SLA
        ticket = await ticket_dao.create(
            org_id=test_org.id,
            created_by_user_id=test_user.id,
            subject="Breached SLA",
            description="SLA is breached",
            priority=TicketPriority.URGENT,
        )

        # Manually set SLA due dates in the past
        ticket.sla_response_due_at = datetime.utcnow() - timedelta(hours=2)
        ticket.sla_resolution_due_at = datetime.utcnow() - timedelta(hours=1)
        await db_session.flush()

        breached = await ticket_dao.get_sla_breached_tickets(test_org.id)

        assert len(breached) >= 1
        assert any(t.id == ticket.id for t in breached)

    @pytest.mark.asyncio
    async def test_mark_first_response(self, db_session, test_org, test_user):
        """Test marking first response on a ticket."""
        ticket = await TicketFactory.create(
            db_session, subject="Response Test", organization=test_org, created_by=test_user
        )
        assert ticket.first_response_at is None

        ticket_dao = TicketDAO(db_session)
        await ticket_dao.record_first_response(ticket.id, test_org.id)

        # Refresh ticket
        ticket = await ticket_dao.get_by_id(ticket.id, test_org.id)
        assert ticket.first_response_at is not None


class TestTicketDAOStats:
    """Tests for statistics operations."""

    @pytest.mark.asyncio
    async def test_get_stats(self, db_session, test_org, test_user):
        """Test getting ticket statistics."""
        # Create tickets with different statuses
        await TicketFactory.create(
            db_session, subject="Open 1", status=TicketStatus.OPEN,
            organization=test_org, created_by=test_user
        )
        await TicketFactory.create(
            db_session, subject="Open 2", status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH, organization=test_org, created_by=test_user
        )
        await TicketFactory.create(
            db_session, subject="In Progress", status=TicketStatus.IN_PROGRESS,
            organization=test_org, created_by=test_user
        )

        ticket_dao = TicketDAO(db_session)
        stats = await ticket_dao.get_stats(test_org.id)

        assert stats["total"] == 3
        assert stats["by_status"]["open"] == 2
        assert stats["by_status"]["in_progress"] == 1
        assert stats["open_count"] == 2  # Only tickets with OPEN status


class TestTicketDAOMultiTenancy:
    """Tests for multi-tenancy isolation."""

    @pytest.mark.asyncio
    async def test_tickets_isolated_by_org(self, db_session):
        """Test that tickets from different orgs are isolated."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")
        user1 = await UserFactory.create(db_session, email="user1@test.com", organization=org1)
        user2 = await UserFactory.create(db_session, email="user2@test.com", organization=org2)

        # Create tickets in each org
        await TicketFactory.create(db_session, subject="Org1 Ticket 1", organization=org1, created_by=user1)
        await TicketFactory.create(db_session, subject="Org1 Ticket 2", organization=org1, created_by=user1)
        await TicketFactory.create(db_session, subject="Org2 Ticket", organization=org2, created_by=user2)

        ticket_dao = TicketDAO(db_session)

        # Verify isolation
        org1_tickets, org1_total = await ticket_dao.list(org1.id)
        org2_tickets, org2_total = await ticket_dao.list(org2.id)

        assert len(org1_tickets) == 2
        assert org1_total == 2
        assert len(org2_tickets) == 1
        assert org2_total == 1
        assert all(t.org_id == org1.id for t in org1_tickets)
        assert all(t.org_id == org2.id for t in org2_tickets)


class TestTicketCommentDAOCreate:
    """Tests for comment creation."""

    @pytest.mark.asyncio
    async def test_create_comment(self, db_session, test_org, test_user):
        """Test creating a comment on a ticket."""
        ticket = await TicketFactory.create(
            db_session, subject="Comment Test", organization=test_org, created_by=test_user
        )

        comment_dao = TicketCommentDAO(db_session)
        comment = await comment_dao.create(
            ticket_id=ticket.id,
            user_id=test_user.id,
            content="This is a test comment",
        )

        assert comment.id is not None
        assert comment.ticket_id == ticket.id
        assert comment.user_id == test_user.id
        assert comment.content == "This is a test comment"
        assert comment.is_internal is False

    @pytest.mark.asyncio
    async def test_create_internal_comment(self, db_session, test_org, test_user):
        """Test creating an internal note."""
        ticket = await TicketFactory.create(
            db_session, subject="Internal Note Test", organization=test_org, created_by=test_user
        )

        comment_dao = TicketCommentDAO(db_session)
        comment = await comment_dao.create(
            ticket_id=ticket.id,
            user_id=test_user.id,
            content="This is an internal note",
            is_internal=True,
        )

        assert comment.is_internal is True


class TestTicketCommentDAORead:
    """Tests for comment read operations."""

    @pytest.mark.asyncio
    async def test_list_for_ticket(self, db_session, test_org, test_user):
        """Test getting all comments for a ticket."""
        ticket = await TicketFactory.create(
            db_session, subject="Multi Comment", organization=test_org, created_by=test_user
        )

        # Create multiple comments
        await TicketCommentFactory.create(db_session, ticket.id, test_user.id, content="Comment 1")
        await TicketCommentFactory.create(db_session, ticket.id, test_user.id, content="Comment 2")
        await TicketCommentFactory.create_internal(db_session, ticket.id, test_user.id, content="Internal")

        comment_dao = TicketCommentDAO(db_session)

        # Get all comments
        comments = await comment_dao.list_for_ticket(ticket.id)
        assert len(comments) == 3

        # Get only public comments
        public_comments = await comment_dao.list_for_ticket(ticket.id, include_internal=False)
        assert len(public_comments) == 2
        assert all(not c.is_internal for c in public_comments)


class TestTicketCommentDAOUpdate:
    """Tests for comment update operations."""

    @pytest.mark.asyncio
    async def test_update_comment(self, db_session, test_org, test_user):
        """Test updating a comment."""
        ticket = await TicketFactory.create(
            db_session, subject="Update Comment", organization=test_org, created_by=test_user
        )
        comment = await TicketCommentFactory.create(
            db_session, ticket.id, test_user.id, content="Original"
        )

        comment_dao = TicketCommentDAO(db_session)
        updated = await comment_dao.update(comment.id, test_user.id, content="Updated content")

        assert updated.content == "Updated content"
        assert updated.updated_at is not None
        assert updated.is_edited is True


class TestTicketCommentDAODelete:
    """Tests for comment deletion."""

    @pytest.mark.asyncio
    async def test_delete_comment(self, db_session, test_org, test_user):
        """Test deleting a comment."""
        ticket = await TicketFactory.create(
            db_session, subject="Delete Comment", organization=test_org, created_by=test_user
        )
        comment = await TicketCommentFactory.create(
            db_session, ticket.id, test_user.id, content="To Delete"
        )

        comment_dao = TicketCommentDAO(db_session)
        result = await comment_dao.delete(comment.id, test_user.id)

        assert result is True

        # Verify deleted
        found = await comment_dao.get_by_id(comment.id)
        assert found is None
