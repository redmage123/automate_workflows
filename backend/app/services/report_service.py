"""
Report Service.

WHAT: Business logic for report operations.

WHY: The service layer:
1. Encapsulates report business logic
2. Coordinates between DAOs
3. Enforces business rules
4. Handles report generation and scheduling

HOW: Orchestrates ScheduledReportDAO, ReportExecutionDAO, ReportTemplateDAO
while validating operations against business rules.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from croniter import croniter

from app.dao.report import ScheduledReportDAO, ReportExecutionDAO, ReportTemplateDAO
from app.models.report import (
    ScheduledReport,
    ReportExecution,
    ReportTemplate,
    ReportType,
    ReportFormat,
    ExecutionStatus,
    DeliveryStatus,
)
from app.core.exceptions import (
    ReportNotFoundError,
    ReportGenerationError,
    ReportScheduleError,
    ValidationError,
    AuthorizationError,
)


# Report type metadata for API documentation
REPORT_TYPE_INFO = {
    ReportType.REVENUE.value: {
        "name": "Revenue Report",
        "description": "Financial overview including invoices, payments, and revenue trends",
        "parameters": ["date_from", "date_to", "project_id", "client_id", "status"],
        "formats": [ReportFormat.PDF, ReportFormat.EXCEL, ReportFormat.CSV],
    },
    ReportType.ACTIVITY.value: {
        "name": "Activity Report",
        "description": "User and system activity summary",
        "parameters": ["date_from", "date_to", "user_id", "entity_type", "event_type"],
        "formats": [ReportFormat.PDF, ReportFormat.EXCEL, ReportFormat.CSV],
    },
    ReportType.PROJECT.value: {
        "name": "Project Report",
        "description": "Project status, progress, and metrics",
        "parameters": ["date_from", "date_to", "project_id", "status", "client_id"],
        "formats": [ReportFormat.PDF, ReportFormat.EXCEL, ReportFormat.CSV],
    },
    ReportType.TICKET.value: {
        "name": "Ticket Report",
        "description": "Support ticket metrics and SLA compliance",
        "parameters": ["date_from", "date_to", "status", "priority", "category", "assignee_id"],
        "formats": [ReportFormat.PDF, ReportFormat.EXCEL, ReportFormat.CSV],
    },
    ReportType.TIME_TRACKING.value: {
        "name": "Time Tracking Report",
        "description": "Time entries, billable hours, and utilization",
        "parameters": ["date_from", "date_to", "user_id", "project_id", "billable_only"],
        "formats": [ReportFormat.PDF, ReportFormat.EXCEL, ReportFormat.CSV],
    },
    ReportType.INVOICE.value: {
        "name": "Invoice Report",
        "description": "Invoice history, aging, and payment status",
        "parameters": ["date_from", "date_to", "status", "client_id", "overdue_only"],
        "formats": [ReportFormat.PDF, ReportFormat.EXCEL, ReportFormat.CSV],
    },
    ReportType.CLIENT.value: {
        "name": "Client Report",
        "description": "Client portfolio, engagement, and value analysis",
        "parameters": ["date_from", "date_to", "client_id", "active_only"],
        "formats": [ReportFormat.PDF, ReportFormat.EXCEL, ReportFormat.CSV],
    },
    ReportType.WORKFLOW.value: {
        "name": "Workflow Report",
        "description": "Workflow execution metrics and performance",
        "parameters": ["date_from", "date_to", "workflow_id", "status", "environment"],
        "formats": [ReportFormat.PDF, ReportFormat.EXCEL, ReportFormat.CSV],
    },
    ReportType.CUSTOM.value: {
        "name": "Custom Report",
        "description": "User-defined custom report",
        "parameters": ["query", "columns", "grouping", "filters"],
        "formats": [ReportFormat.PDF, ReportFormat.EXCEL, ReportFormat.CSV, ReportFormat.JSON],
    },
}


class ReportService:
    """
    Service for report operations.

    WHAT: Provides business logic for reports.

    WHY: Reports enable:
    - Scheduled automated report generation
    - Ad-hoc report generation
    - Custom report templates
    - Export to multiple formats

    HOW: Coordinates DAOs and enforces business rules.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize ReportService.

        Args:
            session: Async database session
        """
        self.session = session
        self.scheduled_report_dao = ScheduledReportDAO(session)
        self.execution_dao = ReportExecutionDAO(session)
        self.template_dao = ReportTemplateDAO(session)

    # =========================================================================
    # Scheduled Report Management
    # =========================================================================

    async def create_scheduled_report(
        self,
        org_id: int,
        created_by: int,
        name: str,
        report_type: str,
        schedule: str,
        parameters: Optional[Dict[str, Any]] = None,
        output_format: str = ReportFormat.PDF.value,
        timezone: str = "UTC",
        recipients: Optional[List[int]] = None,
        email_subject: Optional[str] = None,
        email_body: Optional[str] = None,
    ) -> ScheduledReport:
        """
        Create a new scheduled report.

        WHAT: Creates a report that runs on a schedule.

        WHY: Automate regular report delivery.

        Args:
            org_id: Organization ID
            created_by: Creator user ID
            name: Report name
            report_type: Type of report
            schedule: Cron expression
            parameters: Report parameters
            output_format: Output format
            timezone: Timezone for schedule
            recipients: User IDs to receive report
            email_subject: Email subject
            email_body: Email body

        Returns:
            Created ScheduledReport

        Raises:
            ReportScheduleError: If schedule is invalid
            ValidationError: If validation fails
        """
        # Validate cron expression
        try:
            cron = croniter(schedule)
            next_run = cron.get_next(datetime)
        except (KeyError, ValueError) as e:
            raise ReportScheduleError(
                message="Invalid cron expression",
                details={"schedule": schedule, "error": str(e)},
            )

        # Validate report type
        if report_type not in [rt.value for rt in ReportType]:
            raise ValidationError(
                message="Invalid report type",
                details={"report_type": report_type},
            )

        # Validate output format
        if output_format not in [rf.value for rf in ReportFormat]:
            raise ValidationError(
                message="Invalid output format",
                details={"output_format": output_format},
            )

        report = await self.scheduled_report_dao.create(
            org_id=org_id,
            created_by=created_by,
            name=name,
            report_type=report_type,
            schedule=schedule,
            parameters=parameters or {},
            output_format=output_format,
            timezone=timezone,
            recipients=recipients,
            email_subject=email_subject,
            email_body=email_body,
            is_active=True,
            next_run_at=next_run,
        )

        return report

    async def get_scheduled_report(
        self,
        report_id: int,
        org_id: int,
    ) -> ScheduledReport:
        """
        Get a scheduled report by ID.

        WHAT: Retrieves scheduled report details.

        WHY: View report configuration.

        Args:
            report_id: Report ID
            org_id: Organization ID

        Returns:
            ScheduledReport

        Raises:
            ReportNotFoundError: If not found
        """
        report = await self.scheduled_report_dao.get_by_id_and_org(report_id, org_id)
        if not report:
            raise ReportNotFoundError(
                message="Scheduled report not found",
                details={"report_id": report_id},
            )
        return report

    async def update_scheduled_report(
        self,
        report_id: int,
        org_id: int,
        **kwargs,
    ) -> ScheduledReport:
        """
        Update a scheduled report.

        WHAT: Updates report configuration.

        WHY: Modify report settings.

        Args:
            report_id: Report ID
            org_id: Organization ID
            **kwargs: Fields to update

        Returns:
            Updated ScheduledReport

        Raises:
            ReportNotFoundError: If not found
            ReportScheduleError: If schedule is invalid
        """
        report = await self.get_scheduled_report(report_id, org_id)

        # Validate schedule if being updated
        if "schedule" in kwargs:
            try:
                cron = croniter(kwargs["schedule"])
                kwargs["next_run_at"] = cron.get_next(datetime)
            except (KeyError, ValueError) as e:
                raise ReportScheduleError(
                    message="Invalid cron expression",
                    details={"schedule": kwargs["schedule"], "error": str(e)},
                )

        # Update fields
        for key, value in kwargs.items():
            if value is not None and hasattr(report, key):
                setattr(report, key, value)

        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def delete_scheduled_report(
        self,
        report_id: int,
        org_id: int,
    ) -> None:
        """
        Delete a scheduled report.

        WHAT: Removes scheduled report.

        WHY: Clean up unused reports.

        Args:
            report_id: Report ID
            org_id: Organization ID

        Raises:
            ReportNotFoundError: If not found
        """
        await self.get_scheduled_report(report_id, org_id)
        await self.scheduled_report_dao.delete(report_id)

    async def get_org_scheduled_reports(
        self,
        org_id: int,
        report_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get scheduled reports for an organization.

        WHAT: Lists scheduled reports with filters.

        WHY: Admin management view.

        Args:
            org_id: Organization ID
            report_type: Optional type filter
            is_active: Optional active filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dict with reports and pagination info
        """
        reports = await self.scheduled_report_dao.get_org_reports(
            org_id=org_id,
            report_type=report_type,
            is_active=is_active,
            skip=skip,
            limit=limit + 1,
        )

        has_more = len(reports) > limit
        if has_more:
            reports = reports[:limit]

        return {
            "items": reports,
            "total": len(reports),
            "skip": skip,
            "limit": limit,
        }

    # =========================================================================
    # Report Generation
    # =========================================================================

    async def generate_report(
        self,
        org_id: int,
        report_type: str,
        parameters: Optional[Dict[str, Any]] = None,
        output_format: str = ReportFormat.PDF.value,
        triggered_by: Optional[int] = None,
        scheduled_report_id: Optional[int] = None,
        template_id: Optional[int] = None,
    ) -> ReportExecution:
        """
        Generate a report (ad-hoc or scheduled).

        WHAT: Starts report generation process.

        WHY: Generate reports on demand or from schedule.

        Args:
            org_id: Organization ID
            report_type: Type of report
            parameters: Report parameters
            output_format: Output format
            triggered_by: User who triggered (None for scheduled)
            scheduled_report_id: Scheduled report ID if from schedule
            template_id: Template ID to use for configuration

        Returns:
            ReportExecution tracking the generation

        Raises:
            ValidationError: If validation fails
        """
        # Get template configuration if specified
        if template_id:
            template = await self.template_dao.get_by_id_and_org(template_id, org_id)
            if template:
                # Merge template parameters with provided parameters
                template_params = template.parameters or {}
                params = {**template_params, **(parameters or {})}
                parameters = params
                if not output_format:
                    output_format = template.default_format

        # Determine report name
        report_name = f"{report_type.replace('_', ' ').title()} Report"
        if scheduled_report_id:
            scheduled = await self.scheduled_report_dao.get_by_id(scheduled_report_id)
            if scheduled:
                report_name = scheduled.name

        # Create execution record
        execution = await self.execution_dao.create_execution(
            org_id=org_id,
            report_name=report_name,
            report_type=report_type,
            output_format=output_format,
            scheduled_report_id=scheduled_report_id,
            parameters=parameters,
            triggered_by=triggered_by,
            is_adhoc=scheduled_report_id is None,
        )

        # In a real implementation, this would:
        # 1. Start execution
        # 2. Query data based on report_type and parameters
        # 3. Generate output in requested format
        # 4. Upload to S3
        # 5. Update execution with results

        # For now, mark as started
        execution = await self.execution_dao.start_execution(execution.id)

        return execution

    async def complete_report_generation(
        self,
        execution_id: int,
        output_file_key: str,
        output_size: int,
    ) -> ReportExecution:
        """
        Mark report generation as complete.

        WHAT: Updates execution with output details.

        WHY: Track generated report for download.

        Args:
            execution_id: Execution ID
            output_file_key: S3 key for output file
            output_size: File size in bytes

        Returns:
            Updated execution
        """
        execution = await self.execution_dao.complete_execution(
            execution_id, output_file_key, output_size
        )
        if not execution:
            raise ReportNotFoundError(
                message="Report execution not found",
                details={"execution_id": execution_id},
            )
        return execution

    async def fail_report_generation(
        self,
        execution_id: int,
        error_message: str,
    ) -> ReportExecution:
        """
        Mark report generation as failed.

        WHAT: Records failure with error message.

        WHY: Debug failed reports.

        Args:
            execution_id: Execution ID
            error_message: Error description

        Returns:
            Updated execution
        """
        execution = await self.execution_dao.fail_execution(execution_id, error_message)
        if not execution:
            raise ReportNotFoundError(
                message="Report execution not found",
                details={"execution_id": execution_id},
            )
        return execution

    # =========================================================================
    # Report Execution History
    # =========================================================================

    async def get_execution(
        self,
        execution_id: int,
        org_id: int,
    ) -> ReportExecution:
        """
        Get a report execution by ID.

        WHAT: Retrieves execution details.

        WHY: View execution status and results.

        Args:
            execution_id: Execution ID
            org_id: Organization ID

        Returns:
            ReportExecution

        Raises:
            ReportNotFoundError: If not found
        """
        execution = await self.execution_dao.get_by_id(execution_id)
        if not execution or execution.org_id != org_id:
            raise ReportNotFoundError(
                message="Report execution not found",
                details={"execution_id": execution_id},
            )
        return execution

    async def get_org_executions(
        self,
        org_id: int,
        status: Optional[str] = None,
        report_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get report executions for an organization.

        WHAT: Lists executions with filters.

        WHY: Execution history view.

        Args:
            org_id: Organization ID
            status: Optional status filter
            report_type: Optional type filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dict with executions and pagination info
        """
        executions = await self.execution_dao.get_org_executions(
            org_id=org_id,
            status=status,
            report_type=report_type,
            skip=skip,
            limit=limit + 1,
        )

        has_more = len(executions) > limit
        if has_more:
            executions = executions[:limit]

        return {
            "items": executions,
            "total": len(executions),
            "skip": skip,
            "limit": limit,
        }

    async def get_scheduled_report_executions(
        self,
        scheduled_report_id: int,
        org_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Get executions for a scheduled report.

        WHAT: Lists execution history for a scheduled report.

        WHY: View report run history.

        Args:
            scheduled_report_id: Scheduled report ID
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dict with executions and pagination info
        """
        # Verify report exists and belongs to org
        await self.get_scheduled_report(scheduled_report_id, org_id)

        executions = await self.execution_dao.get_report_executions(
            scheduled_report_id, skip, limit + 1
        )

        has_more = len(executions) > limit
        if has_more:
            executions = executions[:limit]

        return {
            "items": executions,
            "total": len(executions),
            "skip": skip,
            "limit": limit,
        }

    # =========================================================================
    # Report Templates
    # =========================================================================

    async def create_template(
        self,
        org_id: int,
        created_by: int,
        name: str,
        report_type: str,
        parameters: Optional[Dict[str, Any]] = None,
        default_format: str = ReportFormat.PDF.value,
        selected_columns: Optional[List[str]] = None,
        grouping: Optional[Dict[str, Any]] = None,
        sorting: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        include_charts: bool = True,
        include_summary: bool = True,
        chart_config: Optional[Dict[str, Any]] = None,
        is_public: bool = False,
        description: Optional[str] = None,
    ) -> ReportTemplate:
        """
        Create a new report template.

        WHAT: Saves report configuration for reuse.

        WHY: Users can save complex configurations.

        Args:
            org_id: Organization ID
            created_by: Creator user ID
            name: Template name
            report_type: Type of report
            parameters: Default parameters
            default_format: Default output format
            selected_columns: Columns to include
            grouping: Grouping configuration
            sorting: Sorting configuration
            filters: Filter configuration
            include_charts: Include charts
            include_summary: Include summary
            chart_config: Chart configuration
            is_public: Make template public
            description: Template description

        Returns:
            Created ReportTemplate
        """
        return await self.template_dao.create(
            org_id=org_id,
            created_by=created_by,
            name=name,
            description=description,
            report_type=report_type,
            parameters=parameters or {},
            default_format=default_format,
            selected_columns=selected_columns,
            grouping=grouping,
            sorting=sorting,
            filters=filters,
            include_charts=include_charts,
            include_summary=include_summary,
            chart_config=chart_config,
            is_public=is_public,
        )

    async def get_template(
        self,
        template_id: int,
        org_id: int,
        user_id: int,
    ) -> ReportTemplate:
        """
        Get a report template by ID.

        WHAT: Retrieves template details.

        WHY: View template configuration.

        Args:
            template_id: Template ID
            org_id: Organization ID
            user_id: User ID (for access check)

        Returns:
            ReportTemplate

        Raises:
            ReportNotFoundError: If not found
            AuthorizationError: If not authorized
        """
        template = await self.template_dao.get_by_id_and_org(template_id, org_id)
        if not template:
            raise ReportNotFoundError(
                message="Report template not found",
                details={"template_id": template_id},
            )

        # Check access: must be creator or template must be public
        if template.created_by != user_id and not template.is_public:
            raise AuthorizationError(
                message="Not authorized to access this template",
                details={"template_id": template_id},
            )

        return template

    async def update_template(
        self,
        template_id: int,
        org_id: int,
        user_id: int,
        **kwargs,
    ) -> ReportTemplate:
        """
        Update a report template.

        WHAT: Updates template configuration.

        WHY: Modify saved configurations.

        Args:
            template_id: Template ID
            org_id: Organization ID
            user_id: User ID (for authorization)
            **kwargs: Fields to update

        Returns:
            Updated ReportTemplate

        Raises:
            ReportNotFoundError: If not found
            AuthorizationError: If not owner
        """
        template = await self.template_dao.get_by_id_and_org(template_id, org_id)
        if not template:
            raise ReportNotFoundError(
                message="Report template not found",
                details={"template_id": template_id},
            )

        # Only owner can update
        if template.created_by != user_id:
            raise AuthorizationError(
                message="Only the template owner can update it",
                details={"template_id": template_id},
            )

        # Update fields
        for key, value in kwargs.items():
            if value is not None and hasattr(template, key):
                setattr(template, key, value)

        await self.session.flush()
        await self.session.refresh(template)
        return template

    async def delete_template(
        self,
        template_id: int,
        org_id: int,
        user_id: int,
    ) -> None:
        """
        Delete a report template.

        WHAT: Removes template.

        WHY: Clean up unused templates.

        Args:
            template_id: Template ID
            org_id: Organization ID
            user_id: User ID (for authorization)

        Raises:
            ReportNotFoundError: If not found
            AuthorizationError: If not owner
        """
        template = await self.template_dao.get_by_id_and_org(template_id, org_id)
        if not template:
            raise ReportNotFoundError(
                message="Report template not found",
                details={"template_id": template_id},
            )

        # Only owner can delete
        if template.created_by != user_id:
            raise AuthorizationError(
                message="Only the template owner can delete it",
                details={"template_id": template_id},
            )

        await self.template_dao.delete(template_id)

    async def clone_template(
        self,
        template_id: int,
        org_id: int,
        user_id: int,
        new_name: str,
    ) -> ReportTemplate:
        """
        Clone a report template.

        WHAT: Creates a copy of a template.

        WHY: Users can customize public templates.

        Args:
            template_id: Source template ID
            org_id: Organization ID
            user_id: New owner user ID
            new_name: Name for the clone

        Returns:
            New ReportTemplate

        Raises:
            ReportNotFoundError: If not found
            AuthorizationError: If not accessible
        """
        # Verify access to source template
        await self.get_template(template_id, org_id, user_id)

        clone = await self.template_dao.clone_template(
            template_id, new_name, user_id
        )
        if not clone:
            raise ReportNotFoundError(
                message="Report template not found",
                details={"template_id": template_id},
            )

        return clone

    async def get_org_templates(
        self,
        org_id: int,
        user_id: Optional[int] = None,
        report_type: Optional[str] = None,
        include_public: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get report templates for an organization.

        WHAT: Lists templates with filters.

        WHY: Template selection view.

        Args:
            org_id: Organization ID
            user_id: Optional filter by creator
            report_type: Optional type filter
            include_public: Include public templates
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dict with templates and pagination info
        """
        templates = await self.template_dao.get_org_templates(
            org_id=org_id,
            user_id=user_id,
            report_type=report_type,
            include_public=include_public,
            skip=skip,
            limit=limit + 1,
        )

        has_more = len(templates) > limit
        if has_more:
            templates = templates[:limit]

        return {
            "items": templates,
            "total": len(templates),
            "skip": skip,
            "limit": limit,
        }

    # =========================================================================
    # Report Type Information
    # =========================================================================

    def get_report_types(self) -> List[Dict[str, Any]]:
        """
        Get available report types with metadata.

        WHAT: Lists report types and their capabilities.

        WHY: Help users discover and understand reports.

        Returns:
            List of report type information
        """
        return [
            {
                "type": report_type,
                "name": info["name"],
                "description": info["description"],
                "available_parameters": info["parameters"],
                "supports_formats": [f.value for f in info["formats"]],
            }
            for report_type, info in REPORT_TYPE_INFO.items()
        ]

    # =========================================================================
    # Background Job Support
    # =========================================================================

    async def get_due_reports(self) -> List[ScheduledReport]:
        """
        Get reports that are due to run.

        WHAT: Finds reports ready for execution.

        WHY: Background job scheduling.

        Returns:
            List of due reports
        """
        return await self.scheduled_report_dao.get_due_reports(datetime.utcnow())

    async def update_next_run(
        self,
        report_id: int,
        schedule: str,
    ) -> Optional[ScheduledReport]:
        """
        Calculate and update next run time.

        WHAT: Updates schedule after execution.

        WHY: Keep schedule tracking current.

        Args:
            report_id: Report ID
            schedule: Cron expression

        Returns:
            Updated report
        """
        try:
            cron = croniter(schedule)
            next_run = cron.get_next(datetime)
        except (KeyError, ValueError):
            return None

        return await self.scheduled_report_dao.update_next_run(
            report_id, next_run, datetime.utcnow()
        )
