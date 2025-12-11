"""
Pydantic schemas for project endpoints.

WHAT: Request/response schemas for project management API.

WHY: Schemas define API contracts for project operations:
1. Validate incoming request data
2. Document API for OpenAPI/Swagger
3. Provide type safety for handlers
4. Control which fields are exposed in responses

HOW: Uses Pydantic v2 with Field validators and ORM mode for SQLAlchemy.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ProjectStatus(str, Enum):
    """
    Project lifecycle status.

    WHY: Mirrors the SQLAlchemy enum for API consistency.
    """

    DRAFT = "draft"
    PROPOSAL_SENT = "proposal_sent"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectPriority(str, Enum):
    """
    Project priority level.

    WHY: Mirrors the SQLAlchemy enum for API consistency.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ProjectCreate(BaseModel):
    """
    Project creation request schema.

    WHAT: Validates data for creating a new project.

    WHY: Ensures all required fields are present and valid before
    database insertion. Projects start in DRAFT status automatically.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Project name/title",
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Detailed project description",
    )
    priority: ProjectPriority = Field(
        default=ProjectPriority.MEDIUM,
        description="Project priority level",
    )
    estimated_hours: float | None = Field(
        default=None,
        ge=0,
        description="Estimated hours for project completion",
    )
    start_date: datetime | None = Field(
        default=None,
        description="Planned start date (ISO 8601 format)",
    )
    due_date: datetime | None = Field(
        default=None,
        description="Target completion date (ISO 8601 format)",
    )

    @field_validator("due_date")
    @classmethod
    def due_date_after_start_date(cls, v: datetime | None, info) -> datetime | None:
        """
        Validate due_date is after start_date.

        WHY: Logical constraint - can't have due date before start date.
        """
        if v is not None and info.data.get("start_date") is not None:
            if v < info.data["start_date"]:
                raise ValueError("due_date must be after start_date")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Website Automation Project",
                "description": "Automate lead capture and CRM integration",
                "priority": "high",
                "estimated_hours": 40,
                "start_date": "2025-01-15T00:00:00",
                "due_date": "2025-02-15T00:00:00",
            }
        }


class ProjectUpdate(BaseModel):
    """
    Project update request schema.

    WHAT: Validates data for updating an existing project.

    WHY: Allows partial updates - only provided fields are modified.
    Status changes use a separate endpoint for workflow control.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Project name/title",
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Detailed project description",
    )
    priority: ProjectPriority | None = Field(
        default=None,
        description="Project priority level",
    )
    estimated_hours: float | None = Field(
        default=None,
        ge=0,
        description="Estimated hours for project completion",
    )
    actual_hours: float | None = Field(
        default=None,
        ge=0,
        description="Actual hours spent on project",
    )
    start_date: datetime | None = Field(
        default=None,
        description="Planned start date (ISO 8601 format)",
    )
    due_date: datetime | None = Field(
        default=None,
        description="Target completion date (ISO 8601 format)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated Project Name",
                "priority": "urgent",
                "actual_hours": 25,
            }
        }


class ProjectStatusUpdate(BaseModel):
    """
    Project status update request schema.

    WHAT: Validates status change requests.

    WHY: Status changes have business implications:
    - COMPLETED sets completed_at timestamp
    - Certain transitions may trigger notifications
    - Separate endpoint allows audit logging of status changes
    """

    status: ProjectStatus = Field(
        ...,
        description="New project status",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "in_progress",
            }
        }


class ProjectResponse(BaseModel):
    """
    Project response schema.

    WHAT: Structure for project data in API responses.

    WHY: Controls which fields are exposed and adds computed properties.
    Uses ORM mode for automatic SQLAlchemy model conversion.
    """

    id: int = Field(..., description="Project ID")
    name: str = Field(..., description="Project name/title")
    description: str | None = Field(None, description="Project description")
    status: ProjectStatus = Field(..., description="Current project status")
    priority: ProjectPriority = Field(..., description="Project priority level")
    org_id: int = Field(..., description="Organization ID")
    estimated_hours: float | None = Field(None, description="Estimated hours")
    actual_hours: float | None = Field(None, description="Actual hours spent")
    start_date: datetime | None = Field(None, description="Planned start date")
    due_date: datetime | None = Field(None, description="Target completion date")
    completed_at: datetime | None = Field(None, description="Completion timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    is_active: bool = Field(..., description="Whether project is active")
    is_overdue: bool = Field(..., description="Whether project is past due date")
    hours_remaining: float | None = Field(None, description="Estimated hours remaining")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Website Automation Project",
                "description": "Automate lead capture and CRM integration",
                "status": "in_progress",
                "priority": "high",
                "org_id": 1,
                "estimated_hours": 40,
                "actual_hours": 25,
                "start_date": "2025-01-15T00:00:00",
                "due_date": "2025-02-15T00:00:00",
                "completed_at": None,
                "created_at": "2025-01-10T10:30:00",
                "updated_at": "2025-01-20T15:45:00",
                "is_active": True,
                "is_overdue": False,
                "hours_remaining": 15,
            }
        }


class ProjectListResponse(BaseModel):
    """
    Paginated project list response schema.

    WHAT: Wrapper for paginated project list responses.

    WHY: Provides pagination metadata alongside items for:
    - Client-side pagination UI
    - Total count for progress indicators
    - Consistent list response format across API
    """

    items: list[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects matching filters")
    skip: int = Field(..., description="Number of items skipped (offset)")
    limit: int = Field(..., description="Maximum items per page")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": 1,
                        "name": "Website Automation",
                        "status": "in_progress",
                        "priority": "high",
                        "org_id": 1,
                        "is_active": True,
                        "is_overdue": False,
                    }
                ],
                "total": 15,
                "skip": 0,
                "limit": 10,
            }
        }


class ProjectStats(BaseModel):
    """
    Project statistics response schema.

    WHAT: Aggregated project metrics for dashboards.

    WHY: Provides quick overview of project states without
    fetching all project data. Useful for dashboard widgets.
    """

    total: int = Field(..., description="Total projects")
    active: int = Field(..., description="Active (not completed/cancelled) projects")
    by_status: dict[str, int] = Field(
        ..., description="Count of projects by status"
    )
    overdue: int = Field(..., description="Number of overdue projects")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 25,
                "active": 18,
                "by_status": {
                    "draft": 3,
                    "proposal_sent": 2,
                    "approved": 4,
                    "in_progress": 8,
                    "on_hold": 1,
                    "completed": 5,
                    "cancelled": 2,
                },
                "overdue": 2,
            }
        }
