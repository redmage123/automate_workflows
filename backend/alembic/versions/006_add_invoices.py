"""Add invoices table and stripe_customer_id to organizations

Revision ID: 006
Revises: 005
Create Date: 2025-12-11

WHAT: Creates invoices table for billing and adds Stripe integration field.

WHY: Invoices enable:
1. Billing for approved proposals
2. Payment tracking through Stripe
3. Financial record keeping
4. PDF generation for clients

HOW: Creates invoices table with:
- Invoice number and status tracking
- Amount fields (copied from proposal for immutability)
- Stripe integration fields (payment_intent_id, checkout_session_id)
- Date tracking (issue, due, paid, sent)
- Foreign keys to proposals and organizations
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create invoices table and add stripe_customer_id to organizations.

    WHY: Enable billing and Stripe payment integration.
    """
    # Add stripe_customer_id to organizations for Stripe integration
    op.add_column(
        'organizations',
        sa.Column(
            'stripe_customer_id',
            sa.String(255),
            nullable=True,
            comment='Stripe customer ID for payment processing'
        )
    )
    op.create_index(
        'ix_organizations_stripe_customer_id',
        'organizations',
        ['stripe_customer_id']
    )

    # Create enum type for invoice status
    op.execute(
        "CREATE TYPE invoicestatus AS ENUM ("
        "'draft', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled', 'refunded'"
        ")"
    )

    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'invoice_number',
            sa.String(length=50),
            nullable=False,
            comment='Unique invoice number (e.g., INV-2024-0001)'
        ),
        sa.Column(
            'status',
            sa.Enum(
                'draft', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled', 'refunded',
                name='invoicestatus',
                create_type=False
            ),
            nullable=False,
            server_default='draft',
            comment='Current invoice status'
        ),
        sa.Column(
            'proposal_id',
            sa.Integer(),
            nullable=True,
            comment='Associated proposal (null for manual invoices)'
        ),
        sa.Column(
            'org_id',
            sa.Integer(),
            nullable=False,
            comment='Organization (for queries and access control)'
        ),
        # Amounts (copied from proposal for immutability)
        sa.Column(
            'subtotal',
            sa.Numeric(10, 2),
            nullable=False,
            server_default='0',
            comment='Sum of line items before adjustments'
        ),
        sa.Column(
            'discount_amount',
            sa.Numeric(10, 2),
            nullable=True,
            server_default='0',
            comment='Discount amount applied'
        ),
        sa.Column(
            'tax_amount',
            sa.Numeric(10, 2),
            nullable=True,
            server_default='0',
            comment='Tax amount applied'
        ),
        sa.Column(
            'total',
            sa.Numeric(10, 2),
            nullable=False,
            server_default='0',
            comment='Final total amount due'
        ),
        sa.Column(
            'amount_paid',
            sa.Numeric(10, 2),
            nullable=False,
            server_default='0',
            comment='Amount paid so far'
        ),
        # Stripe integration
        sa.Column(
            'stripe_payment_intent_id',
            sa.String(255),
            nullable=True,
            comment='Stripe PaymentIntent ID for tracking'
        ),
        sa.Column(
            'stripe_checkout_session_id',
            sa.String(255),
            nullable=True,
            comment='Stripe Checkout Session ID'
        ),
        sa.Column(
            'payment_method',
            sa.String(50),
            nullable=True,
            comment='Payment method used (card, bank_transfer, etc.)'
        ),
        # Dates
        sa.Column(
            'issue_date',
            sa.Date(),
            nullable=False,
            server_default=sa.text('CURRENT_DATE'),
            comment='Date invoice was issued'
        ),
        sa.Column(
            'due_date',
            sa.Date(),
            nullable=True,
            comment='Payment due date'
        ),
        sa.Column(
            'paid_at',
            sa.DateTime(),
            nullable=True,
            comment='When full payment was received'
        ),
        sa.Column(
            'sent_at',
            sa.DateTime(),
            nullable=True,
            comment='When invoice was sent to client'
        ),
        # Notes
        sa.Column(
            'notes',
            sa.Text(),
            nullable=True,
            comment='Internal notes about the invoice'
        ),
        # Timestamps
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
            comment='Record creation timestamp'
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
            comment='Last modification timestamp'
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ['proposal_id'],
            ['proposals.id'],
            ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['org_id'],
            ['organizations.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for invoices
    op.create_index('ix_invoices_id', 'invoices', ['id'])
    op.create_index('ix_invoices_invoice_number', 'invoices', ['invoice_number'], unique=True)
    op.create_index('ix_invoices_status', 'invoices', ['status'])
    op.create_index('ix_invoices_proposal_id', 'invoices', ['proposal_id'])
    op.create_index('ix_invoices_org_id', 'invoices', ['org_id'])
    op.create_index('ix_invoices_stripe_payment_intent_id', 'invoices', ['stripe_payment_intent_id'])


def downgrade() -> None:
    """
    Drop invoices table and remove stripe_customer_id from organizations.
    """
    # Drop invoices table
    op.drop_index('ix_invoices_stripe_payment_intent_id', table_name='invoices')
    op.drop_index('ix_invoices_org_id', table_name='invoices')
    op.drop_index('ix_invoices_proposal_id', table_name='invoices')
    op.drop_index('ix_invoices_status', table_name='invoices')
    op.drop_index('ix_invoices_invoice_number', table_name='invoices')
    op.drop_index('ix_invoices_id', table_name='invoices')
    op.drop_table('invoices')
    op.execute("DROP TYPE invoicestatus")

    # Remove stripe_customer_id from organizations
    op.drop_index('ix_organizations_stripe_customer_id', table_name='organizations')
    op.drop_column('organizations', 'stripe_customer_id')
