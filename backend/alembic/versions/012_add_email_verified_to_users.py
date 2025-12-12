"""Add email_verified column to users table.

Revision ID: 012
Revises: 011
Create Date: 2025-12-11

WHAT: Adds email_verified column to users table.

WHY: Email verification is required for OWASP A07 (Identification and Authentication Failures)
to prevent fake accounts and ensure email ownership before sensitive operations.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add email_verified column to users table."""
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether the user has verified their email address"
        )
    )


def downgrade() -> None:
    """Remove email_verified column from users table."""
    op.drop_column("users", "email_verified")
