"""
Reports API Routes.

WHAT: REST API endpoints for report operations.

WHY: Reports enable:
1. Scheduled automated report generation and delivery
2. Ad-hoc report generation
3. Custom report templates
4. Export to multiple formats

HOW: Uses FastAPI with dependency injection for auth/db.
All routes require authentication and enforce org-scoping.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_admin
from app.models.user import User
from app.services.report_service import ReportService
from app.services.audit import AuditService
from app.schemas.report import (
    ReportType,
    ReportFormat,
    ExecutionStatus,
    ScheduledReportCreateRequest,
    ScheduledReportUpdateRequest,
    ReportGenerateRequest,
    ReportTemplateCreateRequest,
    ReportTemplateUpdateRequest,
    ReportCloneRequest,
    CreatorResponse,
    ScheduledReportResponse,
    ScheduledReportListResponse,
    ReportExecutionResponse,
    ReportExecutionListResponse,
    ReportTemplateResponse,
    ReportTemplateListResponse,
    ReportGenerateResponse,
    ReportTypeInfo,
    ReportTypesResponse,
)


router = APIRouter(prefix="/reports", tags=["reports"])


def _scheduled_report_to_response(report) -> ScheduledReportResponse:
    """
    Convert ScheduledReport model to response schema.

    WHAT: Maps model fields to response.

    WHY: Consistent response formatting.
    """
    creator = None
    if report.creator:
        creator = CreatorResponse(
            id=report.creator.id,
            name=report.creator.name,
            email=report.creator.email,
        )

    return ScheduledReportResponse(
        id=report.id,
        org_id=report.org_id,
        name=report.name,
        description=report.description,
        report_type=ReportType(report.report_type),
        parameters=report.parameters,
        output_format=ReportFormat(report.output_format),
        schedule=report.schedule,
        timezone=report.timezone,
        recipients=report.recipients,
        email_subject=report.email_subject,
        email_body=report.email_body,
        is_active=report.is_active,
        last_run_at=report.last_run_at,
        next_run_at=report.next_run_at,
        created_by=report.created_by,
        creator=creator,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _execution_to_response(execution) -> ReportExecutionResponse:
    """
    Convert ReportExecution model to response schema.

    WHAT: Maps model fields to response.

    WHY: Consistent response formatting.
    """
    return ReportExecutionResponse(
        id=execution.id,
        scheduled_report_id=execution.scheduled_report_id,
        org_id=execution.org_id,
        report_name=execution.report_name,
        report_type=ReportType(execution.report_type),
        parameters=execution.parameters,
        output_format=ReportFormat(execution.output_format),
        status=ExecutionStatus(execution.status),
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_seconds=execution.duration_seconds,
        output_file_key=execution.output_file_key,
        output_size=execution.output_size,
        error_message=execution.error_message,
        delivery_status=execution.delivery_status,
        delivery_error=execution.delivery_error,
        delivered_at=execution.delivered_at,
        triggered_by=execution.triggered_by,
        is_adhoc=execution.is_adhoc,
        created_at=execution.created_at,
    )


def _template_to_response(template) -> ReportTemplateResponse:
    """
    Convert ReportTemplate model to response schema.

    WHAT: Maps model fields to response.

    WHY: Consistent response formatting.
    """
    creator = None
    if template.creator:
        creator = CreatorResponse(
            id=template.creator.id,
            name=template.creator.name,
            email=template.creator.email,
        )

    return ReportTemplateResponse(
        id=template.id,
        org_id=template.org_id,
        name=template.name,
        description=template.description,
        report_type=ReportType(template.report_type),
        parameters=template.parameters,
        default_format=ReportFormat(template.default_format),
        selected_columns=template.selected_columns,
        grouping=template.grouping,
        sorting=template.sorting,
        filters=template.filters,
        include_charts=template.include_charts,
        include_summary=template.include_summary,
        chart_config=template.chart_config,
        is_public=template.is_public,
        created_by=template.created_by,
        creator=creator,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


# ============================================================================
# Report Types Endpoint
# ============================================================================


@router.get("/types", response_model=ReportTypesResponse)
async def get_report_types(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get available report types.

    WHAT: Lists report types with metadata.

    WHY: Help users discover and understand reports.
    """
    service = ReportService(session)
    types = service.get_report_types()

    return ReportTypesResponse(
        types=[
            ReportTypeInfo(
                type=ReportType(t["type"]),
                name=t["name"],
                description=t["description"],
                available_parameters=t["available_parameters"],
                supports_formats=[ReportFormat(f) for f in t["supports_formats"]],
            )
            for t in types
        ]
    )


# ============================================================================
# Ad-hoc Report Generation
# ============================================================================


@router.post("/generate", response_model=ReportGenerateResponse)
async def generate_report(
    request: ReportGenerateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Generate an ad-hoc report.

    WHAT: Starts immediate report generation.

    WHY: Generate reports on demand.
    """
    service = ReportService(session)

    execution = await service.generate_report(
        org_id=current_user.org_id,
        report_type=request.report_type.value,
        parameters=request.parameters,
        output_format=request.output_format.value,
        triggered_by=current_user.id,
        template_id=request.template_id,
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="report_generated",
        resource_type="report_execution",
        resource_id=execution.id,
        details={
            "report_type": request.report_type.value,
            "output_format": request.output_format.value,
        },
    )

    await session.commit()

    return ReportGenerateResponse(
        execution_id=execution.id,
        status=ExecutionStatus(execution.status),
        download_url=None,  # Will be available when complete
        message="Report generation started",
    )


# ============================================================================
# Scheduled Reports Endpoints
# ============================================================================


@router.get("/scheduled", response_model=ScheduledReportListResponse)
async def list_scheduled_reports(
    report_type: Optional[ReportType] = Query(None, description="Filter by type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    List scheduled reports.

    WHAT: Lists all scheduled reports with filters.

    WHY: Admin management view.

    Requires: Admin role
    """
    service = ReportService(session)

    result = await service.get_org_scheduled_reports(
        org_id=current_user.org_id,
        report_type=report_type.value if report_type else None,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )

    return ScheduledReportListResponse(
        items=[_scheduled_report_to_response(r) for r in result["items"]],
        total=result["total"],
        skip=result["skip"],
        limit=result["limit"],
    )


@router.post("/scheduled", response_model=ScheduledReportResponse)
async def create_scheduled_report(
    request: ScheduledReportCreateRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Create a scheduled report.

    WHAT: Creates a report that runs on a schedule.

    WHY: Automate regular report delivery.

    Requires: Admin role
    """
    service = ReportService(session)

    report = await service.create_scheduled_report(
        org_id=current_user.org_id,
        created_by=current_user.id,
        name=request.name,
        report_type=request.report_type.value,
        schedule=request.schedule,
        parameters=request.parameters,
        output_format=request.output_format.value,
        timezone=request.timezone,
        recipients=request.recipients,
        email_subject=request.email_subject,
        email_body=request.email_body,
        description=request.description,
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="scheduled_report_created",
        resource_type="scheduled_report",
        resource_id=report.id,
        details={"name": report.name, "schedule": report.schedule},
    )

    await session.commit()
    return _scheduled_report_to_response(report)


@router.get("/scheduled/{report_id}", response_model=ScheduledReportResponse)
async def get_scheduled_report(
    report_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Get scheduled report details.

    WHAT: Retrieves report configuration.

    WHY: View report settings.

    Requires: Admin role
    """
    service = ReportService(session)
    report = await service.get_scheduled_report(report_id, current_user.org_id)
    return _scheduled_report_to_response(report)


@router.patch("/scheduled/{report_id}", response_model=ScheduledReportResponse)
async def update_scheduled_report(
    report_id: int,
    request: ScheduledReportUpdateRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Update a scheduled report.

    WHAT: Updates report configuration.

    WHY: Modify report settings.

    Requires: Admin role
    """
    service = ReportService(session)

    # Build update dict from non-None values
    updates = {}
    for key, value in request.model_dump().items():
        if value is not None:
            if key == "output_format":
                updates[key] = value.value
            else:
                updates[key] = value

    report = await service.update_scheduled_report(
        report_id, current_user.org_id, **updates
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="scheduled_report_updated",
        resource_type="scheduled_report",
        resource_id=report_id,
        details=updates,
    )

    await session.commit()
    return _scheduled_report_to_response(report)


@router.delete("/scheduled/{report_id}")
async def delete_scheduled_report(
    report_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete a scheduled report.

    WHAT: Removes scheduled report.

    WHY: Clean up unused reports.

    Requires: Admin role
    """
    service = ReportService(session)
    await service.delete_scheduled_report(report_id, current_user.org_id)

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="scheduled_report_deleted",
        resource_type="scheduled_report",
        resource_id=report_id,
    )

    await session.commit()
    return {"message": "Scheduled report deleted"}


@router.post("/scheduled/{report_id}/run", response_model=ReportGenerateResponse)
async def run_scheduled_report(
    report_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Run a scheduled report immediately.

    WHAT: Triggers immediate execution.

    WHY: Test report or generate on demand.

    Requires: Admin role
    """
    service = ReportService(session)

    # Get report details
    report = await service.get_scheduled_report(report_id, current_user.org_id)

    # Generate report
    execution = await service.generate_report(
        org_id=current_user.org_id,
        report_type=report.report_type,
        parameters=report.parameters,
        output_format=report.output_format,
        triggered_by=current_user.id,
        scheduled_report_id=report_id,
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="scheduled_report_triggered",
        resource_type="scheduled_report",
        resource_id=report_id,
        details={"execution_id": execution.id},
    )

    await session.commit()

    return ReportGenerateResponse(
        execution_id=execution.id,
        status=ExecutionStatus(execution.status),
        download_url=None,
        message="Report generation started",
    )


@router.get(
    "/scheduled/{report_id}/executions",
    response_model=ReportExecutionListResponse
)
async def get_scheduled_report_executions(
    report_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Get execution history for a scheduled report.

    WHAT: Lists past executions.

    WHY: View report run history.

    Requires: Admin role
    """
    service = ReportService(session)

    result = await service.get_scheduled_report_executions(
        scheduled_report_id=report_id,
        org_id=current_user.org_id,
        skip=skip,
        limit=limit,
    )

    return ReportExecutionListResponse(
        items=[_execution_to_response(e) for e in result["items"]],
        total=result["total"],
        skip=result["skip"],
        limit=result["limit"],
    )


# ============================================================================
# Report Executions Endpoints
# ============================================================================


@router.get("/executions", response_model=ReportExecutionListResponse)
async def list_executions(
    status: Optional[ExecutionStatus] = Query(None, description="Filter by status"),
    report_type: Optional[ReportType] = Query(None, description="Filter by type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    List all report executions.

    WHAT: Lists executions with filters.

    WHY: Execution history view.

    Requires: Admin role
    """
    service = ReportService(session)

    result = await service.get_org_executions(
        org_id=current_user.org_id,
        status=status.value if status else None,
        report_type=report_type.value if report_type else None,
        skip=skip,
        limit=limit,
    )

    return ReportExecutionListResponse(
        items=[_execution_to_response(e) for e in result["items"]],
        total=result["total"],
        skip=result["skip"],
        limit=result["limit"],
    )


@router.get("/executions/{execution_id}", response_model=ReportExecutionResponse)
async def get_execution(
    execution_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get execution details.

    WHAT: Retrieves execution status and results.

    WHY: Track report generation progress.
    """
    service = ReportService(session)
    execution = await service.get_execution(execution_id, current_user.org_id)
    return _execution_to_response(execution)


@router.get("/executions/{execution_id}/download")
async def download_report(
    execution_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Download a generated report.

    WHAT: Returns download URL for completed report.

    WHY: Access generated report file.
    """
    service = ReportService(session)
    execution = await service.get_execution(execution_id, current_user.org_id)

    if execution.status != "completed":
        return {
            "message": "Report not ready",
            "status": execution.status,
            "download_url": None,
        }

    # In a real implementation, this would generate a presigned S3 URL
    download_url = f"/api/reports/download/{execution.output_file_key}" if execution.output_file_key else None

    return {
        "message": "Report ready",
        "status": execution.status,
        "download_url": download_url,
    }


# ============================================================================
# Report Templates Endpoints
# ============================================================================


@router.get("/templates", response_model=ReportTemplateListResponse)
async def list_templates(
    report_type: Optional[ReportType] = Query(None, description="Filter by type"),
    my_templates_only: bool = Query(False, description="Only show my templates"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    List report templates.

    WHAT: Lists templates with filters.

    WHY: Template selection view.
    """
    service = ReportService(session)

    result = await service.get_org_templates(
        org_id=current_user.org_id,
        user_id=current_user.id if my_templates_only else None,
        report_type=report_type.value if report_type else None,
        include_public=not my_templates_only,
        skip=skip,
        limit=limit,
    )

    return ReportTemplateListResponse(
        items=[_template_to_response(t) for t in result["items"]],
        total=result["total"],
        skip=result["skip"],
        limit=result["limit"],
    )


@router.post("/templates", response_model=ReportTemplateResponse)
async def create_template(
    request: ReportTemplateCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Create a report template.

    WHAT: Saves report configuration for reuse.

    WHY: Users can save complex configurations.
    """
    service = ReportService(session)

    template = await service.create_template(
        org_id=current_user.org_id,
        created_by=current_user.id,
        name=request.name,
        description=request.description,
        report_type=request.report_type.value,
        parameters=request.parameters,
        default_format=request.default_format.value,
        selected_columns=request.selected_columns,
        grouping=request.grouping,
        sorting=request.sorting,
        filters=request.filters,
        include_charts=request.include_charts,
        include_summary=request.include_summary,
        chart_config=request.chart_config,
        is_public=request.is_public,
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="report_template_created",
        resource_type="report_template",
        resource_id=template.id,
        details={"name": template.name, "report_type": template.report_type},
    )

    await session.commit()
    return _template_to_response(template)


@router.get("/templates/{template_id}", response_model=ReportTemplateResponse)
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get template details.

    WHAT: Retrieves template configuration.

    WHY: View or use template.
    """
    service = ReportService(session)
    template = await service.get_template(
        template_id, current_user.org_id, current_user.id
    )
    return _template_to_response(template)


@router.patch("/templates/{template_id}", response_model=ReportTemplateResponse)
async def update_template(
    template_id: int,
    request: ReportTemplateUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Update a report template.

    WHAT: Updates template configuration.

    WHY: Modify saved configurations.
    """
    service = ReportService(session)

    # Build update dict from non-None values
    updates = {}
    for key, value in request.model_dump().items():
        if value is not None:
            if key == "default_format":
                updates[key] = value.value
            else:
                updates[key] = value

    template = await service.update_template(
        template_id, current_user.org_id, current_user.id, **updates
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="report_template_updated",
        resource_type="report_template",
        resource_id=template_id,
        details=updates,
    )

    await session.commit()
    return _template_to_response(template)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete a report template.

    WHAT: Removes template.

    WHY: Clean up unused templates.
    """
    service = ReportService(session)
    await service.delete_template(template_id, current_user.org_id, current_user.id)

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="report_template_deleted",
        resource_type="report_template",
        resource_id=template_id,
    )

    await session.commit()
    return {"message": "Template deleted"}


@router.post("/templates/{template_id}/clone", response_model=ReportTemplateResponse)
async def clone_template(
    template_id: int,
    request: ReportCloneRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Clone a report template.

    WHAT: Creates a copy of a template.

    WHY: Users can customize public templates.
    """
    service = ReportService(session)

    clone = await service.clone_template(
        template_id, current_user.org_id, current_user.id, request.new_name
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="report_template_cloned",
        resource_type="report_template",
        resource_id=clone.id,
        details={"source_template_id": template_id, "new_name": request.new_name},
    )

    await session.commit()
    return _template_to_response(clone)
