"""
Report models.

WHAT: SQLAlchemy models for scheduled reports and report execution tracking.

WHY: Reports enable:
1. Scheduled automated report generation and delivery
2. Custom report building with parameters
3. Export to PDF/Excel/CSV formats
4. Historical report execution tracking

HOW: Uses SQLAlchemy 2.0 with:
- Cron-based scheduling
- JSONB for flexible parameters
- Multiple output formats
- Delivery status tracking
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
    BigInteger,
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


class ReportType(str, Enum):
    """
    Available report types.

    WHAT: Categorizes reports by their data focus.

    WHY: Different report types have different:
    - Data sources
    - Default parameters
    - Output templates
    - Visualization requirements
    """

    REVENUE = "revenue"
    ACTIVITY = "activity"
    PROJECT = "project"
    TICKET = "ticket"
    TIME_TRACKING = "time_tracking"
    INVOICE = "invoice"
    CLIENT = "client"
    WORKFLOW = "workflow"
    CUSTOM = "custom"


class ReportFormat(str, Enum):
    """
    Report output formats.

    WHAT: Defines available export formats.

    WHY: Different use cases require different formats:
    - PDF: For polished, printable reports
    - Excel: For data analysis and manipulation
    - CSV: For data import/export
    - JSON: For API consumption
    """

    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"


class ExecutionStatus(str, Enum):
    """
    Report execution status.

    WHAT: Tracks the state of report generation.

    WHY: Enables monitoring, debugging, and retry logic.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryStatus(str, Enum):
    """
    Report delivery status.

    WHAT: Tracks email delivery of reports.

    WHY: Enables monitoring and retry of failed deliveries.
    """

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    PARTIAL = "partial"


class ScheduledReport(Base):
    """
    Configuration for automated report generation.

    WHAT: Defines reports that run on a schedule and deliver to users.

    WHY: Managers and clients need regular updates without manual effort.
    Automation reduces workload and ensures consistent reporting.

    HOW: Uses cron expressions for flexible scheduling with timezone support.
    """

    __tablename__ = "scheduled_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Report definition
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Report configuration
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, default=dict
    )
    output_format: Mapped[str] = mapped_column(
        String(20), default=ReportFormat.PDF.value, nullable=False
    )

    # Schedule configuration (cron expression)
    schedule: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)

    # Delivery configuration
    recipients: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer), nullable=True
    )
    email_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    executions: Mapped[List["ReportExecution"]] = relationship(
        "ReportExecution", back_populates="scheduled_report", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_scheduled_reports_org_id", "org_id"),
        Index("ix_scheduled_reports_created_by", "created_by"),
        Index("ix_scheduled_reports_report_type", "report_type"),
        Index("ix_scheduled_reports_is_active", "is_active"),
        Index("ix_scheduled_reports_next_run_at", "next_run_at"),
    )

    def __repr__(self) -> str:
        return f"<ScheduledReport(id={self.id}, name='{self.name}', type={self.report_type})>"


class ReportExecution(Base):
    """
    History of report executions.

    WHAT: Tracks each time a scheduled report runs.

    WHY: Audit trail for report generation, debugging failed reports,
    and allowing users to access historical reports.

    HOW: Records execution status, timing, output, and delivery results.
    """

    __tablename__ = "report_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheduled_report_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("scheduled_reports.id", ondelete="SET NULL"), nullable=True
    )
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Report info (denormalized for history)
    report_name: Mapped[str] = mapped_column(String(100), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    output_format: Mapped[str] = mapped_column(String(20), nullable=False)

    # Execution status
    status: Mapped[str] = mapped_column(
        String(20), default=ExecutionStatus.PENDING.value, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Output
    output_file_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    output_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Delivery status
    delivery_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    delivery_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Metadata
    triggered_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    is_adhoc: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    scheduled_report: Mapped[Optional["ScheduledReport"]] = relationship(
        "ScheduledReport", back_populates="executions"
    )
    organization: Mapped["Organization"] = relationship("Organization")
    trigger_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[triggered_by])

    # Indexes
    __table_args__ = (
        Index("ix_report_executions_org_id", "org_id"),
        Index("ix_report_executions_scheduled_report_id", "scheduled_report_id"),
        Index("ix_report_executions_status", "status"),
        Index("ix_report_executions_created_at", "created_at"),
        Index(
            "ix_report_executions_org_status",
            "org_id",
            "status",
        ),
    )

    def __repr__(self) -> str:
        return f"<ReportExecution(id={self.id}, report='{self.report_name}', status={self.status})>"

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ReportTemplate(Base):
    """
    Custom report templates.

    WHAT: User-defined report configurations for reuse.

    WHY: Users may want to save complex report configurations
    for repeated use without creating a schedule.

    HOW: Stores report parameters as JSONB for flexibility.
    """

    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Template definition
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Template configuration
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, default=dict
    )
    default_format: Mapped[str] = mapped_column(
        String(20), default=ReportFormat.PDF.value, nullable=False
    )

    # Column/field selection
    selected_columns: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )
    grouping: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    sorting: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    filters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Display options
    include_charts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_summary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    chart_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Status
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])

    # Indexes
    __table_args__ = (
        Index("ix_report_templates_org_id", "org_id"),
        Index("ix_report_templates_created_by", "created_by"),
        Index("ix_report_templates_report_type", "report_type"),
        Index("ix_report_templates_is_public", "is_public"),
    )

    def __repr__(self) -> str:
        return f"<ReportTemplate(id={self.id}, name='{self.name}', type={self.report_type})>"
