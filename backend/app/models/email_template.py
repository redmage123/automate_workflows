"""
Email Template models.

WHAT: SQLAlchemy models for customizable email templates.

WHY: Email templates enable:
1. Custom branded transactional emails
2. Variable substitution for personalization
3. Version control for templates
4. Multi-language support

HOW: Uses SQLAlchemy 2.0 with:
- Template versioning
- Variable placeholders
- HTML and text versions
- Category organization
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


class EmailCategory(str, Enum):
    """
    Email template categories.

    WHAT: Groups templates by purpose.

    WHY: Different email types have:
    - Different styling requirements
    - Different variables available
    - Different frequency rules
    """

    ACCOUNT = "account"  # Registration, password reset
    NOTIFICATIONS = "notifications"  # Alerts, reminders
    BILLING = "billing"  # Invoices, payment receipts
    PROJECT = "project"  # Project updates
    MARKETING = "marketing"  # Promotional emails
    SYSTEM = "system"  # System notifications


class EmailTemplate(Base):
    """
    Email template definition.

    WHAT: Defines a reusable email template.

    WHY: Consistent, customizable email communications
    improve professionalism and brand consistency.

    HOW: Stores template with variable placeholders
    and supports both HTML and plain text versions.
    """

    __tablename__ = "email_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Template identity
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(
        String(50), default=EmailCategory.SYSTEM.value, nullable=False
    )

    # Email content
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, nullable=False)
    text_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Template variables (metadata about available variables)
    variables: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    # Example structure:
    # {
    #   "user_name": {"type": "string", "description": "User's name"},
    #   "reset_link": {"type": "url", "description": "Password reset URL"},
    #   "company_name": {"type": "string", "description": "Company name"}
    # }

    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Version tracking
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Creator
    created_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
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
    created_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[created_by_id]
    )
    updated_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[updated_by_id]
    )
    versions: Mapped[List["EmailTemplateVersion"]] = relationship(
        "EmailTemplateVersion",
        back_populates="template",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_email_templates_org_id", "org_id"),
        Index("ix_email_templates_slug", "slug"),
        Index("ix_email_templates_category", "category"),
        Index("ix_email_templates_is_active", "is_active"),
        Index(
            "ix_email_templates_org_slug",
            "org_id",
            "slug",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<EmailTemplate(id={self.id}, name='{self.name}')>"

    @property
    def variable_names(self) -> List[str]:
        """Get list of variable names."""
        if isinstance(self.variables, dict):
            return list(self.variables.keys())
        return []


class EmailTemplateVersion(Base):
    """
    Email template version history.

    WHAT: Stores historical versions of templates.

    WHY: Version control enables:
    - Rollback to previous versions
    - Audit trail of changes
    - A/B testing different versions

    HOW: Creates new version record on each template update.
    """

    __tablename__ = "email_template_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("email_templates.id", ondelete="CASCADE"), nullable=False
    )

    # Version number
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Content snapshot
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, nullable=False)
    text_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    variables: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Change tracking
    changed_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    change_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    template: Mapped["EmailTemplate"] = relationship(
        "EmailTemplate", back_populates="versions"
    )
    changed_by: Mapped[Optional["User"]] = relationship("User")

    # Indexes
    __table_args__ = (
        Index("ix_email_template_versions_template_id", "template_id"),
        Index("ix_email_template_versions_version", "version"),
        Index(
            "ix_email_template_versions_template_version",
            "template_id",
            "version",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<EmailTemplateVersion(id={self.id}, version={self.version})>"


class SentEmail(Base):
    """
    Sent email log.

    WHAT: Records all sent emails for auditing.

    WHY: Email logs enable:
    - Delivery tracking
    - Debugging issues
    - Analytics on email performance

    HOW: Creates record for each sent email with status tracking.
    """

    __tablename__ = "sent_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Template reference
    template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True
    )
    template_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Email details
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    to_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    from_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)

    # Variables used (for debugging)
    variables_used: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )

    # Delivery status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending, sent, delivered, bounced, failed

    # External references
    message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Engagement tracking
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    template: Mapped[Optional["EmailTemplate"]] = relationship("EmailTemplate")

    # Indexes
    __table_args__ = (
        Index("ix_sent_emails_org_id", "org_id"),
        Index("ix_sent_emails_template_id", "template_id"),
        Index("ix_sent_emails_to_email", "to_email"),
        Index("ix_sent_emails_status", "status"),
        Index("ix_sent_emails_sent_at", "sent_at"),
        Index("ix_sent_emails_message_id", "message_id"),
    )

    def __repr__(self) -> str:
        return f"<SentEmail(id={self.id}, to='{self.to_email}')>"
