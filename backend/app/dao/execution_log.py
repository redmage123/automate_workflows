"""
Execution Log Data Access Object (DAO).

WHAT: Database operations for the ExecutionLog model.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for execution log operations
3. Supports immutable audit trail
4. Enables execution history queries

HOW: Extends BaseDAO with log-specific queries:
- Status-based filtering
- Time-based queries
- Aggregation for metrics
- Append-only operations (logs are immutable)

Security Considerations (OWASP):
- A09: Logs are append-only for audit integrity
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.workflow import ExecutionLog, ExecutionStatus


class ExecutionLogDAO(BaseDAO[ExecutionLog]):
    """
    Data Access Object for ExecutionLog model.

    WHAT: Provides CRUD and query operations for execution logs.

    WHY: Centralizes all execution log database operations:
    - Append-only for audit integrity
    - Status tracking
    - Performance metrics

    HOW: Extends BaseDAO with log-specific methods.
    Logs are immutable once created (no update/delete).
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize ExecutionLogDAO.

        Args:
            session: Async database session
        """
        super().__init__(ExecutionLog, session)

    async def create_log(
        self,
        workflow_instance_id: int,
        n8n_execution_id: Optional[str] = None,
        status: ExecutionStatus = ExecutionStatus.RUNNING,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> ExecutionLog:
        """
        Create a new execution log entry.

        WHAT: Records the start of a workflow execution.

        WHY: Execution logs provide:
        - Audit trail for compliance
        - Debugging information
        - Performance metrics
        - Billing data

        Args:
            workflow_instance_id: ID of the workflow instance
            n8n_execution_id: Execution ID from n8n (optional)
            status: Initial status (default RUNNING)
            input_data: Input data passed to the workflow

        Returns:
            Created ExecutionLog instance
        """
        return await self.create(
            workflow_instance_id=workflow_instance_id,
            n8n_execution_id=n8n_execution_id,
            status=status,
            input_data=input_data,
            started_at=datetime.utcnow(),
        )

    async def complete_execution(
        self,
        log_id: int,
        status: ExecutionStatus,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ExecutionLog]:
        """
        Mark an execution as completed.

        WHAT: Updates execution with final status and results.

        WHY: Records execution outcome for:
        - Success/failure tracking
        - Error debugging
        - Result storage

        Args:
            log_id: Execution log ID
            status: Final status (SUCCESS, FAILED, CANCELLED)
            output_data: Output data from workflow
            error_message: Error message if failed

        Returns:
            Updated log or None if not found
        """
        log = await self.get_by_id(log_id)
        if not log:
            return None

        log.status = status
        log.finished_at = datetime.utcnow()
        if output_data is not None:
            log.output_data = output_data
        if error_message is not None:
            log.error_message = error_message

        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_by_instance(
        self,
        workflow_instance_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ExecutionLog]:
        """
        Get execution logs for a workflow instance.

        WHAT: Retrieves execution history for a workflow.

        WHY: Shows execution history on workflow detail page.

        Args:
            workflow_instance_id: Workflow instance ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of execution logs, newest first
        """
        result = await self.session.execute(
            select(ExecutionLog)
            .where(ExecutionLog.workflow_instance_id == workflow_instance_id)
            .order_by(ExecutionLog.started_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_status(
        self,
        workflow_instance_id: int,
        status: ExecutionStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ExecutionLog]:
        """
        Get execution logs by status.

        WHAT: Filters logs by execution status.

        WHY: Find all failed executions, running executions, etc.

        Args:
            workflow_instance_id: Workflow instance ID
            status: Status to filter by
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of matching logs
        """
        result = await self.session.execute(
            select(ExecutionLog)
            .where(
                ExecutionLog.workflow_instance_id == workflow_instance_id,
                ExecutionLog.status == status,
            )
            .order_by(ExecutionLog.started_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_n8n_execution_id(
        self,
        n8n_execution_id: str,
    ) -> Optional[ExecutionLog]:
        """
        Get log by n8n execution ID.

        WHAT: Lookup by external n8n ID.

        WHY: Needed for webhook callbacks from n8n.

        Args:
            n8n_execution_id: Execution ID from n8n

        Returns:
            Log if found, None otherwise
        """
        result = await self.session.execute(
            select(ExecutionLog)
            .where(ExecutionLog.n8n_execution_id == n8n_execution_id)
        )
        return result.scalar_one_or_none()

    async def get_running_executions(
        self,
        workflow_instance_id: int,
    ) -> List[ExecutionLog]:
        """
        Get currently running executions.

        WHAT: Finds executions with RUNNING status.

        WHY: Monitor active executions.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            List of running executions
        """
        return await self.get_by_status(
            workflow_instance_id=workflow_instance_id,
            status=ExecutionStatus.RUNNING,
        )

    async def get_failed_executions(
        self,
        workflow_instance_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ExecutionLog]:
        """
        Get failed executions.

        WHAT: Finds executions with FAILED status.

        WHY: Error investigation and debugging.

        Args:
            workflow_instance_id: Workflow instance ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of failed executions
        """
        return await self.get_by_status(
            workflow_instance_id=workflow_instance_id,
            status=ExecutionStatus.FAILED,
            skip=skip,
            limit=limit,
        )

    async def get_recent_executions(
        self,
        workflow_instance_id: int,
        hours: int = 24,
        limit: int = 100,
    ) -> List[ExecutionLog]:
        """
        Get executions from the last N hours.

        WHAT: Time-based execution query.

        WHY: Recent execution overview for monitoring.

        Args:
            workflow_instance_id: Workflow instance ID
            hours: Number of hours to look back
            limit: Maximum results

        Returns:
            List of recent executions
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(ExecutionLog)
            .where(
                ExecutionLog.workflow_instance_id == workflow_instance_id,
                ExecutionLog.started_at >= cutoff,
            )
            .order_by(ExecutionLog.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_execution(
        self,
        workflow_instance_id: int,
    ) -> Optional[ExecutionLog]:
        """
        Get the most recent execution.

        WHAT: Finds the latest execution.

        WHY: Quick status check for workflow overview.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Latest execution or None
        """
        result = await self.session.execute(
            select(ExecutionLog)
            .where(ExecutionLog.workflow_instance_id == workflow_instance_id)
            .order_by(ExecutionLog.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_by_status(
        self,
        workflow_instance_id: int,
    ) -> Dict[str, int]:
        """
        Get execution counts by status.

        WHAT: Aggregate execution counts by status.

        WHY: Execution statistics for dashboard.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Dict mapping status to count
        """
        result = await self.session.execute(
            select(ExecutionLog.status, func.count(ExecutionLog.id))
            .where(ExecutionLog.workflow_instance_id == workflow_instance_id)
            .group_by(ExecutionLog.status)
        )

        return {row[0].value: row[1] for row in result.all()}

    async def count_total(self, workflow_instance_id: int) -> int:
        """
        Count total executions.

        WHAT: Total execution count.

        WHY: For billing and statistics.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Total number of executions
        """
        result = await self.session.execute(
            select(func.count(ExecutionLog.id))
            .where(ExecutionLog.workflow_instance_id == workflow_instance_id)
        )
        return result.scalar_one()

    async def count_successful(self, workflow_instance_id: int) -> int:
        """
        Count successful executions.

        WHAT: Count of SUCCESS status.

        WHY: Success rate metrics.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Number of successful executions
        """
        result = await self.session.execute(
            select(func.count(ExecutionLog.id))
            .where(
                ExecutionLog.workflow_instance_id == workflow_instance_id,
                ExecutionLog.status == ExecutionStatus.SUCCESS,
            )
        )
        return result.scalar_one()

    async def count_failed(self, workflow_instance_id: int) -> int:
        """
        Count failed executions.

        WHAT: Count of FAILED status.

        WHY: Error rate metrics.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Number of failed executions
        """
        result = await self.session.execute(
            select(func.count(ExecutionLog.id))
            .where(
                ExecutionLog.workflow_instance_id == workflow_instance_id,
                ExecutionLog.status == ExecutionStatus.FAILED,
            )
        )
        return result.scalar_one()

    async def get_success_rate(
        self,
        workflow_instance_id: int,
    ) -> Optional[float]:
        """
        Calculate execution success rate.

        WHAT: Percentage of successful executions.

        WHY: Key workflow health metric.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Success rate (0.0 to 1.0) or None if no executions
        """
        total = await self.count_total(workflow_instance_id)
        if total == 0:
            return None

        successful = await self.count_successful(workflow_instance_id)
        return successful / total

    async def get_average_duration(
        self,
        workflow_instance_id: int,
    ) -> Optional[float]:
        """
        Calculate average execution duration.

        WHAT: Mean duration in seconds for completed executions.

        WHY: Performance monitoring.

        Args:
            workflow_instance_id: Workflow instance ID

        Returns:
            Average duration in seconds or None if no completed executions
        """
        # Get completed executions with both start and finish times
        result = await self.session.execute(
            select(ExecutionLog)
            .where(
                ExecutionLog.workflow_instance_id == workflow_instance_id,
                ExecutionLog.finished_at.isnot(None),
            )
        )
        logs = list(result.scalars().all())

        if not logs:
            return None

        total_duration = sum(
            (log.finished_at - log.started_at).total_seconds()
            for log in logs
        )
        return total_duration / len(logs)

    async def cleanup_old_logs(
        self,
        workflow_instance_id: int,
        days: int = 90,
    ) -> int:
        """
        Delete logs older than N days.

        WHAT: Purges old execution logs.

        WHY: Data retention policy - keep logs manageable.
        Note: Use with caution, consider archiving instead.

        Args:
            workflow_instance_id: Workflow instance ID
            days: Number of days to retain

        Returns:
            Number of logs deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get IDs to delete
        result = await self.session.execute(
            select(ExecutionLog.id)
            .where(
                ExecutionLog.workflow_instance_id == workflow_instance_id,
                ExecutionLog.created_at < cutoff,
            )
        )
        ids_to_delete = [row[0] for row in result.all()]

        # Delete each log
        deleted = 0
        for log_id in ids_to_delete:
            if await self.delete(log_id):
                deleted += 1

        return deleted
