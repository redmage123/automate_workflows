"""
Unit tests for Invoice DAO.

WHAT: Tests for InvoiceDAO database operations.

WHY: Verifies that:
1. Invoice CRUD operations work correctly
2. Org-scoping is enforced (multi-tenancy security)
3. Payment workflow operations (send, mark paid, cancel) work properly
4. Status transitions handle timestamps correctly
5. Stripe integration fields are properly managed
6. Financial calculations are accurate
7. Query methods filter and paginate correctly

HOW: Uses pytest-asyncio with PostgreSQL test database for isolation.
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.dao.invoice import InvoiceDAO
from app.models.invoice import Invoice, InvoiceStatus
from app.models.proposal import ProposalStatus
from tests.factories import (
    OrganizationFactory,
    ProjectFactory,
    ProposalFactory,
)


class TestInvoiceDAOCreate:
    """Tests for invoice creation."""

    @pytest.mark.asyncio
    async def test_create_invoice_success(self, db_session, test_org):
        """Test creating an invoice with all required fields."""
        invoice_dao = InvoiceDAO(db_session)

        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1080.00"),
            tax_amount=Decimal("80.00"),
        )

        assert invoice.id is not None
        assert invoice.invoice_number == "INV-2024-0001"
        assert invoice.org_id == test_org.id
        assert invoice.status == InvoiceStatus.DRAFT
        assert invoice.subtotal == Decimal("1000.00")
        assert invoice.total == Decimal("1080.00")
        assert invoice.amount_paid == Decimal("0")
        assert invoice.created_at is not None

    @pytest.mark.asyncio
    async def test_create_invoice_with_proposal(self, db_session, test_org):
        """Test creating an invoice linked to a proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session,
            title="Test Proposal",
            project=project,
            status=ProposalStatus.APPROVED,
        )

        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0002",
            proposal_id=proposal.id,
            org_id=test_org.id,
            subtotal=proposal.subtotal,
            discount_amount=proposal.discount_amount,
            tax_amount=proposal.tax_amount,
            total=proposal.total,
        )

        assert invoice.proposal_id == proposal.id
        assert invoice.subtotal == proposal.subtotal
        assert invoice.total == proposal.total

    @pytest.mark.asyncio
    async def test_create_invoice_with_stripe_fields(self, db_session, test_org):
        """Test creating an invoice with Stripe integration fields."""
        invoice_dao = InvoiceDAO(db_session)

        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=test_org.id,
            subtotal=Decimal("500.00"),
            total=Decimal("500.00"),
            stripe_payment_intent_id="pi_test123",
            stripe_checkout_session_id="cs_test456",
            payment_method="card",
        )

        assert invoice.stripe_payment_intent_id == "pi_test123"
        assert invoice.stripe_checkout_session_id == "cs_test456"
        assert invoice.payment_method == "card"

    @pytest.mark.asyncio
    async def test_create_invoice_with_dates(self, db_session, test_org):
        """Test creating an invoice with issue and due dates."""
        invoice_dao = InvoiceDAO(db_session)
        issue_date = date.today()
        due_date = date.today() + timedelta(days=30)

        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0004",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
            issue_date=issue_date,
            due_date=due_date,
        )

        assert invoice.issue_date == issue_date
        assert invoice.due_date == due_date


class TestInvoiceDAORead:
    """Tests for invoice read operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_and_org_success(self, db_session, test_org):
        """Test retrieving an invoice by ID with org-scoping."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        found = await invoice_dao.get_by_id_and_org(invoice.id, test_org.id)

        assert found is not None
        assert found.id == invoice.id
        assert found.invoice_number == "INV-2024-0001"

    @pytest.mark.asyncio
    async def test_get_by_id_and_org_wrong_org(self, db_session):
        """Test that org-scoping prevents cross-org access."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=org1.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        # Try to access from wrong org
        found = await invoice_dao.get_by_id_and_org(invoice.id, org2.id)
        assert found is None  # Should not find invoice from other org

    @pytest.mark.asyncio
    async def test_get_by_invoice_number(self, db_session, test_org):
        """Test retrieving an invoice by invoice number."""
        invoice_dao = InvoiceDAO(db_session)
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        found = await invoice_dao.get_by_invoice_number("INV-2024-0001", test_org.id)

        assert found is not None
        assert found.invoice_number == "INV-2024-0001"

    @pytest.mark.asyncio
    async def test_get_by_invoice_number_wrong_org(self, db_session):
        """Test that invoice number lookup respects org-scoping."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        invoice_dao = InvoiceDAO(db_session)
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=org1.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        # Try from wrong org
        found = await invoice_dao.get_by_invoice_number("INV-2024-0001", org2.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_proposal(self, db_session, test_org):
        """Test retrieving an invoice by proposal ID."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Test Proposal", project=project
        )

        invoice_dao = InvoiceDAO(db_session)
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            proposal_id=proposal.id,
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        found = await invoice_dao.get_by_proposal(proposal.id, test_org.id)

        assert found is not None
        assert found.proposal_id == proposal.id


class TestInvoiceDAOStripeQueries:
    """Tests for Stripe-related queries."""

    @pytest.mark.asyncio
    async def test_get_by_stripe_payment_intent(self, db_session, test_org):
        """Test retrieving an invoice by Stripe PaymentIntent ID."""
        invoice_dao = InvoiceDAO(db_session)
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
            stripe_payment_intent_id="pi_test123",
        )

        found = await invoice_dao.get_by_stripe_payment_intent("pi_test123")

        assert found is not None
        assert found.stripe_payment_intent_id == "pi_test123"

    @pytest.mark.asyncio
    async def test_get_by_stripe_payment_intent_not_found(self, db_session):
        """Test that non-existent PaymentIntent returns None."""
        invoice_dao = InvoiceDAO(db_session)
        found = await invoice_dao.get_by_stripe_payment_intent("pi_nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_stripe_checkout_session(self, db_session, test_org):
        """Test retrieving an invoice by Stripe Checkout Session ID."""
        invoice_dao = InvoiceDAO(db_session)
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
            stripe_checkout_session_id="cs_test456",
        )

        found = await invoice_dao.get_by_stripe_checkout_session("cs_test456")

        assert found is not None
        assert found.stripe_checkout_session_id == "cs_test456"


class TestInvoiceDAOStatusFilters:
    """Tests for status-based filtering."""

    @pytest.mark.asyncio
    async def test_get_by_status(self, db_session, test_org):
        """Test filtering invoices by status."""
        invoice_dao = InvoiceDAO(db_session)

        # Create invoices with different statuses
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.DRAFT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            subtotal=Decimal("3000.00"),
            total=Decimal("3000.00"),
        )

        sent = await invoice_dao.get_by_status(test_org.id, InvoiceStatus.SENT)

        assert len(sent) == 1
        assert sent[0].invoice_number == "INV-2024-0002"

    @pytest.mark.asyncio
    async def test_get_unpaid(self, db_session, test_org):
        """Test getting unpaid invoices."""
        invoice_dao = InvoiceDAO(db_session)

        # Create invoices with various statuses
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.DRAFT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=test_org.id,
            status=InvoiceStatus.PARTIALLY_PAID,
            subtotal=Decimal("3000.00"),
            total=Decimal("3000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0004",
            org_id=test_org.id,
            status=InvoiceStatus.OVERDUE,
            subtotal=Decimal("4000.00"),
            total=Decimal("4000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0005",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            subtotal=Decimal("5000.00"),
            total=Decimal("5000.00"),
        )

        unpaid = await invoice_dao.get_unpaid(test_org.id)

        # Should include SENT, PARTIALLY_PAID, OVERDUE but not DRAFT or PAID
        assert len(unpaid) == 3
        numbers = {inv.invoice_number for inv in unpaid}
        assert "INV-2024-0002" in numbers  # SENT
        assert "INV-2024-0003" in numbers  # PARTIALLY_PAID
        assert "INV-2024-0004" in numbers  # OVERDUE
        assert "INV-2024-0001" not in numbers  # DRAFT
        assert "INV-2024-0005" not in numbers  # PAID

    @pytest.mark.asyncio
    async def test_get_overdue(self, db_session, test_org):
        """Test getting overdue invoices."""
        invoice_dao = InvoiceDAO(db_session)
        past_date = date.today() - timedelta(days=7)
        future_date = date.today() + timedelta(days=7)

        # Create invoice past due
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            due_date=past_date,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        # Create invoice not yet due
        await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            due_date=future_date,
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
        )
        # Create paid invoice (past due but paid)
        await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            due_date=past_date,
            subtotal=Decimal("3000.00"),
            total=Decimal("3000.00"),
        )

        overdue = await invoice_dao.get_overdue(test_org.id)

        assert len(overdue) == 1
        assert overdue[0].invoice_number == "INV-2024-0001"


class TestInvoiceDAOWorkflow:
    """Tests for invoice workflow operations."""

    @pytest.mark.asyncio
    async def test_send_invoice_success(self, db_session, test_org):
        """Test sending a draft invoice."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.DRAFT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        sent = await invoice_dao.send_invoice(invoice.id, test_org.id)

        assert sent is not None
        assert sent.status == InvoiceStatus.SENT
        assert sent.sent_at is not None

    @pytest.mark.asyncio
    async def test_send_invoice_invalid_status(self, db_session, test_org):
        """Test that only draft invoices can be sent."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        result = await invoice_dao.send_invoice(invoice.id, test_org.id)

        assert result is None  # Should fail - already paid

    @pytest.mark.asyncio
    async def test_mark_paid_success(self, db_session, test_org):
        """Test marking an invoice as paid."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        paid = await invoice_dao.mark_paid(
            invoice.id,
            test_org.id,
            payment_method="card",
            stripe_payment_intent_id="pi_test123",
        )

        assert paid is not None
        assert paid.status == InvoiceStatus.PAID
        assert paid.paid_at is not None
        assert paid.amount_paid == Decimal("1000.00")
        assert paid.payment_method == "card"
        assert paid.stripe_payment_intent_id == "pi_test123"

    @pytest.mark.asyncio
    async def test_mark_paid_from_overdue(self, db_session, test_org):
        """Test marking an overdue invoice as paid."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.OVERDUE,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        paid = await invoice_dao.mark_paid(invoice.id, test_org.id)

        assert paid is not None
        assert paid.status == InvoiceStatus.PAID

    @pytest.mark.asyncio
    async def test_mark_paid_invalid_status(self, db_session, test_org):
        """Test that draft invoices cannot be marked as paid."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.DRAFT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        result = await invoice_dao.mark_paid(invoice.id, test_org.id)

        assert result is None  # Should fail - still draft

    @pytest.mark.asyncio
    async def test_record_partial_payment(self, db_session, test_org):
        """Test recording a partial payment."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        updated = await invoice_dao.record_partial_payment(
            invoice.id,
            test_org.id,
            amount=Decimal("500.00"),
            payment_method="card",
        )

        assert updated is not None
        assert updated.status == InvoiceStatus.PARTIALLY_PAID
        assert updated.amount_paid == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_record_partial_payment_completes_payment(self, db_session, test_org):
        """Test that partial payment completing full amount marks as paid."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.PARTIALLY_PAID,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
            amount_paid=Decimal("500.00"),
        )

        updated = await invoice_dao.record_partial_payment(
            invoice.id,
            test_org.id,
            amount=Decimal("500.00"),
        )

        assert updated is not None
        assert updated.status == InvoiceStatus.PAID
        assert updated.amount_paid == Decimal("1000.00")
        assert updated.paid_at is not None

    @pytest.mark.asyncio
    async def test_mark_overdue(self, db_session, test_org):
        """Test marking an invoice as overdue."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        overdue = await invoice_dao.mark_overdue(invoice.id, test_org.id)

        assert overdue is not None
        assert overdue.status == InvoiceStatus.OVERDUE

    @pytest.mark.asyncio
    async def test_cancel_invoice(self, db_session, test_org):
        """Test cancelling an invoice."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        cancelled = await invoice_dao.cancel_invoice(
            invoice.id,
            test_org.id,
            reason="Client requested cancellation",
        )

        assert cancelled is not None
        assert cancelled.status == InvoiceStatus.CANCELLED
        assert "Client requested cancellation" in cancelled.notes

    @pytest.mark.asyncio
    async def test_cancel_paid_invoice_fails(self, db_session, test_org):
        """Test that paid invoices cannot be cancelled."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        result = await invoice_dao.cancel_invoice(invoice.id, test_org.id)

        assert result is None  # Should fail - already paid

    @pytest.mark.asyncio
    async def test_mark_refunded(self, db_session, test_org):
        """Test marking a paid invoice as refunded."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        refunded = await invoice_dao.mark_refunded(invoice.id, test_org.id)

        assert refunded is not None
        assert refunded.status == InvoiceStatus.REFUNDED

    @pytest.mark.asyncio
    async def test_mark_refunded_invalid_status(self, db_session, test_org):
        """Test that only paid invoices can be refunded."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        result = await invoice_dao.mark_refunded(invoice.id, test_org.id)

        assert result is None  # Should fail - not paid


class TestInvoiceDAOStripeUpdates:
    """Tests for Stripe field updates."""

    @pytest.mark.asyncio
    async def test_update_stripe_checkout_session(self, db_session, test_org):
        """Test updating Stripe checkout session ID."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        updated = await invoice_dao.update_stripe_checkout_session(
            invoice.id,
            test_org.id,
            "cs_test123",
        )

        assert updated is not None
        assert updated.stripe_checkout_session_id == "cs_test123"


class TestInvoiceDAOStatistics:
    """Tests for statistical queries."""

    @pytest.mark.asyncio
    async def test_count_by_status(self, db_session, test_org):
        """Test counting invoices by status."""
        invoice_dao = InvoiceDAO(db_session)

        # Create invoices with different statuses
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.DRAFT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=test_org.id,
            status=InvoiceStatus.DRAFT,
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("3000.00"),
            total=Decimal("3000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0004",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            subtotal=Decimal("4000.00"),
            total=Decimal("4000.00"),
        )

        counts = await invoice_dao.count_by_status(test_org.id)

        assert counts.get("draft") == 2
        assert counts.get("sent") == 1
        assert counts.get("paid") == 1

    @pytest.mark.asyncio
    async def test_calculate_total_outstanding(self, db_session, test_org):
        """Test calculating total outstanding balance."""
        invoice_dao = InvoiceDAO(db_session)

        # Create sent invoice (full amount outstanding)
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
            amount_paid=Decimal("0"),
        )
        # Create partially paid invoice
        await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=test_org.id,
            status=InvoiceStatus.PARTIALLY_PAID,
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
            amount_paid=Decimal("500.00"),
        )
        # Create overdue invoice
        await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=test_org.id,
            status=InvoiceStatus.OVERDUE,
            subtotal=Decimal("3000.00"),
            total=Decimal("3000.00"),
            amount_paid=Decimal("0"),
        )
        # Create paid invoice (not outstanding)
        await invoice_dao.create(
            invoice_number="INV-2024-0004",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            subtotal=Decimal("5000.00"),
            total=Decimal("5000.00"),
            amount_paid=Decimal("5000.00"),
        )

        outstanding = await invoice_dao.calculate_total_outstanding(test_org.id)

        # 1000 + (2000 - 500) + 3000 = 5500
        assert outstanding == Decimal("5500")

    @pytest.mark.asyncio
    async def test_calculate_total_paid(self, db_session, test_org):
        """Test calculating total payments received."""
        invoice_dao = InvoiceDAO(db_session)

        # Create paid invoices
        paid1 = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
            amount_paid=Decimal("1000.00"),
        )
        paid1.paid_at = datetime.utcnow()
        await db_session.flush()

        paid2 = await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
            amount_paid=Decimal("2000.00"),
        )
        paid2.paid_at = datetime.utcnow()
        await db_session.flush()

        # Create unpaid invoice (not counted)
        await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("5000.00"),
            total=Decimal("5000.00"),
            amount_paid=Decimal("0"),
        )

        total_paid = await invoice_dao.calculate_total_paid(test_org.id)

        assert total_paid == Decimal("3000")


class TestInvoiceDAOInvoiceNumberGeneration:
    """Tests for invoice number generation."""

    @pytest.mark.asyncio
    async def test_get_next_invoice_number_sequence_first(self, db_session, test_org):
        """Test getting first sequence number."""
        invoice_dao = InvoiceDAO(db_session)

        sequence = await invoice_dao.get_next_invoice_number_sequence(test_org.id)

        assert sequence == 1

    @pytest.mark.asyncio
    async def test_get_next_invoice_number_sequence_increments(self, db_session, test_org):
        """Test that sequence increments correctly."""
        invoice_dao = InvoiceDAO(db_session)
        year = datetime.utcnow().year

        # Create some invoices
        await invoice_dao.create(
            invoice_number=f"INV-{year}-0001",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        await invoice_dao.create(
            invoice_number=f"INV-{year}-0002",
            org_id=test_org.id,
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
        )

        sequence = await invoice_dao.get_next_invoice_number_sequence(test_org.id)

        assert sequence == 3

    @pytest.mark.asyncio
    async def test_generate_invoice_number(self, db_session, test_org):
        """Test invoice number format generation."""
        year = datetime.utcnow().year
        invoice_number = Invoice.generate_invoice_number(test_org.id, 1)

        assert invoice_number == f"INV-{year}-0001"

        invoice_number_2 = Invoice.generate_invoice_number(test_org.id, 42)
        assert invoice_number_2 == f"INV-{year}-0042"


class TestInvoiceDAOProposalIntegration:
    """Tests for proposal integration."""

    @pytest.mark.asyncio
    async def test_create_from_proposal(self, db_session, test_org):
        """Test creating an invoice from an approved proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create_approved(
            db_session,
            title="Approved Proposal",
            project=project,
        )

        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create_from_proposal(proposal, due_days=30)

        assert invoice.id is not None
        assert invoice.proposal_id == proposal.id
        assert invoice.org_id == test_org.id
        assert invoice.status == InvoiceStatus.DRAFT
        assert invoice.subtotal == proposal.subtotal
        assert invoice.total == proposal.total
        assert invoice.issue_date == date.today()
        assert invoice.due_date == date.today() + timedelta(days=30)

    @pytest.mark.asyncio
    async def test_get_with_proposal(self, db_session, test_org):
        """Test eagerly loading invoice with proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Test Proposal", project=project
        )

        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            proposal_id=proposal.id,
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        loaded = await invoice_dao.get_with_proposal(invoice.id, test_org.id)

        assert loaded is not None
        assert loaded.proposal is not None
        assert loaded.proposal.title == "Test Proposal"


class TestInvoiceDAODueDates:
    """Tests for due date queries."""

    @pytest.mark.asyncio
    async def test_get_due_soon(self, db_session, test_org):
        """Test getting invoices due soon."""
        invoice_dao = InvoiceDAO(db_session)

        # Create invoice due in 3 days
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            due_date=date.today() + timedelta(days=3),
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        # Create invoice due in 10 days (not within 7)
        await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            due_date=date.today() + timedelta(days=10),
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
        )
        # Create already overdue invoice
        await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            due_date=date.today() - timedelta(days=3),
            subtotal=Decimal("3000.00"),
            total=Decimal("3000.00"),
        )
        # Create paid invoice (not included)
        await invoice_dao.create(
            invoice_number="INV-2024-0004",
            org_id=test_org.id,
            status=InvoiceStatus.PAID,
            due_date=date.today() + timedelta(days=3),
            subtotal=Decimal("4000.00"),
            total=Decimal("4000.00"),
        )

        due_soon = await invoice_dao.get_due_soon(test_org.id, days=7)

        assert len(due_soon) == 1
        assert due_soon[0].invoice_number == "INV-2024-0001"

    @pytest.mark.asyncio
    async def test_update_overdue_invoices(self, db_session, test_org):
        """Test batch updating overdue invoices."""
        invoice_dao = InvoiceDAO(db_session)
        past_date = date.today() - timedelta(days=7)

        # Create invoice past due
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            due_date=past_date,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        # Create another past due
        await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=test_org.id,
            status=InvoiceStatus.PARTIALLY_PAID,
            due_date=past_date,
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
        )
        # Create not yet due (should not be updated)
        await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            due_date=date.today() + timedelta(days=7),
            subtotal=Decimal("3000.00"),
            total=Decimal("3000.00"),
        )

        updated_count = await invoice_dao.update_overdue_invoices(test_org.id)

        assert updated_count == 2

        # Verify statuses updated
        overdue = await invoice_dao.get_by_status(test_org.id, InvoiceStatus.OVERDUE)
        assert len(overdue) == 2


class TestInvoiceDAOMultiTenancy:
    """Tests for multi-tenancy isolation."""

    @pytest.mark.asyncio
    async def test_invoices_isolated_by_org(self, db_session):
        """Test that invoices from different orgs are isolated."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        invoice_dao = InvoiceDAO(db_session)

        # Create invoices in each org
        await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=org1.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=org1.id,
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
        )
        await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=org2.id,
            subtotal=Decimal("3000.00"),
            total=Decimal("3000.00"),
        )

        org1_invoices = await invoice_dao.get_by_org(org1.id)
        org2_invoices = await invoice_dao.get_by_org(org2.id)

        assert len(org1_invoices) == 2
        assert len(org2_invoices) == 1
        assert all(inv.org_id == org1.id for inv in org1_invoices)
        assert all(inv.org_id == org2.id for inv in org2_invoices)

    @pytest.mark.asyncio
    async def test_workflow_operations_respect_org(self, db_session):
        """Test that workflow operations respect org-scoping."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=org1.id,
            status=InvoiceStatus.DRAFT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        # Try operations from wrong org
        result = await invoice_dao.send_invoice(invoice.id, org2.id)
        assert result is None

        result = await invoice_dao.mark_paid(invoice.id, org2.id)
        assert result is None

        result = await invoice_dao.cancel_invoice(invoice.id, org2.id)
        assert result is None


class TestInvoiceModelProperties:
    """Tests for Invoice model properties."""

    @pytest.mark.asyncio
    async def test_is_editable(self, db_session, test_org):
        """Test is_editable property."""
        invoice_dao = InvoiceDAO(db_session)

        draft = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            status=InvoiceStatus.DRAFT,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )
        sent = await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=test_org.id,
            status=InvoiceStatus.SENT,
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
        )

        assert draft.is_editable is True
        assert sent.is_editable is False

    @pytest.mark.asyncio
    async def test_balance_due(self, db_session, test_org):
        """Test balance_due property."""
        invoice_dao = InvoiceDAO(db_session)

        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
            amount_paid=Decimal("400.00"),
        )

        assert invoice.balance_due == Decimal("600.00")

    @pytest.mark.asyncio
    async def test_is_partially_paid(self, db_session, test_org):
        """Test is_partially_paid property."""
        invoice_dao = InvoiceDAO(db_session)

        not_paid = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
            amount_paid=Decimal("0"),
        )
        partial = await invoice_dao.create(
            invoice_number="INV-2024-0002",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
            amount_paid=Decimal("500.00"),
        )
        fully_paid = await invoice_dao.create(
            invoice_number="INV-2024-0003",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
            amount_paid=Decimal("1000.00"),
        )

        assert not_paid.is_partially_paid is False
        assert partial.is_partially_paid is True
        assert fully_paid.is_partially_paid is False


class TestInvoiceDAODelete:
    """Tests for invoice deletion."""

    @pytest.mark.asyncio
    async def test_delete_invoice(self, db_session, test_org):
        """Test deleting an invoice."""
        invoice_dao = InvoiceDAO(db_session)
        invoice = await invoice_dao.create(
            invoice_number="INV-2024-0001",
            org_id=test_org.id,
            subtotal=Decimal("1000.00"),
            total=Decimal("1000.00"),
        )

        result = await invoice_dao.delete(invoice.id)

        assert result is True

        # Verify deleted
        found = await invoice_dao.get_by_id(invoice.id)
        assert found is None
