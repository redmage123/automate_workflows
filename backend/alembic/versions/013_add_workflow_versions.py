"""Add workflow versions table.

Revision ID: 013
Revises: 012
Create Date: 2024-12-12

WHAT: Creates the workflow_versions table for version history tracking.

WHY: Enables rollback, audit trail, and understanding of workflow evolution.
Critical for production workflows where changes must be traceable.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create workflow_versions table.

    WHAT: Creates table for storing workflow version history.

    WHY: Each version captures:
    - Complete workflow JSON definition
    - Change description
    - Creator and timestamp
    - Current version flag
    """
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_instance_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "workflow_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("change_description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, default=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workflow_instance_id"],
            ["workflow_instances.id"],
            name="fk_workflow_versions_instance_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_workflow_versions_created_by",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_instance_id",
            "version_number",
            name="uq_workflow_version",
        ),
    )

    # Create indexes for common queries
    op.create_index(
        "ix_workflow_versions_instance_id",
        "workflow_versions",
        ["workflow_instance_id"],
    )
    op.create_index(
        "ix_workflow_versions_is_current",
        "workflow_versions",
        ["is_current"],
    )


def downgrade() -> None:
    """Drop workflow_versions table."""
    op.drop_index("ix_workflow_versions_is_current", table_name="workflow_versions")
    op.drop_index("ix_workflow_versions_instance_id", table_name="workflow_versions")
    op.drop_table("workflow_versions")
