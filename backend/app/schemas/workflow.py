"""
Pydantic schemas for workflow automation endpoints.

WHAT: Request/response schemas for n8n environment and workflow management API.

WHY: Schemas define API contracts for workflow operations:
1. Validate incoming request data
2. Document API for OpenAPI/Swagger
3. Provide type safety for handlers
4. Control which fields are exposed in responses
5. Mask sensitive fields like API keys

Security Considerations:
- API keys are never returned in responses
- Encrypted fields are hidden from responses
- Org scoping enforced at handler level

HOW: Uses Pydantic v2 with Field validators and ORM mode for SQLAlchemy.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, HttpUrl


# ============================================================================
# Enums
# ============================================================================


class WorkflowStatus(str, Enum):
    """
    Workflow instance status.

    WHY: Mirrors the SQLAlchemy enum for API consistency.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    DELETED = "deleted"


class ExecutionStatus(str, Enum):
    """
    Workflow execution status.

    WHY: Mirrors the SQLAlchemy enum for API consistency.
    """

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# N8n Environment Schemas
# ============================================================================


class N8nEnvironmentCreate(BaseModel):
    """
    N8n environment creation request schema.

    WHAT: Validates data for creating a new n8n environment.

    WHY: Ensures:
    - Valid URL format for base_url
    - API key is provided for authentication
    - Optional webhook URL is valid if provided
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Display name for the n8n environment",
    )
    base_url: str = Field(
        ...,
        max_length=500,
        description="Base URL of the n8n instance (e.g., https://n8n.example.com)",
    )
    api_key: str = Field(
        ...,
        min_length=10,
        description="n8n API key for authentication",
    )
    webhook_url: str | None = Field(
        default=None,
        max_length=500,
        description="Webhook URL for n8n callbacks",
    )
    is_active: bool = Field(
        default=True,
        description="Whether environment is active and available for use",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v.rstrip("/")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Production n8n",
                "base_url": "https://n8n.mycompany.com",
                "api_key": "n8n_api_key_here_xxxxxxx",
                "webhook_url": "https://hooks.mycompany.com/n8n",
                "is_active": True,
            }
        }


class N8nEnvironmentUpdate(BaseModel):
    """
    N8n environment update request schema.

    WHAT: Validates data for updating an existing environment.

    WHY: Allows partial updates - only provided fields are modified.
    API key can be updated separately if credentials change.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Display name for the n8n environment",
    )
    base_url: str | None = Field(
        default=None,
        max_length=500,
        description="Base URL of the n8n instance",
    )
    api_key: str | None = Field(
        default=None,
        min_length=10,
        description="New n8n API key (will be encrypted)",
    )
    webhook_url: str | None = Field(
        default=None,
        max_length=500,
        description="Webhook URL for n8n callbacks",
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether environment is active",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated n8n Environment",
                "is_active": False,
            }
        }


class N8nEnvironmentResponse(BaseModel):
    """
    N8n environment response schema.

    WHAT: Structure for n8n environment data in API responses.

    WHY: Controls which fields are exposed. API key is NEVER
    included in responses for security (OWASP A02).
    """

    id: int = Field(..., description="Environment ID")
    org_id: int = Field(..., description="Organization ID")
    name: str = Field(..., description="Environment name")
    base_url: str = Field(..., description="n8n instance URL")
    is_active: bool = Field(..., description="Whether environment is active")
    webhook_url: str | None = Field(None, description="Webhook URL")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    # Note: api_key_encrypted is intentionally NOT included

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "org_id": 1,
                "name": "Production n8n",
                "base_url": "https://n8n.mycompany.com",
                "is_active": True,
                "webhook_url": "https://hooks.mycompany.com/n8n",
                "created_at": "2025-01-10T10:30:00",
                "updated_at": "2025-01-15T14:20:00",
            }
        }


class N8nEnvironmentListResponse(BaseModel):
    """Paginated n8n environment list response."""

    items: list[N8nEnvironmentResponse] = Field(
        ..., description="List of environments"
    )
    total: int = Field(..., description="Total number of environments")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum items per page")


class N8nHealthCheckResponse(BaseModel):
    """N8n environment health check response."""

    environment_id: int = Field(..., description="Environment ID")
    is_healthy: bool = Field(..., description="Whether n8n is accessible")
    checked_at: datetime = Field(..., description="When check was performed")


# ============================================================================
# Workflow Template Schemas
# ============================================================================


class WorkflowTemplateCreate(BaseModel):
    """
    Workflow template creation request schema.

    WHAT: Validates data for creating a new workflow template.

    WHY: Templates provide reusable automation blueprints.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Template name",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Template description",
    )
    category: str | None = Field(
        default=None,
        max_length=100,
        description="Template category (e.g., notifications, data-sync)",
    )
    n8n_template_id: str | None = Field(
        default=None,
        max_length=100,
        description="ID of template workflow in n8n",
    )
    default_parameters: dict[str, Any] | None = Field(
        default=None,
        description="Default parameter values for the template",
    )
    is_public: bool = Field(
        default=False,
        description="Whether template is visible to all organizations",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Email Notification",
                "description": "Sends email notification when triggered",
                "category": "notifications",
                "is_public": False,
                "default_parameters": {
                    "subject_prefix": "[Alert]",
                    "from_name": "Automation System",
                },
            }
        }


class WorkflowTemplateUpdate(BaseModel):
    """Workflow template update request schema."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Template name",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Template description",
    )
    category: str | None = Field(
        default=None,
        max_length=100,
        description="Template category",
    )
    n8n_template_id: str | None = Field(
        default=None,
        max_length=100,
        description="ID of template workflow in n8n",
    )
    default_parameters: dict[str, Any] | None = Field(
        default=None,
        description="Default parameter values",
    )
    is_public: bool | None = Field(
        default=None,
        description="Whether template is publicly visible",
    )


class WorkflowTemplateResponse(BaseModel):
    """Workflow template response schema."""

    id: int = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    description: str | None = Field(None, description="Template description")
    category: str | None = Field(None, description="Template category")
    n8n_template_id: str | None = Field(None, description="n8n template ID")
    default_parameters: dict[str, Any] | None = Field(
        None, description="Default parameters"
    )
    is_public: bool = Field(..., description="Whether publicly visible")
    created_by_org_id: int | None = Field(
        None, description="Creating organization ID"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")

    class Config:
        from_attributes = True


class WorkflowTemplateListResponse(BaseModel):
    """Paginated workflow template list response."""

    items: list[WorkflowTemplateResponse] = Field(..., description="List of templates")
    total: int = Field(..., description="Total number of templates")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum items per page")
    categories: list[str] = Field(
        default_factory=list, description="Available categories"
    )


# ============================================================================
# Workflow Instance Schemas
# ============================================================================


class WorkflowInstanceCreate(BaseModel):
    """
    Workflow instance creation request schema.

    WHAT: Validates data for creating a new workflow instance.

    WHY: Instances are deployed workflows linked to projects.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Workflow instance name",
    )
    template_id: int | None = Field(
        default=None,
        description="Template to base this instance on",
    )
    project_id: int | None = Field(
        default=None,
        description="Project to link this workflow to",
    )
    n8n_environment_id: int | None = Field(
        default=None,
        description="n8n environment to deploy to",
    )
    parameters: dict[str, Any] | None = Field(
        default=None,
        description="Custom parameters (merged with template defaults)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Lead Capture Automation",
                "template_id": 1,
                "project_id": 5,
                "n8n_environment_id": 1,
                "parameters": {
                    "email_recipients": ["team@example.com"],
                    "slack_channel": "#sales-leads",
                },
            }
        }


class WorkflowInstanceUpdate(BaseModel):
    """Workflow instance update request schema."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Workflow instance name",
    )
    project_id: int | None = Field(
        default=None,
        description="Project to link this workflow to",
    )
    n8n_environment_id: int | None = Field(
        default=None,
        description="n8n environment to deploy to",
    )
    parameters: dict[str, Any] | None = Field(
        default=None,
        description="Custom parameters",
    )


class WorkflowStatusUpdate(BaseModel):
    """
    Workflow status update request schema.

    WHAT: Validates status change requests.

    WHY: Status changes have implications:
    - ACTIVE: Workflow can be executed
    - PAUSED: Temporarily disabled
    - ERROR: Needs attention
    """

    status: WorkflowStatus = Field(
        ...,
        description="New workflow status",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: WorkflowStatus) -> WorkflowStatus:
        """Validate status is not DELETED (use delete endpoint for that)."""
        if v == WorkflowStatus.DELETED:
            raise ValueError("Use DELETE endpoint to delete workflows")
        return v


class WorkflowInstanceResponse(BaseModel):
    """Workflow instance response schema."""

    id: int = Field(..., description="Instance ID")
    org_id: int = Field(..., description="Organization ID")
    name: str = Field(..., description="Instance name")
    status: WorkflowStatus = Field(..., description="Current status")
    template_id: int | None = Field(None, description="Template ID")
    project_id: int | None = Field(None, description="Linked project ID")
    n8n_environment_id: int | None = Field(None, description="n8n environment ID")
    n8n_workflow_id: str | None = Field(None, description="Deployed n8n workflow ID")
    parameters: dict[str, Any] | None = Field(None, description="Custom parameters")
    last_execution_at: datetime | None = Field(
        None, description="Last execution timestamp"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    is_active: bool = Field(..., description="Whether workflow is active")
    can_execute: bool = Field(..., description="Whether workflow can be executed")

    class Config:
        from_attributes = True


class WorkflowInstanceListResponse(BaseModel):
    """Paginated workflow instance list response."""

    items: list[WorkflowInstanceResponse] = Field(
        ..., description="List of workflow instances"
    )
    total: int = Field(..., description="Total number of instances")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum items per page")


class WorkflowStats(BaseModel):
    """Workflow statistics response schema."""

    total: int = Field(..., description="Total workflow instances")
    active: int = Field(..., description="Active workflows")
    by_status: dict[str, int] = Field(..., description="Count by status")
    total_executions: int = Field(..., description="Total executions")
    success_rate: float | None = Field(None, description="Execution success rate")


# ============================================================================
# Execution Log Schemas
# ============================================================================


class ExecutionTriggerRequest(BaseModel):
    """
    Workflow execution trigger request schema.

    WHAT: Validates data for triggering a workflow execution.

    WHY: Allows passing input data to the workflow.
    """

    input_data: dict[str, Any] | None = Field(
        default=None,
        description="Input data to pass to the workflow",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "input_data": {
                    "trigger_source": "api",
                    "lead_id": 12345,
                },
            }
        }


class ExecutionLogResponse(BaseModel):
    """Execution log response schema."""

    id: int = Field(..., description="Execution log ID")
    workflow_instance_id: int = Field(..., description="Workflow instance ID")
    n8n_execution_id: str | None = Field(None, description="n8n execution ID")
    status: ExecutionStatus = Field(..., description="Execution status")
    started_at: datetime = Field(..., description="Execution start time")
    finished_at: datetime | None = Field(None, description="Execution end time")
    input_data: dict[str, Any] | None = Field(None, description="Input data")
    output_data: dict[str, Any] | None = Field(None, description="Output data")
    error_message: str | None = Field(None, description="Error message if failed")
    duration_seconds: float | None = Field(None, description="Execution duration")
    is_complete: bool = Field(..., description="Whether execution is complete")

    class Config:
        from_attributes = True


class ExecutionLogListResponse(BaseModel):
    """Paginated execution log list response."""

    items: list[ExecutionLogResponse] = Field(
        ..., description="List of execution logs"
    )
    total: int = Field(..., description="Total number of logs")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum items per page")


class ExecutionStats(BaseModel):
    """Execution statistics response schema."""

    total: int = Field(..., description="Total executions")
    success: int = Field(..., description="Successful executions")
    failed: int = Field(..., description="Failed executions")
    running: int = Field(..., description="Currently running")
    success_rate: float | None = Field(None, description="Success rate (0-1)")
    average_duration: float | None = Field(
        None, description="Average duration in seconds"
    )


# ============================================================================
# Webhook Schemas
# ============================================================================


class N8nWebhookPayload(BaseModel):
    """
    N8n webhook callback payload schema.

    WHAT: Validates incoming webhook data from n8n.

    WHY: Ensures webhook payloads are properly structured
    before processing.
    """

    execution_id: str = Field(..., description="n8n execution ID")
    workflow_id: str = Field(..., description="n8n workflow ID")
    status: str = Field(..., description="Execution status")
    started_at: datetime | None = Field(None, description="Execution start time")
    finished_at: datetime | None = Field(None, description="Execution end time")
    data: dict[str, Any] | None = Field(None, description="Execution output data")
    error: str | None = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "execution_id": "exec_123",
                "workflow_id": "wf_456",
                "status": "success",
                "started_at": "2025-01-15T10:00:00",
                "finished_at": "2025-01-15T10:00:05",
                "data": {"items_processed": 10},
            }
        }
