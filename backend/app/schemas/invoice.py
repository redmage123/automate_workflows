"""
Invoice schemas for API request/response validation.

WHAT: Pydantic schemas for invoice data validation.

WHY: Schemas provide:
1. Type-safe request/response handling
2. Automatic validation with clear error messages
3. OpenAPI documentation generation
4. Data serialization/deserialization

HOW: Uses Pydantic v2 with Field validators and model_config.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, model_validator, ConfigDict


# ============================================================================
# Enums (matching model enums for API)
# ============================================================================


class InvoiceStatus(str, Enum):
    """
    Invoice status values for API responses.

    WHY: String enum for clean JSON serialization
    matching the model's InvoiceStatus.
    """

    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# ============================================================================
# Request Schemas
# ============================================================================


class InvoiceCreate(BaseModel):
    """
    Schema for creating an invoice.

    WHY: Manual invoice creation for:
    - Non-proposal billing
    - Custom invoices
    - One-time charges

    Note: Most invoices are auto-created from approved proposals.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    proposal_id: Optional[int] = Field(
        default=None,
        description="Associated proposal ID (optional)",
    )
    subtotal: Decimal = Field(
        ...,
        ge=0,
        description="Subtotal before discounts and tax",
    )
    discount_amount: Optional[Decimal] = Field(
        default=Decimal(0),
        ge=0,
        description="Discount amount",
    )
    tax_amount: Optional[Decimal] = Field(
        default=Decimal(0),
        ge=0,
        description="Tax amount",
    )
    total: Decimal = Field(
        ...,
        gt=0,
        description="Total amount due",
    )
    issue_date: Optional[date] = Field(
        default=None,
        description="Invoice issue date (defaults to today)",
    )
    due_date: Optional[date] = Field(
        default=None,
        description="Payment due date",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Internal notes",
    )


class InvoiceUpdate(BaseModel):
    """
    Schema for updating an invoice (draft only).

    WHY: Allows editing before sending:
    - Adjust amounts
    - Change dates
    - Add notes
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    subtotal: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Subtotal before discounts and tax",
    )
    discount_amount: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Discount amount",
    )
    tax_amount: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Tax amount",
    )
    total: Optional[Decimal] = Field(
        default=None,
        gt=0,
        description="Total amount due",
    )
    due_date: Optional[date] = Field(
        default=None,
        description="Payment due date",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Internal notes",
    )


class CheckoutRequest(BaseModel):
    """
    Schema for creating a Stripe Checkout Session.

    WHY: Initiates payment flow:
    - Provides redirect URLs
    - Associates with invoice
    """

    success_url: str = Field(
        ...,
        description="URL to redirect after successful payment",
    )
    cancel_url: str = Field(
        ...,
        description="URL to redirect if payment cancelled",
    )


class PaymentRecord(BaseModel):
    """
    Schema for recording a manual payment.

    WHY: Supports offline payments:
    - Check payments
    - Bank transfers
    - Cash payments
    """

    amount: Decimal = Field(
        ...,
        gt=0,
        description="Payment amount received",
    )
    payment_method: Optional[str] = Field(
        default="manual",
        max_length=50,
        description="Payment method (card, check, bank_transfer, cash)",
    )


# ============================================================================
# Response Schemas
# ============================================================================


class InvoiceResponse(BaseModel):
    """
    Schema for invoice response data.

    WHY: Complete invoice data for display including:
    - All financial fields
    - Stripe references
    - Status and dates
    - Computed properties
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    status: InvoiceStatus

    # Relationships
    proposal_id: Optional[int]
    org_id: int

    # Amounts
    subtotal: float
    discount_amount: Optional[float]
    tax_amount: Optional[float]
    total: float
    amount_paid: float

    # Stripe
    stripe_payment_intent_id: Optional[str]
    stripe_checkout_session_id: Optional[str]
    payment_method: Optional[str]

    # Dates
    issue_date: date
    due_date: Optional[date]
    paid_at: Optional[datetime]
    sent_at: Optional[datetime]

    # Metadata
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Computed properties
    is_editable: bool
    is_paid: bool
    balance_due: float


class InvoiceListResponse(BaseModel):
    """
    Paginated list response for invoices.

    WHY: Standard pagination structure for list endpoints.
    """

    items: List[InvoiceResponse]
    total: int
    skip: int
    limit: int


class InvoiceStats(BaseModel):
    """
    Invoice statistics for dashboard.

    WHY: Aggregated metrics for:
    - Financial overview
    - Payment tracking
    - Status distribution
    """

    total: int = Field(description="Total number of invoices")
    by_status: Dict[str, int] = Field(description="Count by status")
    total_outstanding: float = Field(description="Total unpaid balance")
    total_paid: float = Field(description="Total payments received")


class CheckoutResponse(BaseModel):
    """
    Response for checkout session creation.

    WHY: Provides client with:
    - Checkout URL for redirect
    - Session ID for status checks
    """

    checkout_session_id: str = Field(description="Stripe Checkout Session ID")
    checkout_url: str = Field(description="URL to redirect user to")


class CheckoutStatusResponse(BaseModel):
    """
    Response for checkout session status.

    WHY: Enables polling/webhook verification:
    - Payment status
    - Completion confirmation
    """

    session_id: str
    status: str = Field(description="Session status (open, complete, expired)")
    payment_status: Optional[str] = Field(description="Payment status if applicable")
