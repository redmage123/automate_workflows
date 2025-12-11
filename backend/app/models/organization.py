"""
Organization model.

WHY: Organizations represent multi-tenant entities in the system.
Each organization has its own isolated data (users, projects, etc.),
ensuring strong data separation for security and compliance.
"""

from sqlalchemy import Column, String, Text, JSON, Boolean
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, PrimaryKeyMixin


class Organization(Base, PrimaryKeyMixin, TimestampMixin):
    """
    Organization model representing a tenant in the multi-tenant system.

    WHY: Multi-tenancy requires strict data isolation between organizations.
    The org_id is used throughout the system to scope all queries and
    prevent cross-organization data access (OWASP A01: Broken Access Control).

    Each organization has:
    - Basic info (name, description)
    - Settings (configurable per-org)
    - Relationships to users, projects, etc.
    """

    __tablename__ = "organizations"

    # Organization identification
    name = Column(String(255), nullable=False, index=True)

    # Organization details
    # WHY: description helps admins identify organizations
    description = Column(Text, nullable=True)

    # Organization settings
    # WHY: JSONB allows flexible per-organization configuration
    # without schema changes (e.g., branding, feature flags, limits)
    settings = Column(JSON, nullable=False, default=dict, server_default="{}")

    # Organization status
    # WHY: is_active allows soft-deletion of organizations while
    # preserving audit trails and historical data
    is_active = Column(Boolean, nullable=False, default=True)

    # Stripe integration
    # WHY: Store Stripe customer ID for payment processing.
    # Lazy customer creation - only created when first payment is made.
    stripe_customer_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Stripe customer ID for payment processing"
    )

    # Relationships
    # WHY: Relationships allow easy navigation from organization to its data
    users = relationship("User", back_populates="organization", lazy="dynamic")
    projects = relationship("Project", back_populates="organization", lazy="dynamic")
    proposals = relationship("Proposal", back_populates="organization", lazy="dynamic")
    invoices = relationship("Invoice", back_populates="organization", lazy="dynamic")
    n8n_environments = relationship("N8nEnvironment", back_populates="organization", lazy="dynamic")
    workflow_instances = relationship("WorkflowInstance", back_populates="organization", lazy="dynamic")
    tickets = relationship("Ticket", back_populates="organization", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name})>"
