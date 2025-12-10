"""
Audit Log Model.

WHAT: SQLAlchemy model for storing security audit events.

WHY: OWASP A09 (Security Logging and Monitoring) requires comprehensive
logging of security-relevant events. This model provides:
- Tamper-proof audit trail for compliance
- Authentication event tracking (login, logout, failures)
- Authorization change tracking (role changes, permissions)
- Data mutation tracking (CRUD operations with before/after)
- Request context (IP address, user agent) for forensics

HOW: Immutable append-only table with rich context fields.
Uses JSON for flexible storage of changes and metadata.
(PostgreSQL uses JSONB, SQLite uses JSON for compatibility)
"""

import enum
from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, PrimaryKeyMixin


class AuditAction(str, enum.Enum):
    """
    Enumeration of auditable actions.

    WHY: Using an enum ensures only valid, documented actions can be
    logged, making it easier to query and analyze audit data.

    Categories:
    - Authentication: Login, logout, password changes
    - Authorization: Role and permission changes
    - Data: CRUD operations on resources
    - Account: Activation, deactivation, verification
    """

    # Authentication events
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    PASSWORD_RESET_REQUEST = "PASSWORD_RESET_REQUEST"
    PASSWORD_RESET_COMPLETE = "PASSWORD_RESET_COMPLETE"
    TOKEN_REFRESH = "TOKEN_REFRESH"

    # Authorization events
    ROLE_CHANGE = "ROLE_CHANGE"
    PERMISSION_GRANT = "PERMISSION_GRANT"
    PERMISSION_REVOKE = "PERMISSION_REVOKE"

    # Data mutation events
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

    # Account lifecycle events
    ACCOUNT_CREATED = "ACCOUNT_CREATED"
    ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    EMAIL_VERIFIED = "EMAIL_VERIFIED"
    EMAIL_VERIFICATION_SENT = "EMAIL_VERIFICATION_SENT"

    # Organization events
    ORG_CREATED = "ORG_CREATED"
    ORG_UPDATED = "ORG_UPDATED"
    USER_JOINED_ORG = "USER_JOINED_ORG"
    USER_LEFT_ORG = "USER_LEFT_ORG"

    # Administrative events
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE"
    BULK_OPERATION = "BULK_OPERATION"
    EXPORT_DATA = "EXPORT_DATA"


class AuditLog(Base, PrimaryKeyMixin, TimestampMixin):
    """
    Immutable audit log entry for security event tracking.

    WHAT: Records security-relevant events with full context.

    WHY: Provides forensic evidence for security investigations,
    compliance reporting, and anomaly detection. Audit logs are:
    - Immutable: Cannot be updated or deleted
    - Complete: Include who, what, when, where context
    - Indexed: Optimized for common query patterns

    HOW: Append-only table with rich context fields. Uses JSONB
    for flexible storage of changes and metadata.

    Fields:
    - actor_user_id: Who performed the action (nullable for failed logins)
    - action: What type of event occurred (AuditAction enum)
    - resource_type: Category of affected resource (e.g., "user", "project")
    - resource_id: Specific resource ID (nullable)
    - org_id: Organization context for multi-tenant filtering
    - changes: Before/after values for mutations (JSONB)
    - metadata: Additional context (JSONB)
    - ip_address: Client IP for geographic analysis
    - user_agent: Browser/client info for device tracking
    - created_at: Timestamp (from TimestampMixin)
    """

    __tablename__ = "audit_logs"

    # Actor context
    # WHY: actor_user_id is nullable because failed login attempts
    # may not have a known user (e.g., email doesn't exist)
    actor_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Action classification
    # WHY: Indexed for fast filtering by action type
    action = Column(Enum(AuditAction), nullable=False, index=True)

    # Resource identification
    # WHY: resource_type is required for categorization,
    # resource_id is optional (some actions like login don't have a resource)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(Integer, nullable=True, index=True)

    # Multi-tenancy
    # WHY: org_id allows filtering audit logs by organization
    # for compliance reports. Nullable for system-level events.
    org_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Change tracking
    # WHY: JSON stores flexible before/after values for mutations
    # Example: {"role": {"before": "CLIENT", "after": "ADMIN"}}
    # NOTE: Uses SQLAlchemy JSON type which maps to JSONB on PostgreSQL
    # and JSON on SQLite for test compatibility
    changes = Column(JSON, nullable=True)

    # Additional context
    # WHY: JSON allows storing arbitrary context without schema changes
    # Example: {"attempted_email": "attacker@example.com"} for failed logins
    # NOTE: Named 'extra_data' because 'metadata' is reserved by SQLAlchemy
    extra_data = Column(JSON, nullable=True)

    # Request context
    # WHY: IP and user agent are critical for forensic analysis,
    # detecting attacks, and geographic compliance
    ip_address = Column(String(45), nullable=True, index=True)  # IPv6 max length
    user_agent = Column(Text, nullable=True)

    # Relationships
    actor = relationship("User", foreign_keys=[actor_user_id])
    organization = relationship("Organization", foreign_keys=[org_id])

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action={self.action.value}, "
            f"actor_user_id={self.actor_user_id}, resource_type={self.resource_type})>"
        )
