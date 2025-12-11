"""
Project model for tracking client automation projects.

WHAT: SQLAlchemy model representing an automation project for a client organization.

WHY: Projects are the central business entity that:
1. Track client automation work from inception to completion
2. Connect organizations to proposals, invoices, and workflows
3. Enable status tracking and progress monitoring
4. Support audit logging for security and compliance

HOW: Uses SQLAlchemy 2.0 with:
- Organization-scoped queries (multi-tenancy)
- Status enum for lifecycle management
- Relationships to proposals and workflows
- Timestamps for audit trail
"""

from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship, Mapped

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.proposal import Proposal
    from app.models.workflow import WorkflowInstance


class ProjectStatus(str, Enum):
    """
    Project lifecycle status.

    WHY: Tracks project progression through business workflow:
    - DRAFT: Initial creation, gathering requirements
    - PROPOSAL_SENT: Proposal created and sent to client
    - APPROVED: Client approved, ready to start work
    - IN_PROGRESS: Active development/implementation
    - ON_HOLD: Temporarily paused (client request, waiting for input)
    - COMPLETED: All work finished successfully
    - CANCELLED: Project terminated before completion
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

    WHY: Helps with resource allocation and scheduling:
    - LOW: Nice to have, can be delayed
    - MEDIUM: Standard priority, normal timeline
    - HIGH: Important, prioritize over medium
    - URGENT: Critical, needs immediate attention
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Project(Base):
    """
    Automation project model.

    WHAT: Represents a client automation project.

    WHY: Central entity connecting:
    - Client organization (owner)
    - Proposals (pricing and scope)
    - Workflows (automated processes)
    - Invoices (billing)
    - Tickets (support)

    HOW: Multi-tenant model scoped by org_id with status tracking.

    Attributes:
        id: Primary key
        name: Project name/title
        description: Detailed project description
        status: Current project status
        priority: Project priority level
        org_id: Organization that owns this project
        estimated_hours: Estimated hours for completion
        actual_hours: Actual hours spent
        start_date: When work started
        due_date: Target completion date
        completed_at: When project was completed
        created_at: Record creation timestamp
        updated_at: Last modification timestamp
    """

    __tablename__ = "projects"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)

    # Project details
    name: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Project name/title",
    )
    description: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Detailed project description",
    )

    # Status and priority
    status: Mapped[ProjectStatus] = Column(
        SQLEnum(ProjectStatus),
        nullable=False,
        default=ProjectStatus.DRAFT,
        comment="Current project status",
    )
    priority: Mapped[ProjectPriority] = Column(
        SQLEnum(ProjectPriority),
        nullable=False,
        default=ProjectPriority.MEDIUM,
        comment="Project priority level",
    )

    # Organization (multi-tenancy)
    org_id: Mapped[int] = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this project",
    )

    # Time tracking
    estimated_hours: Mapped[Optional[float]] = Column(
        Integer,
        nullable=True,
        comment="Estimated hours for project completion",
    )
    actual_hours: Mapped[Optional[float]] = Column(
        Integer,
        nullable=True,
        default=0,
        comment="Actual hours spent on project",
    )

    # Date tracking
    start_date: Mapped[Optional[datetime]] = Column(
        DateTime,
        nullable=True,
        comment="Date when work started",
    )
    due_date: Mapped[Optional[datetime]] = Column(
        DateTime,
        nullable=True,
        comment="Target completion date",
    )
    completed_at: Mapped[Optional[datetime]] = Column(
        DateTime,
        nullable=True,
        comment="Date when project was completed",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp",
    )
    updated_at: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last modification timestamp",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="projects",
    )
    proposals: Mapped[list["Proposal"]] = relationship(
        "Proposal",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    workflow_instances: Mapped[list["WorkflowInstance"]] = relationship(
        "WorkflowInstance",
        back_populates="project",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Project(id={self.id}, name={self.name}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        """
        Check if project is in an active state.

        WHY: Quick check for filtering active projects.

        Returns:
            True if project is active (not cancelled/completed)
        """
        return self.status not in [ProjectStatus.COMPLETED, ProjectStatus.CANCELLED]

    @property
    def is_overdue(self) -> bool:
        """
        Check if project is past due date.

        WHY: Flag overdue projects for attention.

        Returns:
            True if due_date has passed and project not completed
        """
        if not self.due_date:
            return False
        if self.status == ProjectStatus.COMPLETED:
            return False
        return datetime.utcnow() > self.due_date

    @property
    def hours_remaining(self) -> Optional[float]:
        """
        Calculate remaining hours estimate.

        WHY: Track progress against estimate.

        Returns:
            Remaining hours or None if no estimate
        """
        if self.estimated_hours is None:
            return None
        actual = self.actual_hours or 0
        return max(0, self.estimated_hours - actual)
