"""Add audit_logs table

Revision ID: 003
Revises: 002
Create Date: 2025-12-10

WHAT: Creates the audit_logs table for security event tracking.

WHY: OWASP A09 (Security Logging and Monitoring) requires comprehensive
logging of security-relevant events. This table stores:
- Authentication events (login, logout, failed attempts)
- Authorization changes (role changes, permissions)
- Data mutations (CRUD operations with before/after)
- Request context (IP address, user agent) for forensics

HOW: Append-only table with indexes optimized for common query patterns.
Uses JSONB for flexible storage of changes and metadata.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create audit_logs table with indexes for security analysis.

    WHY: Audit logs are critical for:
    1. Security investigations (who did what, when)
    2. Compliance reporting (SOC 2, HIPAA)
    3. Anomaly detection (brute force attacks)
    4. Forensic analysis (incident response)

    Indexes are optimized for common query patterns:
    - By user (all actions by a specific user)
    - By action (all failed logins, all role changes)
    - By IP address (all activity from suspicious IP)
    - By organization (compliance reports)
    - By resource (all changes to a specific resource)
    """
    # Create enum for audit actions
    # WHY: Using PostgreSQL enum ensures only valid actions can be stored
    audit_action_enum = sa.Enum(
        'LOGIN_SUCCESS',
        'LOGIN_FAILURE',
        'LOGOUT',
        'PASSWORD_CHANGE',
        'PASSWORD_RESET_REQUEST',
        'PASSWORD_RESET_COMPLETE',
        'TOKEN_REFRESH',
        'ROLE_CHANGE',
        'PERMISSION_GRANT',
        'PERMISSION_REVOKE',
        'CREATE',
        'UPDATE',
        'DELETE',
        'ACCOUNT_CREATED',
        'ACCOUNT_ACTIVATED',
        'ACCOUNT_DEACTIVATED',
        'EMAIL_VERIFIED',
        'EMAIL_VERIFICATION_SENT',
        'ORG_CREATED',
        'ORG_UPDATED',
        'USER_JOINED_ORG',
        'USER_LEFT_ORG',
        'ADMIN_OVERRIDE',
        'BULK_OPERATION',
        'EXPORT_DATA',
        name='auditaction'
    )

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        # Actor context (nullable for failed logins with unknown user)
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        # Action classification
        sa.Column('action', audit_action_enum, nullable=False),
        # Resource identification
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        # Multi-tenancy (nullable for system-level events)
        sa.Column('org_id', sa.Integer(), nullable=True),
        # Change tracking (JSONB for flexible before/after values)
        sa.Column('changes', JSONB, nullable=True),
        # Additional context (JSONB for arbitrary data)
        # NOTE: Named 'extra_data' because 'metadata' is reserved by SQLAlchemy
        sa.Column('extra_data', JSONB, nullable=True),
        # Request context for forensics
        sa.Column('ip_address', sa.String(length=45), nullable=True),  # IPv6 max length
        sa.Column('user_agent', sa.Text(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        # Primary key
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common query patterns
    # WHY: Each index optimizes a specific security analysis scenario

    # Primary key index
    op.create_index('ix_audit_logs_id', 'audit_logs', ['id'])

    # User activity analysis
    # WHY: Security investigations often need all actions by a specific user
    op.create_index('ix_audit_logs_actor_user_id', 'audit_logs', ['actor_user_id'])

    # Action type filtering
    # WHY: Finding all failed logins, role changes, etc.
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])

    # Resource type filtering
    # WHY: Finding all auth events, user modifications, etc.
    op.create_index('ix_audit_logs_resource_type', 'audit_logs', ['resource_type'])

    # Resource-specific history
    # WHY: Viewing all changes to a specific resource
    op.create_index('ix_audit_logs_resource_id', 'audit_logs', ['resource_id'])

    # Organization compliance reports
    # WHY: Multi-tenant filtering for per-org audit reports
    op.create_index('ix_audit_logs_org_id', 'audit_logs', ['org_id'])

    # IP address forensics
    # WHY: Analyzing all activity from a suspicious IP
    op.create_index('ix_audit_logs_ip_address', 'audit_logs', ['ip_address'])

    # Time-based queries
    # WHY: Finding events in a specific time window for incident response
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    # Composite index for failed login detection
    # WHY: Efficient brute force detection queries
    op.create_index(
        'ix_audit_logs_failed_logins',
        'audit_logs',
        ['action', 'ip_address', 'created_at'],
        postgresql_where=sa.text("action = 'LOGIN_FAILURE'")
    )

    # Add foreign key constraints with SET NULL on delete
    # WHY: SET NULL instead of CASCADE because audit logs must be retained
    # even if the user or org is deleted (compliance requirement)
    op.create_foreign_key(
        'fk_audit_logs_actor_user_id_users',
        'audit_logs',
        'users',
        ['actor_user_id'],
        ['id'],
        ondelete='SET NULL'
    )

    op.create_foreign_key(
        'fk_audit_logs_org_id_organizations',
        'audit_logs',
        'organizations',
        ['org_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """
    Drop audit_logs table and related indexes.

    WHY: Downgrade allows rollback if issues are discovered after deployment.
    Note: This will lose all audit data - use with caution in production.
    """
    # Drop foreign keys first
    op.drop_constraint('fk_audit_logs_org_id_organizations', 'audit_logs', type_='foreignkey')
    op.drop_constraint('fk_audit_logs_actor_user_id_users', 'audit_logs', type_='foreignkey')

    # Drop indexes
    op.drop_index('ix_audit_logs_failed_logins', table_name='audit_logs')
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_ip_address', table_name='audit_logs')
    op.drop_index('ix_audit_logs_org_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_resource_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_resource_type', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_actor_user_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_id', table_name='audit_logs')

    # Drop table
    op.drop_table('audit_logs')

    # Drop enum type
    op.execute('DROP TYPE auditaction')
