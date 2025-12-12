"""Add survey tables.

Revision ID: 021
Revises: 020
Create Date: 2024-01-15 15:00:00.000000

WHAT: Creates tables for survey and feedback functionality.

WHY: Surveys enable:
1. Collecting client feedback (NPS, CSAT)
2. Custom satisfaction surveys
3. Post-project reviews
4. Continuous improvement metrics

HOW: Creates four tables:
- surveys: Survey definitions with questions
- survey_responses: Individual responses with answers
- survey_invitations: Invitation tracking
- feedback_scores: Aggregated metrics
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create survey tables.

    WHAT: Adds tables for survey functionality.

    WHY: Provides structured feedback collection with
    various question types and analytics.

    HOW: Creates surveys, responses, invitations, and scores
    with appropriate indexes and foreign keys.
    """
    # Create surveys table
    op.create_table(
        "surveys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("survey_type", sa.String(50), nullable=False, default="custom"),
        sa.Column("questions", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="draft"),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, default=False),
        sa.Column("allow_multiple_responses", sa.Boolean(), nullable=False, default=False),
        sa.Column("show_progress", sa.Boolean(), nullable=False, default=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
    )

    # Create indexes for surveys
    op.create_index("ix_surveys_org_id", "surveys", ["org_id"])
    op.create_index("ix_surveys_status", "surveys", ["status"])
    op.create_index("ix_surveys_survey_type", "surveys", ["survey_type"])
    op.create_index("ix_surveys_project_id", "surveys", ["project_id"])
    op.create_index("ix_surveys_created_by_id", "surveys", ["created_by_id"])

    # Create survey_responses table
    op.create_table(
        "survey_responses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("survey_id", sa.Integer(), nullable=False),
        sa.Column("respondent_id", sa.Integer(), nullable=True),
        sa.Column("answers", JSONB(), nullable=False),
        sa.Column("is_complete", sa.Boolean(), nullable=False, default=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("time_taken_seconds", sa.Integer(), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["survey_id"],
            ["surveys.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["respondent_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )

    # Create indexes for survey_responses
    op.create_index("ix_survey_responses_org_id", "survey_responses", ["org_id"])
    op.create_index("ix_survey_responses_survey_id", "survey_responses", ["survey_id"])
    op.create_index(
        "ix_survey_responses_respondent_id", "survey_responses", ["respondent_id"]
    )
    op.create_index(
        "ix_survey_responses_is_complete", "survey_responses", ["is_complete"]
    )
    op.create_index(
        "ix_survey_responses_survey_respondent",
        "survey_responses",
        ["survey_id", "respondent_id"],
    )

    # Create survey_invitations table
    op.create_table(
        "survey_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("survey_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("response_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["survey_id"],
            ["surveys.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["response_id"],
            ["survey_responses.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("token"),
    )

    # Create indexes for survey_invitations
    op.create_index(
        "ix_survey_invitations_org_id", "survey_invitations", ["org_id"]
    )
    op.create_index(
        "ix_survey_invitations_survey_id", "survey_invitations", ["survey_id"]
    )
    op.create_index(
        "ix_survey_invitations_user_id", "survey_invitations", ["user_id"]
    )
    op.create_index(
        "ix_survey_invitations_token", "survey_invitations", ["token"]
    )

    # Create feedback_scores table
    op.create_table(
        "feedback_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("score_type", sa.String(20), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("response_count", sa.Integer(), nullable=False),
        sa.Column("promoters", sa.Integer(), nullable=True),
        sa.Column("passives", sa.Integer(), nullable=True),
        sa.Column("detractors", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="SET NULL",
        ),
    )

    # Create indexes for feedback_scores
    op.create_index("ix_feedback_scores_org_id", "feedback_scores", ["org_id"])
    op.create_index("ix_feedback_scores_score_type", "feedback_scores", ["score_type"])
    op.create_index(
        "ix_feedback_scores_period",
        "feedback_scores",
        ["period_start", "period_end"],
    )
    op.create_index(
        "ix_feedback_scores_project_id", "feedback_scores", ["project_id"]
    )


def downgrade() -> None:
    """
    Remove survey tables.

    WHAT: Drops all survey-related tables.

    WHY: Allows rolling back the migration if needed.

    HOW: Drops tables in reverse order of creation
    to respect foreign key constraints.
    """
    # Drop feedback_scores table and indexes
    op.drop_index("ix_feedback_scores_project_id", table_name="feedback_scores")
    op.drop_index("ix_feedback_scores_period", table_name="feedback_scores")
    op.drop_index("ix_feedback_scores_score_type", table_name="feedback_scores")
    op.drop_index("ix_feedback_scores_org_id", table_name="feedback_scores")
    op.drop_table("feedback_scores")

    # Drop survey_invitations table and indexes
    op.drop_index("ix_survey_invitations_token", table_name="survey_invitations")
    op.drop_index("ix_survey_invitations_user_id", table_name="survey_invitations")
    op.drop_index("ix_survey_invitations_survey_id", table_name="survey_invitations")
    op.drop_index("ix_survey_invitations_org_id", table_name="survey_invitations")
    op.drop_table("survey_invitations")

    # Drop survey_responses table and indexes
    op.drop_index(
        "ix_survey_responses_survey_respondent", table_name="survey_responses"
    )
    op.drop_index("ix_survey_responses_is_complete", table_name="survey_responses")
    op.drop_index("ix_survey_responses_respondent_id", table_name="survey_responses")
    op.drop_index("ix_survey_responses_survey_id", table_name="survey_responses")
    op.drop_index("ix_survey_responses_org_id", table_name="survey_responses")
    op.drop_table("survey_responses")

    # Drop surveys table and indexes
    op.drop_index("ix_surveys_created_by_id", table_name="surveys")
    op.drop_index("ix_surveys_project_id", table_name="surveys")
    op.drop_index("ix_surveys_survey_type", table_name="surveys")
    op.drop_index("ix_surveys_status", table_name="surveys")
    op.drop_index("ix_surveys_org_id", table_name="surveys")
    op.drop_table("surveys")
