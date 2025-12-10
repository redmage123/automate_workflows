"""
User model.

WHY: Users represent individuals who interact with the platform, with roles
determining their access level (ADMIN or CLIENT) and org_id ensuring multi-tenant isolation.
"""

import enum
from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, PrimaryKeyMixin


class UserRole(str, enum.Enum):
    """
    User role enumeration.

    WHY: Enum ensures only valid roles can be assigned, preventing typos
    and making role-based access control (RBAC) more reliable.
    """

    ADMIN = "ADMIN"  # Service provider with full system access
    CLIENT = "CLIENT"  # Customer with org-scoped access


class User(Base, PrimaryKeyMixin, TimestampMixin):
    """
    User model representing individuals who use the platform.

    WHY: Separating users from organizations allows one organization to have
    multiple users, supporting team collaboration. The org_id foreign key
    ensures every user belongs to exactly one organization (required for
    multi-tenant data isolation).
    """

    __tablename__ = "users"

    # User identification
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)

    # Authentication
    # WHY: hashed_password is nullable to support OAuth-only users who
    # authenticate via external providers (Google, GitHub, etc.)
    hashed_password = Column(String(255), nullable=True)

    # Authorization
    # WHY: Role determines what actions the user can perform.
    # Default CLIENT role ensures least-privilege access (A01: Broken Access Control)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CLIENT)

    # Multi-tenancy
    # WHY: org_id is indexed for query performance and marked NOT NULL to enforce
    # that every user belongs to an organization (critical for data isolation)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)

    # Account status
    # WHY: is_active allows soft-deletion of users without losing audit trail
    is_active = Column(Boolean, default=True, nullable=False)

    # Email verification status
    # WHY: email_verified tracks whether the user has confirmed their email address.
    # This is required for OWASP A07 (Identification and Authentication Failures)
    # to prevent fake accounts and ensure email ownership before sensitive operations.
    # Default False requires explicit verification after registration.
    email_verified = Column(Boolean, default=False, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="users")
    # TODO: Uncomment when AuditLog model is created
    # audit_logs = relationship("AuditLog", back_populates="actor_user", foreign_keys="[AuditLog.actor_user_id]")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
