"""
Workflow Version Data Access Object (DAO).

WHAT: Database operations for the WorkflowVersion model.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for workflow version operations
3. Handles version numbering and current version tracking
4. Supports version history and rollback

HOW: Extends BaseDAO with version-specific queries:
- Version numbering (auto-increment)
- Current version management
- Version history retrieval
- Restore functionality
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.workflow import WorkflowVersion


class WorkflowVersionDAO(BaseDAO[WorkflowVersion]):
    """
    Data Access Object for WorkflowVersion model.

    WHAT: Provides CRUD and query operations for workflow versions.

    WHY: Centralizes all workflow version database operations:
    - Auto-increments version numbers
    - Manages current version flags
    - Provides version history queries

    HOW: Extends BaseDAO with version-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize WorkflowVersionDAO.

        Args:
            session: Async database session
        """
        super().__init__(WorkflowVersion, session)

    async def create_version(
        self,
        workflow_instance_id: int,
        workflow_json: Dict[str, Any],
        created_by: int,
        change_description: Optional[str] = None,
        set_as_current: bool = True,
    ) -> WorkflowVersion:
        """
        Create a new workflow version.

        WHAT: Creates a versioned snapshot of a workflow's JSON definition.

        WHY: Version history enables:
        - Rollback to previous working versions
        - Audit trail of changes
        - Understanding workflow evolution

        HOW: Auto-increments version number and optionally sets as current.

        Args:
            workflow_instance_id: ID of the workflow instance
            workflow_json: The complete workflow JSON definition
            created_by: User ID who created this version
            change_description: Optional description of what changed
            set_as_current: Whether to mark this as the current version

        Returns:
            Created WorkflowVersion
        """
        # Get the next version number
        next_version = await self._get_next_version_number(workflow_instance_id)

        # If setting as current, unset all existing current flags
        if set_as_current:
            await self._unset_current_versions(workflow_instance_id)

        # Create the new version
        version = await self.create(
            workflow_instance_id=workflow_instance_id,
            version_number=next_version,
            workflow_json=workflow_json,
            change_description=change_description,
            created_by=created_by,
            is_current=set_as_current,
        )

        return version

    async def _get_next_version_number(self, workflow_instance_id: int) -> int:
        """
        Get the next version number for a workflow.

        WHAT: Calculates the next sequential version number.

        WHY: Version numbers should be sequential and unique per workflow.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Next version number (1 if first version)
        """
        result = await self.session.execute(
            select(func.max(WorkflowVersion.version_number)).where(
                WorkflowVersion.workflow_instance_id == workflow_instance_id
            )
        )
        max_version = result.scalar_one_or_none()
        return (max_version or 0) + 1

    async def _unset_current_versions(self, workflow_instance_id: int) -> None:
        """
        Unset current flag on all versions for a workflow.

        WHAT: Sets is_current=False on all versions.

        WHY: Only one version should be current at a time.

        Args:
            workflow_instance_id: Workflow instance ID
        """
        await self.session.execute(
            update(WorkflowVersion)
            .where(WorkflowVersion.workflow_instance_id == workflow_instance_id)
            .values(is_current=False)
        )
        await self.session.flush()

    async def get_versions_for_workflow(
        self,
        workflow_instance_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> List[WorkflowVersion]:
        """
        Get all versions for a workflow, ordered by version number descending.

        WHAT: Retrieves version history for a workflow.

        WHY: Users need to see all versions to understand changes
        and select versions for comparison or restoration.

        Args:
            workflow_instance_id: Workflow instance ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of versions, newest first
        """
        result = await self.session.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_instance_id == workflow_instance_id)
            .order_by(WorkflowVersion.version_number.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_version_by_number(
        self,
        workflow_instance_id: int,
        version_number: int,
    ) -> Optional[WorkflowVersion]:
        """
        Get a specific version by workflow ID and version number.

        WHAT: Retrieves a single version by its number.

        WHY: Allows accessing specific historical versions for comparison
        or restoration.

        Args:
            workflow_instance_id: Workflow instance ID
            version_number: The version number to retrieve

        Returns:
            WorkflowVersion if found, None otherwise
        """
        result = await self.session.execute(
            select(WorkflowVersion).where(
                WorkflowVersion.workflow_instance_id == workflow_instance_id,
                WorkflowVersion.version_number == version_number,
            )
        )
        return result.scalar_one_or_none()

    async def get_current_version(
        self,
        workflow_instance_id: int,
    ) -> Optional[WorkflowVersion]:
        """
        Get the current (active) version for a workflow.

        WHAT: Retrieves the version marked as current.

        WHY: The current version is what's deployed to n8n.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Current WorkflowVersion if exists, None otherwise
        """
        result = await self.session.execute(
            select(WorkflowVersion).where(
                WorkflowVersion.workflow_instance_id == workflow_instance_id,
                WorkflowVersion.is_current == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_version(
        self,
        workflow_instance_id: int,
    ) -> Optional[WorkflowVersion]:
        """
        Get the latest version (highest version number) for a workflow.

        WHAT: Retrieves the most recent version.

        WHY: Useful when the latest version is not necessarily current
        (e.g., during rollback operations).

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Latest WorkflowVersion if exists, None otherwise
        """
        result = await self.session.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_instance_id == workflow_instance_id)
            .order_by(WorkflowVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def set_current_version(
        self,
        workflow_instance_id: int,
        version_number: int,
    ) -> Optional[WorkflowVersion]:
        """
        Set a specific version as the current version.

        WHAT: Marks a version as current and unmarks all others.

        WHY: Used for rollback operations when restoring a previous version.

        Args:
            workflow_instance_id: Workflow instance ID
            version_number: Version number to set as current

        Returns:
            Updated WorkflowVersion if found, None otherwise
        """
        # First, unset all current versions
        await self._unset_current_versions(workflow_instance_id)

        # Then set the specified version as current
        result = await self.session.execute(
            update(WorkflowVersion)
            .where(
                WorkflowVersion.workflow_instance_id == workflow_instance_id,
                WorkflowVersion.version_number == version_number,
            )
            .values(is_current=True)
            .returning(WorkflowVersion)
        )

        version = result.scalar_one_or_none()
        if version:
            await self.session.refresh(version)
        return version

    async def count_versions(self, workflow_instance_id: int) -> int:
        """
        Count the number of versions for a workflow.

        WHAT: Returns the total number of versions.

        WHY: Useful for pagination and UI display.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Number of versions
        """
        result = await self.session.execute(
            select(func.count(WorkflowVersion.id)).where(
                WorkflowVersion.workflow_instance_id == workflow_instance_id
            )
        )
        return result.scalar_one()

    async def compare_versions(
        self,
        workflow_instance_id: int,
        version_a: int,
        version_b: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get two versions for comparison.

        WHAT: Retrieves two versions side-by-side.

        WHY: Enables diff visualization between versions.

        Args:
            workflow_instance_id: Workflow instance ID
            version_a: First version number
            version_b: Second version number

        Returns:
            Dict with both versions if both exist, None otherwise
        """
        version_a_obj = await self.get_version_by_number(
            workflow_instance_id, version_a
        )
        version_b_obj = await self.get_version_by_number(
            workflow_instance_id, version_b
        )

        if not version_a_obj or not version_b_obj:
            return None

        return {
            "version_a": {
                "number": version_a_obj.version_number,
                "workflow_json": version_a_obj.workflow_json,
                "change_description": version_a_obj.change_description,
                "created_at": version_a_obj.created_at,
                "created_by": version_a_obj.created_by,
            },
            "version_b": {
                "number": version_b_obj.version_number,
                "workflow_json": version_b_obj.workflow_json,
                "change_description": version_b_obj.change_description,
                "created_at": version_b_obj.created_at,
                "created_by": version_b_obj.created_by,
            },
        }

    async def delete_versions_before(
        self,
        workflow_instance_id: int,
        keep_count: int = 10,
    ) -> int:
        """
        Delete old versions, keeping the most recent ones.

        WHAT: Removes old versions to save storage.

        WHY: Version history can grow large; pruning old versions
        manages storage while keeping recent history.

        Args:
            workflow_instance_id: Workflow instance ID
            keep_count: Number of recent versions to keep

        Returns:
            Number of versions deleted
        """
        # Get version numbers to keep
        result = await self.session.execute(
            select(WorkflowVersion.version_number)
            .where(WorkflowVersion.workflow_instance_id == workflow_instance_id)
            .order_by(WorkflowVersion.version_number.desc())
            .limit(keep_count)
        )
        versions_to_keep = [row[0] for row in result.all()]

        if not versions_to_keep:
            return 0

        # Delete versions not in the keep list
        from sqlalchemy import delete

        delete_result = await self.session.execute(
            delete(WorkflowVersion).where(
                WorkflowVersion.workflow_instance_id == workflow_instance_id,
                ~WorkflowVersion.version_number.in_(versions_to_keep),
            )
        )

        await self.session.flush()
        return delete_result.rowcount
