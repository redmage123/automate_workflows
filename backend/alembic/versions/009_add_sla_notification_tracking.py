"""Add SLA notification tracking fields to tickets.

Revision ID: 009
Revises: 008
Create Date: 2025-12-11

WHAT: Adds SLA notification tracking fields to the tickets table.

WHY: Prevents duplicate SLA breach/warning notifications by tracking
when notifications were sent. The background job checks these fields
before sending notifications.

HOW: Adds four nullable datetime columns for tracking sent timestamps.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add SLA notification tracking columns.

    WHAT: Four new columns to track when notifications were sent.

    WHY: Enables background job to check if notification was already
    sent before sending again (prevents spam).
    """
    op.add_column(
        "tickets",
        sa.Column(
            "sla_response_warning_sent_at",
            sa.DateTime(),
            nullable=True,
            comment="When response SLA warning (75% elapsed) notification was sent",
        ),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "sla_response_breach_sent_at",
            sa.DateTime(),
            nullable=True,
            comment="When response SLA breach notification was sent",
        ),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "sla_resolution_warning_sent_at",
            sa.DateTime(),
            nullable=True,
            comment="When resolution SLA warning (75% elapsed) notification was sent",
        ),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "sla_resolution_breach_sent_at",
            sa.DateTime(),
            nullable=True,
            comment="When resolution SLA breach notification was sent",
        ),
    )


def downgrade() -> None:
    """Remove SLA notification tracking columns."""
    op.drop_column("tickets", "sla_resolution_breach_sent_at")
    op.drop_column("tickets", "sla_resolution_warning_sent_at")
    op.drop_column("tickets", "sla_response_breach_sent_at")
    op.drop_column("tickets", "sla_response_warning_sent_at")
