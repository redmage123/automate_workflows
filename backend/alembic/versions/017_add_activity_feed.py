"""
Add activity feed tables (activity_events, activity_subscriptions).

WHAT: Creates tables for activity feed functionality.

WHY: Activity feeds enable:
- Real-time visibility into project/organization activity
- Better team collaboration and awareness
- Audit trail for non-admin users
- Context for decisions and changes

Revision ID: 017
Revises: 016
Create Date: 2024-01-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create activity feed tables.

    WHAT: Creates activity_events and activity_subscriptions tables.

    WHY: Enables activity tracking and subscriptions.

    HOW: Creates tables with proper indexes and foreign keys.
    """

    # Create activity_events table
    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        # Actor
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # Event type
        sa.Column("event_type", sa.String(50), nullable=False),
        # Target entity
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=True),
        # Parent entity (for hierarchical contexts)
        sa.Column("parent_entity_type", sa.String(50), nullable=True),
        sa.Column("parent_entity_id", sa.Integer(), nullable=True),
        # Description
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("description_html", sa.Text(), nullable=True),
        # Metadata
        sa.Column("metadata", JSONB, nullable=True),
        # Visibility
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        # Timestamp
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create activity_subscriptions table
    op.create_table(
        "activity_subscriptions",
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
        # Subscribed entity
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        # Notification preferences
        sa.Column(
            "notify_in_app",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "notify_email",
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

    # Create indexes for activity_events
    op.create_index("ix_activity_events_org_id", "activity_events", ["org_id"])
    op.create_index("ix_activity_events_actor_id", "activity_events", ["actor_id"])
    op.create_index(
        "ix_activity_events_entity",
        "activity_events",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_activity_events_parent_entity",
        "activity_events",
        ["parent_entity_type", "parent_entity_id"],
    )
    op.create_index("ix_activity_events_event_type", "activity_events", ["event_type"])
    op.create_index("ix_activity_events_created_at", "activity_events", ["created_at"])
    op.create_index(
        "ix_activity_events_org_created",
        "activity_events",
        ["org_id", "created_at"],
    )

    # Create indexes for activity_subscriptions
    op.create_index(
        "ix_activity_subs_user_id",
        "activity_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "ix_activity_subs_entity",
        "activity_subscriptions",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_activity_subs_unique",
        "activity_subscriptions",
        ["user_id", "entity_type", "entity_id"],
        unique=True,
    )


def downgrade() -> None:
    """
    Drop activity feed tables.

    WHAT: Removes activity feed infrastructure.

    WHY: Allows rollback if needed.
    """

    # Drop indexes for activity_subscriptions
    op.drop_index("ix_activity_subs_unique", table_name="activity_subscriptions")
    op.drop_index("ix_activity_subs_entity", table_name="activity_subscriptions")
    op.drop_index("ix_activity_subs_user_id", table_name="activity_subscriptions")

    # Drop indexes for activity_events
    op.drop_index("ix_activity_events_org_created", table_name="activity_events")
    op.drop_index("ix_activity_events_created_at", table_name="activity_events")
    op.drop_index("ix_activity_events_event_type", table_name="activity_events")
    op.drop_index("ix_activity_events_parent_entity", table_name="activity_events")
    op.drop_index("ix_activity_events_entity", table_name="activity_events")
    op.drop_index("ix_activity_events_actor_id", table_name="activity_events")
    op.drop_index("ix_activity_events_org_id", table_name="activity_events")

    # Drop tables
    op.drop_table("activity_subscriptions")
    op.drop_table("activity_events")
