"""
Proposal model for project pricing and scope documentation.

WHAT: SQLAlchemy model representing a proposal/quote for client projects.

WHY: Proposals are critical business documents that:
1. Define project scope and deliverables
2. Specify pricing and payment terms
3. Track approval status
4. Convert to invoices upon approval

HOW: Uses SQLAlchemy 2.0 with:
- Project relationship (what's being proposed)
- Status enum for approval workflow
- JSONB for flexible line items
- Version tracking for revisions
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Numeric,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.organization import Organization
    from app.models.invoice import Invoice


class ProposalStatus(str, Enum):
    """
    Proposal approval workflow status.

    WHY: Tracks proposal through business process:
    - DRAFT: Being created/edited, not visible to client
    - SENT: Sent to client for review
    - VIEWED: Client has opened/viewed the proposal
    - APPROVED: Client accepted the proposal
    - REJECTED: Client declined the proposal
    - EXPIRED: Proposal validity period has passed
    - REVISED: New version created, this one superseded
    """

    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVISED = "revised"


class Proposal(Base):
    """
    Project proposal/quote model.

    WHAT: Represents a pricing proposal for a project.

    WHY: Formalizes business agreement:
    - Documents scope of work
    - Specifies pricing breakdown
    - Tracks approval status
    - Enables invoice generation

    HOW: Links to project with line items stored as JSONB.

    Attributes:
        id: Primary key
        title: Proposal title
        description: Scope description
        status: Current proposal status
        project_id: Associated project
        org_id: Organization for direct queries
        version: Revision number
        line_items: JSONB array of line items
        subtotal: Sum of line items
        discount_percent: Optional discount
        tax_percent: Tax rate
        total: Final amount
        valid_until: Proposal expiration date
        sent_at: When proposal was sent
        viewed_at: When client first viewed
        approved_at: When client approved
        rejected_at: When client rejected
        rejection_reason: Why rejected
        notes: Internal notes
        client_notes: Notes visible to client
        created_at: Record creation timestamp
        updated_at: Last modification timestamp
    """

    __tablename__ = "proposals"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)

    # Proposal details
    title: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Proposal title",
    )
    description: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Scope of work description",
    )

    # Status tracking
    # WHY: create_type=False because enum types are created in migrations
    # WHY: values_callable ensures the enum value (lowercase) is used, not the name (UPPERCASE)
    status: Mapped[ProposalStatus] = Column(
        SQLEnum(
            ProposalStatus,
            name="proposalstatus",
            create_type=False,
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        default=ProposalStatus.DRAFT,
        comment="Current proposal status",
    )

    # Relationships (denormalized org_id for efficient queries)
    project_id: Mapped[int] = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated project",
    )
    org_id: Mapped[int] = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization (denormalized for queries)",
    )

    # Versioning
    version: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Proposal revision number",
    )
    previous_version_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("proposals.id", ondelete="SET NULL"),
        nullable=True,
        comment="Previous version if revised",
    )

    # Line items (JSONB for flexibility)
    # Format: [{"description": str, "quantity": float, "unit_price": float, "amount": float}]
    line_items: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="Line items as JSONB array",
    )

    # Pricing
    subtotal: Mapped[Decimal] = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="Sum of line item amounts",
    )
    discount_percent: Mapped[Optional[Decimal]] = Column(
        Numeric(5, 2),
        nullable=True,
        default=0,
        comment="Discount percentage",
    )
    discount_amount: Mapped[Optional[Decimal]] = Column(
        Numeric(10, 2),
        nullable=True,
        default=0,
        comment="Calculated discount amount",
    )
    tax_percent: Mapped[Optional[Decimal]] = Column(
        Numeric(5, 2),
        nullable=True,
        default=0,
        comment="Tax percentage",
    )
    tax_amount: Mapped[Optional[Decimal]] = Column(
        Numeric(10, 2),
        nullable=True,
        default=0,
        comment="Calculated tax amount",
    )
    total: Mapped[Decimal] = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="Final total amount",
    )

    # Validity
    valid_until: Mapped[Optional[datetime]] = Column(
        DateTime,
        nullable=True,
        comment="Proposal expiration date",
    )

    # Status timestamps
    sent_at: Mapped[Optional[datetime]] = Column(
        DateTime,
        nullable=True,
        comment="When proposal was sent to client",
    )
    viewed_at: Mapped[Optional[datetime]] = Column(
        DateTime,
        nullable=True,
        comment="When client first viewed proposal",
    )
    approved_at: Mapped[Optional[datetime]] = Column(
        DateTime,
        nullable=True,
        comment="When client approved proposal",
    )
    rejected_at: Mapped[Optional[datetime]] = Column(
        DateTime,
        nullable=True,
        comment="When client rejected proposal",
    )
    rejection_reason: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Reason for rejection",
    )

    # Notes
    notes: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Internal notes (not visible to client)",
    )
    client_notes: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Notes visible to client",
    )

    # Terms and conditions
    terms: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Terms and conditions text",
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
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="proposals",
    )
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="proposals",
    )
    previous_version: Mapped[Optional["Proposal"]] = relationship(
        "Proposal",
        remote_side=[id],
        foreign_keys=[previous_version_id],
    )
    invoice: Mapped[Optional["Invoice"]] = relationship(
        "Invoice",
        back_populates="proposal",
        uselist=False,
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Proposal(id={self.id}, title={self.title}, status={self.status})>"

    @property
    def is_editable(self) -> bool:
        """
        Check if proposal can be edited.

        WHY: Only draft proposals should be editable.

        Returns:
            True if proposal is in DRAFT status
        """
        return self.status == ProposalStatus.DRAFT

    @property
    def is_expired(self) -> bool:
        """
        Check if proposal has expired.

        WHY: Expired proposals shouldn't be accepted.

        Returns:
            True if valid_until has passed
        """
        if not self.valid_until:
            return False
        return datetime.utcnow() > self.valid_until

    @property
    def can_be_approved(self) -> bool:
        """
        Check if proposal can be approved.

        WHY: Only sent/viewed proposals that aren't expired can be approved.

        Returns:
            True if proposal can be approved
        """
        if self.status not in [ProposalStatus.SENT, ProposalStatus.VIEWED]:
            return False
        return not self.is_expired

    def calculate_totals(self) -> None:
        """
        Recalculate subtotal, discount, tax, and total from line items.

        WHY: Ensures pricing consistency when line items change.

        HOW: Sums line item amounts, applies discount and tax.
        """
        # Calculate subtotal from line items
        if self.line_items:
            self.subtotal = Decimal(sum(
                Decimal(str(item.get('amount', 0)))
                for item in self.line_items
            ))
        else:
            self.subtotal = Decimal(0)

        # Calculate discount
        discount_pct = self.discount_percent or Decimal(0)
        self.discount_amount = self.subtotal * (discount_pct / Decimal(100))

        # Calculate subtotal after discount
        subtotal_after_discount = self.subtotal - self.discount_amount

        # Calculate tax
        tax_pct = self.tax_percent or Decimal(0)
        self.tax_amount = subtotal_after_discount * (tax_pct / Decimal(100))

        # Calculate total
        self.total = subtotal_after_discount + self.tax_amount
