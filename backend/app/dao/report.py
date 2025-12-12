"""
Report Data Access Object (DAO).

WHAT: Database operations for report models.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for report operations
3. Enforces org-scoping for multi-tenancy
4. Handles complex queries for scheduling and execution

HOW: Extends BaseDAO with report-specific queries:
- CRUD operations for scheduled reports and templates
- Execution tracking and history
- Schedule management
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.report import (
    ScheduledReport,
    ReportExecution,
    ReportTemplate,
    ExecutionStatus,
    DeliveryStatus,
)


class ScheduledReportDAO(BaseDAO[ScheduledReport]):
    """
    Data Access Object for ScheduledReport model.

    WHAT: Provides operations for scheduled reports.

    WHY: Centralizes scheduled report management.

    HOW: Extends BaseDAO with report-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize ScheduledReportDAO."""
        super().__init__(ScheduledReport, session)

    async def get_active_reports(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ScheduledReport]:
        """
        Get active scheduled reports for an organization.

        WHAT: Retrieves active scheduled reports.

        WHY: Scheduler needs to know which reports to run.

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of active scheduled reports
        """
        query = (
            select(ScheduledReport)
            .where(
                ScheduledReport.org_id == org_id,
                ScheduledReport.is_active == True,
            )
            .options(selectinload(ScheduledReport.creator))
            .order_by(ScheduledReport.next_run_at.asc().nullslast())
        )

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_org_reports(
        self,
        org_id: int,
        report_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ScheduledReport]:
        """
        Get all scheduled reports for an organization.

        WHAT: Lists scheduled reports with optional filters.

        WHY: Admin management view.

        Args:
            org_id: Organization ID
            report_type: Optional type filter
            is_active: Optional active status filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of scheduled reports
        """
        query = (
            select(ScheduledReport)
            .where(ScheduledReport.org_id == org_id)
            .options(selectinload(ScheduledReport.creator))
        )

        if report_type:
            query = query.where(ScheduledReport.report_type == report_type)

        if is_active is not None:
            query = query.where(ScheduledReport.is_active == is_active)

        query = query.order_by(ScheduledReport.created_at.desc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_due_reports(
        self,
        before: datetime,
    ) -> List[ScheduledReport]:
        """
        Get reports that are due to run.

        WHAT: Finds reports with next_run_at before given time.

        WHY: Background job needs to find reports to execute.

        Args:
            before: Find reports due before this time

        Returns:
            List of due reports
        """
        query = (
            select(ScheduledReport)
            .where(
                ScheduledReport.is_active == True,
                ScheduledReport.next_run_at.isnot(None),
                ScheduledReport.next_run_at <= before,
            )
            .order_by(ScheduledReport.next_run_at.asc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_next_run(
        self,
        report_id: int,
        next_run_at: datetime,
        last_run_at: Optional[datetime] = None,
    ) -> Optional[ScheduledReport]:
        """
        Update next run time after execution.

        WHAT: Updates scheduling timestamps.

        WHY: Keep schedule tracking current.

        Args:
            report_id: Report ID
            next_run_at: Next scheduled run time
            last_run_at: Optional last run time

        Returns:
            Updated report
        """
        report = await self.get_by_id(report_id)
        if not report:
            return None

        report.next_run_at = next_run_at
        if last_run_at:
            report.last_run_at = last_run_at

        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def count_by_org(self, org_id: int) -> int:
        """
        Count scheduled reports for an organization.

        WHAT: Gets total count of reports.

        WHY: UI pagination and limits.

        Args:
            org_id: Organization ID

        Returns:
            Total count
        """
        result = await self.session.execute(
            select(func.count(ScheduledReport.id)).where(
                ScheduledReport.org_id == org_id
            )
        )
        return result.scalar() or 0


class ReportExecutionDAO(BaseDAO[ReportExecution]):
    """
    Data Access Object for ReportExecution model.

    WHAT: Provides operations for report executions.

    WHY: Tracks report generation history.

    HOW: Extends BaseDAO with execution-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize ReportExecutionDAO."""
        super().__init__(ReportExecution, session)

    async def create_execution(
        self,
        org_id: int,
        report_name: str,
        report_type: str,
        output_format: str,
        scheduled_report_id: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
        triggered_by: Optional[int] = None,
        is_adhoc: bool = False,
    ) -> ReportExecution:
        """
        Create a new report execution record.

        WHAT: Initializes execution tracking.

        WHY: Track report generation from start.

        Args:
            org_id: Organization ID
            report_name: Report name
            report_type: Report type
            output_format: Output format
            scheduled_report_id: Optional scheduled report ID
            parameters: Report parameters
            triggered_by: User who triggered the report
            is_adhoc: Whether this is an ad-hoc report

        Returns:
            Created ReportExecution
        """
        return await self.create(
            org_id=org_id,
            report_name=report_name,
            report_type=report_type,
            output_format=output_format,
            scheduled_report_id=scheduled_report_id,
            parameters=parameters,
            triggered_by=triggered_by,
            is_adhoc=is_adhoc,
            status=ExecutionStatus.PENDING.value,
        )

    async def start_execution(
        self,
        execution_id: int,
    ) -> Optional[ReportExecution]:
        """
        Mark execution as started.

        WHAT: Updates status to running.

        WHY: Track execution start time.

        Args:
            execution_id: Execution ID

        Returns:
            Updated execution
        """
        execution = await self.get_by_id(execution_id)
        if not execution:
            return None

        execution.status = ExecutionStatus.RUNNING.value
        execution.started_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def complete_execution(
        self,
        execution_id: int,
        output_file_key: str,
        output_size: int,
    ) -> Optional[ReportExecution]:
        """
        Mark execution as completed.

        WHAT: Records successful completion.

        WHY: Track output location and size.

        Args:
            execution_id: Execution ID
            output_file_key: S3 key for output file
            output_size: File size in bytes

        Returns:
            Updated execution
        """
        execution = await self.get_by_id(execution_id)
        if not execution:
            return None

        execution.status = ExecutionStatus.COMPLETED.value
        execution.completed_at = datetime.utcnow()
        execution.output_file_key = output_file_key
        execution.output_size = output_size

        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def fail_execution(
        self,
        execution_id: int,
        error_message: str,
    ) -> Optional[ReportExecution]:
        """
        Mark execution as failed.

        WHAT: Records failure with error message.

        WHY: Debug failed reports.

        Args:
            execution_id: Execution ID
            error_message: Error description

        Returns:
            Updated execution
        """
        execution = await self.get_by_id(execution_id)
        if not execution:
            return None

        execution.status = ExecutionStatus.FAILED.value
        execution.completed_at = datetime.utcnow()
        execution.error_message = error_message

        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def update_delivery_status(
        self,
        execution_id: int,
        delivery_status: str,
        delivery_error: Optional[str] = None,
    ) -> Optional[ReportExecution]:
        """
        Update delivery status after email send.

        WHAT: Records delivery result.

        WHY: Track email delivery.

        Args:
            execution_id: Execution ID
            delivery_status: Delivery status
            delivery_error: Optional error message

        Returns:
            Updated execution
        """
        execution = await self.get_by_id(execution_id)
        if not execution:
            return None

        execution.delivery_status = delivery_status
        execution.delivery_error = delivery_error
        if delivery_status == DeliveryStatus.SENT.value:
            execution.delivered_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def get_report_executions(
        self,
        scheduled_report_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> List[ReportExecution]:
        """
        Get executions for a scheduled report.

        WHAT: Lists execution history.

        WHY: View report run history.

        Args:
            scheduled_report_id: Scheduled report ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of executions
        """
        query = (
            select(ReportExecution)
            .where(ReportExecution.scheduled_report_id == scheduled_report_id)
            .order_by(ReportExecution.created_at.desc())
        )

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_org_executions(
        self,
        org_id: int,
        status: Optional[str] = None,
        report_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ReportExecution]:
        """
        Get all executions for an organization.

        WHAT: Lists all executions with filters.

        WHY: Admin view of report history.

        Args:
            org_id: Organization ID
            status: Optional status filter
            report_type: Optional type filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of executions
        """
        query = (
            select(ReportExecution)
            .where(ReportExecution.org_id == org_id)
            .options(selectinload(ReportExecution.scheduled_report))
        )

        if status:
            query = query.where(ReportExecution.status == status)

        if report_type:
            query = query.where(ReportExecution.report_type == report_type)

        query = query.order_by(ReportExecution.created_at.desc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_recent_failures(
        self,
        org_id: int,
        since: datetime,
    ) -> List[ReportExecution]:
        """
        Get recent failed executions.

        WHAT: Lists recent failures.

        WHY: Alerting and monitoring.

        Args:
            org_id: Organization ID
            since: Get failures since this time

        Returns:
            List of failed executions
        """
        query = (
            select(ReportExecution)
            .where(
                ReportExecution.org_id == org_id,
                ReportExecution.status == ExecutionStatus.FAILED.value,
                ReportExecution.created_at >= since,
            )
            .order_by(ReportExecution.created_at.desc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def cleanup_old_executions(
        self,
        older_than: datetime,
    ) -> int:
        """
        Delete old execution records.

        WHAT: Removes old history entries.

        WHY: Prevent table bloat.

        Args:
            older_than: Delete executions older than this

        Returns:
            Number of deleted records
        """
        result = await self.session.execute(
            select(ReportExecution.id).where(
                ReportExecution.created_at < older_than,
                ReportExecution.status.in_([
                    ExecutionStatus.COMPLETED.value,
                    ExecutionStatus.FAILED.value,
                ]),
            )
        )
        ids = list(result.scalars().all())

        if ids:
            for execution_id in ids:
                await self.delete(execution_id)

        return len(ids)


class ReportTemplateDAO(BaseDAO[ReportTemplate]):
    """
    Data Access Object for ReportTemplate model.

    WHAT: Provides operations for report templates.

    WHY: Manages saved report configurations.

    HOW: Extends BaseDAO with template-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize ReportTemplateDAO."""
        super().__init__(ReportTemplate, session)

    async def get_org_templates(
        self,
        org_id: int,
        user_id: Optional[int] = None,
        report_type: Optional[str] = None,
        include_public: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ReportTemplate]:
        """
        Get report templates for an organization.

        WHAT: Lists templates with optional filters.

        WHY: Users need to find templates to use.

        Args:
            org_id: Organization ID
            user_id: Optional filter by creator
            report_type: Optional type filter
            include_public: Include public templates
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of templates
        """
        query = select(ReportTemplate).where(ReportTemplate.org_id == org_id)

        if user_id and include_public:
            # User's own templates or public templates
            query = query.where(
                or_(
                    ReportTemplate.created_by == user_id,
                    ReportTemplate.is_public == True,
                )
            )
        elif user_id:
            # Only user's own templates
            query = query.where(ReportTemplate.created_by == user_id)

        if report_type:
            query = query.where(ReportTemplate.report_type == report_type)

        query = query.options(
            selectinload(ReportTemplate.creator)
        ).order_by(ReportTemplate.name.asc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_public_templates(
        self,
        org_id: int,
        report_type: Optional[str] = None,
    ) -> List[ReportTemplate]:
        """
        Get public templates for an organization.

        WHAT: Lists public templates only.

        WHY: For template discovery.

        Args:
            org_id: Organization ID
            report_type: Optional type filter

        Returns:
            List of public templates
        """
        query = (
            select(ReportTemplate)
            .where(
                ReportTemplate.org_id == org_id,
                ReportTemplate.is_public == True,
            )
            .options(selectinload(ReportTemplate.creator))
        )

        if report_type:
            query = query.where(ReportTemplate.report_type == report_type)

        query = query.order_by(ReportTemplate.name.asc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def clone_template(
        self,
        template_id: int,
        new_name: str,
        new_owner_id: int,
    ) -> Optional[ReportTemplate]:
        """
        Clone an existing template.

        WHAT: Creates a copy of a template.

        WHY: Users may want to customize public templates.

        Args:
            template_id: Source template ID
            new_name: Name for the clone
            new_owner_id: User ID for the new owner

        Returns:
            New template
        """
        source = await self.get_by_id(template_id)
        if not source:
            return None

        return await self.create(
            org_id=source.org_id,
            created_by=new_owner_id,
            name=new_name,
            description=source.description,
            report_type=source.report_type,
            parameters=source.parameters,
            default_format=source.default_format,
            selected_columns=source.selected_columns,
            grouping=source.grouping,
            sorting=source.sorting,
            filters=source.filters,
            include_charts=source.include_charts,
            include_summary=source.include_summary,
            chart_config=source.chart_config,
            is_public=False,  # Clone is private by default
        )
