"""Add onboarding tables.

Revision ID: 020
Revises: 019
Create Date: 2024-01-15 14:00:00.000000

WHAT: Creates tables for client onboarding wizard functionality.

WHY: Onboarding enables:
1. Guided setup for new clients
2. Customizable multi-step flows
3. Progress tracking and completion
4. Data collection at each step

HOW: Creates three tables:
- onboarding_templates: Defines onboarding flows with steps
- client_onboardings: Tracks individual client progress
- onboarding_reminders: Records reminder emails sent
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

# revision identifiers, used by Alembic.
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create onboarding tables.

    WHAT: Adds tables for onboarding wizard functionality.

    WHY: Provides structured onboarding for new clients with
    customizable templates and progress tracking.

    HOW: Creates templates, client onboardings, and reminders
    with appropriate indexes and foreign keys.
    """
    # Create onboarding_templates table
    op.create_table(
        "onboarding_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("steps", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, default=False),
        sa.Column("auto_assign", sa.Boolean(), nullable=False, default=False),
        sa.Column("target_roles", ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
    )

    # Create indexes for onboarding_templates
    op.create_index(
        "ix_onboarding_templates_org_id",
        "onboarding_templates",
        ["org_id"],
    )
    op.create_index(
        "ix_onboarding_templates_slug",
        "onboarding_templates",
        ["slug"],
    )
    op.create_index(
        "ix_onboarding_templates_is_active",
        "onboarding_templates",
        ["is_active"],
    )
    op.create_index(
        "ix_onboarding_templates_is_default",
        "onboarding_templates",
        ["is_default"],
    )
    op.create_index(
        "ix_onboarding_templates_org_slug",
        "onboarding_templates",
        ["org_id", "slug"],
        unique=True,
    )

    # Create client_onboardings table
    op.create_table(
        "client_onboardings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.String(50), nullable=True),
        sa.Column("completed_steps", ARRAY(sa.String()), nullable=True),
        sa.Column("skipped_steps", ARRAY(sa.String()), nullable=True),
        sa.Column("step_data", JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            default="not_started",
        ),
        sa.Column("progress_percent", sa.Integer(), nullable=False, default=0),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["onboarding_templates.id"],
            ondelete="CASCADE",
        ),
    )

    # Create indexes for client_onboardings
    op.create_index(
        "ix_client_onboardings_org_id",
        "client_onboardings",
        ["org_id"],
    )
    op.create_index(
        "ix_client_onboardings_user_id",
        "client_onboardings",
        ["user_id"],
    )
    op.create_index(
        "ix_client_onboardings_template_id",
        "client_onboardings",
        ["template_id"],
    )
    op.create_index(
        "ix_client_onboardings_status",
        "client_onboardings",
        ["status"],
    )
    op.create_index(
        "ix_client_onboardings_user_template",
        "client_onboardings",
        ["user_id", "template_id"],
        unique=True,
    )

    # Create onboarding_reminders table
    op.create_table(
        "onboarding_reminders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("onboarding_id", sa.Integer(), nullable=False),
        sa.Column("reminder_type", sa.String(50), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_to_email", sa.String(255), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("clicked_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["onboarding_id"],
            ["client_onboardings.id"],
            ondelete="CASCADE",
        ),
    )

    # Create indexes for onboarding_reminders
    op.create_index(
        "ix_onboarding_reminders_onboarding_id",
        "onboarding_reminders",
        ["onboarding_id"],
    )
    op.create_index(
        "ix_onboarding_reminders_sent_at",
        "onboarding_reminders",
        ["sent_at"],
    )


def downgrade() -> None:
    """
    Remove onboarding tables.

    WHAT: Drops all onboarding-related tables.

    WHY: Allows rolling back the migration if needed.

    HOW: Drops tables in reverse order of creation
    to respect foreign key constraints.
    """
    # Drop onboarding_reminders table and indexes
    op.drop_index("ix_onboarding_reminders_sent_at", table_name="onboarding_reminders")
    op.drop_index(
        "ix_onboarding_reminders_onboarding_id", table_name="onboarding_reminders"
    )
    op.drop_table("onboarding_reminders")

    # Drop client_onboardings table and indexes
    op.drop_index(
        "ix_client_onboardings_user_template", table_name="client_onboardings"
    )
    op.drop_index("ix_client_onboardings_status", table_name="client_onboardings")
    op.drop_index("ix_client_onboardings_template_id", table_name="client_onboardings")
    op.drop_index("ix_client_onboardings_user_id", table_name="client_onboardings")
    op.drop_index("ix_client_onboardings_org_id", table_name="client_onboardings")
    op.drop_table("client_onboardings")

    # Drop onboarding_templates table and indexes
    op.drop_index("ix_onboarding_templates_org_slug", table_name="onboarding_templates")
    op.drop_index(
        "ix_onboarding_templates_is_default", table_name="onboarding_templates"
    )
    op.drop_index("ix_onboarding_templates_is_active", table_name="onboarding_templates")
    op.drop_index("ix_onboarding_templates_slug", table_name="onboarding_templates")
    op.drop_index("ix_onboarding_templates_org_id", table_name="onboarding_templates")
    op.drop_table("onboarding_templates")
