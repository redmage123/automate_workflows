"""
Add time_entries and time_summaries tables.

WHAT: Creates tables for time tracking functionality.

WHY: Time tracking enables:
- Billing based on hours worked
- Project budget management
- Team productivity insights
- Invoice generation

Revision ID: 015
Revises: 014
Create Date: 2024-01-15
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create time_entries and time_summaries tables.

    WHAT: Creates time tracking infrastructure.

    WHY: Enables time recording and reporting.

    HOW: Creates tables with proper indexes, constraints, and foreign keys.
    """

    # Create time_entries table
    op.create_table(
        "time_entries",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # Association
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id"),
            nullable=True,
        ),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id"),
            nullable=True,
        ),
        # Time tracking
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"),
        # Description
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=True),
        # Billing
        sa.Column("is_billable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=True),
        # Status and workflow
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "approved_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        # Invoice
        sa.Column(
            "invoice_id",
            sa.Integer(),
            sa.ForeignKey("invoices.id"),
            nullable=True,
        ),
        # Timer
        sa.Column("timer_started_at", sa.DateTime(), nullable=True),
        sa.Column("is_running", sa.Boolean(), nullable=False, server_default="false"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        # Constraints
        sa.CheckConstraint(
            "duration_minutes >= 0",
            name="ck_time_entries_positive_duration",
        ),
        sa.CheckConstraint(
            "end_time IS NULL OR start_time IS NULL OR end_time >= start_time",
            name="ck_time_entries_valid_time_range",
        ),
    )

    # Create time_summaries table (for pre-aggregated reporting)
    op.create_table(
        "time_summaries",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        # Aggregation keys
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id"),
            nullable=True,
        ),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("summary_week", sa.Date(), nullable=True),
        sa.Column("summary_month", sa.Date(), nullable=True),
        # Aggregated values
        sa.Column("total_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billable_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("non_billable_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billable_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default="0"),
        # Timestamp
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for time_entries
    op.create_index("ix_time_entries_org_id", "time_entries", ["org_id"])
    op.create_index("ix_time_entries_user_id", "time_entries", ["user_id"])
    op.create_index("ix_time_entries_project_id", "time_entries", ["project_id"])
    op.create_index("ix_time_entries_ticket_id", "time_entries", ["ticket_id"])
    op.create_index("ix_time_entries_date", "time_entries", ["date"])
    op.create_index("ix_time_entries_status", "time_entries", ["status"])
    op.create_index("ix_time_entries_invoice_id", "time_entries", ["invoice_id"])
    op.create_index(
        "ix_time_entries_user_date",
        "time_entries",
        ["user_id", "date"],
    )
    op.create_index(
        "ix_time_entries_running",
        "time_entries",
        ["user_id", "is_running"],
        postgresql_where="is_running = true",
    )

    # Create indexes for time_summaries
    op.create_index(
        "ix_time_summaries_org_date",
        "time_summaries",
        ["org_id", "summary_date"],
    )
    op.create_index(
        "ix_time_summaries_user_date",
        "time_summaries",
        ["user_id", "summary_date"],
    )
    op.create_index(
        "ix_time_summaries_project_date",
        "time_summaries",
        ["project_id", "summary_date"],
    )
    op.create_index(
        "ix_time_summaries_unique",
        "time_summaries",
        ["org_id", "user_id", "project_id", "summary_date"],
        unique=True,
    )


def downgrade() -> None:
    """
    Drop time_entries and time_summaries tables.

    WHAT: Removes time tracking infrastructure.

    WHY: Allows rollback if needed.
    """

    # Drop indexes for time_summaries
    op.drop_index("ix_time_summaries_unique", table_name="time_summaries")
    op.drop_index("ix_time_summaries_project_date", table_name="time_summaries")
    op.drop_index("ix_time_summaries_user_date", table_name="time_summaries")
    op.drop_index("ix_time_summaries_org_date", table_name="time_summaries")

    # Drop indexes for time_entries
    op.drop_index("ix_time_entries_running", table_name="time_entries")
    op.drop_index("ix_time_entries_user_date", table_name="time_entries")
    op.drop_index("ix_time_entries_invoice_id", table_name="time_entries")
    op.drop_index("ix_time_entries_status", table_name="time_entries")
    op.drop_index("ix_time_entries_date", table_name="time_entries")
    op.drop_index("ix_time_entries_ticket_id", table_name="time_entries")
    op.drop_index("ix_time_entries_project_id", table_name="time_entries")
    op.drop_index("ix_time_entries_user_id", table_name="time_entries")
    op.drop_index("ix_time_entries_org_id", table_name="time_entries")

    # Drop tables
    op.drop_table("time_summaries")
    op.drop_table("time_entries")
