"""
Workflow automation models.

WHAT: SQLAlchemy models for n8n integration and workflow management.

WHY: Provides structured storage for:
1. N8n environment configurations (per-org)
2. Workflow templates (reusable blueprints)
3. Workflow instances (project-linked automations)
4. Execution logs (audit trail)

HOW: Uses SQLAlchemy 2.0 with:
- Enums for status fields
- JSONB for flexible parameters
- Encrypted API key storage via app layer
- Proper foreign key relationships
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.project import Project


# ============================================================================
# Enums
# ============================================================================


class WorkflowStatus(str, Enum):
    """
    Workflow instance status values.

    WHAT: Tracks the lifecycle of a workflow instance.

    WHY: Status determines available actions:
    - DRAFT: Not yet created in n8n
    - ACTIVE: Running in n8n, can execute
    - PAUSED: Temporarily disabled
    - ERROR: Failed, needs attention
    - DELETED: Soft-deleted, no longer active
    """

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    DELETED = "deleted"


class ExecutionStatus(str, Enum):
    """
    Workflow execution status values.

    WHAT: Tracks individual execution runs.

    WHY: Status indicates execution outcome:
    - RUNNING: Currently executing
    - SUCCESS: Completed successfully
    - FAILED: Execution failed
    - CANCELLED: Manually or automatically cancelled
    """

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# N8n Environment Model
# ============================================================================


class N8nEnvironment(Base):
    """
    N8n instance configuration per organization.

    WHAT: Stores n8n connection details for each org.

    WHY: Organizations may have their own n8n instances:
    - Isolation for security
    - Different n8n versions
    - Custom integrations

    Security: API key is encrypted at rest (OWASP A02).
    Encryption happens at the DAO/service layer, not in the model.
    """

    __tablename__ = "n8n_environments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Connection details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    # Status and metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="n8n_environments"
    )
    workflow_instances: Mapped[List["WorkflowInstance"]] = relationship(
        "WorkflowInstance", back_populates="n8n_environment"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_n8n_env_org_name"),
    )

    def __repr__(self) -> str:
        return f"<N8nEnvironment(id={self.id}, org_id={self.org_id}, name='{self.name}')>"


# ============================================================================
# Workflow Template Model
# ============================================================================


class WorkflowTemplate(Base):
    """
    Reusable workflow template.

    WHAT: Blueprint for creating workflow instances.

    WHY: Templates provide:
    - Pre-built automations for common tasks
    - Consistent configuration across orgs
    - Starting point for customization

    Templates can be:
    - Public: Available to all organizations
    - Private: Created by org, only visible to that org
    """

    __tablename__ = "workflow_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Template details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # n8n reference (template workflow in n8n)
    n8n_template_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Default parameters (JSONB)
    default_parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Visibility
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_org_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    created_by_org: Mapped[Optional["Organization"]] = relationship(
        "Organization", foreign_keys=[created_by_org_id]
    )
    workflow_instances: Mapped[List["WorkflowInstance"]] = relationship(
        "WorkflowInstance", back_populates="template"
    )

    def __repr__(self) -> str:
        return f"<WorkflowTemplate(id={self.id}, name='{self.name}', is_public={self.is_public})>"


# ============================================================================
# Workflow Instance Model
# ============================================================================


class WorkflowInstance(Base):
    """
    Active workflow linked to a project.

    WHAT: Represents a deployed workflow automation.

    WHY: Instances are:
    - Linked to projects for billing/tracking
    - Based on templates for consistency
    - Connected to n8n for execution

    Status workflow:
    DRAFT → ACTIVE ↔ PAUSED → ERROR → ACTIVE (after fix)
                                   → DELETED
    """

    __tablename__ = "workflow_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("workflow_templates.id"), nullable=True
    )
    n8n_environment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("n8n_environments.id"), nullable=True
    )

    # n8n reference (created workflow ID)
    n8n_workflow_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Instance details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[WorkflowStatus] = mapped_column(
        SQLEnum(WorkflowStatus, name="workflowstatus"),
        default=WorkflowStatus.DRAFT,
        nullable=False,
    )

    # Custom parameters (merged with template defaults)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Execution tracking
    last_execution_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="workflow_instances"
    )
    project: Mapped[Optional["Project"]] = relationship(
        "Project", back_populates="workflow_instances"
    )
    template: Mapped[Optional["WorkflowTemplate"]] = relationship(
        "WorkflowTemplate", back_populates="workflow_instances"
    )
    n8n_environment: Mapped[Optional["N8nEnvironment"]] = relationship(
        "N8nEnvironment", back_populates="workflow_instances"
    )
    execution_logs: Mapped[List["ExecutionLog"]] = relationship(
        "ExecutionLog", back_populates="workflow_instance", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_workflow_instances_org_id", "org_id"),
        Index("ix_workflow_instances_project_id", "project_id"),
        Index("ix_workflow_instances_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowInstance(id={self.id}, name='{self.name}', status={self.status.value})>"

    @property
    def is_active(self) -> bool:
        """Check if workflow is currently active."""
        return self.status == WorkflowStatus.ACTIVE

    @property
    def can_execute(self) -> bool:
        """Check if workflow can be executed."""
        return self.status == WorkflowStatus.ACTIVE and self.n8n_workflow_id is not None

    @property
    def can_activate(self) -> bool:
        """Check if workflow can be activated."""
        return self.status in [WorkflowStatus.DRAFT, WorkflowStatus.PAUSED, WorkflowStatus.ERROR]

    @property
    def can_pause(self) -> bool:
        """Check if workflow can be paused."""
        return self.status == WorkflowStatus.ACTIVE

    def get_merged_parameters(self) -> dict:
        """
        Get parameters merged with template defaults.

        WHY: Template defaults provide base configuration,
        instance parameters override for customization.
        """
        if self.template and self.template.default_parameters:
            merged = dict(self.template.default_parameters)
            if self.parameters:
                merged.update(self.parameters)
            return merged
        return self.parameters or {}


# ============================================================================
# Execution Log Model
# ============================================================================


class ExecutionLog(Base):
    """
    Record of workflow execution.

    WHAT: Audit trail for workflow runs.

    WHY: Execution logs provide:
    - Debugging information
    - Performance metrics
    - Compliance audit trail
    - Billing data (execution count)

    Logs are append-only for integrity.
    """

    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_instance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow_instances.id"), nullable=False
    )

    # n8n reference
    n8n_execution_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status
    status: Mapped[ExecutionStatus] = mapped_column(
        SQLEnum(ExecutionStatus, name="executionstatus"),
        default=ExecutionStatus.RUNNING,
        nullable=False,
    )

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Data (JSONB)
    input_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Error info
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    workflow_instance: Mapped["WorkflowInstance"] = relationship(
        "WorkflowInstance", back_populates="execution_logs"
    )

    # Indexes
    __table_args__ = (
        Index("ix_execution_logs_instance_id", "workflow_instance_id"),
        Index("ix_execution_logs_status", "status"),
        Index("ix_execution_logs_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<ExecutionLog(id={self.id}, instance_id={self.workflow_instance_id}, status={self.status.value})>"

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration in seconds."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    @property
    def is_complete(self) -> bool:
        """Check if execution has completed (success or failure)."""
        return self.status in [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]
