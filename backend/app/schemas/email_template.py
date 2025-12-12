"""
Email Template Pydantic Schemas.

WHAT: Request/Response models for email template API endpoints.

WHY: Pydantic schemas provide:
1. Request validation
2. Response serialization
3. OpenAPI documentation
4. Type safety

HOW: Defines schemas for:
- Template management
- Version control
- Sent email logs
- Email analytics
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, EmailStr


class EmailCategory(str, Enum):
    """Email template categories."""

    ACCOUNT = "account"
    NOTIFICATIONS = "notifications"
    BILLING = "billing"
    PROJECT = "project"
    MARKETING = "marketing"
    SYSTEM = "system"


class EmailStatus(str, Enum):
    """Email delivery status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


# ============================================================================
# Variable Schema
# ============================================================================


class VariableSchema(BaseModel):
    """
    Schema for template variable definition.

    WHAT: Defines a variable in a template.

    WHY: Variables allow personalization.
    """

    type: str = Field(..., description="Variable type (string, url, number, date)")
    description: str = Field(..., description="Variable description")
    required: bool = Field(default=False, description="Is required")
    default: Optional[str] = Field(None, description="Default value")


# ============================================================================
# Request Schemas
# ============================================================================


class EmailTemplateCreateRequest(BaseModel):
    """
    Request schema for creating an email template.

    WHAT: Fields needed to create a template.

    WHY: Validates template creation data.
    """

    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="URL-friendly slug",
        pattern=r"^[a-z0-9-_]+$",
    )
    description: Optional[str] = Field(None, description="Template description")
    category: EmailCategory = Field(
        default=EmailCategory.SYSTEM, description="Template category"
    )

    subject: str = Field(..., min_length=1, max_length=200, description="Email subject")
    html_body: str = Field(..., min_length=1, description="HTML email body")
    text_body: Optional[str] = Field(None, description="Plain text email body")

    variables: Optional[Dict[str, VariableSchema]] = Field(
        None, description="Template variables"
    )


class EmailTemplateUpdateRequest(BaseModel):
    """
    Request schema for updating an email template.

    WHAT: Fields that can be updated.

    WHY: Allows partial updates with versioning.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    category: Optional[EmailCategory] = None

    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    html_body: Optional[str] = Field(None, min_length=1)
    text_body: Optional[str] = None

    variables: Optional[Dict[str, VariableSchema]] = None

    change_note: Optional[str] = Field(
        None, max_length=500, description="Description of changes"
    )


class RenderTemplateRequest(BaseModel):
    """
    Request schema for rendering a template.

    WHAT: Variables for template rendering.

    WHY: Preview or send emails.
    """

    variables: Dict[str, Any] = Field(..., description="Variables to substitute")
    preview_only: bool = Field(default=True, description="Preview without sending")


class SendEmailRequest(BaseModel):
    """
    Request schema for sending an email.

    WHAT: Email sending parameters.

    WHY: Send templated emails.
    """

    template_slug: str = Field(..., description="Template slug to use")
    to_email: EmailStr = Field(..., description="Recipient email")
    to_name: Optional[str] = Field(None, description="Recipient name")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables")
    from_name: Optional[str] = Field(None, description="Override sender name")


# ============================================================================
# Response Schemas
# ============================================================================


class UserResponse(BaseModel):
    """User info for email responses."""

    id: int = Field(..., description="User ID")
    name: Optional[str] = Field(None, description="User name")
    email: str = Field(..., description="User email")

    class Config:
        from_attributes = True


class EmailTemplateResponse(BaseModel):
    """
    Response schema for email template.

    WHAT: Template details for display.

    WHY: Admin template management.
    """

    id: int = Field(..., description="Template ID")
    org_id: int = Field(..., description="Organization ID")

    name: str = Field(..., description="Template name")
    slug: str = Field(..., description="Template slug")
    description: Optional[str] = Field(None, description="Template description")
    category: EmailCategory = Field(..., description="Template category")

    subject: str = Field(..., description="Email subject")
    html_body: str = Field(..., description="HTML body")
    text_body: Optional[str] = Field(None, description="Plain text body")

    variables: Optional[Dict[str, Any]] = Field(None, description="Template variables")
    variable_names: List[str] = Field(..., description="List of variable names")

    is_active: bool = Field(..., description="Is active")
    is_system: bool = Field(..., description="Is system template")
    version: int = Field(..., description="Current version")

    created_by: Optional[UserResponse] = Field(None, description="Creator")
    updated_by: Optional[UserResponse] = Field(None, description="Last updater")

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True


class EmailTemplateListResponse(BaseModel):
    """
    Response schema for template list.

    WHAT: Paginated list of templates.

    WHY: Template management view.
    """

    items: List[EmailTemplateResponse] = Field(..., description="Templates")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")


class EmailTemplateVersionResponse(BaseModel):
    """
    Response schema for template version.

    WHAT: Version details.

    WHY: View version history.
    """

    id: int = Field(..., description="Version ID")
    template_id: int = Field(..., description="Template ID")
    version: int = Field(..., description="Version number")

    subject: str = Field(..., description="Subject at this version")
    html_body: str = Field(..., description="HTML body at this version")
    text_body: Optional[str] = Field(None, description="Plain text body")
    variables: Optional[Dict[str, Any]] = Field(None, description="Variables")

    changed_by: Optional[UserResponse] = Field(None, description="Who made change")
    change_note: Optional[str] = Field(None, description="Change description")

    created_at: datetime = Field(..., description="Version timestamp")

    class Config:
        from_attributes = True


class EmailTemplateVersionListResponse(BaseModel):
    """
    Response schema for version list.

    WHAT: List of template versions.

    WHY: Version history view.
    """

    items: List[EmailTemplateVersionResponse] = Field(..., description="Versions")
    total: int = Field(..., description="Total count")


class RenderedEmailResponse(BaseModel):
    """
    Response schema for rendered email.

    WHAT: Rendered email content.

    WHY: Preview email before sending.
    """

    subject: str = Field(..., description="Rendered subject")
    html_body: str = Field(..., description="Rendered HTML")
    text_body: Optional[str] = Field(None, description="Rendered text")


class SentEmailResponse(BaseModel):
    """
    Response schema for sent email log.

    WHAT: Sent email details.

    WHY: Email history and debugging.
    """

    id: int = Field(..., description="Email ID")
    org_id: int = Field(..., description="Organization ID")

    template_id: Optional[int] = Field(None, description="Template ID")
    template_slug: Optional[str] = Field(None, description="Template slug")

    to_email: str = Field(..., description="Recipient email")
    to_name: Optional[str] = Field(None, description="Recipient name")
    from_email: str = Field(..., description="Sender email")
    from_name: Optional[str] = Field(None, description="Sender name")
    subject: str = Field(..., description="Email subject")

    status: EmailStatus = Field(..., description="Delivery status")
    error_message: Optional[str] = Field(None, description="Error message")

    message_id: Optional[str] = Field(None, description="Provider message ID")
    provider: Optional[str] = Field(None, description="Email provider")

    sent_at: Optional[datetime] = Field(None, description="When sent")
    opened_at: Optional[datetime] = Field(None, description="When opened")
    clicked_at: Optional[datetime] = Field(None, description="When clicked")

    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True


class SentEmailListResponse(BaseModel):
    """
    Response schema for sent email list.

    WHAT: Paginated list of sent emails.

    WHY: Email history view.
    """

    items: List[SentEmailResponse] = Field(..., description="Sent emails")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")


class EmailStatsResponse(BaseModel):
    """
    Response schema for email statistics.

    WHAT: Aggregated email metrics.

    WHY: Analytics dashboard.
    """

    total: int = Field(..., description="Total emails")
    pending: int = Field(..., description="Pending count")
    sent: int = Field(..., description="Sent count")
    delivered: int = Field(..., description="Delivered count")
    bounced: int = Field(..., description="Bounced count")
    failed: int = Field(..., description="Failed count")

    opens: int = Field(..., description="Open count")
    clicks: int = Field(..., description="Click count")

    delivery_rate: float = Field(..., description="Delivery rate (0-1)")
    open_rate: float = Field(..., description="Open rate (0-1)")
    click_rate: float = Field(..., description="Click-through rate (0-1)")
