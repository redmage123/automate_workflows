"""Add OAuth accounts table for social authentication.

Revision ID: 010
Revises: 009
Create Date: 2025-12-11

WHAT: Creates oauth_accounts table for storing linked social authentication accounts.

WHY: OAuth accounts allow users to authenticate via external providers (Google, GitHub)
instead of email/password, improving user experience and security.

HOW: Creates table with indexes for efficient lookups by provider + provider_user_id,
and unique constraint to prevent duplicate OAuth accounts.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create oauth_accounts table and related infrastructure.

    WHAT: Table for storing OAuth provider accounts linked to users.

    WHY: Enables social login via Google, GitHub, etc. without requiring passwords.
    """
    # Create oauthprovider enum
    # WHY: Enum ensures only supported providers can be stored
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'oauthprovider') THEN
                CREATE TYPE oauthprovider AS ENUM ('google');
            END IF;
        END$$;
    """)

    # Create oauth_accounts table
    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("picture_url", sa.String(length=2048), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("scopes", sa.String(length=1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Alter provider column to use enum type
    op.execute("ALTER TABLE oauth_accounts ALTER COLUMN provider TYPE oauthprovider USING provider::oauthprovider")

    # Create indexes
    # WHY: Optimize common query patterns
    op.create_index("ix_oauth_accounts_id", "oauth_accounts", ["id"])
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])

    # Create composite index for provider lookup
    # WHY: Most common query is finding OAuth account by provider + provider_user_id
    op.create_index(
        "ix_oauth_provider_lookup",
        "oauth_accounts",
        ["provider", "provider_user_id"],
    )

    # Create unique constraint
    # WHY: Each provider user can only be linked to one platform account
    op.create_unique_constraint(
        "uq_oauth_provider_user",
        "oauth_accounts",
        ["provider", "provider_user_id"],
    )


def downgrade() -> None:
    """Remove oauth_accounts table and related infrastructure."""
    # Drop constraints and indexes
    op.drop_constraint("uq_oauth_provider_user", "oauth_accounts", type_="unique")
    op.drop_index("ix_oauth_provider_lookup", table_name="oauth_accounts")
    op.drop_index("ix_oauth_accounts_user_id", table_name="oauth_accounts")
    op.drop_index("ix_oauth_accounts_id", table_name="oauth_accounts")

    # Drop table
    op.drop_table("oauth_accounts")

    # Drop enum
    op.execute("DROP TYPE IF EXISTS oauthprovider")
