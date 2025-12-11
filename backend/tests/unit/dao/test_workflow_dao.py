"""
Unit tests for Workflow DAOs.

WHAT: Tests for N8nEnvironmentDAO, WorkflowTemplateDAO, WorkflowInstanceDAO, ExecutionLogDAO.

WHY: Verifies that:
1. CRUD operations work correctly
2. Org-scoping is enforced for security
3. Status transitions work properly
4. API key encryption/decryption works
5. Query methods filter and paginate correctly

HOW: Uses pytest-asyncio with in-memory SQLite database for isolation.
"""

import pytest
from datetime import datetime, timedelta

from app.dao.n8n_environment import N8nEnvironmentDAO
from app.dao.workflow_template import WorkflowTemplateDAO
from app.dao.workflow_instance import WorkflowInstanceDAO
from app.dao.execution_log import ExecutionLogDAO
from app.models.workflow import WorkflowStatus, ExecutionStatus
from tests.factories import (
    OrganizationFactory,
    N8nEnvironmentFactory,
    WorkflowTemplateFactory,
    WorkflowInstanceFactory,
    ExecutionLogFactory,
)


# ============================================================================
# N8nEnvironment DAO Tests
# ============================================================================


class TestN8nEnvironmentDAOCreate:
    """Tests for n8n environment creation."""

    @pytest.mark.asyncio
    async def test_create_environment_success(self, db_session, test_org):
        """Test creating an environment with API key encryption."""
        env_dao = N8nEnvironmentDAO(db_session)

        env = await env_dao.create_environment(
            org_id=test_org.id,
            name="Production n8n",
            base_url="https://n8n.example.com",
            api_key="my-secret-api-key",
            webhook_url="https://hooks.example.com/n8n",
        )

        assert env.id is not None
        assert env.name == "Production n8n"
        assert env.base_url == "https://n8n.example.com"
        assert env.is_active is True
        # API key should be encrypted (not plain text)
        assert env.api_key_encrypted != "my-secret-api-key"
        assert len(env.api_key_encrypted) > 0

    @pytest.mark.asyncio
    async def test_api_key_decryption(self, db_session, test_org):
        """Test that API key can be decrypted correctly."""
        env_dao = N8nEnvironmentDAO(db_session)
        original_key = "my-secret-api-key-12345"

        env = await env_dao.create_environment(
            org_id=test_org.id,
            name="Test n8n",
            base_url="https://n8n.test.com",
            api_key=original_key,
        )

        # Decrypt and verify
        decrypted = env_dao.get_decrypted_api_key(env)
        assert decrypted == original_key


class TestN8nEnvironmentDAORead:
    """Tests for n8n environment read operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_and_org(self, db_session, test_org):
        """Test retrieving environment by ID with org-scoping."""
        env = await N8nEnvironmentFactory.create(
            db_session, name="Findable Env", organization=test_org
        )

        env_dao = N8nEnvironmentDAO(db_session)
        found = await env_dao.get_by_id_and_org(env.id, test_org.id)

        assert found is not None
        assert found.name == "Findable Env"

    @pytest.mark.asyncio
    async def test_get_by_id_and_org_wrong_org(self, db_session):
        """Test that org-scoping prevents cross-org access."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        env = await N8nEnvironmentFactory.create(
            db_session, name="Org1 Env", organization=org1
        )

        env_dao = N8nEnvironmentDAO(db_session)
        found = await env_dao.get_by_id_and_org(env.id, org2.id)

        assert found is None

    @pytest.mark.asyncio
    async def test_get_active_environments(self, db_session, test_org):
        """Test getting only active environments."""
        await N8nEnvironmentFactory.create(
            db_session, name="Active Env", is_active=True, organization=test_org
        )
        await N8nEnvironmentFactory.create(
            db_session, name="Inactive Env", is_active=False, organization=test_org
        )

        env_dao = N8nEnvironmentDAO(db_session)
        active = await env_dao.get_active_environments(test_org.id)

        assert len(active) == 1
        assert active[0].name == "Active Env"

    @pytest.mark.asyncio
    async def test_get_by_name(self, db_session, test_org):
        """Test getting environment by name."""
        await N8nEnvironmentFactory.create(
            db_session, name="Unique Name", organization=test_org
        )

        env_dao = N8nEnvironmentDAO(db_session)
        found = await env_dao.get_by_name(test_org.id, "Unique Name")

        assert found is not None
        assert found.name == "Unique Name"


class TestN8nEnvironmentDAOUpdate:
    """Tests for n8n environment update operations."""

    @pytest.mark.asyncio
    async def test_update_environment(self, db_session, test_org):
        """Test updating environment fields."""
        env = await N8nEnvironmentFactory.create(
            db_session, name="Original", organization=test_org
        )

        env_dao = N8nEnvironmentDAO(db_session)
        updated = await env_dao.update_environment(
            environment_id=env.id,
            org_id=test_org.id,
            name="Updated Name",
            base_url="https://new-url.com",
        )

        assert updated.name == "Updated Name"
        assert updated.base_url == "https://new-url.com"

    @pytest.mark.asyncio
    async def test_update_api_key(self, db_session, test_org):
        """Test updating API key re-encrypts it."""
        env_dao = N8nEnvironmentDAO(db_session)
        env = await env_dao.create_environment(
            org_id=test_org.id,
            name="Test",
            base_url="https://test.com",
            api_key="old-key",
        )
        old_encrypted = env.api_key_encrypted

        updated = await env_dao.update_environment(
            environment_id=env.id,
            org_id=test_org.id,
            api_key="new-secret-key",
        )

        # Encrypted value should change
        assert updated.api_key_encrypted != old_encrypted
        # New key should decrypt correctly
        assert env_dao.get_decrypted_api_key(updated) == "new-secret-key"

    @pytest.mark.asyncio
    async def test_deactivate_environment(self, db_session, test_org):
        """Test deactivating an environment."""
        env = await N8nEnvironmentFactory.create(
            db_session, name="To Deactivate", is_active=True, organization=test_org
        )

        env_dao = N8nEnvironmentDAO(db_session)
        updated = await env_dao.deactivate(env.id, test_org.id)

        assert updated.is_active is False


# ============================================================================
# WorkflowTemplate DAO Tests
# ============================================================================


class TestWorkflowTemplateDAOCreate:
    """Tests for workflow template creation."""

    @pytest.mark.asyncio
    async def test_create_public_template(self, db_session):
        """Test creating a public template."""
        template_dao = WorkflowTemplateDAO(db_session)

        template = await template_dao.create_template(
            name="Email Notification",
            description="Sends email when triggered",
            category="notifications",
            is_public=True,
        )

        assert template.id is not None
        assert template.name == "Email Notification"
        assert template.is_public is True
        assert template.created_by_org_id is None

    @pytest.mark.asyncio
    async def test_create_private_template(self, db_session, test_org):
        """Test creating a private org-specific template."""
        template_dao = WorkflowTemplateDAO(db_session)

        template = await template_dao.create_template(
            name="Custom Workflow",
            description="Org-specific automation",
            is_public=False,
            created_by_org_id=test_org.id,
        )

        assert template.is_public is False
        assert template.created_by_org_id == test_org.id


class TestWorkflowTemplateDAORead:
    """Tests for workflow template read operations."""

    @pytest.mark.asyncio
    async def test_get_public_templates(self, db_session, test_org):
        """Test getting public templates."""
        # Create public template
        await WorkflowTemplateFactory.create(
            db_session, name="Public Template", is_public=True
        )
        # Create private template
        await WorkflowTemplateFactory.create_private(
            db_session, name="Private Template", organization=test_org
        )

        template_dao = WorkflowTemplateDAO(db_session)
        public = await template_dao.get_public_templates()

        assert len(public) == 1
        assert public[0].name == "Public Template"

    @pytest.mark.asyncio
    async def test_get_available_templates(self, db_session, test_org):
        """Test getting templates available to an org (public + org's private)."""
        org2 = await OrganizationFactory.create(db_session, name="Other Org")

        # Public template
        await WorkflowTemplateFactory.create(
            db_session, name="Public", is_public=True
        )
        # test_org's private template
        await WorkflowTemplateFactory.create_private(
            db_session, name="My Private", organization=test_org
        )
        # Other org's private template
        await WorkflowTemplateFactory.create_private(
            db_session, name="Other Private", organization=org2
        )

        template_dao = WorkflowTemplateDAO(db_session)
        available = await template_dao.get_available_templates(test_org.id)

        assert len(available) == 2
        names = [t.name for t in available]
        assert "Public" in names
        assert "My Private" in names
        assert "Other Private" not in names

    @pytest.mark.asyncio
    async def test_get_by_category(self, db_session):
        """Test filtering templates by category."""
        await WorkflowTemplateFactory.create(
            db_session, name="Email 1", category="notifications"
        )
        await WorkflowTemplateFactory.create(
            db_session, name="Email 2", category="notifications"
        )
        await WorkflowTemplateFactory.create(
            db_session, name="Data Sync", category="data"
        )

        template_dao = WorkflowTemplateDAO(db_session)
        notifications = await template_dao.get_by_category("notifications")

        assert len(notifications) == 2
        assert all(t.category == "notifications" for t in notifications)

    @pytest.mark.asyncio
    async def test_get_categories(self, db_session):
        """Test getting unique categories."""
        await WorkflowTemplateFactory.create(db_session, name="T1", category="email")
        await WorkflowTemplateFactory.create(db_session, name="T2", category="email")
        await WorkflowTemplateFactory.create(db_session, name="T3", category="slack")
        await WorkflowTemplateFactory.create(db_session, name="T4", category="data")

        template_dao = WorkflowTemplateDAO(db_session)
        categories = await template_dao.get_categories()

        assert len(categories) == 3
        assert set(categories) == {"email", "slack", "data"}


class TestWorkflowTemplateDAOSearch:
    """Tests for template search."""

    @pytest.mark.asyncio
    async def test_search_templates(self, db_session):
        """Test searching templates by name and description."""
        await WorkflowTemplateFactory.create(
            db_session, name="Email Automation", description="Sends email on trigger"
        )
        await WorkflowTemplateFactory.create(
            db_session, name="Slack Notify", description="Posts to Slack channel"
        )

        template_dao = WorkflowTemplateDAO(db_session)

        # Search by name
        results = await template_dao.search_templates("email")
        assert len(results) == 1
        assert results[0].name == "Email Automation"

        # Search by description
        results = await template_dao.search_templates("slack")
        assert len(results) == 1


# ============================================================================
# WorkflowInstance DAO Tests
# ============================================================================


class TestWorkflowInstanceDAOCreate:
    """Tests for workflow instance creation."""

    @pytest.mark.asyncio
    async def test_create_instance(self, db_session, test_org):
        """Test creating a workflow instance."""
        instance_dao = WorkflowInstanceDAO(db_session)

        instance = await instance_dao.create_instance(
            org_id=test_org.id,
            name="My Workflow",
            parameters={"key": "value"},
        )

        assert instance.id is not None
        assert instance.name == "My Workflow"
        assert instance.status == WorkflowStatus.DRAFT
        assert instance.parameters == {"key": "value"}


class TestWorkflowInstanceDAOStatus:
    """Tests for workflow instance status operations."""

    @pytest.mark.asyncio
    async def test_get_by_status(self, db_session, test_org):
        """Test filtering instances by status."""
        await WorkflowInstanceFactory.create(
            db_session, name="Draft", status=WorkflowStatus.DRAFT, organization=test_org
        )
        await WorkflowInstanceFactory.create_active(
            db_session, name="Active", organization=test_org
        )

        instance_dao = WorkflowInstanceDAO(db_session)
        active = await instance_dao.get_by_status(test_org.id, WorkflowStatus.ACTIVE)

        assert len(active) == 1
        assert active[0].name == "Active"

    @pytest.mark.asyncio
    async def test_activate_workflow(self, db_session, test_org):
        """Test activating a workflow."""
        instance = await WorkflowInstanceFactory.create(
            db_session, name="To Activate", organization=test_org
        )

        instance_dao = WorkflowInstanceDAO(db_session)
        updated = await instance_dao.activate(instance.id, test_org.id)

        assert updated.status == WorkflowStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_pause_workflow(self, db_session, test_org):
        """Test pausing a workflow."""
        instance = await WorkflowInstanceFactory.create_active(
            db_session, name="To Pause", organization=test_org
        )

        instance_dao = WorkflowInstanceDAO(db_session)
        updated = await instance_dao.pause(instance.id, test_org.id)

        assert updated.status == WorkflowStatus.PAUSED

    @pytest.mark.asyncio
    async def test_soft_delete_workflow(self, db_session, test_org):
        """Test soft-deleting a workflow."""
        instance = await WorkflowInstanceFactory.create(
            db_session, name="To Delete", organization=test_org
        )

        instance_dao = WorkflowInstanceDAO(db_session)
        updated = await instance_dao.soft_delete(instance.id, test_org.id)

        assert updated.status == WorkflowStatus.DELETED


class TestWorkflowInstanceDAOMultiTenancy:
    """Tests for workflow instance multi-tenancy."""

    @pytest.mark.asyncio
    async def test_instances_isolated_by_org(self, db_session):
        """Test that instances from different orgs are isolated."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        await WorkflowInstanceFactory.create(db_session, name="Org1 WF", organization=org1)
        await WorkflowInstanceFactory.create(db_session, name="Org2 WF", organization=org2)

        instance_dao = WorkflowInstanceDAO(db_session)

        org1_instances = await instance_dao.get_by_org(org1.id)
        org2_instances = await instance_dao.get_by_org(org2.id)

        assert len(org1_instances) == 1
        assert len(org2_instances) == 1
        assert org1_instances[0].org_id == org1.id
        assert org2_instances[0].org_id == org2.id


class TestWorkflowInstanceDAOCounts:
    """Tests for workflow instance count operations."""

    @pytest.mark.asyncio
    async def test_count_by_status(self, db_session, test_org):
        """Test counting instances by status."""
        await WorkflowInstanceFactory.create(
            db_session, name="D1", status=WorkflowStatus.DRAFT, organization=test_org
        )
        await WorkflowInstanceFactory.create(
            db_session, name="D2", status=WorkflowStatus.DRAFT, organization=test_org
        )
        await WorkflowInstanceFactory.create_active(
            db_session, name="A1", organization=test_org
        )

        instance_dao = WorkflowInstanceDAO(db_session)
        counts = await instance_dao.count_by_status(test_org.id)

        assert counts.get("draft") == 2
        assert counts.get("active") == 1


# ============================================================================
# ExecutionLog DAO Tests
# ============================================================================


class TestExecutionLogDAOCreate:
    """Tests for execution log creation."""

    @pytest.mark.asyncio
    async def test_create_log(self, db_session, test_org):
        """Test creating an execution log."""
        instance = await WorkflowInstanceFactory.create_active(
            db_session, name="Test WF", organization=test_org
        )

        log_dao = ExecutionLogDAO(db_session)
        log = await log_dao.create_log(
            workflow_instance_id=instance.id,
            n8n_execution_id="exec-123",
            input_data={"trigger": "test"},
        )

        assert log.id is not None
        assert log.status == ExecutionStatus.RUNNING
        assert log.n8n_execution_id == "exec-123"
        assert log.input_data == {"trigger": "test"}


class TestExecutionLogDAOComplete:
    """Tests for completing execution logs."""

    @pytest.mark.asyncio
    async def test_complete_execution_success(self, db_session, test_org):
        """Test completing an execution as successful."""
        instance = await WorkflowInstanceFactory.create_active(
            db_session, name="Test WF", organization=test_org
        )
        log = await ExecutionLogFactory.create(
            db_session, workflow_instance_id=instance.id
        )

        log_dao = ExecutionLogDAO(db_session)
        completed = await log_dao.complete_execution(
            log_id=log.id,
            status=ExecutionStatus.SUCCESS,
            output_data={"result": "done"},
        )

        assert completed.status == ExecutionStatus.SUCCESS
        assert completed.finished_at is not None
        assert completed.output_data == {"result": "done"}

    @pytest.mark.asyncio
    async def test_complete_execution_failed(self, db_session, test_org):
        """Test completing an execution as failed."""
        instance = await WorkflowInstanceFactory.create_active(
            db_session, name="Test WF", organization=test_org
        )
        log = await ExecutionLogFactory.create(
            db_session, workflow_instance_id=instance.id
        )

        log_dao = ExecutionLogDAO(db_session)
        completed = await log_dao.complete_execution(
            log_id=log.id,
            status=ExecutionStatus.FAILED,
            error_message="Connection timeout",
        )

        assert completed.status == ExecutionStatus.FAILED
        assert completed.error_message == "Connection timeout"


class TestExecutionLogDAORead:
    """Tests for execution log read operations."""

    @pytest.mark.asyncio
    async def test_get_by_instance(self, db_session, test_org):
        """Test getting logs for a workflow instance."""
        instance = await WorkflowInstanceFactory.create_active(
            db_session, name="Test WF", organization=test_org
        )

        # Create multiple logs
        await ExecutionLogFactory.create(
            db_session, workflow_instance_id=instance.id, n8n_execution_id="exec-1"
        )
        await ExecutionLogFactory.create(
            db_session, workflow_instance_id=instance.id, n8n_execution_id="exec-2"
        )

        log_dao = ExecutionLogDAO(db_session)
        logs = await log_dao.get_by_instance(instance.id)

        assert len(logs) == 2

    @pytest.mark.asyncio
    async def test_get_latest_execution(self, db_session, test_org):
        """Test getting the most recent execution."""
        instance = await WorkflowInstanceFactory.create_active(
            db_session, name="Test WF", organization=test_org
        )

        # Create logs
        await ExecutionLogFactory.create(
            db_session, workflow_instance_id=instance.id, n8n_execution_id="exec-old"
        )
        await ExecutionLogFactory.create(
            db_session, workflow_instance_id=instance.id, n8n_execution_id="exec-new"
        )

        log_dao = ExecutionLogDAO(db_session)
        latest = await log_dao.get_latest_execution(instance.id)

        assert latest is not None
        # Most recent should be returned first
        assert latest.n8n_execution_id == "exec-new"


class TestExecutionLogDAOMetrics:
    """Tests for execution log metrics."""

    @pytest.mark.asyncio
    async def test_count_by_status(self, db_session, test_org):
        """Test counting logs by status."""
        instance = await WorkflowInstanceFactory.create_active(
            db_session, name="Test WF", organization=test_org
        )

        # Create logs with different statuses
        await ExecutionLogFactory.create_completed(
            db_session, workflow_instance_id=instance.id, success=True
        )
        await ExecutionLogFactory.create_completed(
            db_session, workflow_instance_id=instance.id, success=True
        )
        await ExecutionLogFactory.create_completed(
            db_session, workflow_instance_id=instance.id, success=False
        )

        log_dao = ExecutionLogDAO(db_session)
        counts = await log_dao.count_by_status(instance.id)

        assert counts.get("success") == 2
        assert counts.get("failed") == 1

    @pytest.mark.asyncio
    async def test_get_success_rate(self, db_session, test_org):
        """Test calculating success rate."""
        instance = await WorkflowInstanceFactory.create_active(
            db_session, name="Test WF", organization=test_org
        )

        # Create 3 successful, 1 failed
        for _ in range(3):
            await ExecutionLogFactory.create_completed(
                db_session, workflow_instance_id=instance.id, success=True
            )
        await ExecutionLogFactory.create_completed(
            db_session, workflow_instance_id=instance.id, success=False
        )

        log_dao = ExecutionLogDAO(db_session)
        rate = await log_dao.get_success_rate(instance.id)

        assert rate == 0.75  # 3 out of 4
