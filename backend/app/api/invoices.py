"""
Invoice management API endpoints.

WHAT: RESTful API for invoice CRUD and payment workflows.

WHY: Invoices are critical for:
1. Billing clients for approved proposals
2. Tracking payment status
3. Generating financial records
4. Integrating with Stripe payments

HOW: FastAPI router with:
- Org-scoped queries (multi-tenancy)
- RBAC (ADMIN creates/manages, all can view)
- Payment endpoints (checkout, record payment)
- Stripe webhook handling
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, Response, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    InvalidStateTransitionError,
    StripeError,
)
from app.db.session import get_db
from app.dao.invoice import InvoiceDAO
from app.dao.proposal import ProposalDAO
from app.models.user import User, UserRole
from app.models.invoice import InvoiceStatus as InvoiceStatusModel
from app.models.organization import Organization
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceListResponse,
    InvoiceStats,
    InvoiceStatus,
    CheckoutRequest,
    CheckoutResponse,
    CheckoutStatusResponse,
    PaymentRecord,
)
from app.services.audit import AuditService
from app.services.stripe_service import StripeService, get_stripe_service
from app.services.pdf_service import PDFService, get_pdf_service


router = APIRouter(prefix="/invoices", tags=["invoices"])
payments_router = APIRouter(prefix="/payments", tags=["payments"])
webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _invoice_to_response(invoice) -> InvoiceResponse:
    """
    Convert Invoice model to InvoiceResponse schema.

    WHY: Centralized conversion ensures consistent response format
    and proper handling of decimal to float conversion.

    Args:
        invoice: Invoice model instance

    Returns:
        InvoiceResponse schema instance
    """
    return InvoiceResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        status=InvoiceStatus(invoice.status.value),
        proposal_id=invoice.proposal_id,
        org_id=invoice.org_id,
        subtotal=float(invoice.subtotal),
        discount_amount=float(invoice.discount_amount) if invoice.discount_amount else 0,
        tax_amount=float(invoice.tax_amount) if invoice.tax_amount else 0,
        total=float(invoice.total),
        amount_paid=float(invoice.amount_paid) if invoice.amount_paid else 0,
        stripe_payment_intent_id=invoice.stripe_payment_intent_id,
        stripe_checkout_session_id=invoice.stripe_checkout_session_id,
        payment_method=invoice.payment_method,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        paid_at=invoice.paid_at,
        sent_at=invoice.sent_at,
        notes=invoice.notes,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        is_editable=invoice.is_editable,
        is_paid=invoice.is_paid,
        balance_due=float(invoice.balance_due),
    )


# ============================================================================
# Invoice CRUD Endpoints
# ============================================================================


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create invoice",
    description="Create a new invoice manually (ADMIN only)",
)
async def create_invoice(
    data: InvoiceCreate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    """
    Create a new invoice manually.

    WHAT: Creates an invoice in DRAFT status.

    WHY: Manual invoice creation for:
    - Non-proposal billing
    - Custom charges
    - Service fees

    Note: Most invoices are auto-created when proposals are approved.

    RBAC: Requires ADMIN role.

    Args:
        data: Invoice creation data
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Created invoice data

    Raises:
        ResourceNotFoundError (404): If proposal not found
        ValidationError (400): If data validation fails
    """
    invoice_dao = InvoiceDAO(db)
    proposal_dao = ProposalDAO(db)

    # Verify proposal exists if provided
    if data.proposal_id:
        proposal = await proposal_dao.get_by_id_and_org(data.proposal_id, current_user.org_id)
        if not proposal:
            raise ResourceNotFoundError(
                message=f"Proposal with id {data.proposal_id} not found",
                resource_type="Proposal",
                resource_id=data.proposal_id,
            )

        # Check if proposal already has an invoice
        existing = await invoice_dao.get_by_proposal(data.proposal_id, current_user.org_id)
        if existing:
            raise ValidationError(
                message="Proposal already has an invoice",
                proposal_id=data.proposal_id,
                existing_invoice_id=existing.id,
            )

    # Generate invoice number
    sequence = await invoice_dao.get_next_invoice_number_sequence(current_user.org_id)
    from app.models.invoice import Invoice
    invoice_number = Invoice.generate_invoice_number(current_user.org_id, sequence)

    # Create invoice
    invoice = await invoice_dao.create(
        invoice_number=invoice_number,
        proposal_id=data.proposal_id,
        org_id=current_user.org_id,
        subtotal=data.subtotal,
        discount_amount=data.discount_amount or Decimal(0),
        tax_amount=data.tax_amount or Decimal(0),
        total=data.total,
        issue_date=data.issue_date or date.today(),
        due_date=data.due_date,
        notes=data.notes,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="invoice",
        resource_id=invoice.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"invoice_number": invoice_number, "total": float(data.total)},
    )

    return _invoice_to_response(invoice)


@router.get(
    "",
    response_model=InvoiceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List invoices",
    description="Get paginated list of invoices for the current organization",
)
async def list_invoices(
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum items to return"),
    status_filter: Optional[InvoiceStatus] = Query(
        default=None,
        alias="status",
        description="Filter by invoice status",
    ),
    unpaid_only: bool = Query(
        default=False,
        description="Only return unpaid invoices",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceListResponse:
    """
    List invoices for current organization.

    WHAT: Returns paginated list of invoices with optional filters.

    WHY: Users need to:
    - View all invoices
    - Filter by status for workflow management
    - Track unpaid invoices

    Args:
        skip: Pagination offset
        limit: Maximum items per page
        status_filter: Optional status filter
        unpaid_only: If True, only unpaid invoices
        current_user: Current authenticated user
        db: Database session

    Returns:
        Paginated list of invoices
    """
    invoice_dao = InvoiceDAO(db)
    org_id = current_user.org_id

    if unpaid_only:
        invoices = await invoice_dao.get_unpaid(org_id, skip=skip, limit=limit)
        # Get total count of unpaid
        all_unpaid = await invoice_dao.get_unpaid(org_id, limit=10000)
        total = len(all_unpaid)
    elif status_filter:
        status_enum = InvoiceStatusModel(status_filter.value)
        invoices = await invoice_dao.get_by_status(org_id, status_enum, skip=skip, limit=limit)
        counts = await invoice_dao.count_by_status(org_id)
        total = counts.get(status_filter.value, 0)
    else:
        invoices = await invoice_dao.get_by_org(org_id, skip=skip, limit=limit)
        total = await invoice_dao.count(org_id=org_id)

    return InvoiceListResponse(
        items=[_invoice_to_response(inv) for inv in invoices],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/stats",
    response_model=InvoiceStats,
    status_code=status.HTTP_200_OK,
    summary="Get invoice statistics",
    description="Get aggregated invoice statistics for the current organization",
)
async def get_invoice_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceStats:
    """
    Get invoice statistics.

    WHAT: Returns aggregated metrics for dashboard widgets.

    WHY: Quick overview of:
    - Total outstanding balance
    - Payments received
    - Invoice distribution by status

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Invoice statistics
    """
    invoice_dao = InvoiceDAO(db)
    org_id = current_user.org_id

    by_status = await invoice_dao.count_by_status(org_id)
    total = sum(by_status.values())
    outstanding = await invoice_dao.calculate_total_outstanding(org_id)
    paid = await invoice_dao.calculate_total_paid(org_id)

    return InvoiceStats(
        total=total,
        by_status=by_status,
        total_outstanding=float(outstanding),
        total_paid=float(paid),
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get invoice",
    description="Get invoice details by ID (org-scoped)",
)
async def get_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    """
    Get invoice by ID.

    WHAT: Returns invoice details.

    WHY: Users need to view invoice details for:
    - Payment tracking
    - PDF generation
    - Status verification

    Security: Enforces org-scoping.

    Args:
        invoice_id: Invoice ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Invoice data

    Raises:
        ResourceNotFoundError (404): If invoice not found
    """
    invoice_dao = InvoiceDAO(db)

    invoice = await invoice_dao.get_by_id_and_org(invoice_id, current_user.org_id)

    if not invoice:
        raise ResourceNotFoundError(
            message=f"Invoice with id {invoice_id} not found",
            resource_type="Invoice",
            resource_id=invoice_id,
        )

    return _invoice_to_response(invoice)


@router.get(
    "/{invoice_id}/pdf",
    status_code=status.HTTP_200_OK,
    summary="Download invoice PDF",
    description="Generate and download invoice as PDF",
)
async def download_invoice_pdf(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pdf_service: PDFService = Depends(get_pdf_service),
) -> Response:
    """
    Download invoice as PDF.

    WHAT: Generates and returns invoice PDF.

    WHY: PDF download enables:
    - Professional document sharing
    - Print-ready invoices
    - Email attachments
    - Record keeping

    Args:
        invoice_id: Invoice ID
        current_user: Current authenticated user
        db: Database session
        pdf_service: PDF service instance

    Returns:
        PDF file as downloadable response

    Raises:
        ResourceNotFoundError (404): If invoice not found
    """
    invoice_dao = InvoiceDAO(db)

    invoice = await invoice_dao.get_with_proposal(invoice_id, current_user.org_id)
    if not invoice:
        raise ResourceNotFoundError(
            message=f"Invoice with id {invoice_id} not found",
            resource_type="Invoice",
            resource_id=invoice_id,
        )

    # Get organization name for client info
    from sqlalchemy import select
    result = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = result.scalar_one()

    # Get line items from proposal if available
    line_items = None
    if invoice.proposal and invoice.proposal.line_items:
        line_items = invoice.proposal.line_items

    # Generate PDF
    pdf_bytes = pdf_service.generate_invoice_pdf(
        invoice=invoice,
        client_name=org.name,
        line_items=line_items,
    )

    # Return as downloadable file
    filename = f"invoice-{invoice.invoice_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.patch(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update invoice",
    description="Update invoice details (ADMIN only, draft status only)",
)
async def update_invoice(
    invoice_id: int,
    data: InvoiceUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    """
    Update invoice details.

    WHAT: Updates invoice fields.

    WHY: ADMINs update invoices to:
    - Adjust amounts before sending
    - Change due dates
    - Add notes

    RBAC: Requires ADMIN role.
    Constraint: Only DRAFT invoices can be edited.

    Args:
        invoice_id: Invoice ID
        data: Update data (partial update)
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated invoice data

    Raises:
        ResourceNotFoundError (404): If invoice not found
        InvalidStateTransitionError (400): If invoice not editable
    """
    invoice_dao = InvoiceDAO(db)

    invoice = await invoice_dao.get_by_id_and_org(invoice_id, current_user.org_id)
    if not invoice:
        raise ResourceNotFoundError(
            message=f"Invoice with id {invoice_id} not found",
            resource_type="Invoice",
            resource_id=invoice_id,
        )

    if not invoice.is_editable:
        raise InvalidStateTransitionError(
            message="Only DRAFT invoices can be edited",
            current_state=invoice.status.value,
            requested_state="edit",
        )

    # Build update dict
    update_data = {}
    if data.subtotal is not None:
        update_data["subtotal"] = data.subtotal
    if data.discount_amount is not None:
        update_data["discount_amount"] = data.discount_amount
    if data.tax_amount is not None:
        update_data["tax_amount"] = data.tax_amount
    if data.total is not None:
        update_data["total"] = data.total
    if data.due_date is not None:
        update_data["due_date"] = data.due_date
    if data.notes is not None:
        update_data["notes"] = data.notes

    if update_data:
        invoice = await invoice_dao.update(invoice_id, **update_data)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="invoice",
        resource_id=invoice_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes=update_data,
    )

    return _invoice_to_response(invoice)


@router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete invoice",
    description="Delete an invoice (ADMIN only, draft status only)",
)
async def delete_invoice(
    invoice_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete an invoice.

    WHAT: Permanently deletes an invoice.

    WHY: ADMINs may need to delete:
    - Draft invoices no longer needed
    - Duplicates
    - Test data

    Constraint: Only DRAFT invoices can be deleted.
    Sent/paid invoices must be cancelled instead.

    RBAC: Requires ADMIN role.

    Args:
        invoice_id: Invoice ID
        current_user: Current authenticated admin user
        db: Database session

    Raises:
        ResourceNotFoundError (404): If invoice not found
        InvalidStateTransitionError (400): If invoice not in draft
    """
    invoice_dao = InvoiceDAO(db)

    invoice = await invoice_dao.get_by_id_and_org(invoice_id, current_user.org_id)
    if not invoice:
        raise ResourceNotFoundError(
            message=f"Invoice with id {invoice_id} not found",
            resource_type="Invoice",
            resource_id=invoice_id,
        )

    if not invoice.is_editable:
        raise InvalidStateTransitionError(
            message="Only DRAFT invoices can be deleted. Use cancel for sent invoices.",
            current_state=invoice.status.value,
            requested_state="delete",
        )

    # Audit log before deletion
    audit_service = AuditService(db)
    await audit_service.log_delete(
        resource_type="invoice",
        resource_id=invoice_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"invoice_number": invoice.invoice_number, "total": float(invoice.total)},
    )

    await invoice_dao.delete(invoice_id)


# ============================================================================
# Invoice Workflow Endpoints
# ============================================================================


@router.post(
    "/{invoice_id}/send",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Send invoice",
    description="Send an invoice to the client (ADMIN only)",
)
async def send_invoice(
    invoice_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    """
    Send an invoice to the client.

    WHAT: Transitions invoice from DRAFT to SENT status.

    WHY: Sending an invoice:
    - Makes it payable
    - Records sent_at timestamp
    - Triggers notification (future)

    RBAC: Requires ADMIN role.
    Constraint: Only DRAFT invoices can be sent.

    Args:
        invoice_id: Invoice ID
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated invoice data

    Raises:
        ResourceNotFoundError (404): If invoice not found
        InvalidStateTransitionError (400): If invoice not in draft
    """
    invoice_dao = InvoiceDAO(db)

    invoice = await invoice_dao.send_invoice(invoice_id, current_user.org_id)

    if not invoice:
        existing = await invoice_dao.get_by_id_and_org(invoice_id, current_user.org_id)
        if not existing:
            raise ResourceNotFoundError(
                message=f"Invoice with id {invoice_id} not found",
                resource_type="Invoice",
                resource_id=invoice_id,
            )
        raise InvalidStateTransitionError(
            message="Only DRAFT invoices can be sent",
            current_state=existing.status.value,
            requested_state="sent",
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="invoice",
        resource_id=invoice_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes={"status": {"before": "draft", "after": "sent"}},
    )

    return _invoice_to_response(invoice)


@router.post(
    "/{invoice_id}/cancel",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel invoice",
    description="Cancel an invoice (ADMIN only)",
)
async def cancel_invoice(
    invoice_id: int,
    reason: Optional[str] = Query(default=None, description="Cancellation reason"),
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    """
    Cancel an invoice.

    WHAT: Transitions invoice to CANCELLED status.

    WHY: Cancel invoices when:
    - Created in error
    - Client cancels
    - Superseded by new invoice

    Constraint: Paid or refunded invoices cannot be cancelled.

    Args:
        invoice_id: Invoice ID
        reason: Optional cancellation reason
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated invoice data

    Raises:
        ResourceNotFoundError (404): If invoice not found
        InvalidStateTransitionError (400): If invoice cannot be cancelled
    """
    invoice_dao = InvoiceDAO(db)

    invoice = await invoice_dao.cancel_invoice(invoice_id, current_user.org_id, reason=reason)

    if not invoice:
        existing = await invoice_dao.get_by_id_and_org(invoice_id, current_user.org_id)
        if not existing:
            raise ResourceNotFoundError(
                message=f"Invoice with id {invoice_id} not found",
                resource_type="Invoice",
                resource_id=invoice_id,
            )
        raise InvalidStateTransitionError(
            message="Paid or refunded invoices cannot be cancelled",
            current_state=existing.status.value,
            requested_state="cancelled",
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="invoice",
        resource_id=invoice_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes={"status": {"after": "cancelled"}, "reason": reason},
    )

    return _invoice_to_response(invoice)


@router.post(
    "/{invoice_id}/record-payment",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Record payment",
    description="Record a manual payment (ADMIN only)",
)
async def record_payment(
    invoice_id: int,
    data: PaymentRecord,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    """
    Record a manual payment.

    WHAT: Records payment received outside Stripe.

    WHY: Supports offline payments:
    - Check payments
    - Bank transfers
    - Cash payments

    Args:
        invoice_id: Invoice ID
        data: Payment details
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated invoice data

    Raises:
        ResourceNotFoundError (404): If invoice not found
        InvalidStateTransitionError (400): If invoice cannot accept payment
    """
    invoice_dao = InvoiceDAO(db)

    invoice = await invoice_dao.record_partial_payment(
        invoice_id,
        current_user.org_id,
        amount=data.amount,
        payment_method=data.payment_method,
    )

    if not invoice:
        existing = await invoice_dao.get_by_id_and_org(invoice_id, current_user.org_id)
        if not existing:
            raise ResourceNotFoundError(
                message=f"Invoice with id {invoice_id} not found",
                resource_type="Invoice",
                resource_id=invoice_id,
            )
        raise InvalidStateTransitionError(
            message="Invoice cannot accept payments in current status",
            current_state=existing.status.value,
            requested_state="payment",
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="invoice",
        resource_id=invoice_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes={
            "payment_amount": float(data.amount),
            "payment_method": data.payment_method,
            "new_status": invoice.status.value,
        },
    )

    return _invoice_to_response(invoice)


# ============================================================================
# Payment Endpoints (Stripe Integration)
# ============================================================================


@payments_router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create checkout session",
    description="Create a Stripe Checkout Session for invoice payment",
)
async def create_checkout_session(
    invoice_id: int = Query(..., description="Invoice ID to pay"),
    data: CheckoutRequest = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
) -> CheckoutResponse:
    """
    Create a Stripe Checkout Session.

    WHAT: Creates a hosted payment page for invoice.

    WHY: Checkout Sessions provide:
    - PCI-compliant payment collection
    - Support for multiple payment methods
    - Built-in fraud protection

    Args:
        invoice_id: Invoice to create checkout for
        data: Checkout configuration with redirect URLs
        current_user: Current authenticated user
        db: Database session
        stripe_service: Stripe service instance

    Returns:
        Checkout session details with redirect URL

    Raises:
        ResourceNotFoundError (404): If invoice not found
        ValidationError (400): If invoice not payable
    """
    invoice_dao = InvoiceDAO(db)

    invoice = await invoice_dao.get_by_id_and_org(invoice_id, current_user.org_id)
    if not invoice:
        raise ResourceNotFoundError(
            message=f"Invoice with id {invoice_id} not found",
            resource_type="Invoice",
            resource_id=invoice_id,
        )

    # Verify invoice is payable
    payable_statuses = [InvoiceStatusModel.SENT, InvoiceStatusModel.PARTIALLY_PAID, InvoiceStatusModel.OVERDUE]
    if invoice.status not in payable_statuses:
        raise ValidationError(
            message="Invoice is not in a payable status",
            invoice_id=invoice_id,
            current_status=invoice.status.value,
        )

    # Get or create Stripe customer
    from sqlalchemy import select
    result = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = result.scalar_one()

    customer = await stripe_service.get_or_create_customer(
        org_id=org.id,
        org_name=org.name,
        email=current_user.email,
        existing_customer_id=org.stripe_customer_id,
    )

    # Update org with customer ID if new
    if not org.stripe_customer_id:
        org.stripe_customer_id = customer.id
        await db.commit()

    # Create checkout session
    session = await stripe_service.create_checkout_session(
        invoice=invoice,
        customer_id=customer.id,
        success_url=data.success_url,
        cancel_url=data.cancel_url,
    )

    # Update invoice with checkout session ID
    await invoice_dao.update_stripe_checkout_session(invoice_id, current_user.org_id, session.id)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="checkout_session",
        resource_id=0,  # Session ID is string
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"session_id": session.id, "invoice_id": invoice_id},
    )

    return CheckoutResponse(
        checkout_session_id=session.id,
        checkout_url=session.url,
    )


@payments_router.get(
    "/checkout/{session_id}/status",
    response_model=CheckoutStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get checkout status",
    description="Get the status of a Stripe Checkout Session",
)
async def get_checkout_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
    stripe_service: StripeService = Depends(get_stripe_service),
) -> CheckoutStatusResponse:
    """
    Get Checkout Session status.

    WHAT: Retrieves current status of checkout session.

    WHY: Enables:
    - Polling for payment completion
    - Verifying payment status
    - Handling redirects

    Args:
        session_id: Stripe Checkout Session ID
        current_user: Current authenticated user
        stripe_service: Stripe service instance

    Returns:
        Checkout session status
    """
    session = await stripe_service.get_checkout_session(session_id)

    return CheckoutStatusResponse(
        session_id=session.id,
        status=session.status.value,
        payment_status=None,  # Would come from payment intent
    )


# ============================================================================
# Webhook Endpoints
# ============================================================================


@webhooks_router.post(
    "/stripe",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook",
    description="Handle Stripe webhook events (no auth required)",
)
async def handle_stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Handle Stripe webhook events.

    WHAT: Processes payment events from Stripe.

    WHY: Webhook handling enables:
    - Reliable payment status updates
    - Async payment confirmation
    - Refund handling

    Security: Uses signature verification to validate
    webhook came from Stripe (OWASP A02).

    Note: No authentication required - uses signature verification.

    Args:
        request: Raw request with webhook payload
        db: Database session

    Returns:
        Success acknowledgment

    Raises:
        StripeError: If signature verification fails
    """
    stripe_service = StripeService()
    invoice_dao = InvoiceDAO(db)

    # Get raw payload and signature
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    # Verify and parse event
    try:
        event = stripe_service.verify_webhook_signature(payload, signature)
    except StripeError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Handle events
    if event.type == "checkout.session.completed":
        session_data = event.data
        invoice = await invoice_dao.get_by_stripe_checkout_session(session_data.get("id"))
        if invoice:
            await invoice_dao.mark_paid(
                invoice.id,
                invoice.org_id,
                payment_method="card",
                stripe_payment_intent_id=session_data.get("payment_intent"),
            )

            # Audit log
            audit_service = AuditService(db)
            await audit_service.log_update(
                resource_type="invoice",
                resource_id=invoice.id,
                actor_user_id=None,  # System action
                org_id=invoice.org_id,
                changes={
                    "status": {"after": "paid"},
                    "payment_intent_id": session_data.get("payment_intent"),
                    "source": "stripe_webhook",
                },
            )

    elif event.type == "charge.refunded":
        charge_data = event.data
        payment_intent_id = charge_data.get("payment_intent")
        if payment_intent_id:
            invoice = await invoice_dao.get_by_stripe_payment_intent(payment_intent_id)
            if invoice:
                await invoice_dao.mark_refunded(invoice.id, invoice.org_id)

                # Audit log
                audit_service = AuditService(db)
                await audit_service.log_update(
                    resource_type="invoice",
                    resource_id=invoice.id,
                    actor_user_id=None,
                    org_id=invoice.org_id,
                    changes={"status": {"after": "refunded"}, "source": "stripe_webhook"},
                )

    return {"status": "received"}
