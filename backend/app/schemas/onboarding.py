"""
Onboarding Pydantic Schemas.

WHAT: Request/Response models for onboarding API endpoints.

WHY: Pydantic schemas provide:
1. Request validation
2. Response serialization
3. OpenAPI documentation
4. Type safety

HOW: Defines schemas for:
- Onboarding templates
- Client onboarding progress
- Step completion
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class OnboardingStatus(str, Enum):
    """Onboarding status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    SKIPPED = "skipped"


class StepType(str, Enum):
    """Step types."""

    INFO = "info"
    FORM = "form"
    UPLOAD = "upload"
    CHOICE = "choice"
    VERIFICATION = "verification"
    INTEGRATION = "integration"
    REVIEW = "review"


# ============================================================================
# Step Schemas
# ============================================================================


class StepFieldSchema(BaseModel):
    """
    Schema for a form field in a step.

    WHAT: Defines a data collection field.

    WHY: Form steps contain multiple fields.
    """

    name: str = Field(..., description="Field name")
    type: str = Field(..., description="Field type (text, select, checkbox, etc.)")
    label: Optional[str] = Field(None, description="Field label")
    required: bool = Field(default=False, description="Is required")
    placeholder: Optional[str] = Field(None, description="Placeholder text")
    options: Optional[List[str]] = Field(None, description="Options for select/radio")
    validation: Optional[Dict[str, Any]] = Field(None, description="Validation rules")


class StepSchema(BaseModel):
    """
    Schema for an onboarding step.

    WHAT: Defines a single step in the flow.

    WHY: Templates contain multiple steps.
    """

    id: str = Field(..., description="Unique step ID")
    title: str = Field(..., description="Step title")
    type: StepType = Field(..., description="Step type")
    description: Optional[str] = Field(None, description="Step description")
    content: Optional[str] = Field(None, description="Info content (for info type)")
    fields: Optional[List[StepFieldSchema]] = Field(None, description="Form fields")
    required_docs: Optional[List[str]] = Field(
        None, description="Required documents (for upload type)"
    )
    is_required: bool = Field(default=True, description="Is step required")
    can_skip: bool = Field(default=False, description="Can user skip this step")


# ============================================================================
# Request Schemas
# ============================================================================


class OnboardingTemplateCreateRequest(BaseModel):
    """
    Request schema for creating an onboarding template.

    WHAT: Fields needed to create a template.

    WHY: Validates template creation data.
    """

    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    slug: str = Field(
        ..., min_length=1, max_length=50,
        description="URL-friendly slug",
        pattern=r"^[a-z0-9-]+$",
    )

    steps: List[StepSchema] = Field(..., min_length=1, description="Template steps")

    is_active: bool = Field(default=True, description="Is active")
    is_default: bool = Field(default=False, description="Is default template")
    auto_assign: bool = Field(default=False, description="Auto-assign to new users")
    target_roles: Optional[List[str]] = Field(None, description="Target user roles")


class OnboardingTemplateUpdateRequest(BaseModel):
    """
    Request schema for updating an onboarding template.

    WHAT: Fields that can be updated.

    WHY: Allows partial updates.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    steps: Optional[List[StepSchema]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    auto_assign: Optional[bool] = None
    target_roles: Optional[List[str]] = None


class StepCompleteRequest(BaseModel):
    """
    Request schema for completing a step.

    WHAT: Data submitted when completing a step.

    WHY: Validates step completion data.
    """

    step_data: Optional[Dict[str, Any]] = Field(
        None, description="Data collected in this step"
    )


class OnboardingStartRequest(BaseModel):
    """
    Request schema for starting onboarding.

    WHAT: Parameters to start onboarding.

    WHY: Specify which template to use.
    """

    template_id: Optional[int] = Field(
        None, description="Template ID (uses default if not specified)"
    )


# ============================================================================
# Response Schemas
# ============================================================================


class OnboardingTemplateResponse(BaseModel):
    """
    Response schema for onboarding template.

    WHAT: Template details for display.

    WHY: Admin template management.
    """

    id: int = Field(..., description="Template ID")
    org_id: int = Field(..., description="Organization ID")

    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    slug: str = Field(..., description="URL slug")

    steps: List[StepSchema] = Field(..., description="Template steps")
    step_count: int = Field(..., description="Number of steps")
    required_step_count: int = Field(..., description="Number of required steps")

    is_active: bool = Field(..., description="Is active")
    is_default: bool = Field(..., description="Is default")
    auto_assign: bool = Field(..., description="Auto-assign to new users")
    target_roles: Optional[List[str]] = Field(None, description="Target roles")

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True


class OnboardingTemplateListResponse(BaseModel):
    """
    Response schema for template list.

    WHAT: Paginated list of templates.

    WHY: Template management view.
    """

    items: List[OnboardingTemplateResponse] = Field(..., description="Templates")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")


class UserResponse(BaseModel):
    """User info for onboarding response."""

    id: int = Field(..., description="User ID")
    name: Optional[str] = Field(None, description="User name")
    email: str = Field(..., description="User email")

    class Config:
        from_attributes = True


class ClientOnboardingResponse(BaseModel):
    """
    Response schema for client onboarding.

    WHAT: Onboarding progress for display.

    WHY: Show progress to user.
    """

    id: int = Field(..., description="Onboarding ID")
    org_id: int = Field(..., description="Organization ID")
    user_id: int = Field(..., description="User ID")
    template_id: int = Field(..., description="Template ID")

    status: OnboardingStatus = Field(..., description="Status")
    current_step: Optional[str] = Field(None, description="Current step ID")
    completed_steps: Optional[List[str]] = Field(None, description="Completed step IDs")
    skipped_steps: Optional[List[str]] = Field(None, description="Skipped step IDs")
    progress_percent: int = Field(..., description="Progress percentage")

    step_data: Optional[Dict[str, Any]] = Field(None, description="Collected data")

    started_at: Optional[datetime] = Field(None, description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    last_activity_at: Optional[datetime] = Field(None, description="Last activity time")

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    # Include template and user info
    template: Optional[OnboardingTemplateResponse] = Field(
        None, description="Template details"
    )
    user: Optional[UserResponse] = Field(None, description="User details")

    class Config:
        from_attributes = True


class ClientOnboardingListResponse(BaseModel):
    """
    Response schema for onboarding list.

    WHAT: Paginated list of onboardings.

    WHY: Admin view of all onboardings.
    """

    items: List[ClientOnboardingResponse] = Field(..., description="Onboardings")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")


class OnboardingProgressResponse(BaseModel):
    """
    Response schema for current user's onboarding progress.

    WHAT: Progress details with current step info.

    WHY: Show wizard UI to user.
    """

    id: int = Field(..., description="Onboarding ID")
    status: OnboardingStatus = Field(..., description="Status")
    progress_percent: int = Field(..., description="Progress percentage")

    current_step: Optional[StepSchema] = Field(None, description="Current step details")
    current_step_index: int = Field(..., description="Current step index (0-based)")
    total_steps: int = Field(..., description="Total number of steps")

    completed_steps: List[str] = Field(..., description="Completed step IDs")
    skipped_steps: List[str] = Field(..., description="Skipped step IDs")

    step_data: Dict[str, Any] = Field(..., description="All collected data")

    template_name: str = Field(..., description="Template name")
    template_description: Optional[str] = Field(None, description="Template description")


class OnboardingStatsResponse(BaseModel):
    """
    Response schema for onboarding statistics.

    WHAT: Aggregated stats for analytics.

    WHY: Dashboard metrics.
    """

    not_started: int = Field(..., description="Count not started")
    in_progress: int = Field(..., description="Count in progress")
    completed: int = Field(..., description="Count completed")
    abandoned: int = Field(..., description="Count abandoned")
    skipped: int = Field(..., description="Count skipped")
    total: int = Field(..., description="Total count")
    completion_rate: float = Field(..., description="Completion rate (0-1)")
