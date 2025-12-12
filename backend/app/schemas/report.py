"""
Report Pydantic Schemas.

WHAT: Request/Response models for report API endpoints.

WHY: Pydantic schemas provide:
1. Request validation
2. Response serialization
3. OpenAPI documentation
4. Type safety

HOW: Defines schemas for:
- Scheduled reports
- Report executions
- Report templates
- Ad-hoc report generation
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class ReportType(str, Enum):
    """Report types."""

    REVENUE = "revenue"
    ACTIVITY = "activity"
    PROJECT = "project"
    TICKET = "ticket"
    TIME_TRACKING = "time_tracking"
    INVOICE = "invoice"
    CLIENT = "client"
    WORKFLOW = "workflow"
    CUSTOM = "custom"


class ReportFormat(str, Enum):
    """Report output formats."""

    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"


class ExecutionStatus(str, Enum):
    """Report execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryStatus(str, Enum):
    """Report delivery status."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    PARTIAL = "partial"


# ============================================================================
# Request Schemas
# ============================================================================


class ScheduledReportCreateRequest(BaseModel):
    """
    Request schema for creating a scheduled report.

    WHAT: Fields needed to create a scheduled report.

    WHY: Validates report creation data.
    """

    name: str = Field(..., min_length=1, max_length=100, description="Report name")
    description: Optional[str] = Field(None, description="Report description")
    report_type: ReportType = Field(..., description="Type of report")

    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Report parameters (filters, date range, etc.)"
    )
    output_format: ReportFormat = Field(
        default=ReportFormat.PDF, description="Output format"
    )

    schedule: str = Field(
        ..., min_length=5, max_length=100,
        description="Cron expression for schedule (e.g., '0 9 * * 1' for Monday 9am)"
    )
    timezone: str = Field(default="UTC", description="Timezone for schedule")

    recipients: Optional[List[int]] = Field(None, description="User IDs to receive report")
    email_subject: Optional[str] = Field(
        None, max_length=255, description="Email subject"
    )
    email_body: Optional[str] = Field(None, description="Email body text")


class ScheduledReportUpdateRequest(BaseModel):
    """
    Request schema for updating a scheduled report.

    WHAT: Fields that can be updated.

    WHY: Allows partial updates.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    output_format: Optional[ReportFormat] = None

    schedule: Optional[str] = Field(None, min_length=5, max_length=100)
    timezone: Optional[str] = None

    recipients: Optional[List[int]] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None

    is_active: Optional[bool] = None


class ReportGenerateRequest(BaseModel):
    """
    Request schema for generating an ad-hoc report.

    WHAT: Parameters for immediate report generation.

    WHY: Users need to generate reports on demand.
    """

    report_type: ReportType = Field(..., description="Type of report")
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Report parameters"
    )
    output_format: ReportFormat = Field(
        default=ReportFormat.PDF, description="Output format"
    )
    template_id: Optional[int] = Field(
        None, description="Optional template to use for configuration"
    )


class ReportTemplateCreateRequest(BaseModel):
    """
    Request schema for creating a report template.

    WHAT: Fields needed to create a template.

    WHY: Validates template creation data.
    """

    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    report_type: ReportType = Field(..., description="Type of report")

    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Default parameters"
    )
    default_format: ReportFormat = Field(
        default=ReportFormat.PDF, description="Default output format"
    )

    selected_columns: Optional[List[str]] = Field(
        None, description="Columns to include in report"
    )
    grouping: Optional[Dict[str, Any]] = Field(None, description="Grouping configuration")
    sorting: Optional[Dict[str, Any]] = Field(None, description="Sorting configuration")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filter configuration")

    include_charts: bool = Field(default=True, description="Include charts")
    include_summary: bool = Field(default=True, description="Include summary")
    chart_config: Optional[Dict[str, Any]] = Field(
        None, description="Chart configuration"
    )

    is_public: bool = Field(default=False, description="Make template public")


class ReportTemplateUpdateRequest(BaseModel):
    """
    Request schema for updating a report template.

    WHAT: Fields that can be updated.

    WHY: Allows partial updates.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    default_format: Optional[ReportFormat] = None

    selected_columns: Optional[List[str]] = None
    grouping: Optional[Dict[str, Any]] = None
    sorting: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None

    include_charts: Optional[bool] = None
    include_summary: Optional[bool] = None
    chart_config: Optional[Dict[str, Any]] = None

    is_public: Optional[bool] = None


class ReportCloneRequest(BaseModel):
    """
    Request schema for cloning a template.

    WHAT: Parameters for cloning a template.

    WHY: Users may want to customize public templates.
    """

    new_name: str = Field(..., min_length=1, max_length=100, description="New template name")


# ============================================================================
# Response Schemas
# ============================================================================


class CreatorResponse(BaseModel):
    """
    Response schema for report creator.

    WHAT: User who created the report.

    WHY: Display creator info.
    """

    id: int = Field(..., description="User ID")
    name: Optional[str] = Field(None, description="User name")
    email: Optional[str] = Field(None, description="User email")

    class Config:
        from_attributes = True


class ScheduledReportResponse(BaseModel):
    """
    Response schema for scheduled report.

    WHAT: Scheduled report details for display.

    WHY: Provides all report information for UI.
    """

    id: int = Field(..., description="Report ID")
    org_id: int = Field(..., description="Organization ID")

    name: str = Field(..., description="Report name")
    description: Optional[str] = Field(None, description="Report description")
    report_type: ReportType = Field(..., description="Type of report")

    parameters: Optional[Dict[str, Any]] = Field(None, description="Report parameters")
    output_format: ReportFormat = Field(..., description="Output format")

    schedule: str = Field(..., description="Cron expression")
    timezone: str = Field(..., description="Timezone")

    recipients: Optional[List[int]] = Field(None, description="Recipient user IDs")
    email_subject: Optional[str] = Field(None, description="Email subject")
    email_body: Optional[str] = Field(None, description="Email body")

    is_active: bool = Field(..., description="Is active")
    last_run_at: Optional[datetime] = Field(None, description="Last run time")
    next_run_at: Optional[datetime] = Field(None, description="Next run time")

    created_by: int = Field(..., description="Creator user ID")
    creator: Optional[CreatorResponse] = Field(None, description="Creator details")

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True


class ScheduledReportListResponse(BaseModel):
    """
    Response schema for scheduled report list.

    WHAT: Paginated list of scheduled reports.

    WHY: Admin management view.
    """

    items: List[ScheduledReportResponse] = Field(..., description="Reports")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")


class ReportExecutionResponse(BaseModel):
    """
    Response schema for report execution.

    WHAT: Execution details for display.

    WHY: Track report generation history.
    """

    id: int = Field(..., description="Execution ID")
    scheduled_report_id: Optional[int] = Field(None, description="Scheduled report ID")
    org_id: int = Field(..., description="Organization ID")

    report_name: str = Field(..., description="Report name")
    report_type: ReportType = Field(..., description="Type of report")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Report parameters")
    output_format: ReportFormat = Field(..., description="Output format")

    status: ExecutionStatus = Field(..., description="Execution status")
    started_at: Optional[datetime] = Field(None, description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    duration_seconds: Optional[float] = Field(None, description="Duration in seconds")

    output_file_key: Optional[str] = Field(None, description="S3 key for output")
    output_size: Optional[int] = Field(None, description="File size in bytes")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    delivery_status: Optional[DeliveryStatus] = Field(None, description="Delivery status")
    delivery_error: Optional[str] = Field(None, description="Delivery error")
    delivered_at: Optional[datetime] = Field(None, description="Delivery time")

    triggered_by: Optional[int] = Field(None, description="User who triggered")
    is_adhoc: bool = Field(..., description="Was ad-hoc generation")

    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True


class ReportExecutionListResponse(BaseModel):
    """
    Response schema for execution list.

    WHAT: Paginated list of executions.

    WHY: Execution history view.
    """

    items: List[ReportExecutionResponse] = Field(..., description="Executions")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")


class ReportTemplateResponse(BaseModel):
    """
    Response schema for report template.

    WHAT: Template details for display.

    WHY: Template management view.
    """

    id: int = Field(..., description="Template ID")
    org_id: int = Field(..., description="Organization ID")

    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    report_type: ReportType = Field(..., description="Type of report")

    parameters: Optional[Dict[str, Any]] = Field(None, description="Default parameters")
    default_format: ReportFormat = Field(..., description="Default output format")

    selected_columns: Optional[List[str]] = Field(None, description="Selected columns")
    grouping: Optional[Dict[str, Any]] = Field(None, description="Grouping config")
    sorting: Optional[Dict[str, Any]] = Field(None, description="Sorting config")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filter config")

    include_charts: bool = Field(..., description="Include charts")
    include_summary: bool = Field(..., description="Include summary")
    chart_config: Optional[Dict[str, Any]] = Field(None, description="Chart config")

    is_public: bool = Field(..., description="Is public")

    created_by: int = Field(..., description="Creator user ID")
    creator: Optional[CreatorResponse] = Field(None, description="Creator details")

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True


class ReportTemplateListResponse(BaseModel):
    """
    Response schema for template list.

    WHAT: Paginated list of templates.

    WHY: Template selection view.
    """

    items: List[ReportTemplateResponse] = Field(..., description="Templates")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")


class ReportGenerateResponse(BaseModel):
    """
    Response schema for report generation.

    WHAT: Generation result with download info.

    WHY: Provide access to generated report.
    """

    execution_id: int = Field(..., description="Execution ID for tracking")
    status: ExecutionStatus = Field(..., description="Execution status")
    download_url: Optional[str] = Field(None, description="Download URL if ready")
    message: str = Field(..., description="Status message")


class ReportTypeInfo(BaseModel):
    """
    Response schema for report type information.

    WHAT: Metadata about a report type.

    WHY: Help users understand available reports.
    """

    type: ReportType = Field(..., description="Report type")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Description")
    available_parameters: List[str] = Field(..., description="Available parameters")
    supports_formats: List[ReportFormat] = Field(..., description="Supported formats")


class ReportTypesResponse(BaseModel):
    """
    Response schema for available report types.

    WHAT: List of available report types with metadata.

    WHY: Help users discover and understand reports.
    """

    types: List[ReportTypeInfo] = Field(..., description="Available report types")
