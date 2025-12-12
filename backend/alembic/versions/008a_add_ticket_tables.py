"""Add ticket tables for support ticketing system.

Revision ID: 008a
Revises: 007
Create Date: 2025-12-11

WHAT: Adds tables for tickets, comments, and attachments.

WHY: Enables support ticketing system with:
- Priority-based SLA tracking
- Status workflow management
- Comment threading with internal notes
- File attachment support
- Project linking for context
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "008a"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create ticket tables.

    Creates:
    - tickets: Main support ticket table
    - ticket_comments: Comments/replies on tickets
    - ticket_attachments: File attachments on tickets/comments
    """

    # Create ticket enums using raw SQL
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticketstatus') THEN
                CREATE TYPE ticketstatus AS ENUM ('open', 'in_progress', 'waiting', 'resolved', 'closed');
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticketpriority') THEN
                CREATE TYPE ticketpriority AS ENUM ('low', 'medium', 'high', 'urgent');
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticketcategory') THEN
                CREATE TYPE ticketcategory AS ENUM ('general', 'bug', 'feature', 'question', 'support');
            END IF;
        END$$;
    """)

    # Create tickets table
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "assigned_to_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("category", sa.String(50), nullable=False, server_default="support"),
        sa.Column("sla_response_due_at", sa.DateTime(), nullable=True),
        sa.Column("sla_resolution_due_at", sa.DateTime(), nullable=True),
        sa.Column("first_response_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Convert String columns to enum types
    op.execute("ALTER TABLE tickets ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE tickets ALTER COLUMN status TYPE ticketstatus USING status::ticketstatus")
    op.execute("ALTER TABLE tickets ALTER COLUMN status SET DEFAULT 'open'::ticketstatus")

    op.execute("ALTER TABLE tickets ALTER COLUMN priority DROP DEFAULT")
    op.execute("ALTER TABLE tickets ALTER COLUMN priority TYPE ticketpriority USING priority::ticketpriority")
    op.execute("ALTER TABLE tickets ALTER COLUMN priority SET DEFAULT 'medium'::ticketpriority")

    op.execute("ALTER TABLE tickets ALTER COLUMN category DROP DEFAULT")
    op.execute("ALTER TABLE tickets ALTER COLUMN category TYPE ticketcategory USING category::ticketcategory")
    op.execute("ALTER TABLE tickets ALTER COLUMN category SET DEFAULT 'support'::ticketcategory")

    # Create indexes for tickets
    op.create_index("ix_tickets_org_id", "tickets", ["org_id"])
    op.create_index("ix_tickets_project_id", "tickets", ["project_id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_priority", "tickets", ["priority"])
    op.create_index("ix_tickets_assigned_to", "tickets", ["assigned_to_user_id"])
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])

    # Create ticket_comments table
    op.create_table(
        "ticket_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Create indexes for ticket_comments
    op.create_index("ix_ticket_comments_ticket_id", "ticket_comments", ["ticket_id"])
    op.create_index("ix_ticket_comments_user_id", "ticket_comments", ["user_id"])
    op.create_index("ix_ticket_comments_created_at", "ticket_comments", ["created_at"])

    # Create ticket_attachments table
    op.create_table(
        "ticket_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id"),
            nullable=False,
        ),
        sa.Column(
            "comment_id",
            sa.Integer(),
            sa.ForeignKey("ticket_comments.id"),
            nullable=True,
        ),
        sa.Column(
            "uploaded_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for ticket_attachments
    op.create_index(
        "ix_ticket_attachments_ticket_id", "ticket_attachments", ["ticket_id"]
    )
    op.create_index(
        "ix_ticket_attachments_comment_id", "ticket_attachments", ["comment_id"]
    )


def downgrade() -> None:
    """Drop ticket tables."""

    # Drop ticket_attachments
    op.drop_index("ix_ticket_attachments_comment_id", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_ticket_id", table_name="ticket_attachments")
    op.drop_table("ticket_attachments")

    # Drop ticket_comments
    op.drop_index("ix_ticket_comments_created_at", table_name="ticket_comments")
    op.drop_index("ix_ticket_comments_user_id", table_name="ticket_comments")
    op.drop_index("ix_ticket_comments_ticket_id", table_name="ticket_comments")
    op.drop_table("ticket_comments")

    # Drop tickets
    op.drop_index("ix_tickets_created_at", table_name="tickets")
    op.drop_index("ix_tickets_assigned_to", table_name="tickets")
    op.drop_index("ix_tickets_priority", table_name="tickets")
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.drop_index("ix_tickets_project_id", table_name="tickets")
    op.drop_index("ix_tickets_org_id", table_name="tickets")
    op.drop_table("tickets")

    # Drop enums
    sa.Enum(name="ticketcategory").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ticketpriority").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ticketstatus").drop(op.get_bind(), checkfirst=True)
