"""Add verification_tokens table

Revision ID: 004
Revises: 003
Create Date: 2025-12-10

WHAT: Creates the verification_tokens table for email verification and password reset.

WHY: Secure token-based verification requires:
1. Time-limited tokens to prevent stale token attacks
2. One-time use to prevent token reuse attacks
3. Cryptographically secure token generation
4. Audit trail for security analysis

HOW: Tokens are generated with secrets.token_urlsafe() and stored with:
- Expiration time (24h for email verification, 1h for password reset)
- Usage tracking (used_at timestamp marks token as consumed)
- Token type to distinguish between verification and reset
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create verification_tokens table with indexes for token lookup.

    WHY: Verification tokens are critical for:
    1. Email verification (SEC-007) - Prevent fake account creation
    2. Password reset (AUTH-009) - Secure account recovery
    3. Email change confirmation - Verify ownership of new email

    Indexes are optimized for common query patterns:
    - By token (primary lookup method)
    - By user_id + token_type + expires_at (find active tokens)
    """
    # Create enum for token types
    # WHY: Using PostgreSQL enum ensures only valid token types can be stored
    token_type_enum = sa.Enum(
        'email_verification',
        'password_reset',
        'email_change',
        name='tokentype'
    )

    # Create verification_tokens table
    op.create_table(
        'verification_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        # Token data - cryptographically secure token string
        # WHY: 32-byte random data provides 256 bits of entropy,
        # making brute-force attacks computationally infeasible
        sa.Column('token', sa.String(length=255), nullable=False),
        # Token type - distinguishes between verification types
        sa.Column('token_type', token_type_enum, nullable=False),
        # Optional 6-digit code for mobile/UX convenience
        # WHY: While less secure than full token, 6-digit codes are:
        # - Easier to enter on mobile devices
        # - Usable for in-app verification
        # - Protected by rate limiting and short expiration
        sa.Column('code', sa.String(length=6), nullable=True),
        # User association
        sa.Column('user_id', sa.Integer(), nullable=False),
        # For email change tokens, store the new email
        sa.Column('new_email', sa.String(length=255), nullable=True),
        # Expiration and usage tracking
        # WHY: Time-limited tokens prevent stale tokens being used
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        # WHY: used_at marks token as consumed (single-use)
        sa.Column('used_at', sa.DateTime(), nullable=True),
        # IP address tracking for security audit
        sa.Column('created_ip', sa.String(length=45), nullable=True),
        sa.Column('used_ip', sa.String(length=45), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        # Primary key
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient lookups
    # WHY: Token lookups must be fast for user experience

    # Unique index on token for fast lookups from email links
    op.create_index('ix_verification_tokens_token', 'verification_tokens', ['token'], unique=True)

    # Index on user_id for finding user's tokens
    op.create_index('ix_verification_tokens_user_id', 'verification_tokens', ['user_id'])

    # Composite index for finding unexpired tokens by user and type
    # WHY: Common pattern - check if user has valid token before creating new one
    op.create_index(
        'ix_verification_tokens_user_type_expires',
        'verification_tokens',
        ['user_id', 'token_type', 'expires_at']
    )

    # Add foreign key constraint with CASCADE delete
    # WHY: CASCADE because verification tokens are meaningless without the user
    op.create_foreign_key(
        'fk_verification_tokens_user_id_users',
        'verification_tokens',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """
    Drop verification_tokens table and related indexes.

    WHY: Downgrade allows rollback if issues are discovered after deployment.
    Note: This will invalidate all pending verification tokens.
    """
    # Drop foreign key first
    op.drop_constraint('fk_verification_tokens_user_id_users', 'verification_tokens', type_='foreignkey')

    # Drop indexes
    op.drop_index('ix_verification_tokens_user_type_expires', table_name='verification_tokens')
    op.drop_index('ix_verification_tokens_user_id', table_name='verification_tokens')
    op.drop_index('ix_verification_tokens_token', table_name='verification_tokens')

    # Drop table
    op.drop_table('verification_tokens')

    # Drop enum type
    op.execute('DROP TYPE tokentype')
