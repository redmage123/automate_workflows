"""
Integration tests for project management API.

WHAT: Tests for project CRUD operations via HTTP API.

WHY: Projects are the central business entity. These tests ensure:
1. Only admins can create/modify projects
2. Users can view projects in their organization
3. Org-scoping prevents cross-org access (OWASP A01)
4. Status transitions work correctly
5. Search and filtering work as expected

HOW: Uses pytest-asyncio with AsyncClient for HTTP testing.
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import OrganizationFactory, UserFactory, ProjectFactory
from app.models.project import ProjectStatus, ProjectPriority


class TestProjectCreate:
    """Integration tests for project creation endpoint."""

    @pytest.mark.asyncio
    async def test_create_project_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test creating a project as ADMIN.

        WHY: Admins should be able to create new projects.
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

        # Create project
        response = await client.post(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "New Project",
                "description": "A test project",
                "priority": "high",
                "estimated_hours": 40,
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Project"
        assert data["description"] == "A test project"
        assert data["status"] == "draft"
        assert data["priority"] == "high"
        assert data["estimated_hours"] == 40
        assert data["org_id"] == org.id
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_project_with_dates(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test creating a project with start and due dates.

        WHY: Projects need scheduling for resource planning.
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

        # Create project with dates
        start_date = datetime.utcnow().isoformat()
        due_date = (datetime.utcnow() + timedelta(days=30)).isoformat()

        response = await client.post(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Scheduled Project",
                "start_date": start_date,
                "due_date": due_date,
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["start_date"] is not None
        assert data["due_date"] is not None

    @pytest.mark.asyncio
    async def test_cannot_create_project_as_client(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that CLIENT users cannot create projects.

        WHY: RBAC - only admins should create projects.
        """
        # Create organization and client user
        org = await OrganizationFactory.create(db_session)
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

        # Try to create project
        response = await client.post(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Unauthorized Project",
            },
        )

        # Should be forbidden
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_project_without_auth(self, client: AsyncClient):
        """
        Test that unauthenticated requests are rejected.

        WHY: Security - all project operations require authentication.
        """
        response = await client.post(
            "/api/projects",
            json={"name": "Test Project"},
        )

        # Should be unauthorized/forbidden (401 or 403 depending on FastAPI auth setup)
        assert response.status_code in (401, 403)


class TestProjectList:
    """Integration tests for project listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_projects(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test listing projects for current organization.

        WHY: Users need to browse projects in their organization.
        """
        # Create organization, user, and projects
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        await ProjectFactory.create(db_session, name="Project 1", organization=org)
        await ProjectFactory.create(db_session, name="Project 2", organization=org)
        await ProjectFactory.create(db_session, name="Project 3", organization=org)

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # List projects
        response = await client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_list_projects_pagination(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test project list pagination.

        WHY: Large project lists need pagination for performance.
        """
        # Create organization, user, and many projects
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        for i in range(15):
            await ProjectFactory.create(
                db_session, name=f"Project {i}", organization=org
            )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # First page
        response = await client.get(
            "/api/projects?skip=0&limit=5",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["total"] == 15

        # Second page
        response = await client.get(
            "/api/projects?skip=5&limit=5",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5

    @pytest.mark.asyncio
    async def test_list_projects_filter_by_status(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test filtering projects by status.

        WHY: Dashboard views need to filter by project status.
        """
        # Create organization, user, and projects with different statuses
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        await ProjectFactory.create(
            db_session, name="Draft", status=ProjectStatus.DRAFT, organization=org
        )
        await ProjectFactory.create(
            db_session, name="Active", status=ProjectStatus.IN_PROGRESS, organization=org
        )
        await ProjectFactory.create(
            db_session, name="Done", status=ProjectStatus.COMPLETED, organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Filter by in_progress status
        response = await client.get(
            "/api/projects?status=in_progress",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Active"

    @pytest.mark.asyncio
    async def test_list_projects_active_only(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test filtering to active projects only.

        WHY: Common dashboard view excludes completed/cancelled projects.
        """
        # Create organization, user, and projects
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        await ProjectFactory.create(
            db_session, name="Draft", status=ProjectStatus.DRAFT, organization=org
        )
        await ProjectFactory.create(
            db_session, name="Active", status=ProjectStatus.IN_PROGRESS, organization=org
        )
        await ProjectFactory.create(
            db_session, name="Done", status=ProjectStatus.COMPLETED, organization=org
        )
        await ProjectFactory.create(
            db_session, name="Cancelled", status=ProjectStatus.CANCELLED, organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Filter active only
        response = await client.get(
            "/api/projects?active_only=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Draft + Active
        names = {item["name"] for item in data["items"]}
        assert names == {"Draft", "Active"}

    @pytest.mark.asyncio
    async def test_list_projects_org_isolation(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that users only see projects in their organization.

        WHY: Multi-tenancy security (OWASP A01).
        """
        # Create two organizations with projects
        org1 = await OrganizationFactory.create(db_session, name="Company 1")
        org2 = await OrganizationFactory.create(db_session, name="Company 2")

        await UserFactory.create(
            db_session,
            email="user1@test.com",
            password="Password123!",
            organization=org1,
        )

        await ProjectFactory.create(db_session, name="Org1 Project", organization=org1)
        await ProjectFactory.create(db_session, name="Org2 Project", organization=org2)

        # Login as user from org1
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user1@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # List projects
        response = await client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should only see org1's project
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Org1 Project"


class TestProjectGet:
    """Integration tests for getting individual project."""

    @pytest.mark.asyncio
    async def test_get_project_by_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting a project by ID.

        WHY: Users need to view project details.
        """
        # Create organization, user, and project
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get project
        response = await client.get(
            f"/api/projects/{project.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project.id
        assert data["name"] == "Test Project"

    @pytest.mark.asyncio
    async def test_get_project_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting a non-existent project.

        WHY: Should return 404 for missing resources.
        """
        # Create organization and user
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get non-existent project
        response = await client.get(
            "/api/projects/99999",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should be not found
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_get_other_org_project(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that users cannot access projects from other organizations.

        WHY: Multi-tenancy security (OWASP A01).
        """
        # Create two organizations
        org1 = await OrganizationFactory.create(db_session, name="Company 1")
        org2 = await OrganizationFactory.create(db_session, name="Company 2")

        await UserFactory.create(
            db_session,
            email="user1@test.com",
            password="Password123!",
            organization=org1,
        )

        project2 = await ProjectFactory.create(
            db_session, name="Org2 Project", organization=org2
        )

        # Login as user from org1
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user1@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to access org2's project
        response = await client.get(
            f"/api/projects/{project2.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should be not found (hiding existence)
        assert response.status_code == 404


class TestProjectUpdate:
    """Integration tests for project update endpoint."""

    @pytest.mark.asyncio
    async def test_update_project_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test updating a project as ADMIN.

        WHY: Admins should be able to modify project details.
        """
        # Create organization, admin, and project
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Old Name", description="Old description", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Update project
        response = await client.put(
            f"/api/projects/{project.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "New Name",
                "description": "New description",
                "priority": "urgent",
            },
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "New description"
        assert data["priority"] == "urgent"

    @pytest.mark.asyncio
    async def test_cannot_update_project_as_client(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that CLIENT users cannot update projects.

        WHY: RBAC - only admins should modify projects.
        """
        # Create organization, client, and project
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to update project
        response = await client.put(
            f"/api/projects/{project.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Hacked Name"},
        )

        # Should be forbidden
        assert response.status_code == 403


class TestProjectStatusUpdate:
    """Integration tests for project status update endpoint."""

    @pytest.mark.asyncio
    async def test_update_project_status(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test updating project status.

        WHY: Status transitions are key to project lifecycle.
        """
        # Create organization, admin, and project
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", status=ProjectStatus.DRAFT, organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Update status
        response = await client.patch(
            f"/api/projects/{project.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "in_progress"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_complete_project_sets_completed_at(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that completing a project sets completed_at timestamp.

        WHY: Timestamp tracking for reporting and analytics.
        """
        # Create organization, admin, and in-progress project
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create_in_progress(
            db_session, name="Test Project", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Complete project
        response = await client.patch(
            f"/api/projects/{project.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "completed"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None


class TestProjectDelete:
    """Integration tests for project deletion endpoint."""

    @pytest.mark.asyncio
    async def test_delete_project_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test deleting a project as ADMIN.

        WHY: Admins should be able to delete projects.
        """
        # Create organization, admin, and project
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="To Delete", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Delete project
        response = await client.delete(
            f"/api/projects/{project.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify deletion
        assert response.status_code == 204

        # Verify project is gone
        get_response = await client.get(
            f"/api/projects/{project.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_delete_project_as_client(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that CLIENT users cannot delete projects.

        WHY: RBAC - only admins should delete projects.
        """
        # Create organization, client, and project
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to delete project
        response = await client.delete(
            f"/api/projects/{project.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should be forbidden
        assert response.status_code == 403


class TestProjectStats:
    """Integration tests for project statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_project_stats(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting project statistics.

        WHY: Dashboard needs aggregated project metrics.
        """
        # Create organization, user, and projects with different statuses
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        await ProjectFactory.create(
            db_session, name="Draft 1", status=ProjectStatus.DRAFT, organization=org
        )
        await ProjectFactory.create(
            db_session, name="Draft 2", status=ProjectStatus.DRAFT, organization=org
        )
        await ProjectFactory.create(
            db_session, name="Active", status=ProjectStatus.IN_PROGRESS, organization=org
        )
        await ProjectFactory.create(
            db_session, name="Done", status=ProjectStatus.COMPLETED, organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get stats
        response = await client.get(
            "/api/projects/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert data["active"] == 3  # Draft + In Progress
        assert "by_status" in data
        assert data["by_status"].get("draft") == 2
        assert data["by_status"].get("in_progress") == 1
        assert data["by_status"].get("completed") == 1


class TestProjectSearch:
    """Integration tests for project search endpoint."""

    @pytest.mark.asyncio
    async def test_search_projects_by_name(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test searching projects by name.

        WHY: Users need to quickly find projects.
        """
        # Create organization, user, and projects
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        await ProjectFactory.create(
            db_session, name="Website Automation", organization=org
        )
        await ProjectFactory.create(
            db_session, name="CRM Integration", organization=org
        )
        await ProjectFactory.create(
            db_session, name="Email Marketing", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Search for automation
        response = await client.get(
            "/api/projects/search/automation",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Website Automation"

    @pytest.mark.asyncio
    async def test_search_projects_short_query_rejected(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that search rejects queries shorter than 2 characters.

        WHY: Very short queries would return too many results.
        """
        # Create organization and user
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Search with single character
        response = await client.get(
            "/api/projects/search/a",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should fail validation
        assert response.status_code == 400


class TestProjectProposals:
    """Integration tests for project proposals endpoint."""

    @pytest.mark.asyncio
    async def test_get_project_proposals(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting proposals for a project.

        WHY: Users need to see all proposals associated with a project.
        """
        from tests.factories import ProposalFactory

        # Create organization, user, project, and proposals
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        await ProposalFactory.create(
            db_session, title="Proposal v1", project=project
        )
        await ProposalFactory.create(
            db_session, title="Proposal v2", project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get proposals
        response = await client.get(
            f"/api/projects/{project.id}/proposals",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
