"""Add notification preferences table.

Revision ID: 008
Revises: 007_add_workflow_tables
Create Date: 2025-12-11

WHAT: Creates notification_preferences table for user notification settings.

WHY: Allows users to control which notifications they receive,
through which channels (email, Slack, in-app), and how frequently.

HOW: Creates table with unique constraint on user_id + category.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create notification_preferences table.

    WHAT: Table storing per-user, per-category notification settings.

    WHY: Enables user control over notification behavior.
    """
    # Create notification category enum
    notification_category_enum = sa.Enum(
        "security",
        "tickets",
        "proposals",
        "invoices",
        "projects",
        "workflows",
        "system",
        name="notificationcategory",
    )

    # Create notification frequency enum
    notification_frequency_enum = sa.Enum(
        "immediate",
        "daily_digest",
        "weekly_digest",
        "none",
        name="notificationfrequency",
    )

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", notification_category_enum, nullable=False),
        sa.Column("channel_email", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("channel_slack", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("channel_in_app", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("frequency", notification_frequency_enum, nullable=False, server_default="immediate"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "category", name="uix_user_category"),
    )

    # Create index on user_id for faster lookups
    op.create_index(
        "ix_notification_preferences_user_id",
        "notification_preferences",
        ["user_id"],
    )


def downgrade() -> None:
    """Remove notification_preferences table."""
    op.drop_index("ix_notification_preferences_user_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS notificationcategory")
    op.execute("DROP TYPE IF EXISTS notificationfrequency")
