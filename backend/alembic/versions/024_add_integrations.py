"""Add integration tables for calendar and webhooks.

Revision ID: 024
Revises: 023
Create Date: 2024-01-15

WHAT: Creates tables for external integrations.

WHY: External integrations enable:
1. Calendar sync with Google/Outlook
2. Webhook delivery to external systems
3. Custom automation triggers

HOW: Creates three tables:
- calendar_integrations: OAuth tokens and sync settings
- webhook_endpoints: Webhook URL configurations
- webhook_deliveries: Delivery attempt logs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create integration tables.

    WHAT: Creates calendar_integrations, webhook_endpoints, webhook_deliveries.

    WHY: Supports external integrations for calendar sync and webhooks.
    """
    # Calendar integrations table
    op.create_table(
        "calendar_integrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        # Provider info
        sa.Column("provider", sa.String(50), nullable=False, server_default="google"),
        sa.Column("provider_account_id", sa.String(255), nullable=True),
        sa.Column("provider_email", sa.String(255), nullable=True),
        # OAuth tokens (should be encrypted in production)
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        # Calendar settings
        sa.Column("calendar_id", sa.String(255), nullable=True),
        sa.Column("calendar_name", sa.String(255), nullable=True),
        # Sync settings
        sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sync_projects", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sync_tickets", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sync_invoices", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        # Status
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
    )

    # Calendar integration indexes
    op.create_index(
        "ix_calendar_integrations_user_id",
        "calendar_integrations",
        ["user_id"],
    )
    op.create_index(
        "ix_calendar_integrations_org_id",
        "calendar_integrations",
        ["org_id"],
    )
    op.create_index(
        "ix_calendar_integrations_provider",
        "calendar_integrations",
        ["provider"],
    )
    # Unique constraint: one provider per user
    op.create_index(
        "ix_calendar_integrations_user_provider",
        "calendar_integrations",
        ["user_id", "provider"],
        unique=True,
    )

    # Webhook endpoints table
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        # Endpoint identity
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        # Security
        sa.Column("secret", sa.String(255), nullable=False),
        sa.Column("headers", postgresql.JSONB(), nullable=True),
        # Event subscriptions
        sa.Column(
            "events",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        # Settings
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("retry_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        # Stats
        sa.Column("delivery_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(), nullable=True),
        # Creator
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
        ),
    )

    # Webhook endpoint indexes
    op.create_index(
        "ix_webhook_endpoints_org_id",
        "webhook_endpoints",
        ["org_id"],
    )
    op.create_index(
        "ix_webhook_endpoints_is_active",
        "webhook_endpoints",
        ["is_active"],
    )

    # Webhook deliveries table
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("endpoint_id", sa.Integer(), nullable=False),
        # Event info
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_id", sa.String(100), nullable=False),
        # Request details
        sa.Column("request_url", sa.Text(), nullable=False),
        sa.Column("request_headers", postgresql.JSONB(), nullable=True),
        sa.Column("request_body", postgresql.JSONB(), nullable=True),
        # Response details
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_headers", postgresql.JSONB(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        # Delivery status
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Timing
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "triggered_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["endpoint_id"],
            ["webhook_endpoints.id"],
            ondelete="CASCADE",
        ),
    )

    # Webhook delivery indexes
    op.create_index(
        "ix_webhook_deliveries_endpoint_id",
        "webhook_deliveries",
        ["endpoint_id"],
    )
    op.create_index(
        "ix_webhook_deliveries_event_type",
        "webhook_deliveries",
        ["event_type"],
    )
    op.create_index(
        "ix_webhook_deliveries_delivered",
        "webhook_deliveries",
        ["delivered"],
    )
    op.create_index(
        "ix_webhook_deliveries_triggered_at",
        "webhook_deliveries",
        ["triggered_at"],
    )
    # Index for retry queries
    op.create_index(
        "ix_webhook_deliveries_pending_retry",
        "webhook_deliveries",
        ["delivered", "next_retry_at"],
        postgresql_where=sa.text("delivered = false AND next_retry_at IS NOT NULL"),
    )


def downgrade() -> None:
    """
    Drop integration tables.

    WHAT: Removes all integration tables.

    WHY: Allows rolling back the migration if needed.
    """
    # Drop webhook deliveries
    op.drop_index("ix_webhook_deliveries_pending_retry", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_triggered_at", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_delivered", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_event_type", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_endpoint_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")

    # Drop webhook endpoints
    op.drop_index("ix_webhook_endpoints_is_active", table_name="webhook_endpoints")
    op.drop_index("ix_webhook_endpoints_org_id", table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")

    # Drop calendar integrations
    op.drop_index(
        "ix_calendar_integrations_user_provider",
        table_name="calendar_integrations",
    )
    op.drop_index(
        "ix_calendar_integrations_provider",
        table_name="calendar_integrations",
    )
    op.drop_index(
        "ix_calendar_integrations_org_id",
        table_name="calendar_integrations",
    )
    op.drop_index(
        "ix_calendar_integrations_user_id",
        table_name="calendar_integrations",
    )
    op.drop_table("calendar_integrations")
