"""
Onboarding models.

WHAT: SQLAlchemy models for client onboarding wizard.

WHY: Onboarding enables:
1. Guided setup for new clients
2. Customizable multi-step flows
3. Progress tracking and completion
4. Data collection at each step

HOW: Uses SQLAlchemy 2.0 with:
- Template-based flows
- Step-by-step progress tracking
- JSONB for flexible step data
- Status management
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
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class OnboardingStatus(str, Enum):
    """
    Onboarding status.

    WHAT: Tracks overall onboarding progress.

    WHY: Different statuses require different UI treatment.
    """

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    SKIPPED = "skipped"


class StepType(str, Enum):
    """
    Onboarding step types.

    WHAT: Categorizes step content.

    WHY: Different step types have different:
    - UI rendering requirements
    - Validation rules
    - Data handling
    """

    INFO = "info"  # Informational/welcome content
    FORM = "form"  # Data collection form
    UPLOAD = "upload"  # Document upload
    CHOICE = "choice"  # Selection/preferences
    VERIFICATION = "verification"  # Email/phone verification
    INTEGRATION = "integration"  # Third-party connection
    REVIEW = "review"  # Summary/confirmation


class OnboardingTemplate(Base):
    """
    Templates for client onboarding flows.

    WHAT: Defines steps and requirements for new client onboarding.

    WHY: Consistent onboarding improves client experience and ensures
    all necessary information is collected upfront.

    HOW: Contains step definitions with validation rules and UI configuration.
    """

    __tablename__ = "onboarding_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Template identity
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False)

    # Steps definition (JSON array of step objects)
    steps: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Example structure:
    # [
    #   {
    #     "id": "welcome",
    #     "title": "Welcome",
    #     "type": "info",
    #     "content": "Welcome to our platform...",
    #     "is_required": false
    #   },
    #   {
    #     "id": "profile",
    #     "title": "Company Profile",
    #     "type": "form",
    #     "fields": [
    #       {"name": "company_name", "type": "text", "required": true},
    #       {"name": "industry", "type": "select", "options": [...]}
    #     ],
    #     "is_required": true
    #   },
    #   {
    #     "id": "documents",
    #     "title": "Required Documents",
    #     "type": "upload",
    #     "required_docs": ["contract", "nda"],
    #     "is_required": true
    #   }
    # ]

    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_assign: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Target users (by role or all)
    target_roles: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
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
    onboardings: Mapped[List["ClientOnboarding"]] = relationship(
        "ClientOnboarding", back_populates="template", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_onboarding_templates_org_id", "org_id"),
        Index("ix_onboarding_templates_slug", "slug"),
        Index("ix_onboarding_templates_is_active", "is_active"),
        Index("ix_onboarding_templates_is_default", "is_default"),
        Index(
            "ix_onboarding_templates_org_slug",
            "org_id",
            "slug",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<OnboardingTemplate(id={self.id}, name='{self.name}')>"

    @property
    def step_count(self) -> int:
        """Get number of steps in template."""
        if isinstance(self.steps, list):
            return len(self.steps)
        return 0

    @property
    def required_step_count(self) -> int:
        """Get number of required steps."""
        if isinstance(self.steps, list):
            return sum(1 for s in self.steps if s.get("is_required", True))
        return 0


class ClientOnboarding(Base):
    """
    Tracks individual client onboarding progress.

    WHAT: Records a client's progress through onboarding steps.

    WHY: Allows tracking incomplete onboardings, sending reminders,
    and understanding where clients get stuck.

    HOW: Links user to template and tracks step completion with data.
    """

    __tablename__ = "client_onboardings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("onboarding_templates.id"), nullable=False
    )

    # Progress tracking
    current_step: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    completed_steps: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True, default=list
    )
    skipped_steps: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True, default=list
    )

    # Data collected at each step
    step_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, default=dict
    )
    # Example structure:
    # {
    #   "profile": {"company_name": "Acme Inc", "industry": "Technology"},
    #   "documents": {"contract": {"file_id": 123, "uploaded_at": "..."}},
    # }

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default=OnboardingStatus.NOT_STARTED.value, nullable=False
    )

    # Progress percentage (calculated)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")
    template: Mapped["OnboardingTemplate"] = relationship(
        "OnboardingTemplate", back_populates="onboardings"
    )

    # Indexes
    __table_args__ = (
        Index("ix_client_onboardings_org_id", "org_id"),
        Index("ix_client_onboardings_user_id", "user_id"),
        Index("ix_client_onboardings_template_id", "template_id"),
        Index("ix_client_onboardings_status", "status"),
        Index(
            "ix_client_onboardings_user_template",
            "user_id",
            "template_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<ClientOnboarding(id={self.id}, user_id={self.user_id}, status={self.status})>"

    def calculate_progress(self, template_steps: List[Dict]) -> int:
        """
        Calculate progress percentage.

        WHAT: Computes completion percentage based on steps.

        WHY: Show progress to user.

        Args:
            template_steps: List of step definitions from template

        Returns:
            Progress percentage (0-100)
        """
        if not template_steps:
            return 0

        completed = self.completed_steps or []
        skipped = self.skipped_steps or []
        required_steps = [s for s in template_steps if s.get("is_required", True)]

        if not required_steps:
            return 100 if completed else 0

        completed_required = sum(
            1 for s in required_steps
            if s.get("id") in completed or s.get("id") in skipped
        )

        return int((completed_required / len(required_steps)) * 100)


class OnboardingReminder(Base):
    """
    Reminder tracking for incomplete onboardings.

    WHAT: Tracks reminder emails sent for stalled onboardings.

    WHY: Helps re-engage users who haven't completed onboarding.

    HOW: Records reminder history to prevent spam.
    """

    __tablename__ = "onboarding_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    onboarding_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("client_onboardings.id", ondelete="CASCADE"), nullable=False
    )

    # Reminder details
    reminder_type: Mapped[str] = mapped_column(String(50), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    sent_to_email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Engagement tracking
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    onboarding: Mapped["ClientOnboarding"] = relationship("ClientOnboarding")

    # Indexes
    __table_args__ = (
        Index("ix_onboarding_reminders_onboarding_id", "onboarding_id"),
        Index("ix_onboarding_reminders_sent_at", "sent_at"),
    )

    def __repr__(self) -> str:
        return f"<OnboardingReminder(id={self.id}, type={self.reminder_type})>"
