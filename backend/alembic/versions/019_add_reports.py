"""
Add reports tables (scheduled_reports, report_executions, report_templates).

WHAT: Creates tables for report builder and scheduled reports.

WHY: Reports enable:
- Scheduled automated report generation and delivery
- Custom report building with parameters
- Export to PDF/Excel/CSV formats
- Historical report execution tracking

Revision ID: 019
Revises: 018
Create Date: 2024-01-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY


# revision identifiers, used by Alembic.
revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create reports tables.

    WHAT: Creates scheduled_reports, report_executions, and report_templates tables.

    WHY: Enables scheduled reports and report builder functionality.

    HOW: Creates tables with proper indexes and foreign keys.
    """

    # Create scheduled_reports table
    op.create_table(
        "scheduled_reports",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # Report definition
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("report_type", sa.String(50), nullable=False),
        # Report configuration
        sa.Column("parameters", JSONB, nullable=True),
        sa.Column(
            "output_format",
            sa.String(20),
            nullable=False,
            server_default="pdf",
        ),
        # Schedule configuration
        sa.Column("schedule", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        # Delivery configuration
        sa.Column("recipients", ARRAY(sa.Integer), nullable=True),
        sa.Column("email_subject", sa.String(255), nullable=True),
        sa.Column("email_body", sa.Text(), nullable=True),
        # Status
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Create report_executions table
    op.create_table(
        "report_executions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "scheduled_report_id",
            sa.Integer(),
            sa.ForeignKey("scheduled_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        # Report info (denormalized)
        sa.Column("report_name", sa.String(100), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("parameters", JSONB, nullable=True),
        sa.Column("output_format", sa.String(20), nullable=False),
        # Execution status
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        # Output
        sa.Column("output_file_key", sa.String(500), nullable=True),
        sa.Column("output_size", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Delivery status
        sa.Column("delivery_status", sa.String(20), nullable=True),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        # Metadata
        sa.Column(
            "triggered_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "is_adhoc",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create report_templates table
    op.create_table(
        "report_templates",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # Template definition
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("report_type", sa.String(50), nullable=False),
        # Template configuration
        sa.Column("parameters", JSONB, nullable=True),
        sa.Column(
            "default_format",
            sa.String(20),
            nullable=False,
            server_default="pdf",
        ),
        # Column/field selection
        sa.Column("selected_columns", ARRAY(sa.String), nullable=True),
        sa.Column("grouping", JSONB, nullable=True),
        sa.Column("sorting", JSONB, nullable=True),
        sa.Column("filters", JSONB, nullable=True),
        # Display options
        sa.Column(
            "include_charts",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "include_summary",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("chart_config", JSONB, nullable=True),
        # Status
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Create indexes for scheduled_reports
    op.create_index(
        "ix_scheduled_reports_org_id",
        "scheduled_reports",
        ["org_id"],
    )
    op.create_index(
        "ix_scheduled_reports_created_by",
        "scheduled_reports",
        ["created_by"],
    )
    op.create_index(
        "ix_scheduled_reports_report_type",
        "scheduled_reports",
        ["report_type"],
    )
    op.create_index(
        "ix_scheduled_reports_is_active",
        "scheduled_reports",
        ["is_active"],
    )
    op.create_index(
        "ix_scheduled_reports_next_run_at",
        "scheduled_reports",
        ["next_run_at"],
    )

    # Create indexes for report_executions
    op.create_index(
        "ix_report_executions_org_id",
        "report_executions",
        ["org_id"],
    )
    op.create_index(
        "ix_report_executions_scheduled_report_id",
        "report_executions",
        ["scheduled_report_id"],
    )
    op.create_index(
        "ix_report_executions_status",
        "report_executions",
        ["status"],
    )
    op.create_index(
        "ix_report_executions_created_at",
        "report_executions",
        ["created_at"],
    )
    op.create_index(
        "ix_report_executions_org_status",
        "report_executions",
        ["org_id", "status"],
    )

    # Create indexes for report_templates
    op.create_index(
        "ix_report_templates_org_id",
        "report_templates",
        ["org_id"],
    )
    op.create_index(
        "ix_report_templates_created_by",
        "report_templates",
        ["created_by"],
    )
    op.create_index(
        "ix_report_templates_report_type",
        "report_templates",
        ["report_type"],
    )
    op.create_index(
        "ix_report_templates_is_public",
        "report_templates",
        ["is_public"],
    )


def downgrade() -> None:
    """
    Drop reports tables.

    WHAT: Removes reports infrastructure.

    WHY: Allows rollback if needed.
    """

    # Drop indexes for report_templates
    op.drop_index("ix_report_templates_is_public", table_name="report_templates")
    op.drop_index("ix_report_templates_report_type", table_name="report_templates")
    op.drop_index("ix_report_templates_created_by", table_name="report_templates")
    op.drop_index("ix_report_templates_org_id", table_name="report_templates")

    # Drop indexes for report_executions
    op.drop_index("ix_report_executions_org_status", table_name="report_executions")
    op.drop_index("ix_report_executions_created_at", table_name="report_executions")
    op.drop_index("ix_report_executions_status", table_name="report_executions")
    op.drop_index(
        "ix_report_executions_scheduled_report_id", table_name="report_executions"
    )
    op.drop_index("ix_report_executions_org_id", table_name="report_executions")

    # Drop indexes for scheduled_reports
    op.drop_index("ix_scheduled_reports_next_run_at", table_name="scheduled_reports")
    op.drop_index("ix_scheduled_reports_is_active", table_name="scheduled_reports")
    op.drop_index("ix_scheduled_reports_report_type", table_name="scheduled_reports")
    op.drop_index("ix_scheduled_reports_created_by", table_name="scheduled_reports")
    op.drop_index("ix_scheduled_reports_org_id", table_name="scheduled_reports")

    # Drop tables
    op.drop_table("report_templates")
    op.drop_table("report_executions")
    op.drop_table("scheduled_reports")
