"""
Add messaging tables (conversations, participants, messages, read receipts).

WHAT: Creates tables for in-app messaging functionality.

WHY: In-app messaging enables:
- Direct communication between team members
- Client-provider conversations
- Context-aware messaging (linked to projects/tickets)
- Reduced email dependency

Revision ID: 016
Revises: 015
Create Date: 2024-01-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create messaging tables.

    WHAT: Creates conversations, participants, messages, and read receipts tables.

    WHY: Enables in-app messaging functionality.

    HOW: Creates tables with proper indexes, constraints, and foreign keys.
    """

    # Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        # Type and title
        sa.Column(
            "type",
            sa.String(20),
            nullable=False,
            server_default="direct",
        ),
        sa.Column("title", sa.String(255), nullable=True),
        # Entity association (polymorphic)
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        # Creator
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # Latest message info (denormalized for performance)
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_preview", sa.String(200), nullable=True),
        # Status
        sa.Column(
            "is_archived",
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

    # Create conversation_participants table
    op.create_table(
        "conversation_participants",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # Join/leave tracking
        sa.Column(
            "joined_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("left_at", sa.DateTime(), nullable=True),
        # Read status
        sa.Column("last_read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "unread_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        # Notifications
        sa.Column(
            "is_muted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Role in conversation
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Create messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # Content
        sa.Column("content", sa.Text(), nullable=False),
        # Reply threading
        sa.Column(
            "reply_to_id",
            sa.Integer(),
            sa.ForeignKey("messages.id"),
            nullable=True,
        ),
        # Attachments (document IDs)
        sa.Column(
            "attachment_ids",
            ARRAY(sa.Integer()),
            nullable=True,
        ),
        # Status
        sa.Column(
            "is_edited",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        # System message (for join/leave notifications)
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Timestamp
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create message_read_receipts table
    op.create_table(
        "message_read_receipts",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "read_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for conversations
    op.create_index("ix_conversations_org_id", "conversations", ["org_id"])
    op.create_index("ix_conversations_created_by", "conversations", ["created_by"])
    op.create_index(
        "ix_conversations_entity",
        "conversations",
        ["entity_type", "entity_id"],
    )
    op.create_index("ix_conversations_last_message", "conversations", ["last_message_at"])

    # Create indexes for conversation_participants
    op.create_index(
        "ix_conv_participants_conversation_id",
        "conversation_participants",
        ["conversation_id"],
    )
    op.create_index(
        "ix_conv_participants_user_id",
        "conversation_participants",
        ["user_id"],
    )
    op.create_index(
        "ix_conv_participants_unique",
        "conversation_participants",
        ["conversation_id", "user_id"],
        unique=True,
    )

    # Create indexes for messages
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index("ix_messages_reply_to_id", "messages", ["reply_to_id"])

    # Create indexes for message_read_receipts
    op.create_index(
        "ix_msg_read_receipts_message_id",
        "message_read_receipts",
        ["message_id"],
    )
    op.create_index(
        "ix_msg_read_receipts_user_id",
        "message_read_receipts",
        ["user_id"],
    )
    op.create_index(
        "ix_msg_read_receipts_unique",
        "message_read_receipts",
        ["message_id", "user_id"],
        unique=True,
    )


def downgrade() -> None:
    """
    Drop messaging tables.

    WHAT: Removes messaging infrastructure.

    WHY: Allows rollback if needed.
    """

    # Drop indexes for message_read_receipts
    op.drop_index("ix_msg_read_receipts_unique", table_name="message_read_receipts")
    op.drop_index("ix_msg_read_receipts_user_id", table_name="message_read_receipts")
    op.drop_index("ix_msg_read_receipts_message_id", table_name="message_read_receipts")

    # Drop indexes for messages
    op.drop_index("ix_messages_reply_to_id", table_name="messages")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")

    # Drop indexes for conversation_participants
    op.drop_index("ix_conv_participants_unique", table_name="conversation_participants")
    op.drop_index("ix_conv_participants_user_id", table_name="conversation_participants")
    op.drop_index("ix_conv_participants_conversation_id", table_name="conversation_participants")

    # Drop indexes for conversations
    op.drop_index("ix_conversations_last_message", table_name="conversations")
    op.drop_index("ix_conversations_entity", table_name="conversations")
    op.drop_index("ix_conversations_created_by", table_name="conversations")
    op.drop_index("ix_conversations_org_id", table_name="conversations")

    # Drop tables (order matters due to foreign keys)
    op.drop_table("message_read_receipts")
    op.drop_table("messages")
    op.drop_table("conversation_participants")
    op.drop_table("conversations")
