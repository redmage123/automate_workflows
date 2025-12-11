"""
Integration tests for ticket management API.

WHAT: Tests for ticket CRUD operations via HTTP API.

WHY: Tickets are critical for support request management. These tests ensure:
1. Users can create tickets to report issues
2. Admins can manage tickets (assign, change status)
3. SLA tracking works correctly
4. Comments and internal notes work
5. Org-scoping prevents cross-org access (OWASP A01)

HOW: Uses pytest-asyncio with AsyncClient for HTTP testing.
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import OrganizationFactory, UserFactory, ProjectFactory, TicketFactory
from app.models.ticket import TicketStatus, TicketPriority, TicketCategory


class TestTicketCreate:
    """Integration tests for ticket creation endpoint."""

    @pytest.mark.asyncio
    async def test_create_ticket_as_client(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test creating a ticket as CLIENT.

        WHY: Clients should be able to create support tickets.
        """
        # Create organization and client user
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Create ticket
        response = await client.post(
            "/api/tickets",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "subject": "Login not working",
                "description": "I cannot log in to the system. Getting error 500.",
                "priority": "high",
                "category": "bug",
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["subject"] == "Login not working"
        assert data["description"] == "I cannot log in to the system. Getting error 500."
        assert data["status"] == "open"
        assert data["priority"] == "high"
        assert data["category"] == "bug"
        assert data["org_id"] == org.id
        assert "id" in data
        assert "created_at" in data
        # SLA should be calculated
        assert data["sla_response_due_at"] is not None
        assert data["sla_resolution_due_at"] is not None

    @pytest.mark.asyncio
    async def test_create_ticket_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test creating a ticket as ADMIN.

        WHY: Admins can also create tickets on behalf of clients.
        """
        # Create organization and admin user
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Create ticket
        response = await client.post(
            "/api/tickets",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "subject": "System maintenance request",
                "description": "Schedule routine maintenance.",
                "priority": "low",
                "category": "general",
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["subject"] == "System maintenance request"
        assert data["priority"] == "low"
        assert data["category"] == "general"

    @pytest.mark.asyncio
    async def test_create_ticket_with_project(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test creating a ticket linked to a project.

        WHY: Tickets can be associated with projects for context.
        """
        # Create organization, user, and project
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Website Project", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Create ticket with project
        response = await client.post(
            "/api/tickets",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "subject": "Website issue",
                "description": "CSS not loading properly.",
                "priority": "medium",
                "category": "bug",
                "project_id": project.id,
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["project_id"] == project.id

    @pytest.mark.asyncio
    async def test_create_ticket_sla_based_on_priority(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that SLA is calculated based on priority.

        WHY: Different priorities have different SLA times.
        """
        # Create organization and user
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Create urgent ticket
        response = await client.post(
            "/api/tickets",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "subject": "Critical system down",
                "description": "Production is not working!",
                "priority": "urgent",
                "category": "bug",
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()

        # Urgent priority = 1h response, 4h resolution
        response_due = datetime.fromisoformat(data["sla_response_due_at"].replace("Z", "+00:00"))
        created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        expected_response = created + timedelta(hours=1)

        # Allow 1 minute tolerance for test execution time
        assert abs((response_due - expected_response).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_create_ticket_without_auth(self, client: AsyncClient):
        """
        Test that unauthenticated requests are rejected.

        WHY: Security - ticket creation requires authentication.
        """
        response = await client.post(
            "/api/tickets",
            json={"subject": "Test", "description": "Test"},
        )

        assert response.status_code in (401, 403)


class TestTicketList:
    """Integration tests for ticket listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_tickets(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test listing tickets for current organization.

        WHY: Users need to browse tickets in their organization.
        """
        # Create organization, user, and tickets
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        await TicketFactory.create(
            db_session, subject="Ticket 1", organization=org, created_by=user
        )
        await TicketFactory.create(
            db_session, subject="Ticket 2", organization=org, created_by=user
        )
        await TicketFactory.create(
            db_session, subject="Ticket 3", organization=org, created_by=user
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # List tickets
        response = await client.get(
            "/api/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_list_tickets_filter_by_status(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test filtering tickets by status.

        WHY: Users often want to see only open or in-progress tickets.
        """
        # Create organization, user, and tickets with different statuses
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        await TicketFactory.create(
            db_session, subject="Open", status=TicketStatus.OPEN,
            organization=org, created_by=user
        )
        await TicketFactory.create(
            db_session, subject="In Progress", status=TicketStatus.IN_PROGRESS,
            organization=org, created_by=user
        )
        await TicketFactory.create(
            db_session, subject="Closed", status=TicketStatus.CLOSED,
            organization=org, created_by=user
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Filter by open status
        response = await client.get(
            "/api/tickets?status=open",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["subject"] == "Open"

    @pytest.mark.asyncio
    async def test_list_tickets_filter_by_priority(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test filtering tickets by priority.

        WHY: Support teams often prioritize urgent tickets.
        """
        # Create organization, user, and tickets with different priorities
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        await TicketFactory.create(
            db_session, subject="Urgent", priority=TicketPriority.URGENT,
            organization=org, created_by=user
        )
        await TicketFactory.create(
            db_session, subject="Low", priority=TicketPriority.LOW,
            organization=org, created_by=user
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Filter by urgent priority
        response = await client.get(
            "/api/tickets?priority=urgent",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["subject"] == "Urgent"

    @pytest.mark.asyncio
    async def test_list_tickets_org_isolation(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that users only see tickets in their organization.

        WHY: Multi-tenancy security (OWASP A01).
        """
        # Create two organizations with tickets
        org1 = await OrganizationFactory.create(db_session, name="Company 1")
        org2 = await OrganizationFactory.create(db_session, name="Company 2")

        user1 = await UserFactory.create_client(
            db_session,
            email="user1@test.com",
            password="Password123!",
            organization=org1,
        )
        user2 = await UserFactory.create_client(
            db_session,
            email="user2@test.com",
            password="Password123!",
            organization=org2,
        )

        await TicketFactory.create(
            db_session, subject="Org1 Ticket", organization=org1, created_by=user1
        )
        await TicketFactory.create(
            db_session, subject="Org2 Ticket", organization=org2, created_by=user2
        )

        # Login as user from org1
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user1@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # List tickets
        response = await client.get(
            "/api/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should only see org1's ticket
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["subject"] == "Org1 Ticket"

    @pytest.mark.asyncio
    async def test_list_my_tickets(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test filtering tickets created by current user.

        WHY: Users want to see their own tickets.
        """
        # Create organization and two users
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user1 = await UserFactory.create_client(
            db_session,
            email="user1@test.com",
            password="Password123!",
            organization=org,
        )
        user2 = await UserFactory.create_client(
            db_session,
            email="user2@test.com",
            password="Password123!",
            organization=org,
        )

        await TicketFactory.create(
            db_session, subject="User1 Ticket", organization=org, created_by=user1
        )
        await TicketFactory.create(
            db_session, subject="User2 Ticket", organization=org, created_by=user2
        )

        # Login as user1
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user1@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Filter my tickets
        response = await client.get(
            "/api/tickets?created_by_me=true",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["subject"] == "User1 Ticket"


class TestTicketGet:
    """Integration tests for getting individual ticket."""

    @pytest.mark.asyncio
    async def test_get_ticket_by_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting a ticket by ID.

        WHY: Users need to view ticket details.
        """
        # Create organization, user, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", organization=org, created_by=user
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get ticket
        response = await client.get(
            f"/api/tickets/{ticket.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == ticket.id
        assert data["subject"] == "Test Ticket"
        # Should include comments array (even if empty)
        assert "comments" in data

    @pytest.mark.asyncio
    async def test_get_ticket_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting a non-existent ticket.

        WHY: Should return 404 for missing resources.
        """
        # Create organization and user
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get non-existent ticket
        response = await client.get(
            "/api/tickets/99999",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_get_other_org_ticket(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that users cannot access tickets from other organizations.

        WHY: Multi-tenancy security (OWASP A01).
        """
        # Create two organizations
        org1 = await OrganizationFactory.create(db_session, name="Company 1")
        org2 = await OrganizationFactory.create(db_session, name="Company 2")

        await UserFactory.create_client(
            db_session,
            email="user1@test.com",
            password="Password123!",
            organization=org1,
        )
        user2 = await UserFactory.create_client(
            db_session,
            email="user2@test.com",
            password="Password123!",
            organization=org2,
        )

        ticket2 = await TicketFactory.create(
            db_session, subject="Org2 Ticket", organization=org2, created_by=user2
        )

        # Login as user from org1
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user1@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to access org2's ticket
        response = await client.get(
            f"/api/tickets/{ticket2.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should be not found (hiding existence)
        assert response.status_code == 404


class TestTicketStatusChange:
    """Integration tests for ticket status change endpoint."""

    @pytest.mark.asyncio
    async def test_change_status_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test changing ticket status as ADMIN.

        WHY: Admins manage ticket workflow.
        """
        # Create organization, admin, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        admin = await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", status=TicketStatus.OPEN,
            organization=org, created_by=user
        )

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Change status
        response = await client.patch(
            f"/api/tickets/{ticket.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "in_progress"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_resolve_ticket_sets_resolved_at(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that resolving a ticket sets resolved_at timestamp.

        WHY: Timestamp tracking for SLA metrics.
        """
        # Create organization, admin, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", status=TicketStatus.IN_PROGRESS,
            organization=org, created_by=user
        )

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Resolve ticket
        response = await client.patch(
            f"/api/tickets/{ticket.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "resolved"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["resolved_at"] is not None

    @pytest.mark.asyncio
    async def test_client_cannot_change_status(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that CLIENT users cannot change ticket status.

        WHY: RBAC - only admins manage ticket workflow.
        """
        # Create organization and client user
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", organization=org, created_by=user
        )

        # Login as client
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to change status
        response = await client.patch(
            f"/api/tickets/{ticket.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "resolved"},
        )

        # Should be forbidden
        assert response.status_code == 403


class TestTicketAssignment:
    """Integration tests for ticket assignment endpoint."""

    @pytest.mark.asyncio
    async def test_assign_ticket_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test assigning a ticket to a user.

        WHY: Admins assign tickets to team members.
        """
        # Create organization, users, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        client_user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        admin = await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", organization=org, created_by=client_user
        )

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Assign ticket
        response = await client.patch(
            f"/api/tickets/{ticket.id}/assign",
            headers={"Authorization": f"Bearer {token}"},
            json={"assigned_to_user_id": admin.id},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_to"]["id"] == admin.id

    @pytest.mark.asyncio
    async def test_assign_ticket_auto_changes_status(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that assigning a ticket changes status to in_progress.

        WHY: Assignment indicates work is starting.
        """
        # Create organization, users, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        client_user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        admin = await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", status=TicketStatus.OPEN,
            organization=org, created_by=client_user
        )

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Assign ticket
        response = await client.patch(
            f"/api/tickets/{ticket.id}/assign",
            headers={"Authorization": f"Bearer {token}"},
            json={"assigned_to_user_id": admin.id},
        )

        # Verify status changed
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"


class TestTicketComments:
    """Integration tests for ticket comment operations."""

    @pytest.mark.asyncio
    async def test_add_comment_to_ticket(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test adding a public comment to a ticket.

        WHY: Comments enable communication on tickets.
        """
        # Create organization, user, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", organization=org, created_by=user
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Add comment
        response = await client.post(
            f"/api/tickets/{ticket.id}/comments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": "This is my comment.",
                "is_internal": False,
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "This is my comment."
        assert data["is_internal"] is False
        assert data["user"]["id"] == user.id

    @pytest.mark.asyncio
    async def test_admin_add_internal_note(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that admins can add internal notes.

        WHY: Internal notes are for team discussion only.
        """
        # Create organization, users, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        client_user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", organization=org, created_by=client_user
        )

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Add internal note
        response = await client.post(
            f"/api/tickets/{ticket.id}/comments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": "Internal: Need to escalate this.",
                "is_internal": True,
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["is_internal"] is True

    @pytest.mark.asyncio
    async def test_client_cannot_add_internal_note(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that clients cannot add internal notes.

        WHY: Internal notes should only be visible to admins.
        """
        # Create organization, user, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", organization=org, created_by=user
        )

        # Login as client
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to add internal note
        response = await client.post(
            f"/api/tickets/{ticket.id}/comments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": "Trying to add internal note.",
                "is_internal": True,
            },
        )

        # Should either be forbidden or the flag should be ignored
        # Depending on implementation, this could be 403 or 201 with is_internal=False
        if response.status_code == 201:
            data = response.json()
            assert data["is_internal"] is False  # Flag should be ignored
        else:
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_own_comment(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test deleting own comment.

        WHY: Users should be able to delete their own comments.
        """
        # Create organization, user, ticket, and comment
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", organization=org, created_by=user
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Add comment
        add_response = await client.post(
            f"/api/tickets/{ticket.id}/comments",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "To be deleted."},
        )
        comment_id = add_response.json()["id"]

        # Delete comment
        delete_response = await client.delete(
            f"/api/tickets/{ticket.id}/comments/{comment_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert delete_response.status_code == 204


class TestTicketSLA:
    """Integration tests for SLA-related endpoints."""

    @pytest.mark.asyncio
    async def test_get_ticket_sla_status(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting SLA status for a ticket.

        WHY: Users need to monitor SLA compliance.
        """
        # Create organization, user, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", organization=org, created_by=user
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get SLA status
        response = await client.get(
            f"/api/tickets/{ticket.id}/sla",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "resolution" in data
        assert "sla_config" in data


class TestTicketStats:
    """Integration tests for ticket statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_ticket_stats(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting ticket statistics.

        WHY: Dashboard needs aggregated ticket metrics.
        """
        # Create organization, user, and tickets with different statuses
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        await TicketFactory.create(
            db_session, subject="Open 1", status=TicketStatus.OPEN,
            organization=org, created_by=user
        )
        await TicketFactory.create(
            db_session, subject="Open 2", status=TicketStatus.OPEN,
            organization=org, created_by=user
        )
        await TicketFactory.create(
            db_session, subject="In Progress", status=TicketStatus.IN_PROGRESS,
            organization=org, created_by=user
        )
        await TicketFactory.create(
            db_session, subject="Closed", status=TicketStatus.CLOSED,
            organization=org, created_by=user
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get stats
        response = await client.get(
            "/api/tickets/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert data["open_count"] == 2
        assert "by_status" in data
        assert "by_priority" in data


class TestTicketDelete:
    """Integration tests for ticket deletion endpoint."""

    @pytest.mark.asyncio
    async def test_delete_ticket_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test deleting a ticket as ADMIN.

        WHY: Admins should be able to delete spam/test tickets.
        """
        # Create organization, admin, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="To Delete", organization=org, created_by=user
        )

        # Login as admin
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Delete ticket
        response = await client.delete(
            f"/api/tickets/{ticket.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify deletion
        assert response.status_code == 204

        # Verify ticket is gone
        get_response = await client.get(
            f"/api/tickets/{ticket.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_client_cannot_delete_ticket(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that CLIENT users cannot delete tickets.

        WHY: RBAC - only admins should delete tickets.
        """
        # Create organization, client, and ticket
        org = await OrganizationFactory.create(db_session, name="Test Company")
        user = await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        ticket = await TicketFactory.create(
            db_session, subject="Test Ticket", organization=org, created_by=user
        )

        # Login as client
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to delete ticket
        response = await client.delete(
            f"/api/tickets/{ticket.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should be forbidden
        assert response.status_code == 403
