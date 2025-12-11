"""
Unit tests for Project DAO.

WHAT: Tests for ProjectDAO database operations.

WHY: Verifies that:
1. Project CRUD operations work correctly
2. Org-scoping is enforced (multi-tenancy security)
3. Status transitions handle timestamps properly
4. Query methods filter and paginate correctly

HOW: Uses pytest-asyncio with in-memory SQLite database for isolation.
"""

import pytest
from datetime import datetime, timedelta

from app.dao.project import ProjectDAO
from app.models.project import Project, ProjectStatus, ProjectPriority
from tests.factories import OrganizationFactory, ProjectFactory


class TestProjectDAOCreate:
    """Tests for project creation."""

    @pytest.mark.asyncio
    async def test_create_project_success(self, db_session, test_org):
        """Test creating a project with all required fields."""
        project_dao = ProjectDAO(db_session)

        project = await project_dao.create(
            name="Test Project",
            description="Test description",
            org_id=test_org.id,
        )

        assert project.id is not None
        assert project.name == "Test Project"
        assert project.description == "Test description"
        assert project.status == ProjectStatus.DRAFT
        assert project.priority == ProjectPriority.MEDIUM
        assert project.org_id == test_org.id
        assert project.created_at is not None

    @pytest.mark.asyncio
    async def test_create_project_with_priority(self, db_session, test_org):
        """Test creating a project with custom priority."""
        project_dao = ProjectDAO(db_session)

        project = await project_dao.create(
            name="Urgent Project",
            org_id=test_org.id,
            priority=ProjectPriority.URGENT,
        )

        assert project.priority == ProjectPriority.URGENT

    @pytest.mark.asyncio
    async def test_create_project_with_dates(self, db_session, test_org):
        """Test creating a project with start and due dates."""
        project_dao = ProjectDAO(db_session)
        start = datetime.utcnow()
        due = start + timedelta(days=30)

        project = await project_dao.create(
            name="Dated Project",
            org_id=test_org.id,
            start_date=start,
            due_date=due,
            estimated_hours=40,
        )

        assert project.start_date is not None
        assert project.due_date is not None
        assert project.estimated_hours == 40


class TestProjectDAORead:
    """Tests for project read operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_and_org_success(self, db_session, test_org):
        """Test retrieving a project by ID with org-scoping."""
        project = await ProjectFactory.create(
            db_session, name="Findable Project", organization=test_org
        )

        project_dao = ProjectDAO(db_session)
        found = await project_dao.get_by_id_and_org(project.id, test_org.id)

        assert found is not None
        assert found.id == project.id
        assert found.name == "Findable Project"

    @pytest.mark.asyncio
    async def test_get_by_id_and_org_wrong_org(self, db_session):
        """Test that org-scoping prevents cross-org access."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        project = await ProjectFactory.create(
            db_session, name="Org1 Project", organization=org1
        )

        project_dao = ProjectDAO(db_session)
        # Try to access from wrong org
        found = await project_dao.get_by_id_and_org(project.id, org2.id)

        assert found is None  # Should not find project from other org

    @pytest.mark.asyncio
    async def test_get_by_org(self, db_session, test_org):
        """Test listing projects by organization."""
        # Create multiple projects
        await ProjectFactory.create(db_session, name="Project 1", organization=test_org)
        await ProjectFactory.create(db_session, name="Project 2", organization=test_org)
        await ProjectFactory.create(db_session, name="Project 3", organization=test_org)

        project_dao = ProjectDAO(db_session)
        projects = await project_dao.get_by_org(test_org.id)

        assert len(projects) == 3

    @pytest.mark.asyncio
    async def test_get_by_org_pagination(self, db_session, test_org):
        """Test pagination for project listing."""
        # Create 5 projects
        for i in range(5):
            await ProjectFactory.create(
                db_session, name=f"Project {i}", organization=test_org
            )

        project_dao = ProjectDAO(db_session)

        # Get first page
        page1 = await project_dao.get_by_org(test_org.id, skip=0, limit=2)
        assert len(page1) == 2

        # Get second page
        page2 = await project_dao.get_by_org(test_org.id, skip=2, limit=2)
        assert len(page2) == 2

        # Get remaining
        page3 = await project_dao.get_by_org(test_org.id, skip=4, limit=2)
        assert len(page3) == 1


class TestProjectDAOStatusFilters:
    """Tests for status-based filtering."""

    @pytest.mark.asyncio
    async def test_get_by_status(self, db_session, test_org):
        """Test filtering projects by status."""
        # Create projects with different statuses
        await ProjectFactory.create(
            db_session, name="Draft", status=ProjectStatus.DRAFT, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Active", status=ProjectStatus.IN_PROGRESS, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Done", status=ProjectStatus.COMPLETED, organization=test_org
        )

        project_dao = ProjectDAO(db_session)

        # Get only in-progress projects
        in_progress = await project_dao.get_by_status(
            test_org.id, ProjectStatus.IN_PROGRESS
        )

        assert len(in_progress) == 1
        assert in_progress[0].name == "Active"

    @pytest.mark.asyncio
    async def test_get_active_projects(self, db_session, test_org):
        """Test getting active (not completed/cancelled) projects."""
        await ProjectFactory.create(
            db_session, name="Draft", status=ProjectStatus.DRAFT, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Active", status=ProjectStatus.IN_PROGRESS, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Completed", status=ProjectStatus.COMPLETED, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Cancelled", status=ProjectStatus.CANCELLED, organization=test_org
        )

        project_dao = ProjectDAO(db_session)
        active = await project_dao.get_active_projects(test_org.id)

        assert len(active) == 2
        assert all(p.status not in [ProjectStatus.COMPLETED, ProjectStatus.CANCELLED] for p in active)

    @pytest.mark.asyncio
    async def test_get_overdue_projects(self, db_session, test_org):
        """Test getting overdue projects."""
        # Create overdue project
        await ProjectFactory.create_overdue(
            db_session, name="Overdue", organization=test_org
        )
        # Create future project
        await ProjectFactory.create(
            db_session,
            name="Future",
            status=ProjectStatus.IN_PROGRESS,
            organization=test_org,
            due_date=datetime.utcnow() + timedelta(days=30),
        )
        # Create completed project (not overdue even if past due)
        await ProjectFactory.create(
            db_session,
            name="Completed",
            status=ProjectStatus.COMPLETED,
            organization=test_org,
            due_date=datetime.utcnow() - timedelta(days=7),
        )

        project_dao = ProjectDAO(db_session)
        overdue = await project_dao.get_overdue_projects(test_org.id)

        assert len(overdue) == 1
        assert overdue[0].name == "Overdue"


class TestProjectDAOPriorityFilters:
    """Tests for priority-based filtering."""

    @pytest.mark.asyncio
    async def test_get_by_priority(self, db_session, test_org):
        """Test filtering projects by priority."""
        await ProjectFactory.create(
            db_session, name="Low", priority=ProjectPriority.LOW, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="High", priority=ProjectPriority.HIGH, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Urgent", priority=ProjectPriority.URGENT, organization=test_org
        )

        project_dao = ProjectDAO(db_session)
        urgent = await project_dao.get_by_priority(test_org.id, ProjectPriority.URGENT)

        assert len(urgent) == 1
        assert urgent[0].name == "Urgent"


class TestProjectDAOUpdate:
    """Tests for project update operations."""

    @pytest.mark.asyncio
    async def test_update_project(self, db_session, test_org):
        """Test updating project fields."""
        project = await ProjectFactory.create(
            db_session, name="Original", organization=test_org
        )

        project_dao = ProjectDAO(db_session)
        updated = await project_dao.update(
            project.id,
            name="Updated Name",
            description="Updated description",
        )

        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"

    @pytest.mark.asyncio
    async def test_update_status_sets_completed_at(self, db_session, test_org):
        """Test that completing a project sets completed_at."""
        project = await ProjectFactory.create_in_progress(
            db_session, name="To Complete", organization=test_org
        )
        assert project.completed_at is None

        project_dao = ProjectDAO(db_session)
        updated = await project_dao.update_status(
            project.id, test_org.id, ProjectStatus.COMPLETED
        )

        assert updated.status == ProjectStatus.COMPLETED
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_status_clears_completed_at_on_reopen(self, db_session, test_org):
        """Test that reopening a project clears completed_at."""
        # Create and complete a project
        project = await ProjectFactory.create(
            db_session,
            name="Completed",
            status=ProjectStatus.COMPLETED,
            organization=test_org,
        )
        # Manually set completed_at
        project.completed_at = datetime.utcnow()
        await db_session.flush()

        project_dao = ProjectDAO(db_session)
        # Reopen project
        updated = await project_dao.update_status(
            project.id, test_org.id, ProjectStatus.IN_PROGRESS
        )

        assert updated.status == ProjectStatus.IN_PROGRESS
        assert updated.completed_at is None

    @pytest.mark.asyncio
    async def test_update_status_wrong_org(self, db_session):
        """Test that status update fails for wrong org."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        project = await ProjectFactory.create(
            db_session, name="Org1 Project", organization=org1
        )

        project_dao = ProjectDAO(db_session)
        result = await project_dao.update_status(
            project.id, org2.id, ProjectStatus.COMPLETED
        )

        assert result is None  # Should fail


class TestProjectDAOHours:
    """Tests for hours tracking."""

    @pytest.mark.asyncio
    async def test_add_hours(self, db_session, test_org):
        """Test adding hours to a project."""
        project = await ProjectFactory.create(
            db_session,
            name="Tracked Project",
            organization=test_org,
            estimated_hours=40,
            actual_hours=0,
        )

        project_dao = ProjectDAO(db_session)

        # Add hours
        updated = await project_dao.add_hours(project.id, test_org.id, 8)
        assert updated.actual_hours == 8

        # Add more hours
        updated = await project_dao.add_hours(project.id, test_org.id, 4)
        assert updated.actual_hours == 12

    @pytest.mark.asyncio
    async def test_hours_remaining_property(self, db_session, test_org):
        """Test the hours_remaining computed property."""
        project = await ProjectFactory.create(
            db_session,
            name="Tracked Project",
            organization=test_org,
            estimated_hours=40,
            actual_hours=25,
        )

        assert project.hours_remaining == 15


class TestProjectDAOSearch:
    """Tests for project search."""

    @pytest.mark.asyncio
    async def test_search_projects_by_name(self, db_session, test_org):
        """Test searching projects by name."""
        await ProjectFactory.create(
            db_session, name="Website Automation", organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="CRM Integration", organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Email Marketing", organization=test_org
        )

        project_dao = ProjectDAO(db_session)
        results = await project_dao.search_projects(test_org.id, "automation")

        assert len(results) == 1
        assert results[0].name == "Website Automation"

    @pytest.mark.asyncio
    async def test_search_projects_by_description(self, db_session, test_org):
        """Test searching projects by description."""
        await ProjectFactory.create(
            db_session,
            name="Project A",
            description="Automate lead capture workflow",
            organization=test_org,
        )
        await ProjectFactory.create(
            db_session,
            name="Project B",
            description="Customer onboarding system",
            organization=test_org,
        )

        project_dao = ProjectDAO(db_session)
        results = await project_dao.search_projects(test_org.id, "lead")

        assert len(results) == 1
        assert results[0].name == "Project A"


class TestProjectDAOCounts:
    """Tests for count operations."""

    @pytest.mark.asyncio
    async def test_count_by_status(self, db_session, test_org):
        """Test counting projects by status."""
        await ProjectFactory.create(
            db_session, name="Draft 1", status=ProjectStatus.DRAFT, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Draft 2", status=ProjectStatus.DRAFT, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Active", status=ProjectStatus.IN_PROGRESS, organization=test_org
        )

        project_dao = ProjectDAO(db_session)
        counts = await project_dao.count_by_status(test_org.id)

        assert counts.get("draft") == 2
        assert counts.get("in_progress") == 1

    @pytest.mark.asyncio
    async def test_count_active(self, db_session, test_org):
        """Test counting active projects."""
        await ProjectFactory.create(
            db_session, name="Draft", status=ProjectStatus.DRAFT, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Active", status=ProjectStatus.IN_PROGRESS, organization=test_org
        )
        await ProjectFactory.create(
            db_session, name="Completed", status=ProjectStatus.COMPLETED, organization=test_org
        )

        project_dao = ProjectDAO(db_session)
        count = await project_dao.count_active(test_org.id)

        assert count == 2  # Draft + Active, not Completed


class TestProjectDAODelete:
    """Tests for project deletion."""

    @pytest.mark.asyncio
    async def test_delete_project(self, db_session, test_org):
        """Test deleting a project."""
        project = await ProjectFactory.create(
            db_session, name="To Delete", organization=test_org
        )

        project_dao = ProjectDAO(db_session)
        result = await project_dao.delete(project.id)

        assert result is True

        # Verify deleted
        found = await project_dao.get_by_id(project.id)
        assert found is None


class TestProjectDAOMultiTenancy:
    """Tests for multi-tenancy isolation."""

    @pytest.mark.asyncio
    async def test_projects_isolated_by_org(self, db_session):
        """Test that projects from different orgs are isolated."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        # Create projects in each org
        await ProjectFactory.create(db_session, name="Org1 Project 1", organization=org1)
        await ProjectFactory.create(db_session, name="Org1 Project 2", organization=org1)
        await ProjectFactory.create(db_session, name="Org2 Project", organization=org2)

        project_dao = ProjectDAO(db_session)

        # Verify isolation
        org1_projects = await project_dao.get_by_org(org1.id)
        org2_projects = await project_dao.get_by_org(org2.id)

        assert len(org1_projects) == 2
        assert len(org2_projects) == 1
        assert all(p.org_id == org1.id for p in org1_projects)
        assert all(p.org_id == org2.id for p in org2_projects)
