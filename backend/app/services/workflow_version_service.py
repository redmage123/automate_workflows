"""
Workflow Version Service.

WHAT: Business logic for workflow version management.

WHY: The service layer:
1. Encapsulates business logic separate from data access
2. Handles authorization checks
3. Coordinates between DAOs
4. Provides transaction management

HOW: Provides methods for:
- Creating versions
- Retrieving version history
- Restoring previous versions
- Comparing versions
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.workflow_version import WorkflowVersionDAO
from app.dao.workflow_instance import WorkflowInstanceDAO
from app.dao.user import UserDAO
from app.models.workflow import WorkflowVersion, WorkflowInstance
from app.core.exceptions import (
    WorkflowNotFoundError,
    WorkflowVersionNotFoundError,
    WorkflowVersionRestoreError,
    AuthorizationError,
)


class WorkflowVersionService:
    """
    Service for workflow version management.

    WHAT: Provides business logic for workflow versioning.

    WHY: Versioning enables:
    - Rollback to previous working versions
    - Audit trail of changes
    - Safe experimentation with workflow changes

    HOW: Coordinates between WorkflowVersionDAO and WorkflowInstanceDAO,
    enforcing business rules and authorization.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize WorkflowVersionService.

        Args:
            session: Async database session
        """
        self.session = session
        self.version_dao = WorkflowVersionDAO(session)
        self.instance_dao = WorkflowInstanceDAO(session)
        self.user_dao = UserDAO(session)

    async def create_version(
        self,
        workflow_instance_id: int,
        org_id: int,
        user_id: int,
        workflow_json: Dict[str, Any],
        change_description: Optional[str] = None,
        set_as_current: bool = True,
    ) -> WorkflowVersion:
        """
        Create a new version of a workflow.

        WHAT: Creates a versioned snapshot of the workflow JSON.

        WHY: Every significant change to a workflow should be versioned
        to enable rollback and provide an audit trail.

        HOW: Validates ownership, auto-increments version number,
        and optionally sets as current.

        Args:
            workflow_instance_id: ID of the workflow to version
            org_id: Organization ID for authorization
            user_id: User creating the version
            workflow_json: The complete workflow JSON definition
            change_description: Optional description of changes
            set_as_current: Whether to mark as current version

        Returns:
            Created WorkflowVersion

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist or wrong org
        """
        # Verify workflow exists and belongs to org
        workflow = await self.instance_dao.get_by_id_and_org(
            workflow_instance_id, org_id
        )
        if not workflow:
            raise WorkflowNotFoundError(
                message="Workflow not found",
                workflow_instance_id=workflow_instance_id,
            )

        # Create the version
        version = await self.version_dao.create_version(
            workflow_instance_id=workflow_instance_id,
            workflow_json=workflow_json,
            created_by=user_id,
            change_description=change_description,
            set_as_current=set_as_current,
        )

        return version

    async def get_versions(
        self,
        workflow_instance_id: int,
        org_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get version history for a workflow.

        WHAT: Retrieves all versions with pagination.

        WHY: Users need to see version history to understand changes
        and select versions for restoration.

        Args:
            workflow_instance_id: ID of the workflow
            org_id: Organization ID for authorization
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dict with versions, total count, and current version info

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist or wrong org
        """
        # Verify workflow exists and belongs to org
        workflow = await self.instance_dao.get_by_id_and_org(
            workflow_instance_id, org_id
        )
        if not workflow:
            raise WorkflowNotFoundError(
                message="Workflow not found",
                workflow_instance_id=workflow_instance_id,
            )

        # Get versions
        versions = await self.version_dao.get_versions_for_workflow(
            workflow_instance_id, skip, limit
        )

        # Get total count
        total = await self.version_dao.count_versions(workflow_instance_id)

        # Get current version number
        current_version = await self.version_dao.get_current_version(
            workflow_instance_id
        )
        current_version_number = (
            current_version.version_number if current_version else None
        )

        # Enrich with creator emails
        enriched_versions = []
        for version in versions:
            creator = await self.user_dao.get_by_id(version.created_by)
            enriched_versions.append({
                "version": version,
                "created_by_email": creator.email if creator else None,
            })

        return {
            "items": enriched_versions,
            "total": total,
            "workflow_instance_id": workflow_instance_id,
            "current_version": current_version_number,
        }

    async def get_version(
        self,
        workflow_instance_id: int,
        version_number: int,
        org_id: int,
    ) -> WorkflowVersion:
        """
        Get a specific workflow version.

        WHAT: Retrieves a single version by number.

        WHY: Allows viewing specific historical versions.

        Args:
            workflow_instance_id: ID of the workflow
            version_number: Version number to retrieve
            org_id: Organization ID for authorization

        Returns:
            WorkflowVersion

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist or wrong org
            WorkflowVersionNotFoundError: If version doesn't exist
        """
        # Verify workflow exists and belongs to org
        workflow = await self.instance_dao.get_by_id_and_org(
            workflow_instance_id, org_id
        )
        if not workflow:
            raise WorkflowNotFoundError(
                message="Workflow not found",
                workflow_instance_id=workflow_instance_id,
            )

        # Get version
        version = await self.version_dao.get_version_by_number(
            workflow_instance_id, version_number
        )
        if not version:
            raise WorkflowVersionNotFoundError(
                message=f"Version {version_number} not found",
                workflow_instance_id=workflow_instance_id,
                version_number=version_number,
            )

        return version

    async def restore_version(
        self,
        workflow_instance_id: int,
        version_number: int,
        org_id: int,
        user_id: int,
        restore_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Restore a previous workflow version.

        WHAT: Creates a new version based on a historical version's JSON.

        WHY: Enables rollback when a workflow change causes problems.

        HOW: Copies the historical version's JSON to a new version,
        setting it as current. Does NOT modify the original version.

        Args:
            workflow_instance_id: ID of the workflow
            version_number: Version number to restore
            org_id: Organization ID for authorization
            user_id: User performing the restoration
            restore_description: Optional description of why restoring

        Returns:
            Dict with message, new version info

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist or wrong org
            WorkflowVersionNotFoundError: If version doesn't exist
        """
        # Verify workflow exists and belongs to org
        workflow = await self.instance_dao.get_by_id_and_org(
            workflow_instance_id, org_id
        )
        if not workflow:
            raise WorkflowNotFoundError(
                message="Workflow not found",
                workflow_instance_id=workflow_instance_id,
            )

        # Get version to restore
        version_to_restore = await self.version_dao.get_version_by_number(
            workflow_instance_id, version_number
        )
        if not version_to_restore:
            raise WorkflowVersionNotFoundError(
                message=f"Version {version_number} not found",
                workflow_instance_id=workflow_instance_id,
                version_number=version_number,
            )

        # Create description for the restoration
        description = restore_description or f"Restored from version {version_number}"
        if version_to_restore.change_description:
            description += f" ({version_to_restore.change_description})"

        # Create a new version with the restored JSON
        new_version = await self.version_dao.create_version(
            workflow_instance_id=workflow_instance_id,
            workflow_json=version_to_restore.workflow_json,
            created_by=user_id,
            change_description=description,
            set_as_current=True,
        )

        # Get creator email for response
        creator = await self.user_dao.get_by_id(user_id)

        return {
            "message": f"Successfully restored version {version_number}",
            "restored_version": new_version,
            "created_by_email": creator.email if creator else None,
            "new_version_number": new_version.version_number,
        }

    async def compare_versions(
        self,
        workflow_instance_id: int,
        version_a: int,
        version_b: int,
        org_id: int,
    ) -> Dict[str, Any]:
        """
        Compare two workflow versions.

        WHAT: Retrieves two versions for side-by-side comparison.

        WHY: Enables understanding what changed between versions.

        Args:
            workflow_instance_id: ID of the workflow
            version_a: First version number
            version_b: Second version number
            org_id: Organization ID for authorization

        Returns:
            Dict with both versions' details

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist or wrong org
            WorkflowVersionNotFoundError: If either version doesn't exist
        """
        # Verify workflow exists and belongs to org
        workflow = await self.instance_dao.get_by_id_and_org(
            workflow_instance_id, org_id
        )
        if not workflow:
            raise WorkflowNotFoundError(
                message="Workflow not found",
                workflow_instance_id=workflow_instance_id,
            )

        # Get comparison
        comparison = await self.version_dao.compare_versions(
            workflow_instance_id, version_a, version_b
        )
        if not comparison:
            raise WorkflowVersionNotFoundError(
                message=f"One or both versions not found: {version_a}, {version_b}",
                workflow_instance_id=workflow_instance_id,
            )

        return comparison

    async def get_current_version(
        self,
        workflow_instance_id: int,
        org_id: int,
    ) -> Optional[WorkflowVersion]:
        """
        Get the current (active) version for a workflow.

        WHAT: Retrieves the version marked as current.

        WHY: The current version is what's deployed to n8n.

        Args:
            workflow_instance_id: ID of the workflow
            org_id: Organization ID for authorization

        Returns:
            Current WorkflowVersion if exists, None otherwise

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist or wrong org
        """
        # Verify workflow exists and belongs to org
        workflow = await self.instance_dao.get_by_id_and_org(
            workflow_instance_id, org_id
        )
        if not workflow:
            raise WorkflowNotFoundError(
                message="Workflow not found",
                workflow_instance_id=workflow_instance_id,
            )

        return await self.version_dao.get_current_version(workflow_instance_id)

    async def prune_old_versions(
        self,
        workflow_instance_id: int,
        org_id: int,
        keep_count: int = 10,
    ) -> int:
        """
        Delete old versions, keeping the most recent ones.

        WHAT: Removes old versions to manage storage.

        WHY: Version history can grow large; pruning old versions
        keeps storage manageable while retaining recent history.

        Args:
            workflow_instance_id: ID of the workflow
            org_id: Organization ID for authorization
            keep_count: Number of recent versions to keep

        Returns:
            Number of versions deleted

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist or wrong org
        """
        # Verify workflow exists and belongs to org
        workflow = await self.instance_dao.get_by_id_and_org(
            workflow_instance_id, org_id
        )
        if not workflow:
            raise WorkflowNotFoundError(
                message="Workflow not found",
                workflow_instance_id=workflow_instance_id,
            )

        return await self.version_dao.delete_versions_before(
            workflow_instance_id, keep_count
        )
