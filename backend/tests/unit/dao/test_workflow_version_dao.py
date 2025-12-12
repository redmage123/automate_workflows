"""
Unit tests for WorkflowVersionDAO.

WHAT: Tests for workflow version data access operations.

WHY: Ensures version history management works correctly:
- Version creation with auto-incrementing numbers
- Current version management
- Version retrieval and history
- Version comparison and restoration
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.workflow_version import WorkflowVersionDAO
from app.dao.workflow_instance import WorkflowInstanceDAO
from app.dao.n8n_environment import N8nEnvironmentDAO
from app.dao.user import UserDAO
from app.models.workflow import WorkflowVersion, WorkflowStatus


class TestWorkflowVersionDAO:
    """
    Test suite for WorkflowVersionDAO.

    WHAT: Tests all DAO methods for workflow version management.

    WHY: Verifies correct database operations and version tracking.
    """

    @pytest_asyncio.fixture
    async def setup_data(self, db_session: AsyncSession):
        """
        Set up test data.

        WHY: Creates necessary related records (org, user, env, workflow)
        for version tests.
        """
        from tests.factories import (
            OrganizationFactory,
            UserFactory,
        )

        # Create organization
        org = await OrganizationFactory.create_async(
            db_session, name="Test Org", slug="test-org"
        )

        # Create user
        user = await UserFactory.create_async(
            db_session,
            email="test@example.com",
            org_id=org.id,
        )

        # Create n8n environment
        env_dao = N8nEnvironmentDAO(db_session)
        env = await env_dao.create_environment(
            org_id=org.id,
            name="Test Environment",
            base_url="http://localhost:5678",
            api_key="test-api-key",
        )

        # Create workflow instance
        instance_dao = WorkflowInstanceDAO(db_session)
        instance = await instance_dao.create_instance(
            org_id=org.id,
            name="Test Workflow",
            n8n_environment_id=env.id,
        )

        await db_session.commit()

        return {
            "org": org,
            "user": user,
            "env": env,
            "instance": instance,
        }

    @pytest.mark.asyncio
    async def test_create_version(self, db_session: AsyncSession, setup_data):
        """
        Test creating a workflow version.

        WHAT: Creates a version and verifies it's saved correctly.

        WHY: Basic functionality test for version creation.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        workflow_json = {
            "name": "Test Workflow",
            "nodes": [{"id": "1", "type": "n8n-nodes-base.start"}],
            "connections": {},
        }

        version = await dao.create_version(
            workflow_instance_id=data["instance"].id,
            workflow_json=workflow_json,
            created_by=data["user"].id,
            change_description="Initial version",
            set_as_current=True,
        )

        assert version is not None
        assert version.version_number == 1
        assert version.workflow_json == workflow_json
        assert version.change_description == "Initial version"
        assert version.is_current is True
        assert version.created_by == data["user"].id

    @pytest.mark.asyncio
    async def test_version_number_auto_increment(
        self, db_session: AsyncSession, setup_data
    ):
        """
        Test that version numbers auto-increment.

        WHAT: Creates multiple versions and verifies sequential numbering.

        WHY: Version numbers must be sequential for proper ordering.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Create three versions
        for i in range(3):
            version = await dao.create_version(
                workflow_instance_id=data["instance"].id,
                workflow_json={"version": i + 1},
                created_by=data["user"].id,
                change_description=f"Version {i + 1}",
            )
            assert version.version_number == i + 1

    @pytest.mark.asyncio
    async def test_current_version_management(
        self, db_session: AsyncSession, setup_data
    ):
        """
        Test current version flag management.

        WHAT: Creates versions and verifies only one is current.

        WHY: Only one version should be marked as current at any time.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Create first version (current)
        v1 = await dao.create_version(
            workflow_instance_id=data["instance"].id,
            workflow_json={"v": 1},
            created_by=data["user"].id,
            set_as_current=True,
        )
        assert v1.is_current is True

        # Create second version (should become current, v1 should not be current)
        v2 = await dao.create_version(
            workflow_instance_id=data["instance"].id,
            workflow_json={"v": 2},
            created_by=data["user"].id,
            set_as_current=True,
        )
        assert v2.is_current is True

        # Refresh v1 and check it's no longer current
        await db_session.refresh(v1)
        assert v1.is_current is False

        # Verify only v2 is current
        current = await dao.get_current_version(data["instance"].id)
        assert current.version_number == 2

    @pytest.mark.asyncio
    async def test_get_versions_for_workflow(
        self, db_session: AsyncSession, setup_data
    ):
        """
        Test retrieving version history.

        WHAT: Creates versions and retrieves them in order.

        WHY: Version history must be ordered newest first.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Create multiple versions
        for i in range(5):
            await dao.create_version(
                workflow_instance_id=data["instance"].id,
                workflow_json={"v": i + 1},
                created_by=data["user"].id,
            )

        # Get versions
        versions = await dao.get_versions_for_workflow(
            data["instance"].id, skip=0, limit=10
        )

        assert len(versions) == 5
        # Should be in descending order (newest first)
        assert versions[0].version_number == 5
        assert versions[4].version_number == 1

    @pytest.mark.asyncio
    async def test_get_version_by_number(
        self, db_session: AsyncSession, setup_data
    ):
        """
        Test retrieving a specific version by number.

        WHAT: Creates versions and retrieves specific ones.

        WHY: Users need to view specific historical versions.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Create versions with distinct JSON
        for i in range(3):
            await dao.create_version(
                workflow_instance_id=data["instance"].id,
                workflow_json={"data": f"version_{i + 1}"},
                created_by=data["user"].id,
            )

        # Get version 2
        version = await dao.get_version_by_number(data["instance"].id, 2)
        assert version is not None
        assert version.version_number == 2
        assert version.workflow_json == {"data": "version_2"}

        # Non-existent version
        not_found = await dao.get_version_by_number(data["instance"].id, 99)
        assert not_found is None

    @pytest.mark.asyncio
    async def test_get_latest_version(
        self, db_session: AsyncSession, setup_data
    ):
        """
        Test retrieving the latest version.

        WHAT: Creates versions and gets the most recent one.

        WHY: Latest version is useful for display and comparison.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Create versions
        for i in range(3):
            await dao.create_version(
                workflow_instance_id=data["instance"].id,
                workflow_json={"v": i + 1},
                created_by=data["user"].id,
            )

        latest = await dao.get_latest_version(data["instance"].id)
        assert latest is not None
        assert latest.version_number == 3

    @pytest.mark.asyncio
    async def test_set_current_version(
        self, db_session: AsyncSession, setup_data
    ):
        """
        Test setting a specific version as current.

        WHAT: Creates versions and changes which one is current.

        WHY: Used for rollback operations.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Create three versions
        for i in range(3):
            await dao.create_version(
                workflow_instance_id=data["instance"].id,
                workflow_json={"v": i + 1},
                created_by=data["user"].id,
                set_as_current=(i == 2),  # Only v3 is current
            )

        # Set v1 as current
        updated = await dao.set_current_version(data["instance"].id, 1)
        assert updated is not None
        assert updated.is_current is True

        # Verify v1 is current and v3 is not
        current = await dao.get_current_version(data["instance"].id)
        assert current.version_number == 1

    @pytest.mark.asyncio
    async def test_count_versions(self, db_session: AsyncSession, setup_data):
        """
        Test counting versions for a workflow.

        WHAT: Creates versions and counts them.

        WHY: Useful for pagination and UI display.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Initially no versions
        count = await dao.count_versions(data["instance"].id)
        assert count == 0

        # Create versions
        for i in range(4):
            await dao.create_version(
                workflow_instance_id=data["instance"].id,
                workflow_json={"v": i + 1},
                created_by=data["user"].id,
            )

        count = await dao.count_versions(data["instance"].id)
        assert count == 4

    @pytest.mark.asyncio
    async def test_compare_versions(self, db_session: AsyncSession, setup_data):
        """
        Test comparing two versions.

        WHAT: Creates versions and compares them.

        WHY: Enables diff visualization between versions.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Create versions with different JSON
        await dao.create_version(
            workflow_instance_id=data["instance"].id,
            workflow_json={"nodes": [{"id": "1"}]},
            created_by=data["user"].id,
            change_description="Version 1",
        )
        await dao.create_version(
            workflow_instance_id=data["instance"].id,
            workflow_json={"nodes": [{"id": "1"}, {"id": "2"}]},
            created_by=data["user"].id,
            change_description="Version 2",
        )

        comparison = await dao.compare_versions(data["instance"].id, 1, 2)
        assert comparison is not None
        assert comparison["version_a"]["number"] == 1
        assert comparison["version_b"]["number"] == 2
        assert len(comparison["version_a"]["workflow_json"]["nodes"]) == 1
        assert len(comparison["version_b"]["workflow_json"]["nodes"]) == 2

    @pytest.mark.asyncio
    async def test_compare_versions_not_found(
        self, db_session: AsyncSession, setup_data
    ):
        """
        Test comparing with non-existent versions.

        WHAT: Attempts to compare versions that don't exist.

        WHY: Should return None gracefully.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Create only one version
        await dao.create_version(
            workflow_instance_id=data["instance"].id,
            workflow_json={"v": 1},
            created_by=data["user"].id,
        )

        # Try to compare with non-existent version
        comparison = await dao.compare_versions(data["instance"].id, 1, 99)
        assert comparison is None

    @pytest.mark.asyncio
    async def test_delete_versions_before(
        self, db_session: AsyncSession, setup_data
    ):
        """
        Test pruning old versions.

        WHAT: Creates many versions and deletes old ones.

        WHY: Version history can grow large; pruning manages storage.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Create 10 versions
        for i in range(10):
            await dao.create_version(
                workflow_instance_id=data["instance"].id,
                workflow_json={"v": i + 1},
                created_by=data["user"].id,
            )

        # Keep only 3 most recent
        deleted_count = await dao.delete_versions_before(
            data["instance"].id, keep_count=3
        )
        assert deleted_count == 7

        # Verify only 3 remain
        remaining = await dao.get_versions_for_workflow(data["instance"].id)
        assert len(remaining) == 3
        # Verify we kept the newest versions
        assert remaining[0].version_number == 10
        assert remaining[1].version_number == 9
        assert remaining[2].version_number == 8

    @pytest.mark.asyncio
    async def test_pagination(self, db_session: AsyncSession, setup_data):
        """
        Test version pagination.

        WHAT: Creates versions and retrieves with skip/limit.

        WHY: Pagination is needed for large version histories.
        """
        dao = WorkflowVersionDAO(db_session)
        data = await setup_data

        # Create 10 versions
        for i in range(10):
            await dao.create_version(
                workflow_instance_id=data["instance"].id,
                workflow_json={"v": i + 1},
                created_by=data["user"].id,
            )

        # Get first page (3 items)
        page1 = await dao.get_versions_for_workflow(
            data["instance"].id, skip=0, limit=3
        )
        assert len(page1) == 3
        assert page1[0].version_number == 10  # Newest first

        # Get second page
        page2 = await dao.get_versions_for_workflow(
            data["instance"].id, skip=3, limit=3
        )
        assert len(page2) == 3
        assert page2[0].version_number == 7
