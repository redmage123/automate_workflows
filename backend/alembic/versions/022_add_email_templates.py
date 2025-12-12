"""Add email templates tables.

Revision ID: 022
Revises: 021
Create Date: 2024-01-01 00:00:00.000000

WHAT: Creates tables for database-backed email template management.

WHY: Organization-specific email templates enable:
1. Custom branded transactional emails
2. Version control with rollback capability
3. Analytics on email performance
4. Admin-manageable templates

HOW: Creates three tables:
- email_templates: Template definitions with versioning
- email_template_versions: Version history for templates
- sent_emails: Log of all sent emails for analytics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic
revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create email template management tables.

    Tables:
    - email_templates: Template definitions
    - email_template_versions: Version history
    - sent_emails: Sent email logs
    """

    # =========================================================================
    # Email Templates Table
    # =========================================================================
    op.create_table(
        "email_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        # Template identity
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="system"),
        # Email content
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=True),
        # Template variables metadata
        sa.Column("variables", JSONB(), nullable=True),
        # Settings
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        # Version tracking
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        # Creator/updater tracking
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
    )

    # Indexes for email_templates
    op.create_index(
        "ix_email_templates_org_id",
        "email_templates",
        ["org_id"],
    )
    op.create_index(
        "ix_email_templates_slug",
        "email_templates",
        ["slug"],
    )
    op.create_index(
        "ix_email_templates_category",
        "email_templates",
        ["category"],
    )
    op.create_index(
        "ix_email_templates_is_active",
        "email_templates",
        ["is_active"],
    )
    op.create_index(
        "ix_email_templates_org_slug",
        "email_templates",
        ["org_id", "slug"],
        unique=True,
    )

    # =========================================================================
    # Email Template Versions Table
    # =========================================================================
    op.create_table(
        "email_template_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        # Version number
        sa.Column("version", sa.Integer(), nullable=False),
        # Content snapshot
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=True),
        sa.Column("variables", JSONB(), nullable=True),
        # Change tracking
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("change_note", sa.String(500), nullable=True),
        # Timestamp
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["email_templates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
    )

    # Indexes for email_template_versions
    op.create_index(
        "ix_email_template_versions_template_id",
        "email_template_versions",
        ["template_id"],
    )
    op.create_index(
        "ix_email_template_versions_version",
        "email_template_versions",
        ["version"],
    )
    op.create_index(
        "ix_email_template_versions_template_version",
        "email_template_versions",
        ["template_id", "version"],
        unique=True,
    )

    # =========================================================================
    # Sent Emails Table
    # =========================================================================
    op.create_table(
        "sent_emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        # Template reference
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("template_slug", sa.String(100), nullable=True),
        # Email details
        sa.Column("to_email", sa.String(255), nullable=False),
        sa.Column("to_name", sa.String(255), nullable=True),
        sa.Column("from_email", sa.String(255), nullable=False),
        sa.Column("from_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        # Variables used (for debugging)
        sa.Column("variables_used", JSONB(), nullable=True),
        # Delivery status
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # External references
        sa.Column("message_id", sa.String(255), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        # Error tracking
        sa.Column("error_message", sa.Text(), nullable=True),
        # Engagement tracking
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("clicked_at", sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["email_templates.id"],
            ondelete="SET NULL",
        ),
    )

    # Indexes for sent_emails
    op.create_index(
        "ix_sent_emails_org_id",
        "sent_emails",
        ["org_id"],
    )
    op.create_index(
        "ix_sent_emails_template_id",
        "sent_emails",
        ["template_id"],
    )
    op.create_index(
        "ix_sent_emails_to_email",
        "sent_emails",
        ["to_email"],
    )
    op.create_index(
        "ix_sent_emails_status",
        "sent_emails",
        ["status"],
    )
    op.create_index(
        "ix_sent_emails_sent_at",
        "sent_emails",
        ["sent_at"],
    )
    op.create_index(
        "ix_sent_emails_message_id",
        "sent_emails",
        ["message_id"],
    )


def downgrade() -> None:
    """Remove email template management tables."""
    # Drop sent_emails
    op.drop_index("ix_sent_emails_message_id", table_name="sent_emails")
    op.drop_index("ix_sent_emails_sent_at", table_name="sent_emails")
    op.drop_index("ix_sent_emails_status", table_name="sent_emails")
    op.drop_index("ix_sent_emails_to_email", table_name="sent_emails")
    op.drop_index("ix_sent_emails_template_id", table_name="sent_emails")
    op.drop_index("ix_sent_emails_org_id", table_name="sent_emails")
    op.drop_table("sent_emails")

    # Drop email_template_versions
    op.drop_index(
        "ix_email_template_versions_template_version",
        table_name="email_template_versions",
    )
    op.drop_index(
        "ix_email_template_versions_version",
        table_name="email_template_versions",
    )
    op.drop_index(
        "ix_email_template_versions_template_id",
        table_name="email_template_versions",
    )
    op.drop_table("email_template_versions")

    # Drop email_templates
    op.drop_index("ix_email_templates_org_slug", table_name="email_templates")
    op.drop_index("ix_email_templates_is_active", table_name="email_templates")
    op.drop_index("ix_email_templates_category", table_name="email_templates")
    op.drop_index("ix_email_templates_slug", table_name="email_templates")
    op.drop_index("ix_email_templates_org_id", table_name="email_templates")
    op.drop_table("email_templates")
