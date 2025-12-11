"""
Invoice Data Access Object (DAO).

WHAT: Database operations for the Invoice model.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides a consistent API for invoice operations
3. Enforces org-scoping for multi-tenancy
4. Encapsulates complex queries for billing management

HOW: Extends BaseDAO with invoice-specific queries:
- Status-based filtering
- Stripe payment tracking
- Payment workflow operations
- Financial reporting queries
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.invoice import Invoice, InvoiceStatus
from app.models.proposal import Proposal


class InvoiceDAO(BaseDAO[Invoice]):
    """
    Data Access Object for Invoice model.

    WHAT: Provides CRUD and query operations for invoices.

    WHY: Centralizes all invoice database operations:
    - Enforces org_id scoping for security
    - Provides specialized invoice queries
    - Manages payment workflow
    - Supports Stripe integration

    HOW: Extends BaseDAO with invoice-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize InvoiceDAO.

        Args:
            session: Async database session
        """
        super().__init__(Invoice, session)

    async def get_by_invoice_number(
        self,
        invoice_number: str,
        org_id: int,
    ) -> Optional[Invoice]:
        """
        Get an invoice by its invoice number.

        WHAT: Look up invoice by human-readable identifier.

        WHY: Invoice numbers are used in:
        - Client communications
        - Payment references
        - Accounting systems

        Args:
            invoice_number: The invoice number (e.g., INV-2024-0001)
            org_id: Organization ID for security

        Returns:
            Invoice if found and belongs to org, None otherwise
        """
        result = await self.session.execute(
            select(Invoice)
            .where(
                Invoice.invoice_number == invoice_number,
                Invoice.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_proposal(
        self,
        proposal_id: int,
        org_id: int,
    ) -> Optional[Invoice]:
        """
        Get the invoice associated with a proposal.

        WHAT: Find invoice created from a specific proposal.

        WHY: Used when:
        - Checking if proposal already has an invoice
        - Linking proposal view to invoice view
        - Preventing duplicate invoice creation

        Args:
            proposal_id: Proposal ID
            org_id: Organization ID for security

        Returns:
            Invoice if found, None otherwise
        """
        result = await self.session.execute(
            select(Invoice)
            .where(
                Invoice.proposal_id == proposal_id,
                Invoice.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_stripe_payment_intent(
        self,
        payment_intent_id: str,
    ) -> Optional[Invoice]:
        """
        Get an invoice by Stripe PaymentIntent ID.

        WHAT: Look up invoice by Stripe reference.

        WHY: Used in webhook handlers when Stripe
        sends payment status updates. Note: No org_id
        filtering because webhooks don't have org context.

        Args:
            payment_intent_id: Stripe PaymentIntent ID

        Returns:
            Invoice if found, None otherwise
        """
        result = await self.session.execute(
            select(Invoice)
            .where(Invoice.stripe_payment_intent_id == payment_intent_id)
        )
        return result.scalar_one_or_none()

    async def get_by_stripe_checkout_session(
        self,
        checkout_session_id: str,
    ) -> Optional[Invoice]:
        """
        Get an invoice by Stripe Checkout Session ID.

        WHAT: Look up invoice by Stripe checkout reference.

        WHY: Used to:
        - Verify checkout session belongs to invoice
        - Update invoice after successful checkout
        - Handle checkout completion

        Args:
            checkout_session_id: Stripe Checkout Session ID

        Returns:
            Invoice if found, None otherwise
        """
        result = await self.session.execute(
            select(Invoice)
            .where(Invoice.stripe_checkout_session_id == checkout_session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_status(
        self,
        org_id: int,
        status: InvoiceStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Invoice]:
        """
        Get invoices by status for an organization.

        WHAT: Filter invoices by their status.

        WHY: Common use case for dashboards:
        - "Show me unpaid invoices"
        - "What invoices are overdue?"
        - "List all paid invoices this month"

        Args:
            org_id: Organization ID
            status: Invoice status to filter by
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of invoices matching the status
        """
        result = await self.session.execute(
            select(Invoice)
            .where(
                Invoice.org_id == org_id,
                Invoice.status == status,
            )
            .order_by(Invoice.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_unpaid(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Invoice]:
        """
        Get all unpaid invoices (sent, partially paid, overdue).

        WHAT: Find invoices requiring payment.

        WHY: Business critical view:
        - Track outstanding receivables
        - Follow up on payments
        - Cash flow management

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of unpaid invoices
        """
        result = await self.session.execute(
            select(Invoice)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.in_([
                    InvoiceStatus.SENT,
                    InvoiceStatus.PARTIALLY_PAID,
                    InvoiceStatus.OVERDUE,
                ]),
            )
            .order_by(Invoice.due_date.asc().nullslast())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_overdue(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Invoice]:
        """
        Get invoices that are past due date.

        WHAT: Find invoices past due_date that aren't paid/cancelled.

        WHY: Trigger:
        - Overdue notifications
        - Collection activities
        - Late fee calculations

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of overdue invoices
        """
        today = date.today()
        result = await self.session.execute(
            select(Invoice)
            .where(
                Invoice.org_id == org_id,
                Invoice.due_date < today,
                Invoice.status.in_([
                    InvoiceStatus.SENT,
                    InvoiceStatus.PARTIALLY_PAID,
                ]),
            )
            .order_by(Invoice.due_date.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def send_invoice(
        self,
        invoice_id: int,
        org_id: int,
    ) -> Optional[Invoice]:
        """
        Mark an invoice as sent to the client.

        WHAT: Transition status from DRAFT to SENT.

        WHY: Track when invoices are sent:
        - Audit trail
        - Trigger email notifications
        - Start payment tracking

        Args:
            invoice_id: Invoice ID
            org_id: Organization ID for security

        Returns:
            Updated invoice or None if not found/invalid state
        """
        invoice = await self.get_by_id_and_org(invoice_id, org_id)
        if not invoice:
            return None

        if invoice.status != InvoiceStatus.DRAFT:
            return None  # Can only send draft invoices

        invoice.status = InvoiceStatus.SENT
        invoice.sent_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(invoice)
        return invoice

    async def mark_paid(
        self,
        invoice_id: int,
        org_id: int,
        payment_method: Optional[str] = None,
        stripe_payment_intent_id: Optional[str] = None,
    ) -> Optional[Invoice]:
        """
        Mark an invoice as fully paid.

        WHAT: Transition status to PAID.

        WHY: Record successful payment:
        - Update financial records
        - Trigger confirmation emails
        - Update project status

        Args:
            invoice_id: Invoice ID
            org_id: Organization ID for security
            payment_method: How payment was made
            stripe_payment_intent_id: Stripe payment reference

        Returns:
            Updated invoice or None if not found/invalid state
        """
        invoice = await self.get_by_id_and_org(invoice_id, org_id)
        if not invoice:
            return None

        # Can mark sent, partially paid, or overdue invoices as paid
        valid_statuses = [
            InvoiceStatus.SENT,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.OVERDUE,
        ]
        if invoice.status not in valid_statuses:
            return None

        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.utcnow()
        invoice.amount_paid = invoice.total

        if payment_method:
            invoice.payment_method = payment_method
        if stripe_payment_intent_id:
            invoice.stripe_payment_intent_id = stripe_payment_intent_id

        await self.session.flush()
        await self.session.refresh(invoice)
        return invoice

    async def record_partial_payment(
        self,
        invoice_id: int,
        org_id: int,
        amount: Decimal,
        payment_method: Optional[str] = None,
    ) -> Optional[Invoice]:
        """
        Record a partial payment on an invoice.

        WHAT: Add payment amount and update status if needed.

        WHY: Support partial payments:
        - Split payments
        - Payment plans
        - Incremental billing

        Args:
            invoice_id: Invoice ID
            org_id: Organization ID for security
            amount: Payment amount received
            payment_method: How payment was made

        Returns:
            Updated invoice or None if not found/invalid
        """
        invoice = await self.get_by_id_and_org(invoice_id, org_id)
        if not invoice:
            return None

        # Can only add payments to sent, partially paid, or overdue
        valid_statuses = [
            InvoiceStatus.SENT,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.OVERDUE,
        ]
        if invoice.status not in valid_statuses:
            return None

        # Update amount paid
        current_paid = invoice.amount_paid or Decimal(0)
        new_paid = current_paid + amount
        invoice.amount_paid = new_paid

        if payment_method:
            invoice.payment_method = payment_method

        # Determine new status
        if new_paid >= invoice.total:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.utcnow()
        elif new_paid > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        await self.session.flush()
        await self.session.refresh(invoice)
        return invoice

    async def mark_overdue(
        self,
        invoice_id: int,
        org_id: int,
    ) -> Optional[Invoice]:
        """
        Mark an invoice as overdue.

        WHAT: Transition status to OVERDUE.

        WHY: Explicit overdue marking:
        - Trigger late payment handling
        - Enable overdue filtering
        - Support automated reminders

        Args:
            invoice_id: Invoice ID
            org_id: Organization ID for security

        Returns:
            Updated invoice or None if not found/invalid state
        """
        invoice = await self.get_by_id_and_org(invoice_id, org_id)
        if not invoice:
            return None

        # Can only mark sent or partially paid as overdue
        valid_statuses = [InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]
        if invoice.status not in valid_statuses:
            return None

        invoice.status = InvoiceStatus.OVERDUE

        await self.session.flush()
        await self.session.refresh(invoice)
        return invoice

    async def cancel_invoice(
        self,
        invoice_id: int,
        org_id: int,
        reason: Optional[str] = None,
    ) -> Optional[Invoice]:
        """
        Cancel an invoice.

        WHAT: Transition status to CANCELLED.

        WHY: Void invoices when:
        - Created in error
        - Client cancels
        - Superseded by new invoice

        Args:
            invoice_id: Invoice ID
            org_id: Organization ID for security
            reason: Optional cancellation reason

        Returns:
            Updated invoice or None if not found/invalid state
        """
        invoice = await self.get_by_id_and_org(invoice_id, org_id)
        if not invoice:
            return None

        # Cannot cancel already paid or refunded invoices
        if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.REFUNDED]:
            return None

        invoice.status = InvoiceStatus.CANCELLED
        if reason:
            invoice.notes = (invoice.notes or "") + f"\nCancelled: {reason}"

        await self.session.flush()
        await self.session.refresh(invoice)
        return invoice

    async def mark_refunded(
        self,
        invoice_id: int,
        org_id: int,
    ) -> Optional[Invoice]:
        """
        Mark an invoice as refunded.

        WHAT: Transition status to REFUNDED.

        WHY: Track refunds:
        - Financial reconciliation
        - Audit trail
        - Stripe refund handling

        Args:
            invoice_id: Invoice ID
            org_id: Organization ID for security

        Returns:
            Updated invoice or None if not found/invalid state
        """
        invoice = await self.get_by_id_and_org(invoice_id, org_id)
        if not invoice:
            return None

        # Can only refund paid invoices
        if invoice.status != InvoiceStatus.PAID:
            return None

        invoice.status = InvoiceStatus.REFUNDED

        await self.session.flush()
        await self.session.refresh(invoice)
        return invoice

    async def update_stripe_checkout_session(
        self,
        invoice_id: int,
        org_id: int,
        checkout_session_id: str,
    ) -> Optional[Invoice]:
        """
        Update invoice with Stripe checkout session ID.

        WHAT: Store checkout session reference.

        WHY: Track Stripe checkout:
        - Verify checkout completion
        - Link invoice to payment
        - Enable checkout status checks

        Args:
            invoice_id: Invoice ID
            org_id: Organization ID for security
            checkout_session_id: Stripe Checkout Session ID

        Returns:
            Updated invoice or None if not found
        """
        invoice = await self.get_by_id_and_org(invoice_id, org_id)
        if not invoice:
            return None

        invoice.stripe_checkout_session_id = checkout_session_id

        await self.session.flush()
        await self.session.refresh(invoice)
        return invoice

    async def count_by_status(self, org_id: int) -> dict:
        """
        Get count of invoices by status for an organization.

        WHAT: Aggregate invoice counts by status.

        WHY: Dashboard statistics:
        - Invoice pipeline overview
        - Accounts receivable summary
        - Payment status distribution

        Args:
            org_id: Organization ID

        Returns:
            Dict mapping status to count
        """
        result = await self.session.execute(
            select(Invoice.status, func.count(Invoice.id))
            .where(Invoice.org_id == org_id)
            .group_by(Invoice.status)
        )

        return {row[0].value: row[1] for row in result.all()}

    async def calculate_total_outstanding(self, org_id: int) -> Decimal:
        """
        Calculate total outstanding balance for an organization.

        WHAT: Sum of (total - amount_paid) for unpaid invoices.

        WHY: Critical financial metric:
        - Accounts receivable total
        - Cash flow projections
        - Financial reporting

        Args:
            org_id: Organization ID

        Returns:
            Total outstanding balance
        """
        result = await self.session.execute(
            select(
                func.coalesce(
                    func.sum(Invoice.total - Invoice.amount_paid),
                    0
                )
            )
            .where(
                Invoice.org_id == org_id,
                Invoice.status.in_([
                    InvoiceStatus.SENT,
                    InvoiceStatus.PARTIALLY_PAID,
                    InvoiceStatus.OVERDUE,
                ]),
            )
        )
        return Decimal(str(result.scalar_one()))

    async def calculate_total_paid(
        self,
        org_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Decimal:
        """
        Calculate total payments received for an organization.

        WHAT: Sum of amount_paid for paid invoices.

        WHY: Revenue tracking:
        - Monthly/yearly revenue
        - Financial reports
        - Cash flow analysis

        Args:
            org_id: Organization ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Total paid amount
        """
        query = select(
            func.coalesce(func.sum(Invoice.amount_paid), 0)
        ).where(
            Invoice.org_id == org_id,
            Invoice.status == InvoiceStatus.PAID,
        )

        if start_date:
            query = query.where(Invoice.paid_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.where(Invoice.paid_at <= datetime.combine(end_date, datetime.max.time()))

        result = await self.session.execute(query)
        return Decimal(str(result.scalar_one()))

    async def get_next_invoice_number_sequence(self, org_id: int) -> int:
        """
        Get the next sequence number for invoice numbering.

        WHAT: Count invoices for this year to determine next number.

        WHY: Generate unique, sequential invoice numbers
        for professional invoicing.

        Args:
            org_id: Organization ID

        Returns:
            Next sequence number (starting from 1)
        """
        year = datetime.utcnow().year
        year_prefix = f"INV-{year}-"

        # Count existing invoices with this year's prefix
        result = await self.session.execute(
            select(func.count(Invoice.id))
            .where(
                Invoice.org_id == org_id,
                Invoice.invoice_number.like(f"{year_prefix}%"),
            )
        )
        count = result.scalar_one()
        return count + 1

    async def create_from_proposal(
        self,
        proposal: Proposal,
        due_days: int = 30,
    ) -> Invoice:
        """
        Create an invoice from an approved proposal.

        WHAT: Generate invoice copying proposal amounts.

        WHY: Streamlined workflow:
        - Proposal approval triggers invoice creation
        - Amounts copied for immutability
        - Reduces manual entry

        Args:
            proposal: Approved proposal to invoice
            due_days: Days until payment due (default 30)

        Returns:
            Newly created invoice
        """
        # Get next sequence number
        sequence = await self.get_next_invoice_number_sequence(proposal.org_id)
        invoice_number = Invoice.generate_invoice_number(proposal.org_id, sequence)

        # Calculate due date
        due_date = date.today() + timedelta(days=due_days)

        # Create invoice
        invoice = Invoice(
            invoice_number=invoice_number,
            status=InvoiceStatus.DRAFT,
            proposal_id=proposal.id,
            org_id=proposal.org_id,
            subtotal=proposal.subtotal,
            discount_amount=proposal.discount_amount or Decimal(0),
            tax_amount=proposal.tax_amount or Decimal(0),
            total=proposal.total,
            amount_paid=Decimal(0),
            issue_date=date.today(),
            due_date=due_date,
        )

        self.session.add(invoice)
        await self.session.flush()
        await self.session.refresh(invoice)
        return invoice

    async def get_with_proposal(
        self,
        invoice_id: int,
        org_id: int,
    ) -> Optional[Invoice]:
        """
        Get invoice with proposal eagerly loaded.

        WHAT: Load invoice with related proposal in single query.

        WHY: Avoid N+1 queries when displaying invoice
        with proposal details.

        Args:
            invoice_id: Invoice ID
            org_id: Organization ID for security

        Returns:
            Invoice with proposal loaded, or None
        """
        result = await self.session.execute(
            select(Invoice)
            .options(selectinload(Invoice.proposal))
            .where(
                Invoice.id == invoice_id,
                Invoice.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_overdue_invoices(self, org_id: int) -> int:
        """
        Batch update sent invoices past due date to overdue status.

        WHAT: Find and mark all overdue invoices.

        WHY: Background job support:
        - Daily overdue check
        - Automated status updates
        - Trigger reminder workflows

        Args:
            org_id: Organization ID

        Returns:
            Number of invoices marked as overdue
        """
        today = date.today()

        # Get invoices that are past due
        result = await self.session.execute(
            select(Invoice)
            .where(
                Invoice.org_id == org_id,
                Invoice.due_date < today,
                Invoice.status.in_([
                    InvoiceStatus.SENT,
                    InvoiceStatus.PARTIALLY_PAID,
                ]),
            )
        )
        invoices = list(result.scalars().all())

        # Update each to overdue
        for invoice in invoices:
            invoice.status = InvoiceStatus.OVERDUE

        await self.session.flush()
        return len(invoices)

    async def get_due_soon(
        self,
        org_id: int,
        days: int = 7,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Invoice]:
        """
        Get invoices due within N days.

        WHAT: Find invoices with due_date approaching.

        WHY: Proactive payment reminders:
        - Send reminder emails
        - Dashboard alerts
        - Collection planning

        Args:
            org_id: Organization ID
            days: Days until due
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of invoices due soon
        """
        today = date.today()
        future = today + timedelta(days=days)

        result = await self.session.execute(
            select(Invoice)
            .where(
                Invoice.org_id == org_id,
                Invoice.due_date >= today,
                Invoice.due_date <= future,
                Invoice.status.in_([
                    InvoiceStatus.SENT,
                    InvoiceStatus.PARTIALLY_PAID,
                ]),
            )
            .order_by(Invoice.due_date.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
