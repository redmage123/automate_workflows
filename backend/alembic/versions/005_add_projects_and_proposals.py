"""Add projects and proposals tables

Revision ID: 005
Revises: 004
Create Date: 2025-12-10

WHY: Projects are the core business entity connecting clients to work.
Proposals formalize pricing and scope agreements.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create projects and proposals tables.

    WHY: Enable project tracking and proposal management for automation services.
    """
    # Create enum types for projects
    # WHY: Using DO block with IF NOT EXISTS to prevent duplicate type errors
    # when model metadata is loaded (which might pre-register enum types)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'projectstatus') THEN
                CREATE TYPE projectstatus AS ENUM ('draft', 'proposal_sent', 'approved', 'in_progress', 'on_hold', 'completed', 'cancelled');
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'projectpriority') THEN
                CREATE TYPE projectpriority AS ENUM ('low', 'medium', 'high', 'urgent');
            END IF;
        END$$;
    """)

    # Create projects table
    # WHY: Using String columns then ALTER to enum type to avoid SQLAlchemy
    # auto-creating enum types even when create_type=False is specified
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('priority', sa.String(50), nullable=False, server_default='medium'),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('estimated_hours', sa.Integer(), nullable=True),
        sa.Column('actual_hours', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Convert String columns to enum types
    op.execute("ALTER TABLE projects ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE projects ALTER COLUMN status TYPE projectstatus USING status::projectstatus")
    op.execute("ALTER TABLE projects ALTER COLUMN status SET DEFAULT 'draft'::projectstatus")
    op.execute("ALTER TABLE projects ALTER COLUMN priority DROP DEFAULT")
    op.execute("ALTER TABLE projects ALTER COLUMN priority TYPE projectpriority USING priority::projectpriority")
    op.execute("ALTER TABLE projects ALTER COLUMN priority SET DEFAULT 'medium'::projectpriority")

    # Create indexes for projects
    op.create_index('ix_projects_id', 'projects', ['id'])
    op.create_index('ix_projects_org_id', 'projects', ['org_id'])
    op.create_index('ix_projects_status', 'projects', ['status'])

    # Create enum type for proposals
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'proposalstatus') THEN
                CREATE TYPE proposalstatus AS ENUM ('draft', 'sent', 'viewed', 'approved', 'rejected', 'expired', 'revised');
            END IF;
        END$$;
    """)

    # Create proposals table
    op.create_table(
        'proposals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('previous_version_id', sa.Integer(), nullable=True),
        sa.Column('line_items', JSONB(), nullable=True),
        sa.Column('subtotal', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('discount_percent', sa.Numeric(5, 2), nullable=True, server_default='0'),
        sa.Column('discount_amount', sa.Numeric(10, 2), nullable=True, server_default='0'),
        sa.Column('tax_percent', sa.Numeric(5, 2), nullable=True, server_default='0'),
        sa.Column('tax_amount', sa.Numeric(10, 2), nullable=True, server_default='0'),
        sa.Column('total', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('viewed_at', sa.DateTime(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejected_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('client_notes', sa.Text(), nullable=True),
        sa.Column('terms', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['previous_version_id'], ['proposals.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Convert String columns to enum types for proposals
    op.execute("ALTER TABLE proposals ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE proposals ALTER COLUMN status TYPE proposalstatus USING status::proposalstatus")
    op.execute("ALTER TABLE proposals ALTER COLUMN status SET DEFAULT 'draft'::proposalstatus")

    # Create indexes for proposals
    op.create_index('ix_proposals_id', 'proposals', ['id'])
    op.create_index('ix_proposals_project_id', 'proposals', ['project_id'])
    op.create_index('ix_proposals_org_id', 'proposals', ['org_id'])
    op.create_index('ix_proposals_status', 'proposals', ['status'])


def downgrade() -> None:
    """
    Drop projects and proposals tables.
    """
    # Drop proposals table first (has FK to projects)
    op.drop_index('ix_proposals_status', table_name='proposals')
    op.drop_index('ix_proposals_org_id', table_name='proposals')
    op.drop_index('ix_proposals_project_id', table_name='proposals')
    op.drop_index('ix_proposals_id', table_name='proposals')
    op.drop_table('proposals')
    op.execute("DROP TYPE proposalstatus")

    # Drop projects table
    op.drop_index('ix_projects_status', table_name='projects')
    op.drop_index('ix_projects_org_id', table_name='projects')
    op.drop_index('ix_projects_id', table_name='projects')
    op.drop_table('projects')
    op.execute("DROP TYPE projectpriority")
    op.execute("DROP TYPE projectstatus")
