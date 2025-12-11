"""
Stripe payment service for invoice payment processing.

WHAT: Provides a unified interface for Stripe payment operations including
customer management, checkout sessions, and webhook handling.

WHY: Payment processing is critical for:
1. Collecting payments for approved proposals (PAY-002)
2. Tracking payment status through webhooks (PAY-003)
3. Managing customer data for repeat billing
4. Generating receipts and payment confirmations

HOW: Uses the Stripe Python SDK with:
- Customer management (lazy creation per organization)
- Checkout Sessions for secure hosted payment pages
- Webhook handling for async payment status updates
- Signature verification for webhook security (OWASP A02)

Design decisions:
- Customer per organization: Enables future subscription billing
- Checkout Sessions over direct charges: PCI compliance, hosted payment page
- Webhook-first status updates: More reliable than polling
- Service class pattern: Testable with mocked Stripe SDK
"""

import logging
import hmac
import hashlib
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any

import stripe

from app.core.config import settings
from app.core.exceptions import StripeError, ValidationError
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)


# ============================================================================
# Stripe Configuration
# ============================================================================


def configure_stripe() -> None:
    """
    Configure Stripe SDK with API key from settings.

    WHAT: Sets up the Stripe SDK with the secret key.

    WHY: Must be called before any Stripe API operations.
    Centralized configuration ensures consistent setup.

    HOW: Sets the stripe.api_key module-level variable.
    """
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = "2023-10-16"  # Pin API version for stability


# Initialize Stripe on module load
configure_stripe()


# ============================================================================
# Data Classes
# ============================================================================


class CheckoutSessionStatus(str, Enum):
    """
    Stripe Checkout Session status values.

    WHY: Enum for type safety when handling session status.
    """

    OPEN = "open"
    COMPLETE = "complete"
    EXPIRED = "expired"


@dataclass
class StripeCustomer:
    """
    Represents a Stripe customer.

    WHAT: Data container for customer information from Stripe.

    WHY: Structured data for consistent handling of customer info.
    """

    id: str
    """Stripe customer ID (cus_xxx)."""

    email: Optional[str] = None
    """Customer email address."""

    name: Optional[str] = None
    """Customer name."""

    metadata: Optional[Dict[str, str]] = None
    """Custom metadata attached to customer."""


@dataclass
class CheckoutSession:
    """
    Represents a Stripe Checkout Session.

    WHAT: Data container for checkout session information.

    WHY: Provides structured access to checkout session data
    for payment flow handling.
    """

    id: str
    """Stripe Checkout Session ID (cs_xxx)."""

    url: str
    """URL to redirect user to for payment."""

    status: CheckoutSessionStatus
    """Current session status."""

    payment_intent_id: Optional[str] = None
    """Associated PaymentIntent ID (pi_xxx) after completion."""

    amount_total: Optional[int] = None
    """Total amount in cents."""

    currency: str = "usd"
    """Currency code."""

    customer_id: Optional[str] = None
    """Associated customer ID."""

    metadata: Optional[Dict[str, str]] = None
    """Custom metadata."""


@dataclass
class PaymentIntent:
    """
    Represents a Stripe PaymentIntent.

    WHAT: Data container for payment intent information.

    WHY: Provides structured access to payment data
    for status tracking and confirmation.
    """

    id: str
    """Stripe PaymentIntent ID (pi_xxx)."""

    amount: int
    """Amount in cents."""

    currency: str
    """Currency code."""

    status: str
    """Payment status (succeeded, processing, requires_payment_method, etc.)."""

    customer_id: Optional[str] = None
    """Associated customer ID."""

    metadata: Optional[Dict[str, str]] = None
    """Custom metadata."""


@dataclass
class WebhookEvent:
    """
    Represents a verified Stripe webhook event.

    WHAT: Data container for webhook event data.

    WHY: Structured event data for type-safe webhook handling.
    """

    id: str
    """Event ID (evt_xxx)."""

    type: str
    """Event type (e.g., checkout.session.completed)."""

    data: Dict[str, Any]
    """Event data object."""

    created: int
    """Unix timestamp when event was created."""


# ============================================================================
# Stripe Service
# ============================================================================


class StripeService:
    """
    Service for Stripe payment operations.

    WHAT: High-level interface for Stripe payment processing.

    WHY: Centralizes Stripe integration:
    - Customer management
    - Checkout session creation
    - Payment status tracking
    - Webhook handling

    HOW: Uses Stripe Python SDK with proper error handling
    and audit logging for all payment operations.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Stripe service.

        WHAT: Sets up Stripe service with optional API key override.

        WHY: Allows testing with different API keys (test vs live).

        Args:
            api_key: Optional Stripe API key (defaults to settings)
        """
        if api_key:
            stripe.api_key = api_key

    # ========================================================================
    # Customer Management
    # ========================================================================

    async def get_or_create_customer(
        self,
        org_id: int,
        org_name: str,
        email: str,
        existing_customer_id: Optional[str] = None,
    ) -> StripeCustomer:
        """
        Get existing Stripe customer or create new one.

        WHAT: Ensures organization has a Stripe customer record.

        WHY: Lazy customer creation:
        - Only creates customer when first payment is made
        - Links customer to organization for future payments
        - Enables saved payment methods and subscriptions

        HOW: Checks if existing_customer_id is valid, creates new if not.

        Args:
            org_id: Organization ID (stored in metadata)
            org_name: Organization name
            email: Contact email for receipts
            existing_customer_id: Optional existing Stripe customer ID

        Returns:
            StripeCustomer with Stripe customer details

        Raises:
            StripeError: If Stripe API call fails
        """
        try:
            # Try to retrieve existing customer if ID provided
            if existing_customer_id:
                try:
                    customer = stripe.Customer.retrieve(existing_customer_id)
                    if not customer.get("deleted", False):
                        return StripeCustomer(
                            id=customer["id"],
                            email=customer.get("email"),
                            name=customer.get("name"),
                            metadata=customer.get("metadata"),
                        )
                except stripe.StripeError:
                    # Customer not found or deleted, create new one
                    pass

            # Create new customer
            customer = stripe.Customer.create(
                name=org_name,
                email=email,
                metadata={
                    "org_id": str(org_id),
                    "source": "automation_platform",
                },
            )

            logger.info(
                f"Created Stripe customer {customer['id']} for org {org_id}",
                extra={
                    "stripe_customer_id": customer["id"],
                    "org_id": org_id,
                },
            )

            return StripeCustomer(
                id=customer["id"],
                email=customer.get("email"),
                name=customer.get("name"),
                metadata=customer.get("metadata"),
            )

        except stripe.StripeError as e:
            logger.error(f"Stripe customer error: {e}", extra={"org_id": org_id})
            raise StripeError(
                message="Failed to create payment customer",
                stripe_error=str(e),
                org_id=org_id,
            )

    # ========================================================================
    # Checkout Sessions
    # ========================================================================

    async def create_checkout_session(
        self,
        invoice: Invoice,
        customer_id: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        """
        Create a Stripe Checkout Session for invoice payment.

        WHAT: Creates a hosted checkout page for collecting payment.

        WHY: Checkout Sessions provide:
        - PCI-compliant hosted payment page
        - Support for multiple payment methods
        - Built-in fraud protection
        - Automatic receipt emails

        HOW: Creates session with invoice details and redirect URLs.

        Args:
            invoice: Invoice to create payment for
            customer_id: Stripe customer ID
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment cancelled

        Returns:
            CheckoutSession with session details and redirect URL

        Raises:
            StripeError: If Stripe API call fails
            ValidationError: If invoice amount is invalid
        """
        if invoice.total <= 0:
            raise ValidationError(
                message="Invoice total must be greater than zero",
                invoice_id=invoice.id,
                total=str(invoice.total),
            )

        # Convert decimal to cents
        amount_cents = int(invoice.total * 100)

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                customer=customer_id,
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"Invoice {invoice.invoice_number}",
                                "description": f"Payment for invoice {invoice.invoice_number}",
                            },
                            "unit_amount": amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                metadata={
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "org_id": str(invoice.org_id),
                },
                success_url=success_url,
                cancel_url=cancel_url,
                # Enable customer email for receipts
                customer_update={
                    "address": "auto",
                },
            )

            logger.info(
                f"Created checkout session {session['id']} for invoice {invoice.id}",
                extra={
                    "checkout_session_id": session["id"],
                    "invoice_id": invoice.id,
                    "amount_cents": amount_cents,
                },
            )

            return CheckoutSession(
                id=session["id"],
                url=session["url"],
                status=CheckoutSessionStatus(session["status"]),
                payment_intent_id=session.get("payment_intent"),
                amount_total=session.get("amount_total"),
                currency=session.get("currency", "usd"),
                customer_id=session.get("customer"),
                metadata=session.get("metadata"),
            )

        except stripe.StripeError as e:
            logger.error(
                f"Stripe checkout session error: {e}",
                extra={"invoice_id": invoice.id},
            )
            raise StripeError(
                message="Failed to create checkout session",
                stripe_error=str(e),
                invoice_id=invoice.id,
            )

    async def get_checkout_session(
        self,
        session_id: str,
    ) -> CheckoutSession:
        """
        Retrieve a Checkout Session by ID.

        WHAT: Gets current status of a checkout session.

        WHY: Used to verify payment completion and get PaymentIntent ID.

        Args:
            session_id: Stripe Checkout Session ID

        Returns:
            CheckoutSession with current status

        Raises:
            StripeError: If session not found or API error
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id)

            return CheckoutSession(
                id=session["id"],
                url=session.get("url", ""),
                status=CheckoutSessionStatus(session["status"]),
                payment_intent_id=session.get("payment_intent"),
                amount_total=session.get("amount_total"),
                currency=session.get("currency", "usd"),
                customer_id=session.get("customer"),
                metadata=session.get("metadata"),
            )

        except stripe.StripeError as e:
            logger.error(f"Stripe session retrieval error: {e}")
            raise StripeError(
                message="Failed to retrieve checkout session",
                stripe_error=str(e),
                session_id=session_id,
            )

    # ========================================================================
    # Payment Intents
    # ========================================================================

    async def get_payment_intent(
        self,
        payment_intent_id: str,
    ) -> PaymentIntent:
        """
        Retrieve a PaymentIntent by ID.

        WHAT: Gets payment details and status.

        WHY: Used to confirm payment status and get transaction details.

        Args:
            payment_intent_id: Stripe PaymentIntent ID

        Returns:
            PaymentIntent with payment details

        Raises:
            StripeError: If payment intent not found or API error
        """
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            return PaymentIntent(
                id=intent["id"],
                amount=intent["amount"],
                currency=intent["currency"],
                status=intent["status"],
                customer_id=intent.get("customer"),
                metadata=intent.get("metadata"),
            )

        except stripe.StripeError as e:
            logger.error(f"Stripe payment intent error: {e}")
            raise StripeError(
                message="Failed to retrieve payment intent",
                stripe_error=str(e),
                payment_intent_id=payment_intent_id,
            )

    # ========================================================================
    # Refunds
    # ========================================================================

    async def create_refund(
        self,
        payment_intent_id: str,
        amount_cents: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a refund for a PaymentIntent.

        WHAT: Refunds a payment (full or partial).

        WHY: Enables:
        - Customer refund requests
        - Invoice cancellation after payment
        - Partial refunds for disputes

        Args:
            payment_intent_id: PaymentIntent to refund
            amount_cents: Optional partial refund amount in cents
            reason: Optional refund reason

        Returns:
            Refund object with refund details

        Raises:
            StripeError: If refund fails
        """
        try:
            refund_params: Dict[str, Any] = {
                "payment_intent": payment_intent_id,
            }

            if amount_cents:
                refund_params["amount"] = amount_cents

            if reason:
                refund_params["reason"] = reason

            refund = stripe.Refund.create(**refund_params)

            logger.info(
                f"Created refund {refund['id']} for payment {payment_intent_id}",
                extra={
                    "refund_id": refund["id"],
                    "payment_intent_id": payment_intent_id,
                    "amount": amount_cents,
                },
            )

            return refund

        except stripe.StripeError as e:
            logger.error(f"Stripe refund error: {e}")
            raise StripeError(
                message="Failed to create refund",
                stripe_error=str(e),
                payment_intent_id=payment_intent_id,
            )

    # ========================================================================
    # Webhook Handling
    # ========================================================================

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: Optional[str] = None,
    ) -> WebhookEvent:
        """
        Verify Stripe webhook signature and parse event.

        WHAT: Validates that webhook came from Stripe.

        WHY: Security critical (OWASP A02):
        - Prevents webhook forgery attacks
        - Ensures data integrity
        - Required for PCI compliance

        HOW: Uses Stripe's signature verification with HMAC-SHA256.

        Args:
            payload: Raw request body bytes
            signature: Stripe-Signature header value
            webhook_secret: Optional webhook signing secret (defaults to settings)

        Returns:
            WebhookEvent with verified event data

        Raises:
            StripeError: If signature verification fails
        """
        secret = webhook_secret or settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                secret,
            )

            logger.info(
                f"Verified webhook event {event['id']} type {event['type']}",
                extra={
                    "event_id": event["id"],
                    "event_type": event["type"],
                },
            )

            return WebhookEvent(
                id=event["id"],
                type=event["type"],
                data=event["data"]["object"],
                created=event["created"],
            )

        except stripe.error.SignatureVerificationError as e:
            logger.warning(f"Webhook signature verification failed: {e}")
            raise StripeError(
                message="Invalid webhook signature",
                stripe_error=str(e),
            )
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            raise StripeError(
                message="Webhook processing failed",
                stripe_error=str(e),
            )

    def is_payment_successful(self, payment_intent: PaymentIntent) -> bool:
        """
        Check if a PaymentIntent represents successful payment.

        WHAT: Determines if payment has completed.

        WHY: Simplifies payment status checking in business logic.

        Args:
            payment_intent: PaymentIntent to check

        Returns:
            True if payment succeeded
        """
        return payment_intent.status == "succeeded"


# ============================================================================
# Module-level convenience functions
# ============================================================================


_stripe_service: Optional[StripeService] = None


def get_stripe_service() -> StripeService:
    """
    Get or create the global Stripe service instance.

    WHY: Singleton pattern ensures consistent configuration
    and resource sharing across the application.

    Returns:
        StripeService instance
    """
    global _stripe_service

    if _stripe_service is None:
        _stripe_service = StripeService()

    return _stripe_service
