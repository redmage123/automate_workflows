"""Initial schema - users table

Revision ID: 001
Revises:
Create Date: 2025-10-12

WHY: This is the initial database migration creating the foundational users table.
The users table is required for authentication and is a dependency for most other tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create users table with all required fields for authentication and RBAC.

    WHY: Users are the foundation of the authentication system. This table includes:
    - Basic user info (name, email)
    - Authentication (hashed_password, nullable for OAuth users)
    - Authorization (role enum for RBAC)
    - Multi-tenancy (org_id foreign key)
    - Soft deletion (is_active flag)
    - Audit timestamps (created_at, updated_at)
    """
    # Create enum type for user roles
    # WHY: PostgreSQL ENUMs provide type safety at the database level
    op.execute("CREATE TYPE userrole AS ENUM ('ADMIN', 'CLIENT')")

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=True),
        sa.Column('role', sa.Enum('ADMIN', 'CLIENT', name='userrole', create_type=False), nullable=False, server_default='CLIENT'),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    # WHY: These indexes optimize common query patterns
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_org_id', 'users', ['org_id'])

    # Note: Foreign key to organizations table will be added in next migration
    # WHY: Can't add FK constraint until organizations table exists


def downgrade() -> None:
    """
    Drop users table and enum type.

    WHY: Downgrade allows rollback if issues are discovered after deployment.
    """
    op.drop_index('ix_users_org_id', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_id', table_name='users')
    op.drop_table('users')
    op.execute("DROP TYPE userrole")
