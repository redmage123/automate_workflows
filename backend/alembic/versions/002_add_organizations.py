"""Add organizations table

Revision ID: 002
Revises: 001
Create Date: 2025-10-12

WHY: Organizations are the foundation of multi-tenancy. This migration creates
the organizations table and adds the foreign key constraint from users to organizations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create organizations table and add foreign key constraint to users.

    WHY: Multi-tenancy requires organizations to exist before users can reference them.
    This migration:
    1. Creates organizations table
    2. Adds foreign key constraint from users.org_id to organizations.id
    3. Creates indexes for query performance
    """
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    # WHY: name index for searching/listing organizations
    op.create_index('ix_organizations_id', 'organizations', ['id'])
    op.create_index('ix_organizations_name', 'organizations', ['name'])

    # Add foreign key constraint from users to organizations
    # WHY: Enforces referential integrity at database level, ensuring
    # users can't reference non-existent organizations
    op.create_foreign_key(
        'fk_users_org_id_organizations',
        'users',
        'organizations',
        ['org_id'],
        ['id'],
        ondelete='RESTRICT'  # WHY: Prevent deleting org if users exist
    )


def downgrade() -> None:
    """
    Drop organizations table and foreign key constraint.

    WHY: Downgrade allows rollback if issues are discovered after deployment.
    """
    # Drop foreign key first
    op.drop_constraint('fk_users_org_id_organizations', 'users', type_='foreignkey')

    # Drop indexes
    op.drop_index('ix_organizations_name', table_name='organizations')
    op.drop_index('ix_organizations_id', table_name='organizations')

    # Drop table
    op.drop_table('organizations')
