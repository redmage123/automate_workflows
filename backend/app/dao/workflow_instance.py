"""
Workflow Instance Data Access Object (DAO).

WHAT: Database operations for the WorkflowInstance model.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for workflow instance operations
3. Enforces org-scoping for multi-tenancy
4. Handles workflow lifecycle management

HOW: Extends BaseDAO with instance-specific queries:
- Status-based filtering
- Project association
- Execution tracking
- State transitions
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.workflow import WorkflowInstance, WorkflowStatus


class WorkflowInstanceDAO(BaseDAO[WorkflowInstance]):
    """
    Data Access Object for WorkflowInstance model.

    WHAT: Provides CRUD and query operations for workflow instances.

    WHY: Centralizes all workflow instance database operations:
    - Enforces org_id scoping for security
    - Handles status state machine transitions
    - Provides workflow-specific queries

    HOW: Extends BaseDAO with instance-specific methods.
    Status transitions follow defined state machine.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize WorkflowInstanceDAO.

        Args:
            session: Async database session
        """
        super().__init__(WorkflowInstance, session)

    async def create_instance(
        self,
        org_id: int,
        name: str,
        template_id: Optional[int] = None,
        project_id: Optional[int] = None,
        n8n_environment_id: Optional[int] = None,
        n8n_workflow_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        status: WorkflowStatus = WorkflowStatus.DRAFT,
    ) -> WorkflowInstance:
        """
        Create a new workflow instance.

        WHAT: Creates a workflow instance (deployed automation).

        WHY: Instances represent active workflows:
        - Can be linked to projects for billing/tracking
        - Based on templates for consistency
        - Connected to n8n for execution

        Args:
            org_id: Organization that owns this instance
            name: Display name for the workflow
            template_id: Optional template this was based on
            project_id: Optional linked project
            n8n_environment_id: n8n environment to deploy to
            n8n_workflow_id: ID of workflow in n8n (after deployment)
            parameters: Custom parameters (merged with template defaults)
            status: Initial status (default DRAFT)

        Returns:
            Created WorkflowInstance
        """
        return await self.create(
            org_id=org_id,
            name=name,
            template_id=template_id,
            project_id=project_id,
            n8n_environment_id=n8n_environment_id,
            n8n_workflow_id=n8n_workflow_id,
            parameters=parameters,
            status=status,
        )

    async def get_by_status(
        self,
        org_id: int,
        status: WorkflowStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowInstance]:
        """
        Get workflow instances by status.

        WHAT: Filters instances by their status.

        WHY: Common use case for dashboards:
        - "Show me all active workflows"
        - "What workflows are in error state?"

        Args:
            org_id: Organization ID
            status: Workflow status to filter by
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of instances matching the status
        """
        result = await self.session.execute(
            select(WorkflowInstance)
            .where(
                WorkflowInstance.org_id == org_id,
                WorkflowInstance.status == status,
            )
            .order_by(WorkflowInstance.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_instances(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowInstance]:
        """
        Get all active (running) workflow instances.

        WHAT: Filters to only ACTIVE status.

        WHY: Common view - show currently running workflows.

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of active instances
        """
        return await self.get_by_status(
            org_id=org_id,
            status=WorkflowStatus.ACTIVE,
            skip=skip,
            limit=limit,
        )

    async def get_by_project(
        self,
        org_id: int,
        project_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowInstance]:
        """
        Get workflow instances for a project.

        WHAT: Filters instances by linked project.

        WHY: Shows all workflows associated with a project
        for project detail views.

        Args:
            org_id: Organization ID
            project_id: Project ID to filter by
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of instances for the project
        """
        result = await self.session.execute(
            select(WorkflowInstance)
            .where(
                WorkflowInstance.org_id == org_id,
                WorkflowInstance.project_id == project_id,
                WorkflowInstance.status != WorkflowStatus.DELETED,
            )
            .order_by(WorkflowInstance.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_environment(
        self,
        org_id: int,
        n8n_environment_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowInstance]:
        """
        Get workflow instances for an n8n environment.

        WHAT: Filters instances by deployment environment.

        WHY: Shows all workflows deployed to a specific n8n instance.

        Args:
            org_id: Organization ID
            n8n_environment_id: Environment ID to filter by
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of instances in the environment
        """
        result = await self.session.execute(
            select(WorkflowInstance)
            .where(
                WorkflowInstance.org_id == org_id,
                WorkflowInstance.n8n_environment_id == n8n_environment_id,
                WorkflowInstance.status != WorkflowStatus.DELETED,
            )
            .order_by(WorkflowInstance.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_n8n_workflow_id(
        self,
        org_id: int,
        n8n_workflow_id: str,
    ) -> Optional[WorkflowInstance]:
        """
        Get instance by n8n workflow ID.

        WHAT: Lookup by external n8n ID.

        WHY: Needed for webhook callbacks from n8n.

        Args:
            org_id: Organization ID
            n8n_workflow_id: Workflow ID from n8n

        Returns:
            Instance if found, None otherwise
        """
        result = await self.session.execute(
            select(WorkflowInstance)
            .where(
                WorkflowInstance.org_id == org_id,
                WorkflowInstance.n8n_workflow_id == n8n_workflow_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_execution_logs(
        self,
        instance_id: int,
        org_id: int,
    ) -> Optional[WorkflowInstance]:
        """
        Get instance with execution logs eagerly loaded.

        WHAT: Fetches instance with related logs in one query.

        WHY: Avoids N+1 queries when displaying execution history.

        Args:
            instance_id: Workflow instance ID
            org_id: Organization ID for security

        Returns:
            Instance with logs loaded, or None if not found
        """
        result = await self.session.execute(
            select(WorkflowInstance)
            .options(selectinload(WorkflowInstance.execution_logs))
            .where(
                WorkflowInstance.id == instance_id,
                WorkflowInstance.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        instance_id: int,
        org_id: int,
        new_status: WorkflowStatus,
    ) -> Optional[WorkflowInstance]:
        """
        Update workflow instance status.

        WHAT: Changes instance status with validation.

        WHY: Status changes drive workflow behavior:
        - ACTIVE: Can execute
        - PAUSED: Temporarily disabled
        - ERROR: Needs attention
        - DELETED: Soft-deleted

        Args:
            instance_id: Instance ID
            org_id: Organization ID for security
            new_status: New status to set

        Returns:
            Updated instance or None if not found
        """
        instance = await self.get_by_id_and_org(instance_id, org_id)
        if not instance:
            return None

        instance.status = new_status
        instance.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def activate(
        self,
        instance_id: int,
        org_id: int,
    ) -> Optional[WorkflowInstance]:
        """
        Activate a workflow instance.

        WHAT: Sets status to ACTIVE.

        WHY: Enables workflow execution.

        Args:
            instance_id: Instance ID
            org_id: Organization ID for security

        Returns:
            Updated instance or None if not found
        """
        return await self.update_status(instance_id, org_id, WorkflowStatus.ACTIVE)

    async def pause(
        self,
        instance_id: int,
        org_id: int,
    ) -> Optional[WorkflowInstance]:
        """
        Pause a workflow instance.

        WHAT: Sets status to PAUSED.

        WHY: Temporarily disables workflow without deleting.

        Args:
            instance_id: Instance ID
            org_id: Organization ID for security

        Returns:
            Updated instance or None if not found
        """
        return await self.update_status(instance_id, org_id, WorkflowStatus.PAUSED)

    async def set_error(
        self,
        instance_id: int,
        org_id: int,
    ) -> Optional[WorkflowInstance]:
        """
        Mark workflow instance as errored.

        WHAT: Sets status to ERROR.

        WHY: Flags workflow for attention after failure.

        Args:
            instance_id: Instance ID
            org_id: Organization ID for security

        Returns:
            Updated instance or None if not found
        """
        return await self.update_status(instance_id, org_id, WorkflowStatus.ERROR)

    async def soft_delete(
        self,
        instance_id: int,
        org_id: int,
    ) -> Optional[WorkflowInstance]:
        """
        Soft-delete a workflow instance.

        WHAT: Sets status to DELETED.

        WHY: Preserves historical data while hiding from views.

        Args:
            instance_id: Instance ID
            org_id: Organization ID for security

        Returns:
            Updated instance or None if not found
        """
        return await self.update_status(instance_id, org_id, WorkflowStatus.DELETED)

    async def update_n8n_workflow_id(
        self,
        instance_id: int,
        org_id: int,
        n8n_workflow_id: str,
    ) -> Optional[WorkflowInstance]:
        """
        Set the n8n workflow ID after deployment.

        WHAT: Links instance to deployed n8n workflow.

        WHY: Enables execution and status tracking.

        Args:
            instance_id: Instance ID
            org_id: Organization ID for security
            n8n_workflow_id: Workflow ID from n8n

        Returns:
            Updated instance or None if not found
        """
        instance = await self.get_by_id_and_org(instance_id, org_id)
        if not instance:
            return None

        instance.n8n_workflow_id = n8n_workflow_id
        instance.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update_last_execution(
        self,
        instance_id: int,
        org_id: int,
    ) -> Optional[WorkflowInstance]:
        """
        Update last execution timestamp.

        WHAT: Sets last_execution_at to now.

        WHY: Tracks when workflow last ran for monitoring.

        Args:
            instance_id: Instance ID
            org_id: Organization ID for security

        Returns:
            Updated instance or None if not found
        """
        instance = await self.get_by_id_and_org(instance_id, org_id)
        if not instance:
            return None

        instance.last_execution_at = datetime.utcnow()
        instance.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def count_by_status(self, org_id: int) -> Dict[str, int]:
        """
        Get count of instances by status.

        WHAT: Aggregate instance counts by status.

        WHY: Dashboard statistics.

        Args:
            org_id: Organization ID

        Returns:
            Dict mapping status to count
        """
        result = await self.session.execute(
            select(WorkflowInstance.status, func.count(WorkflowInstance.id))
            .where(WorkflowInstance.org_id == org_id)
            .group_by(WorkflowInstance.status)
        )

        return {row[0].value: row[1] for row in result.all()}

    async def count_active(self, org_id: int) -> int:
        """
        Count active instances for an organization.

        WHAT: Count instances with ACTIVE status.

        WHY: Quick metric for dashboard.

        Args:
            org_id: Organization ID

        Returns:
            Number of active instances
        """
        result = await self.session.execute(
            select(func.count(WorkflowInstance.id))
            .where(
                WorkflowInstance.org_id == org_id,
                WorkflowInstance.status == WorkflowStatus.ACTIVE,
            )
        )
        return result.scalar_one()

    async def get_non_deleted(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowInstance]:
        """
        Get all non-deleted instances.

        WHAT: Filters out DELETED status.

        WHY: Standard list view excludes soft-deleted items.

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of non-deleted instances
        """
        result = await self.session.execute(
            select(WorkflowInstance)
            .where(
                WorkflowInstance.org_id == org_id,
                WorkflowInstance.status != WorkflowStatus.DELETED,
            )
            .order_by(WorkflowInstance.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def search_instances(
        self,
        org_id: int,
        query: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowInstance]:
        """
        Search instances by name.

        WHAT: Full-text search on instance name.

        WHY: Enable users to find workflows quickly.

        Args:
            org_id: Organization ID
            query: Search query string
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of matching instances
        """
        search_pattern = f"%{query}%"
        result = await self.session.execute(
            select(WorkflowInstance)
            .where(
                WorkflowInstance.org_id == org_id,
                WorkflowInstance.status != WorkflowStatus.DELETED,
                WorkflowInstance.name.ilike(search_pattern),
            )
            .order_by(WorkflowInstance.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
