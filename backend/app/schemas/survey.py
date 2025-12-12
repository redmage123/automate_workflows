"""
Survey Pydantic Schemas.

WHAT: Request/Response models for survey API endpoints.

WHY: Pydantic schemas provide:
1. Request validation
2. Response serialization
3. OpenAPI documentation
4. Type safety

HOW: Defines schemas for:
- Survey management
- Questions and responses
- NPS/CSAT metrics
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class SurveyType(str, Enum):
    """Survey types."""

    NPS = "nps"
    CSAT = "csat"
    CES = "ces"
    PROJECT_FEEDBACK = "project_feedback"
    CUSTOM = "custom"


class SurveyStatus(str, Enum):
    """Survey status."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class QuestionType(str, Enum):
    """Question types."""

    RATING = "rating"
    NPS = "nps"
    TEXT = "text"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    YES_NO = "yes_no"
    DATE = "date"


# ============================================================================
# Question Schemas
# ============================================================================


class QuestionSchema(BaseModel):
    """
    Schema for a survey question.

    WHAT: Defines a question in a survey.

    WHY: Questions have different types with different options.
    """

    id: str = Field(..., description="Unique question ID")
    type: QuestionType = Field(..., description="Question type")
    text: str = Field(..., description="Question text")
    required: bool = Field(default=False, description="Is required")
    order: int = Field(default=0, description="Display order")

    # Type-specific options
    min_value: Optional[int] = Field(None, description="Min value for rating")
    max_value: Optional[int] = Field(None, description="Max value for rating")
    options: Optional[List[str]] = Field(None, description="Choices for select types")
    placeholder: Optional[str] = Field(None, description="Placeholder text")
    description: Optional[str] = Field(None, description="Help text")


# ============================================================================
# Request Schemas
# ============================================================================


class SurveyCreateRequest(BaseModel):
    """
    Request schema for creating a survey.

    WHAT: Fields needed to create a survey.

    WHY: Validates survey creation data.
    """

    title: str = Field(..., min_length=1, max_length=200, description="Survey title")
    description: Optional[str] = Field(None, description="Survey description")
    survey_type: SurveyType = Field(
        default=SurveyType.CUSTOM, description="Survey type"
    )

    questions: List[QuestionSchema] = Field(
        ..., min_length=1, description="Survey questions"
    )

    is_anonymous: bool = Field(default=False, description="Allow anonymous responses")
    allow_multiple_responses: bool = Field(
        default=False, description="Allow multiple responses per user"
    )
    show_progress: bool = Field(default=True, description="Show progress indicator")

    project_id: Optional[int] = Field(None, description="Associated project")

    starts_at: Optional[datetime] = Field(None, description="Survey start time")
    ends_at: Optional[datetime] = Field(None, description="Survey end time")


class SurveyUpdateRequest(BaseModel):
    """
    Request schema for updating a survey.

    WHAT: Fields that can be updated.

    WHY: Allows partial updates.
    """

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    questions: Optional[List[QuestionSchema]] = None
    is_anonymous: Optional[bool] = None
    allow_multiple_responses: Optional[bool] = None
    show_progress: Optional[bool] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class ResponseSubmitRequest(BaseModel):
    """
    Request schema for submitting a survey response.

    WHAT: Answer data for a survey.

    WHY: Validates response data.
    """

    answers: Dict[str, Any] = Field(..., description="Answers keyed by question ID")
    time_taken_seconds: Optional[int] = Field(None, description="Time to complete")


class ResponseUpdateRequest(BaseModel):
    """
    Request schema for updating a response.

    WHAT: Partial answer updates.

    WHY: Allow saving progress.
    """

    answers: Dict[str, Any] = Field(..., description="Updated answers")


class InvitationCreateRequest(BaseModel):
    """
    Request schema for creating invitations.

    WHAT: Users to invite.

    WHY: Bulk invitation creation.
    """

    user_ids: List[int] = Field(..., min_length=1, description="User IDs to invite")


# ============================================================================
# Response Schemas
# ============================================================================


class UserResponse(BaseModel):
    """User info for survey responses."""

    id: int = Field(..., description="User ID")
    name: Optional[str] = Field(None, description="User name")
    email: str = Field(..., description="User email")

    class Config:
        from_attributes = True


class SurveyResponse(BaseModel):
    """
    Response schema for survey.

    WHAT: Survey details for display.

    WHY: Admin and user views.
    """

    id: int = Field(..., description="Survey ID")
    org_id: int = Field(..., description="Organization ID")

    title: str = Field(..., description="Survey title")
    description: Optional[str] = Field(None, description="Survey description")
    survey_type: SurveyType = Field(..., description="Survey type")

    questions: List[QuestionSchema] = Field(..., description="Survey questions")
    question_count: int = Field(..., description="Number of questions")
    required_question_count: int = Field(..., description="Required questions")

    status: SurveyStatus = Field(..., description="Survey status")

    is_anonymous: bool = Field(..., description="Anonymous responses")
    allow_multiple_responses: bool = Field(..., description="Multiple responses")
    show_progress: bool = Field(..., description="Show progress")

    project_id: Optional[int] = Field(None, description="Project ID")

    starts_at: Optional[datetime] = Field(None, description="Start time")
    ends_at: Optional[datetime] = Field(None, description="End time")
    is_active: bool = Field(..., description="Currently active")

    response_count: int = Field(default=0, description="Number of responses")

    created_by: Optional[UserResponse] = Field(None, description="Creator")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True


class SurveyListResponse(BaseModel):
    """
    Response schema for survey list.

    WHAT: Paginated list of surveys.

    WHY: Survey management view.
    """

    items: List[SurveyResponse] = Field(..., description="Surveys")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")


class SurveyResponseDetail(BaseModel):
    """
    Response schema for individual survey response.

    WHAT: Response details.

    WHY: View submitted answers.
    """

    id: int = Field(..., description="Response ID")
    org_id: int = Field(..., description="Organization ID")
    survey_id: int = Field(..., description="Survey ID")

    respondent: Optional[UserResponse] = Field(None, description="Respondent")
    answers: Dict[str, Any] = Field(..., description="Answer data")

    is_complete: bool = Field(..., description="Is complete")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    time_taken_seconds: Optional[int] = Field(None, description="Time taken")

    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True


class SurveyResponseListResponse(BaseModel):
    """
    Response schema for response list.

    WHAT: Paginated list of responses.

    WHY: Response analysis view.
    """

    items: List[SurveyResponseDetail] = Field(..., description="Responses")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")


class InvitationResponse(BaseModel):
    """
    Response schema for invitation.

    WHAT: Invitation details.

    WHY: Track invitations.
    """

    id: int = Field(..., description="Invitation ID")
    survey_id: int = Field(..., description="Survey ID")
    user_id: int = Field(..., description="User ID")
    token: str = Field(..., description="Access token")

    sent_at: Optional[datetime] = Field(None, description="Sent time")
    opened_at: Optional[datetime] = Field(None, description="Opened time")
    responded_at: Optional[datetime] = Field(None, description="Response time")

    user: Optional[UserResponse] = Field(None, description="Invited user")

    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True


class InvitationListResponse(BaseModel):
    """
    Response schema for invitation list.

    WHAT: List of invitations.

    WHY: Track distribution.
    """

    items: List[InvitationResponse] = Field(..., description="Invitations")
    total: int = Field(..., description="Total count")


# ============================================================================
# Analytics Schemas
# ============================================================================


class NPSResponse(BaseModel):
    """
    Response schema for NPS metrics.

    WHAT: Net Promoter Score data.

    WHY: Standard satisfaction metric.
    """

    score: Optional[float] = Field(None, description="NPS score (-100 to 100)")
    promoters: int = Field(..., description="Promoters count (9-10)")
    passives: int = Field(..., description="Passives count (7-8)")
    detractors: int = Field(..., description="Detractors count (0-6)")
    response_count: int = Field(..., description="Total responses")


class RatingResponse(BaseModel):
    """
    Response schema for rating metrics.

    WHAT: Average rating data.

    WHY: CSAT and other ratings.
    """

    average: Optional[float] = Field(None, description="Average rating")
    min: Optional[float] = Field(None, description="Minimum rating")
    max: Optional[float] = Field(None, description="Maximum rating")
    response_count: int = Field(..., description="Total responses")
    distribution: Dict[int, int] = Field(..., description="Rating distribution")


class FeedbackScoreResponse(BaseModel):
    """
    Response schema for feedback score.

    WHAT: Aggregated score data.

    WHY: Historical metrics.
    """

    id: int = Field(..., description="Score ID")
    score_type: str = Field(..., description="Score type")
    period_start: datetime = Field(..., description="Period start")
    period_end: datetime = Field(..., description="Period end")
    score: float = Field(..., description="Score value")
    response_count: int = Field(..., description="Response count")

    promoters: Optional[int] = Field(None, description="NPS promoters")
    passives: Optional[int] = Field(None, description="NPS passives")
    detractors: Optional[int] = Field(None, description="NPS detractors")

    project_id: Optional[int] = Field(None, description="Project ID")

    class Config:
        from_attributes = True


class FeedbackScoreHistoryResponse(BaseModel):
    """
    Response schema for score history.

    WHAT: Historical scores.

    WHY: Trend analysis.
    """

    scores: List[FeedbackScoreResponse] = Field(..., description="Score history")
    current_score: Optional[float] = Field(None, description="Latest score")
    trend: Optional[str] = Field(None, description="Trend direction (up/down/stable)")


class SurveyStatsResponse(BaseModel):
    """
    Response schema for survey statistics.

    WHAT: Aggregated survey stats.

    WHY: Dashboard metrics.
    """

    total_surveys: int = Field(..., description="Total surveys")
    active_surveys: int = Field(..., description="Active surveys")
    total_responses: int = Field(..., description="Total responses")
    completion_rate: float = Field(..., description="Completion rate (0-1)")

    nps: Optional[NPSResponse] = Field(None, description="Latest NPS")
    csat: Optional[RatingResponse] = Field(None, description="Latest CSAT")
