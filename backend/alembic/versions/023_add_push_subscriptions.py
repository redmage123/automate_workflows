"""Add push subscriptions table.

Revision ID: 023
Revises: 022
Create Date: 2024-01-01 00:00:00.000000

WHAT: Creates table for web push notification subscriptions.

WHY: Push subscriptions enable:
1. Real-time notifications to users
2. Engagement even when app is closed
3. Cross-device notification delivery
4. Persistent subscription storage

HOW: Creates push_subscriptions table with:
- Web Push endpoint and encryption keys
- User and organization relationships
- Delivery tracking (last used, failures)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic
revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create push_subscriptions table."""

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        # Subscription endpoint (unique URL for this subscription)
        sa.Column("endpoint", sa.Text(), nullable=False),
        # Encryption keys
        sa.Column("p256dh_key", sa.Text(), nullable=False),
        sa.Column("auth_key", sa.Text(), nullable=False),
        # Full subscription object
        sa.Column("subscription_info", JSONB(), nullable=False),
        # Device info
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("device_type", sa.String(50), nullable=True),
        # Status
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )

    # Indexes
    op.create_index(
        "ix_push_subscriptions_user_id",
        "push_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "ix_push_subscriptions_org_id",
        "push_subscriptions",
        ["org_id"],
    )
    op.create_index(
        "ix_push_subscriptions_is_active",
        "push_subscriptions",
        ["is_active"],
    )
    op.create_index(
        "ix_push_subscriptions_endpoint",
        "push_subscriptions",
        ["endpoint"],
        unique=True,
    )


def downgrade() -> None:
    """Drop push_subscriptions table."""
    op.drop_index("ix_push_subscriptions_endpoint", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_is_active", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_org_id", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
