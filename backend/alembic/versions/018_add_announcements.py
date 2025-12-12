"""
Add announcements tables (announcements, announcement_reads).

WHAT: Creates tables for organization-wide announcements.

WHY: Announcements enable:
- Broadcasting important updates to all users
- Scheduled communication
- Targeted messaging (by role, user group)
- Acknowledgment tracking

Revision ID: 018
Revises: 017
Create Date: 2024-01-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY


# revision identifiers, used by Alembic.
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create announcements tables.

    WHAT: Creates announcements and announcement_reads tables.

    WHY: Enables organization-wide announcements with targeting
    and acknowledgment tracking.

    HOW: Creates tables with proper indexes and foreign keys.
    """

    # Create announcements table
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        # Content
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=True),
        # Type and priority
        sa.Column(
            "type",
            sa.String(20),
            nullable=False,
            server_default="info",
        ),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="normal",
        ),
        # Status
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        # Scheduling
        sa.Column("publish_at", sa.DateTime(), nullable=True),
        sa.Column("expire_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        # Targeting
        sa.Column(
            "target_all",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("target_roles", ARRAY(sa.String), nullable=True),
        sa.Column("target_user_ids", ARRAY(sa.Integer), nullable=True),
        # Display options
        sa.Column(
            "is_dismissible",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "require_acknowledgment",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "show_banner",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Link (optional CTA)
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("action_text", sa.String(100), nullable=True),
        # Metadata
        sa.Column("metadata", JSONB, nullable=True),
        # Creator
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
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

    # Create announcement_reads table
    op.create_table(
        "announcement_reads",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "announcement_id",
            sa.Integer(),
            sa.ForeignKey("announcements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # Interaction type
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "is_acknowledged",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "is_dismissed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Timestamps
        sa.Column(
            "read_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
    )

    # Create indexes for announcements
    op.create_index("ix_announcements_org_id", "announcements", ["org_id"])
    op.create_index("ix_announcements_status", "announcements", ["status"])
    op.create_index("ix_announcements_publish_at", "announcements", ["publish_at"])
    op.create_index("ix_announcements_expire_at", "announcements", ["expire_at"])
    op.create_index("ix_announcements_created_by", "announcements", ["created_by"])
    op.create_index(
        "ix_announcements_org_status",
        "announcements",
        ["org_id", "status"],
    )

    # Create indexes for announcement_reads
    op.create_index(
        "ix_announcement_reads_announcement_id",
        "announcement_reads",
        ["announcement_id"],
    )
    op.create_index(
        "ix_announcement_reads_user_id",
        "announcement_reads",
        ["user_id"],
    )
    op.create_index(
        "ix_announcement_reads_unique",
        "announcement_reads",
        ["announcement_id", "user_id"],
        unique=True,
    )


def downgrade() -> None:
    """
    Drop announcements tables.

    WHAT: Removes announcements infrastructure.

    WHY: Allows rollback if needed.
    """

    # Drop indexes for announcement_reads
    op.drop_index("ix_announcement_reads_unique", table_name="announcement_reads")
    op.drop_index("ix_announcement_reads_user_id", table_name="announcement_reads")
    op.drop_index(
        "ix_announcement_reads_announcement_id", table_name="announcement_reads"
    )

    # Drop indexes for announcements
    op.drop_index("ix_announcements_org_status", table_name="announcements")
    op.drop_index("ix_announcements_created_by", table_name="announcements")
    op.drop_index("ix_announcements_expire_at", table_name="announcements")
    op.drop_index("ix_announcements_publish_at", table_name="announcements")
    op.drop_index("ix_announcements_status", table_name="announcements")
    op.drop_index("ix_announcements_org_id", table_name="announcements")

    # Drop tables
    op.drop_table("announcement_reads")
    op.drop_table("announcements")
