"""
Integration Models.

WHAT: SQLAlchemy models for external integrations.

WHY: External integrations enable:
1. Calendar sync with Google/Outlook
2. Custom webhooks for external systems
3. Third-party app connections
4. Data synchronization

HOW: Uses SQLAlchemy 2.0 with:
- OAuth token storage for calendar
- Webhook configuration
- Integration logs
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


class CalendarProvider(str, Enum):
    """Calendar provider types."""

    GOOGLE = "google"
    OUTLOOK = "outlook"
    APPLE = "apple"
    CALDAV = "caldav"


class WebhookEventType(str, Enum):
    """Webhook event types."""

    # Ticket events
    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_CLOSED = "ticket.closed"
    TICKET_COMMENT = "ticket.comment"

    # Project events
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    PROJECT_COMPLETED = "project.completed"

    # Proposal events
    PROPOSAL_SENT = "proposal.sent"
    PROPOSAL_APPROVED = "proposal.approved"
    PROPOSAL_REJECTED = "proposal.rejected"

    # Invoice events
    INVOICE_CREATED = "invoice.created"
    INVOICE_PAID = "invoice.paid"
    INVOICE_OVERDUE = "invoice.overdue"

    # User events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"

    # Workflow events
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"


class CalendarIntegration(Base):
    """
    Calendar integration configuration.

    WHAT: Stores calendar OAuth tokens and settings.

    WHY: Calendar integration enables:
    - Syncing project milestones
    - Meeting scheduling
    - Deadline reminders

    HOW: Stores OAuth refresh tokens for calendar access.
    """

    __tablename__ = "calendar_integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Provider info
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, default=CalendarProvider.GOOGLE.value
    )
    provider_account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # OAuth tokens (encrypted in production)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Calendar settings
    calendar_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    calendar_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sync settings
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sync_projects: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sync_tickets: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sync_invoices: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    organization: Mapped["Organization"] = relationship("Organization")

    # Indexes
    __table_args__ = (
        Index("ix_calendar_integrations_user_id", "user_id"),
        Index("ix_calendar_integrations_org_id", "org_id"),
        Index("ix_calendar_integrations_provider", "provider"),
        Index(
            "ix_calendar_integrations_user_provider",
            "user_id",
            "provider",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<CalendarIntegration(id={self.id}, provider='{self.provider}')>"


class WebhookEndpoint(Base):
    """
    Webhook endpoint configuration.

    WHAT: Stores webhook URLs and settings.

    WHY: Webhooks enable:
    - Real-time notifications to external systems
    - Integration with third-party apps
    - Custom automation triggers

    HOW: Stores URL, secret, and event subscriptions.
    """

    __tablename__ = "webhook_endpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Endpoint identity
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)

    # Security
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    headers: Mapped[Optional[Dict[str, str]]] = mapped_column(JSONB, nullable=True)

    # Event subscriptions
    events: Mapped[List[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )

    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    retry_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Stats
    delivery_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Creator
    created_by_id: Mapped[Optional[int]] = mapped_column(
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
    created_by: Mapped[Optional["User"]] = relationship("User")
    deliveries: Mapped[List["WebhookDelivery"]] = relationship(
        "WebhookDelivery",
        back_populates="endpoint",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_webhook_endpoints_org_id", "org_id"),
        Index("ix_webhook_endpoints_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<WebhookEndpoint(id={self.id}, name='{self.name}')>"

    def subscribes_to(self, event_type: str) -> bool:
        """Check if endpoint subscribes to event type."""
        if not self.events:
            return False
        # Support wildcards like "ticket.*"
        for pattern in self.events:
            if pattern == "*" or pattern == event_type:
                return True
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if event_type.startswith(prefix + "."):
                    return True
        return False


class WebhookDelivery(Base):
    """
    Webhook delivery log.

    WHAT: Records individual webhook delivery attempts.

    WHY: Delivery logs enable:
    - Debugging failed webhooks
    - Retry management
    - Audit trail

    HOW: Stores request/response details for each delivery.
    """

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False
    )

    # Event info
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Request details
    request_url: Mapped[str] = mapped_column(Text, nullable=False)
    request_headers: Mapped[Optional[Dict[str, str]]] = mapped_column(JSONB, nullable=True)
    request_body: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Response details
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_headers: Mapped[Optional[Dict[str, str]]] = mapped_column(JSONB, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Delivery status
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    endpoint: Mapped["WebhookEndpoint"] = relationship(
        "WebhookEndpoint", back_populates="deliveries"
    )

    # Indexes
    __table_args__ = (
        Index("ix_webhook_deliveries_endpoint_id", "endpoint_id"),
        Index("ix_webhook_deliveries_event_type", "event_type"),
        Index("ix_webhook_deliveries_delivered", "delivered"),
        Index("ix_webhook_deliveries_triggered_at", "triggered_at"),
    )

    def __repr__(self) -> str:
        return f"<WebhookDelivery(id={self.id}, event='{self.event_type}')>"
