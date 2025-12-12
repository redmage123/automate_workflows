"""Add subscriptions table for SaaS billing.

Revision ID: 011
Revises: 010
Create Date: 2025-12-11

WHAT: Creates subscriptions table for managing SaaS subscription plans.

WHY: Subscriptions enable recurring revenue and tiered feature access:
1. Organizations subscribe to plans (Free, Pro, Enterprise)
2. Plans define limits (projects, workflows, users)
3. Stripe handles billing, we track subscription state
4. Webhook events keep subscription status in sync

HOW: Creates table with foreign key to organizations, Stripe IDs for integration,
plan/status enums, and billing period tracking. Each organization has exactly
one subscription (1:1 relationship enforced by unique constraint).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create subscriptions table and related infrastructure.

    WHAT: Table for tracking organization billing and plan limits.

    WHY: Enables SaaS subscription model with tiered plans and Stripe integration.
    """
    # Create subscriptionplan enum
    # WHY: Enum ensures only valid plans can be stored
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscriptionplan') THEN
                CREATE TYPE subscriptionplan AS ENUM ('free', 'pro', 'enterprise');
            END IF;
        END$$;
    """)

    # Create subscriptionstatus enum
    # WHY: Mirrors Stripe subscription statuses for accurate state tracking
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscriptionstatus') THEN
                CREATE TYPE subscriptionstatus AS ENUM (
                    'trialing', 'active', 'past_due', 'canceled',
                    'unpaid', 'incomplete', 'incomplete_expired', 'paused'
                );
            END IF;
        END$$;
    """)

    # Create subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # Stripe identifiers
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        # Plan and status (will be converted to enum below)
        sa.Column("plan", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        # Billing period
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        # Trial tracking
        sa.Column("trial_start", sa.DateTime(), nullable=True),
        sa.Column("trial_end", sa.DateTime(), nullable=True),
        # Cancellation
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        # Timestamps
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

    # Convert plan column to use enum type
    # WHY: Must drop default, convert type, then re-add default with enum value
    op.execute("ALTER TABLE subscriptions ALTER COLUMN plan DROP DEFAULT")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN plan TYPE subscriptionplan USING plan::subscriptionplan")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN plan SET DEFAULT 'free'::subscriptionplan")

    # Convert status column to use enum type
    op.execute("ALTER TABLE subscriptions ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN status TYPE subscriptionstatus USING status::subscriptionstatus")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN status SET DEFAULT 'active'::subscriptionstatus")

    # Create indexes
    # WHY: Optimize common query patterns
    op.create_index("ix_subscriptions_id", "subscriptions", ["id"])
    op.create_index("ix_subscriptions_org_id", "subscriptions", ["org_id"])
    op.create_index("ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"])

    # Create unique constraint for org_id
    # WHY: Each organization has exactly one subscription
    op.create_unique_constraint(
        "uq_subscription_org",
        "subscriptions",
        ["org_id"],
    )


def downgrade() -> None:
    """Remove subscriptions table and related infrastructure."""
    # Drop constraints and indexes
    op.drop_constraint("uq_subscription_org", "subscriptions", type_="unique")
    op.drop_index("ix_subscriptions_stripe_subscription_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_org_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_id", table_name="subscriptions")

    # Drop table
    op.drop_table("subscriptions")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS subscriptionstatus")
    op.execute("DROP TYPE IF EXISTS subscriptionplan")
