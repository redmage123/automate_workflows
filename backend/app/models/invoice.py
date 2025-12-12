"""
Invoice model for billing and payment tracking.

WHAT: SQLAlchemy model representing an invoice generated from approved proposals.

WHY: Invoices are critical financial documents that:
1. Track amounts owed by clients
2. Record payment status and history
3. Enable Stripe payment integration
4. Generate PDF documents for clients
5. Maintain audit trail for accounting

HOW: Uses SQLAlchemy 2.0 with:
- Proposal relationship (1:1 on approval)
- Organization relationship (direct queries)
- Status enum for payment workflow
- Stripe integration fields
- Amount tracking with proper decimal precision
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Date,
    ForeignKey,
    Numeric,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship, Mapped

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.proposal import Proposal
    from app.models.organization import Organization


class InvoiceStatus(str, Enum):
    """
    Invoice payment workflow status.

    WHAT: Enumeration of possible invoice states.

    WHY: Tracks invoice through business/payment process:
    - DRAFT: Invoice created but not finalized/sent
    - SENT: Invoice sent to client for payment
    - PAID: Full payment received
    - PARTIALLY_PAID: Partial payment received, balance due
    - OVERDUE: Past due date without full payment
    - CANCELLED: Invoice voided/cancelled
    - REFUNDED: Payment refunded to client

    HOW: String enum for database storage and API serialization.
    """

    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Invoice(Base):
    """
    Invoice model for billing and payments.

    WHAT: Represents an invoice for client billing.

    WHY: Formalizes financial transactions:
    - Documents amounts owed from approved proposals
    - Tracks payment status through Stripe integration
    - Enables PDF generation for professional documents
    - Maintains audit trail for accounting/compliance

    HOW: Links to proposal with denormalized amounts and Stripe references.
    Amounts are copied from proposal for immutability (invoice shouldn't change
    if proposal is later edited).

    Attributes:
        id: Primary key
        invoice_number: Unique human-readable identifier
        proposal_id: Associated proposal (optional, manual invoices allowed)
        org_id: Organization for queries and access control

        Amounts (copied from proposal for immutability):
        subtotal: Sum of line items before adjustments
        discount_amount: Applied discount
        tax_amount: Applied tax
        total: Final amount due
        amount_paid: Amount received so far

        Payment tracking:
        stripe_payment_intent_id: Stripe PaymentIntent ID
        stripe_checkout_session_id: Stripe Checkout Session ID
        payment_method: How payment was made (card, bank_transfer, etc.)

        Dates:
        issue_date: When invoice was issued
        due_date: Payment due date
        paid_at: When payment was received
        sent_at: When invoice was sent to client

        Metadata:
        notes: Internal notes
        created_at: Record creation timestamp
        updated_at: Last modification timestamp
    """

    __tablename__ = "invoices"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)

    # Invoice identification
    invoice_number: Mapped[str] = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique invoice number (e.g., INV-2024-0001)",
    )

    # Status tracking
    # WHY: create_type=False because enum types are created in migrations
    # WHY: values_callable ensures the enum value (lowercase) is used, not the name (UPPERCASE)
    status: Mapped[InvoiceStatus] = Column(
        SQLEnum(
            InvoiceStatus,
            name="invoicestatus",
            create_type=False,
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        default=InvoiceStatus.DRAFT,
        index=True,
        comment="Current invoice status",
    )

    # Relationships
    proposal_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("proposals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated proposal (null for manual invoices)",
    )
    org_id: Mapped[int] = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization (for queries and access control)",
    )

    # Amounts (copied from proposal for immutability)
    subtotal: Mapped[Decimal] = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="Sum of line items before adjustments",
    )
    discount_amount: Mapped[Optional[Decimal]] = Column(
        Numeric(10, 2),
        nullable=True,
        default=0,
        comment="Discount amount applied",
    )
    tax_amount: Mapped[Optional[Decimal]] = Column(
        Numeric(10, 2),
        nullable=True,
        default=0,
        comment="Tax amount applied",
    )
    total: Mapped[Decimal] = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="Final total amount due",
    )
    amount_paid: Mapped[Decimal] = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="Amount paid so far",
    )

    # Stripe integration
    stripe_payment_intent_id: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Stripe PaymentIntent ID for tracking",
    )
    stripe_checkout_session_id: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
        comment="Stripe Checkout Session ID",
    )
    payment_method: Mapped[Optional[str]] = Column(
        String(50),
        nullable=True,
        comment="Payment method used (card, bank_transfer, etc.)",
    )

    # Dates
    issue_date: Mapped[date] = Column(
        Date,
        nullable=False,
        default=date.today,
        comment="Date invoice was issued",
    )
    due_date: Mapped[Optional[date]] = Column(
        Date,
        nullable=True,
        comment="Payment due date",
    )
    paid_at: Mapped[Optional[datetime]] = Column(
        DateTime,
        nullable=True,
        comment="When full payment was received",
    )
    sent_at: Mapped[Optional[datetime]] = Column(
        DateTime,
        nullable=True,
        comment="When invoice was sent to client",
    )

    # Notes
    notes: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Internal notes about the invoice",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp",
    )
    updated_at: Mapped[datetime] = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last modification timestamp",
    )

    # Relationships
    proposal: Mapped[Optional["Proposal"]] = relationship(
        "Proposal",
        back_populates="invoice",
    )
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="invoices",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Invoice(id={self.id}, number={self.invoice_number}, status={self.status})>"

    @property
    def is_editable(self) -> bool:
        """
        Check if invoice can be edited.

        WHAT: Determines if invoice modifications are allowed.

        WHY: Only draft invoices should be editable to maintain
        financial record integrity. Once sent, the invoice is
        a legal document that shouldn't change.

        Returns:
            True if invoice is in DRAFT status
        """
        return self.status == InvoiceStatus.DRAFT

    @property
    def is_paid(self) -> bool:
        """
        Check if invoice has been fully paid.

        WHAT: Determines if full payment received.

        WHY: Quick check for payment status in business logic.

        Returns:
            True if invoice status is PAID
        """
        return self.status == InvoiceStatus.PAID

    @property
    def is_overdue(self) -> bool:
        """
        Check if invoice is past due date.

        WHAT: Determines if invoice payment is late.

        WHY: Enables automatic overdue status updates and
        payment reminder functionality.

        Returns:
            True if due_date has passed and invoice isn't paid/cancelled
        """
        if not self.due_date:
            return False
        if self.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED]:
            return False
        return date.today() > self.due_date

    @property
    def balance_due(self) -> Decimal:
        """
        Calculate remaining balance on invoice.

        WHAT: Returns amount still owed.

        WHY: Supports partial payments by tracking outstanding balance.

        Returns:
            Remaining amount due (total - amount_paid)
        """
        return self.total - (self.amount_paid or Decimal(0))

    @property
    def is_partially_paid(self) -> bool:
        """
        Check if invoice has partial payment.

        WHAT: Determines if some but not all payment received.

        WHY: Different business logic for partial vs. full payments.

        Returns:
            True if some payment received but balance remains
        """
        paid = self.amount_paid or Decimal(0)
        return paid > 0 and paid < self.total

    @classmethod
    def generate_invoice_number(cls, org_id: int, sequence: int) -> str:
        """
        Generate a unique invoice number.

        WHAT: Creates human-readable invoice identifier.

        WHY: Professional invoices need readable reference numbers
        for client communication and accounting.

        HOW: Format: INV-YYYY-NNNN where YYYY is year and NNNN
        is zero-padded sequence number.

        Args:
            org_id: Organization ID (for future multi-tenant numbering)
            sequence: Sequential number for this invoice

        Returns:
            Formatted invoice number string
        """
        year = datetime.utcnow().year
        return f"INV-{year}-{sequence:04d}"

    def copy_from_proposal(self, proposal: "Proposal") -> None:
        """
        Copy financial data from associated proposal.

        WHAT: Transfers amounts from proposal to invoice.

        WHY: Invoice amounts should be immutable snapshots of
        proposal values at time of approval. If proposal is
        later revised, invoice remains unchanged.

        HOW: Copies subtotal, discount, tax, and total amounts.

        Args:
            proposal: The proposal to copy amounts from
        """
        self.subtotal = proposal.subtotal
        self.discount_amount = proposal.discount_amount or Decimal(0)
        self.tax_amount = proposal.tax_amount or Decimal(0)
        self.total = proposal.total
