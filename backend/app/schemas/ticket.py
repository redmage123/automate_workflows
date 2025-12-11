"""
Pydantic schemas for ticket endpoints.

WHAT: Request/response schemas for ticket management API.

WHY: Schemas define API contracts for ticket operations:
1. Validate incoming request data including comments and attachments
2. Document API for OpenAPI/Swagger
3. Provide type safety for handlers
4. Control which fields are exposed (hide internal notes from clients)

HOW: Uses Pydantic v2 with Field validators, nested models for related data,
and ORM mode for SQLAlchemy integration.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any, List
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Enums (mirrors SQLAlchemy enums for API)
# ============================================================================


class TicketStatus(str, Enum):
    """
    Ticket status values.

    WHY: Mirrors the SQLAlchemy enum for API consistency.
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """
    Ticket priority levels.

    WHY: Mirrors the SQLAlchemy enum for API consistency.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketCategory(str, Enum):
    """
    Ticket category values.

    WHY: Mirrors the SQLAlchemy enum for API consistency.
    """

    GENERAL = "general"
    BUG = "bug"
    FEATURE = "feature"
    QUESTION = "question"
    SUPPORT = "support"


# ============================================================================
# User Reference Schema
# ============================================================================


class UserReference(BaseModel):
    """
    Minimal user info for ticket references.

    WHAT: Compact user data for embedding in ticket responses.

    WHY: Avoids exposing full user details while providing
    necessary info for display (name, email).
    """

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: str | None = Field(None, description="User name")

    class Config:
        from_attributes = True


# ============================================================================
# Attachment Schemas
# ============================================================================


class AttachmentCreate(BaseModel):
    """
    Attachment creation request.

    WHAT: Data for uploading a file attachment.

    WHY: Validates file metadata before storage.
    Note: Actual file upload is handled separately via multipart form.
    """

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original filename",
    )
    file_size: int = Field(
        ...,
        gt=0,
        le=10 * 1024 * 1024,  # 10MB max
        description="File size in bytes",
    )
    mime_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="MIME type of the file",
    )

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, v: str) -> str:
        """
        Validate MIME type is allowed.

        WHY: Prevent upload of dangerous file types.
        """
        allowed_types = [
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "application/pdf",
            "text/plain",
            "text/csv",
            "application/json",
            "application/zip",
            "application/x-zip-compressed",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ]
        if v not in allowed_types:
            raise ValueError(f"File type not allowed: {v}")
        return v


class AttachmentResponse(BaseModel):
    """
    Attachment response schema.

    WHAT: Attachment data for API responses.

    WHY: Controls which fields are exposed and formats data.
    """

    id: int = Field(..., description="Attachment ID")
    ticket_id: int = Field(..., description="Parent ticket ID")
    comment_id: int | None = Field(None, description="Parent comment ID if attached to comment")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    created_at: datetime = Field(..., description="Upload timestamp")
    uploaded_by: UserReference | None = Field(None, description="User who uploaded")
    download_url: str | None = Field(None, description="URL to download file")

    @property
    def file_size_formatted(self) -> str:
        """Get human-readable file size."""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"

    class Config:
        from_attributes = True


# ============================================================================
# Comment Schemas
# ============================================================================


class CommentCreate(BaseModel):
    """
    Comment creation request.

    WHAT: Data for adding a comment to a ticket.

    WHY: Validates comment content and internal flag.
    """

    content: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Comment content (supports markdown)",
    )
    is_internal: bool = Field(
        default=False,
        description="True for internal notes (hidden from clients)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "I've investigated this issue and found the root cause...",
                "is_internal": False,
            }
        }


class CommentUpdate(BaseModel):
    """
    Comment update request.

    WHAT: Data for editing a comment.

    WHY: Allows editing comment content (not internal flag).
    """

    content: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Updated comment content",
    )


class CommentResponse(BaseModel):
    """
    Comment response schema.

    WHAT: Comment data for API responses.

    WHY: Controls which fields are exposed.
    Note: is_internal comments are filtered based on user role.
    """

    id: int = Field(..., description="Comment ID")
    ticket_id: int = Field(..., description="Parent ticket ID")
    content: str = Field(..., description="Comment content")
    is_internal: bool = Field(..., description="True if internal note")
    is_edited: bool = Field(default=False, description="True if comment was edited")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last edit timestamp")
    user: UserReference | None = Field(None, description="Comment author")
    attachments: List[AttachmentResponse] = Field(
        default_factory=list,
        description="Attachments on this comment",
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "ticket_id": 1,
                "content": "I've looked into this and found the issue...",
                "is_internal": False,
                "is_edited": False,
                "created_at": "2025-12-11T10:00:00",
                "updated_at": None,
                "user": {
                    "id": 1,
                    "email": "admin@example.com",
                    "first_name": "Admin",
                    "last_name": "User",
                },
                "attachments": [],
            }
        }


# ============================================================================
# SLA Schemas
# ============================================================================


class SLATimeRemaining(BaseModel):
    """
    SLA time remaining breakdown.

    WHAT: Detailed time remaining until SLA deadline.

    WHY: Enables countdown timers and progress bars in UI.
    """

    hours: int = Field(..., description="Hours remaining")
    minutes: int = Field(..., description="Minutes remaining")
    seconds: int = Field(..., description="Seconds remaining")
    total_seconds: int = Field(..., description="Total seconds remaining")
    is_breached: bool = Field(..., description="True if SLA is breached")
    formatted: str = Field(..., description="Human-readable format (e.g., '2h 30m')")


class SLAStatus(BaseModel):
    """
    SLA status for response or resolution.

    WHAT: Current state of an SLA timer.

    WHY: Provides all info needed to display SLA status.
    """

    due_at: datetime | None = Field(None, description="SLA deadline")
    is_met: bool = Field(..., description="True if SLA was met")
    is_breached: bool = Field(..., description="True if SLA is breached")
    is_warning: bool = Field(..., description="True if approaching breach")
    time_remaining: SLATimeRemaining | None = Field(
        None,
        description="Time remaining until deadline",
    )


class TicketSLAResponse(BaseModel):
    """
    Full SLA status response.

    WHAT: Complete SLA information for a ticket.

    WHY: Single response with all SLA data for ticket details view.
    """

    ticket_id: int = Field(..., description="Ticket ID")
    priority: TicketPriority = Field(..., description="Ticket priority")
    status: TicketStatus = Field(..., description="Ticket status")
    sla_config: dict[str, int] = Field(
        ...,
        description="SLA config (response_hours, resolution_hours)",
    )
    response: SLAStatus = Field(..., description="First response SLA status")
    resolution: SLAStatus = Field(..., description="Resolution SLA status")


# ============================================================================
# Ticket Schemas
# ============================================================================


class TicketCreate(BaseModel):
    """
    Ticket creation request.

    WHAT: Data for creating a new support ticket.

    WHY: Validates required fields and sets defaults.
    """

    subject: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Ticket subject/title",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=50000,
        description="Detailed description of the issue",
    )
    project_id: int | None = Field(
        default=None,
        gt=0,
        description="Related project ID (optional)",
    )
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM,
        description="Ticket priority",
    )
    category: TicketCategory = Field(
        default=TicketCategory.SUPPORT,
        description="Ticket category",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "subject": "Cannot connect workflow to Google Sheets",
                "description": "When I try to connect the workflow to Google Sheets, I get an authentication error. I've already re-authorized the connection but the issue persists.",
                "project_id": 1,
                "priority": "high",
                "category": "bug",
            }
        }


class TicketUpdate(BaseModel):
    """
    Ticket update request.

    WHAT: Data for updating a ticket.

    WHY: Allows partial updates to ticket fields.
    Note: Status changes should use dedicated endpoint.
    """

    subject: str | None = Field(
        default=None,
        min_length=5,
        max_length=500,
        description="Updated subject",
    )
    description: str | None = Field(
        default=None,
        min_length=10,
        max_length=50000,
        description="Updated description",
    )
    project_id: int | None = Field(
        default=None,
        description="Updated project ID",
    )
    priority: TicketPriority | None = Field(
        default=None,
        description="Updated priority",
    )
    category: TicketCategory | None = Field(
        default=None,
        description="Updated category",
    )


class TicketStatusChange(BaseModel):
    """
    Ticket status change request.

    WHAT: Data for changing ticket status.

    WHY: Status changes may require additional data (resolution notes).
    """

    status: TicketStatus = Field(..., description="New status")
    resolution_notes: str | None = Field(
        default=None,
        max_length=5000,
        description="Notes when resolving/closing",
    )


class TicketAssign(BaseModel):
    """
    Ticket assignment request.

    WHAT: Data for assigning a ticket to a user.

    WHY: Assignment triggers notifications and status changes.
    """

    assigned_to_user_id: int | None = Field(
        default=None,
        description="User ID to assign to (None to unassign)",
    )


class TicketResponse(BaseModel):
    """
    Ticket response schema.

    WHAT: Full ticket data for API responses.

    WHY: Controls which fields are exposed and includes computed properties.
    """

    id: int = Field(..., description="Ticket ID")
    org_id: int = Field(..., description="Organization ID")
    project_id: int | None = Field(None, description="Related project ID")
    subject: str = Field(..., description="Ticket subject")
    description: str = Field(..., description="Ticket description")
    status: TicketStatus = Field(..., description="Current status")
    priority: TicketPriority = Field(..., description="Priority level")
    category: TicketCategory = Field(..., description="Ticket category")

    # SLA fields
    sla_response_due_at: datetime | None = Field(None, description="Response SLA deadline")
    sla_resolution_due_at: datetime | None = Field(None, description="Resolution SLA deadline")
    first_response_at: datetime | None = Field(None, description="When first response was made")
    is_sla_response_breached: bool = Field(default=False, description="Response SLA breached")
    is_sla_resolution_breached: bool = Field(default=False, description="Resolution SLA breached")

    # Status timestamps
    resolved_at: datetime | None = Field(None, description="When resolved")
    closed_at: datetime | None = Field(None, description="When closed")

    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")

    # Related users
    created_by: UserReference | None = Field(None, description="Ticket creator")
    assigned_to: UserReference | None = Field(None, description="Assigned user")

    # Comment count (not full comments for list views)
    comment_count: int = Field(default=0, description="Number of comments")
    attachment_count: int = Field(default=0, description="Number of attachments")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "org_id": 1,
                "project_id": 1,
                "subject": "Cannot connect workflow to Google Sheets",
                "description": "When I try to connect...",
                "status": "open",
                "priority": "high",
                "category": "bug",
                "sla_response_due_at": "2025-12-11T14:00:00",
                "sla_resolution_due_at": "2025-12-12T10:00:00",
                "first_response_at": None,
                "is_sla_response_breached": False,
                "is_sla_resolution_breached": False,
                "resolved_at": None,
                "closed_at": None,
                "created_at": "2025-12-11T10:00:00",
                "updated_at": None,
                "created_by": {
                    "id": 2,
                    "email": "client@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                },
                "assigned_to": None,
                "comment_count": 0,
                "attachment_count": 0,
            }
        }


class TicketDetailResponse(TicketResponse):
    """
    Detailed ticket response with comments.

    WHAT: Full ticket data including comments and attachments.

    WHY: Used for ticket detail view, includes all related data.
    Note: Internal comments are filtered based on user role.
    """

    comments: List[CommentResponse] = Field(
        default_factory=list,
        description="Ticket comments",
    )
    attachments: List[AttachmentResponse] = Field(
        default_factory=list,
        description="Ticket attachments",
    )
    project_name: str | None = Field(None, description="Related project name")


class TicketListResponse(BaseModel):
    """
    Paginated ticket list response.

    WHAT: Wrapper for paginated ticket responses.

    WHY: Provides pagination metadata alongside items.
    """

    items: List[TicketResponse] = Field(..., description="List of tickets")
    total: int = Field(..., description="Total tickets matching filters")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum items per page")


# ============================================================================
# Stats Schemas
# ============================================================================


class TicketStats(BaseModel):
    """
    Ticket statistics response.

    WHAT: Aggregated ticket metrics for dashboards.

    WHY: Quick overview of ticket status without fetching all data.
    """

    total: int = Field(..., description="Total tickets")
    by_status: dict[str, int] = Field(..., description="Count by status")
    by_priority: dict[str, int] = Field(..., description="Count by priority")
    open_count: int = Field(..., description="Open tickets")
    sla_breached_count: int = Field(..., description="Tickets with breached SLA")
    avg_resolution_hours: float | None = Field(
        None,
        description="Average resolution time in hours",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total": 45,
                "by_status": {
                    "open": 10,
                    "in_progress": 8,
                    "waiting": 5,
                    "resolved": 12,
                    "closed": 10,
                },
                "by_priority": {
                    "urgent": 2,
                    "high": 8,
                    "medium": 25,
                    "low": 10,
                },
                "open_count": 23,
                "sla_breached_count": 3,
                "avg_resolution_hours": 18.5,
            }
        }


class SLAAtRiskResponse(BaseModel):
    """
    Tickets at risk of SLA breach.

    WHAT: Lists tickets that are breached or approaching breach.

    WHY: Enables SLA monitoring dashboard.
    """

    breached: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Tickets with breached SLA",
    )
    warning: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Tickets approaching SLA breach",
    )
