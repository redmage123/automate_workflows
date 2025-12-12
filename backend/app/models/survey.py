"""
Survey and Feedback models.

WHAT: SQLAlchemy models for surveys, questions, and responses.

WHY: Surveys enable:
1. Collecting client feedback (NPS, CSAT)
2. Custom satisfaction surveys
3. Post-project reviews
4. Continuous improvement metrics

HOW: Uses SQLAlchemy 2.0 with:
- Flexible question types (rating, text, choice)
- Anonymous response support
- JSONB for question configuration
- Response aggregation
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.project import Project


class SurveyType(str, Enum):
    """
    Survey types.

    WHAT: Categorizes survey purpose.

    WHY: Different survey types have different:
    - Question structures
    - Analysis methods
    - Benchmark comparisons
    """

    NPS = "nps"  # Net Promoter Score
    CSAT = "csat"  # Customer Satisfaction
    CES = "ces"  # Customer Effort Score
    PROJECT_FEEDBACK = "project_feedback"  # Post-project survey
    CUSTOM = "custom"  # Custom survey


class SurveyStatus(str, Enum):
    """
    Survey status.

    WHAT: Tracks survey lifecycle.

    WHY: Control survey visibility and response collection.
    """

    DRAFT = "draft"  # Not yet published
    ACTIVE = "active"  # Accepting responses
    PAUSED = "paused"  # Temporarily closed
    CLOSED = "closed"  # Permanently closed


class QuestionType(str, Enum):
    """
    Question types.

    WHAT: Defines response format.

    WHY: Different question types need:
    - Different UI rendering
    - Different validation rules
    - Different analysis methods
    """

    RATING = "rating"  # 1-5 or 1-10 scale
    NPS = "nps"  # 0-10 NPS scale
    TEXT = "text"  # Free text
    SINGLE_CHOICE = "single_choice"  # Radio buttons
    MULTIPLE_CHOICE = "multiple_choice"  # Checkboxes
    YES_NO = "yes_no"  # Boolean
    DATE = "date"  # Date picker


class Survey(Base):
    """
    Survey definition.

    WHAT: Defines a survey with questions.

    WHY: Structured feedback collection improves service quality
    and provides measurable client satisfaction metrics.

    HOW: Contains survey metadata and questions in JSONB.
    """

    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Survey identity
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    survey_type: Mapped[str] = mapped_column(
        String(50), default=SurveyType.CUSTOM.value, nullable=False
    )

    # Questions (JSON array of question objects)
    questions: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Example structure:
    # [
    #   {
    #     "id": "q1",
    #     "type": "nps",
    #     "text": "How likely are you to recommend us?",
    #     "required": true,
    #     "order": 1
    #   },
    #   {
    #     "id": "q2",
    #     "type": "text",
    #     "text": "What could we improve?",
    #     "required": false,
    #     "order": 2
    #   }
    # ]

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default=SurveyStatus.DRAFT.value, nullable=False
    )

    # Settings
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_multiple_responses: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    show_progress: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Optional project association
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True
    )

    # Scheduling
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Creator
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped["User"] = relationship("User")
    project: Mapped[Optional["Project"]] = relationship("Project")
    responses: Mapped[List["SurveyResponse"]] = relationship(
        "SurveyResponse", back_populates="survey", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_surveys_org_id", "org_id"),
        Index("ix_surveys_status", "status"),
        Index("ix_surveys_survey_type", "survey_type"),
        Index("ix_surveys_project_id", "project_id"),
        Index("ix_surveys_created_by_id", "created_by_id"),
    )

    def __repr__(self) -> str:
        return f"<Survey(id={self.id}, title='{self.title}')>"

    @property
    def question_count(self) -> int:
        """Get number of questions."""
        if isinstance(self.questions, list):
            return len(self.questions)
        return 0

    @property
    def required_question_count(self) -> int:
        """Get number of required questions."""
        if isinstance(self.questions, list):
            return sum(1 for q in self.questions if q.get("required", False))
        return 0

    @property
    def is_active(self) -> bool:
        """Check if survey is currently active."""
        if self.status != SurveyStatus.ACTIVE.value:
            return False
        now = datetime.utcnow()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True


class SurveyResponse(Base):
    """
    Individual survey response.

    WHAT: Records a user's answers to a survey.

    WHY: Collect and analyze feedback data.

    HOW: Stores answers in JSONB for flexibility.
    """

    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    survey_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False
    )

    # Respondent (nullable for anonymous)
    respondent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    # Answers (JSON object keyed by question ID)
    answers: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Example structure:
    # {
    #   "q1": 9,           # NPS score
    #   "q2": "Great service, very responsive"  # Text answer
    # }

    # Completion status
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Metadata
    time_taken_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    survey: Mapped["Survey"] = relationship("Survey", back_populates="responses")
    respondent: Mapped[Optional["User"]] = relationship("User")

    # Indexes
    __table_args__ = (
        Index("ix_survey_responses_org_id", "org_id"),
        Index("ix_survey_responses_survey_id", "survey_id"),
        Index("ix_survey_responses_respondent_id", "respondent_id"),
        Index("ix_survey_responses_is_complete", "is_complete"),
        Index(
            "ix_survey_responses_survey_respondent",
            "survey_id",
            "respondent_id",
            unique=False,
        ),
    )

    def __repr__(self) -> str:
        return f"<SurveyResponse(id={self.id}, survey_id={self.survey_id})>"


class SurveyInvitation(Base):
    """
    Survey invitation.

    WHAT: Tracks invitations sent to collect responses.

    WHY: Manage survey distribution and track response rates.

    HOW: Links users to surveys with unique tokens.
    """

    __tablename__ = "survey_invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    survey_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Unique token for anonymous access
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # Status
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Response link (if responded)
    response_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("survey_responses.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    survey: Mapped["Survey"] = relationship("Survey")
    user: Mapped["User"] = relationship("User")
    response: Mapped[Optional["SurveyResponse"]] = relationship("SurveyResponse")

    # Indexes
    __table_args__ = (
        Index("ix_survey_invitations_org_id", "org_id"),
        Index("ix_survey_invitations_survey_id", "survey_id"),
        Index("ix_survey_invitations_user_id", "user_id"),
        Index("ix_survey_invitations_token", "token"),
    )

    def __repr__(self) -> str:
        return f"<SurveyInvitation(id={self.id}, survey_id={self.survey_id})>"


class FeedbackScore(Base):
    """
    Aggregated feedback scores.

    WHAT: Pre-computed scores for analytics.

    WHY: Efficient querying of NPS, CSAT, and other metrics
    without re-calculating from raw responses.

    HOW: Stores period-based aggregations.
    """

    __tablename__ = "feedback_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Score type
    score_type: Mapped[str] = mapped_column(String(20), nullable=False)  # nps, csat, ces

    # Period
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Scores
    score: Mapped[float] = mapped_column(Float, nullable=False)
    response_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # NPS specific
    promoters: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    passives: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detractors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Optional project association
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    project: Mapped[Optional["Project"]] = relationship("Project")

    # Indexes
    __table_args__ = (
        Index("ix_feedback_scores_org_id", "org_id"),
        Index("ix_feedback_scores_score_type", "score_type"),
        Index("ix_feedback_scores_period", "period_start", "period_end"),
        Index("ix_feedback_scores_project_id", "project_id"),
    )

    def __repr__(self) -> str:
        return f"<FeedbackScore(id={self.id}, type={self.score_type}, score={self.score})>"
