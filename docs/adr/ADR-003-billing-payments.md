# ADR-003: Billing & Payments Architecture

## Status
Accepted

## Context
The platform needs to handle payments for approved proposals and generate invoices. We need:
1. Invoice management for tracking payments
2. Stripe integration for payment processing
3. PDF generation for proposals and invoices
4. Webhook handling for payment status updates

Key requirements:
- Support one-time payments from approved proposals
- Track invoice status (draft, sent, paid, overdue, cancelled)
- Generate professional PDF documents
- Handle Stripe webhooks securely
- Maintain audit trail for all payment activities

## Decision

### Invoice Model
- Create Invoice model linked to Proposal (1:1 relationship on approval)
- Track payment status with clear state machine
- Store Stripe payment IDs for reference
- Include payment method and transaction details

Invoice statuses:
- DRAFT: Invoice created but not sent
- SENT: Invoice sent to client
- PAID: Payment received
- PARTIALLY_PAID: Partial payment received
- OVERDUE: Past due date without full payment
- CANCELLED: Invoice cancelled
- REFUNDED: Payment refunded

### Stripe Integration
- Use Stripe Checkout Sessions for payment collection
- Create Stripe customers for organizations (lazy creation)
- Store minimal Stripe data (customer_id on org, payment_intent_id on invoice)
- Implement webhook handler for payment events
- Use signature verification for webhook security

Key Stripe events to handle:
- checkout.session.completed: Payment successful
- payment_intent.succeeded: Confirm payment
- payment_intent.payment_failed: Handle failure
- charge.refunded: Handle refunds

### PDF Generation
- Use ReportLab for PDF generation (pure Python, no external dependencies)
- Create reusable templates for proposals and invoices
- Include company branding, line items, totals
- Generate PDFs on-demand (not stored)
- Return as downloadable attachment

### API Endpoints

Invoices:
- GET /api/invoices - List invoices (paginated, filterable)
- GET /api/invoices/:id - Get invoice details
- POST /api/invoices - Create invoice manually (admin)
- PATCH /api/invoices/:id - Update invoice (draft only)
- DELETE /api/invoices/:id - Delete invoice (draft only)
- POST /api/invoices/:id/send - Send invoice to client
- GET /api/invoices/:id/pdf - Download invoice PDF

Payments:
- POST /api/payments/checkout - Create Stripe checkout session
- GET /api/payments/checkout/:id/status - Check payment status
- POST /api/webhooks/stripe - Stripe webhook handler (no auth)

Proposals (PDF):
- GET /api/proposals/:id/pdf - Download proposal PDF

## Consequences

### Positive
- Stripe handles PCI compliance
- Checkout Sessions provide secure, hosted payment pages
- Webhook-based updates ensure data consistency
- PDF generation on-demand reduces storage
- Clear status tracking for business processes

### Negative
- Stripe dependency for payments (but standard choice)
- Webhook reliability depends on Stripe
- PDF generation is synchronous (could be slow for large documents)

### Mitigations
- Implement webhook retry logic
- Cache checkout session status
- Add background job option for bulk PDF generation later

## Implementation Guide

### Phase 1: Invoice Model & DAO (PAY-001)
1. Create Invoice model with status enum
2. Create migration for invoices table
3. Implement InvoiceDAO with CRUD + workflow methods
4. Add unit tests (target: 20+ tests)

### Phase 2: Stripe Service (PAY-002, PAY-003)
1. Create StripeService class with configuration
2. Implement customer creation/retrieval
3. Add stripe_customer_id to Organization model
4. Create checkout session creation method
5. Add unit tests with mocked Stripe API

### Phase 3: Payment Endpoints (PAY-004, PAY-005, PAY-006)
1. Create payments router
2. Implement checkout session endpoint
3. Create webhook handler with signature verification
4. Handle payment success/failure events
5. Add integration tests

### Phase 4: Invoice Generation (PAY-007)
1. Auto-create invoice when proposal approved with payment
2. Update invoice status on payment success
3. Send payment confirmation email
4. Add audit logging

### Phase 5: PDF Service (PDF-001, PDF-002, PDF-003)
1. Create PDFService using ReportLab
2. Design proposal PDF template
3. Design invoice PDF template
4. Add PDF download endpoints
5. Add unit tests

### Phase 6: Frontend (PAY-008, PAY-009)
1. Create invoice list page
2. Create invoice detail page
3. Implement checkout flow
4. Add payment status display
5. Add PDF download buttons

## Security Considerations
- Stripe webhook signature verification (OWASP A02)
- No storage of card details - Stripe handles this (PCI DSS)
- Org-scoped invoice access (OWASP A01)
- Audit logging for all payment events (OWASP A09)
- Rate limiting on payment endpoints

## Database Schema

```sql
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    proposal_id INTEGER REFERENCES proposals(id),
    org_id INTEGER NOT NULL REFERENCES organizations(id),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',

    -- Amounts (copied from proposal for immutability)
    subtotal NUMERIC(10,2) NOT NULL,
    discount_amount NUMERIC(10,2) DEFAULT 0,
    tax_amount NUMERIC(10,2) DEFAULT 0,
    total NUMERIC(10,2) NOT NULL,
    amount_paid NUMERIC(10,2) DEFAULT 0,

    -- Payment details
    stripe_payment_intent_id VARCHAR(255),
    stripe_checkout_session_id VARCHAR(255),
    payment_method VARCHAR(50),

    -- Dates
    issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date DATE,
    paid_at TIMESTAMP,
    sent_at TIMESTAMP,

    -- Notes
    notes TEXT,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invoices_org_id ON invoices(org_id);
CREATE INDEX idx_invoices_proposal_id ON invoices(proposal_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_stripe_payment_intent ON invoices(stripe_payment_intent_id);

-- Add stripe_customer_id to organizations
ALTER TABLE organizations ADD COLUMN stripe_customer_id VARCHAR(255);
```
