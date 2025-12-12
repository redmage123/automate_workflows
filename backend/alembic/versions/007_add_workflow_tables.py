"""Add workflow automation tables.

Revision ID: 007
Revises: 006
Create Date: 2025-12-11

WHAT: Creates tables for n8n integration and workflow management.

WHY: Sprint 5 implements workflow automation with:
- N8n environment configuration (per-org)
- Workflow templates (reusable blueprints)
- Workflow instances (project-linked automations)
- Execution logs (audit trail)

HOW: Creates 4 new tables with proper relationships and indexes.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create workflow automation tables."""

    # Create workflow status enum using raw SQL to avoid SQLAlchemy auto-creation
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workflowstatus') THEN
                CREATE TYPE workflowstatus AS ENUM ('draft', 'active', 'paused', 'error', 'deleted');
            END IF;
        END$$;
    """)

    # Create execution status enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'executionstatus') THEN
                CREATE TYPE executionstatus AS ENUM ('running', 'success', 'failed', 'cancelled');
            END IF;
        END$$;
    """)

    # N8n environments table
    op.create_table(
        "n8n_environments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("webhook_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("org_id", "name", name="uq_n8n_env_org_name"),
    )
    op.create_index("ix_n8n_environments_org_id", "n8n_environments", ["org_id"])

    # Workflow templates table
    op.create_table(
        "workflow_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("n8n_template_id", sa.String(100), nullable=True),
        sa.Column("default_parameters", sa.JSON(), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_by_org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_workflow_templates_category", "workflow_templates", ["category"])
    op.create_index("ix_workflow_templates_is_public", "workflow_templates", ["is_public"])

    # Workflow instances table
    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("workflow_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "n8n_environment_id",
            sa.Integer(),
            sa.ForeignKey("n8n_environments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("n8n_workflow_id", sa.String(100), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), server_default="draft", nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("last_execution_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    # Convert workflow_instances.status to enum
    op.execute("ALTER TABLE workflow_instances ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE workflow_instances ALTER COLUMN status TYPE workflowstatus USING status::workflowstatus")
    op.execute("ALTER TABLE workflow_instances ALTER COLUMN status SET DEFAULT 'draft'::workflowstatus")

    op.create_index("ix_workflow_instances_org_id", "workflow_instances", ["org_id"])
    op.create_index("ix_workflow_instances_project_id", "workflow_instances", ["project_id"])
    op.create_index("ix_workflow_instances_status", "workflow_instances", ["status"])

    # Execution logs table
    op.create_table(
        "execution_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workflow_instance_id",
            sa.Integer(),
            sa.ForeignKey("workflow_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("n8n_execution_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), server_default="running", nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    # Convert execution_logs.status to enum
    op.execute("ALTER TABLE execution_logs ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE execution_logs ALTER COLUMN status TYPE executionstatus USING status::executionstatus")
    op.execute("ALTER TABLE execution_logs ALTER COLUMN status SET DEFAULT 'running'::executionstatus")

    op.create_index("ix_execution_logs_instance_id", "execution_logs", ["workflow_instance_id"])
    op.create_index("ix_execution_logs_status", "execution_logs", ["status"])
    op.create_index("ix_execution_logs_started_at", "execution_logs", ["started_at"])


def downgrade() -> None:
    """Drop workflow automation tables."""

    # Drop tables in reverse order (due to foreign keys)
    op.drop_table("execution_logs")
    op.drop_table("workflow_instances")
    op.drop_table("workflow_templates")
    op.drop_table("n8n_environments")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS executionstatus")
    op.execute("DROP TYPE IF EXISTS workflowstatus")
