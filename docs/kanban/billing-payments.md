# Billing & Payments Sub-Board

**Parent**: Master Kanban Board
**Sprint**: 4 (Billing & Payments)
**Focus**: Stripe integration, invoice management, PDF generation

---

## 🔴 Blocked

*None currently*

---

## 🟡 In Progress

*None currently*

---

## ⚪ Todo (Priority Order)

### PAY-001: Invoice Model + DAO (3 points)
**Priority**: P1
**Dependencies**: PROJ-001

**Description**:
Create Invoice SQLAlchemy model and DAO.

**Fields**:
- id, org_id, proposal_id, stripe_invoice_id
- invoice_number, amount, tax, total
- status (PENDING, PAID, FAILED, REFUNDED)
- pdf_url, paid_at
- created_at, updated_at

**Acceptance Criteria**:
- [ ] Model with all fields
- [ ] DAO with CRUD operations
- [ ] Invoice number generation
- [ ] Org-scoped queries
- [ ] Unit tests

---

### PAY-002: Stripe Service Setup (5 points)
**Priority**: P1
**Dependencies**: None

**Description**:
Configure Stripe SDK and service layer.

**Acceptance Criteria**:
- [ ] stripe-python installed
- [ ] Stripe API key from env
- [ ] StripeService class created
- [ ] Error handling (StripeError exception)
- [ ] Webhook secret configured
- [ ] Test mode toggle

---

### PAY-003: Stripe Customer Creation (3 points)
**Priority**: P1
**Dependencies**: ORG-001, PAY-002

**Description**:
Create Stripe customer for organization.

**Acceptance Criteria**:
- [ ] Customer created on org creation or first payment
- [ ] Stripe customer ID stored in org
- [ ] Customer email from org billing contact
- [ ] Idempotent (don't create if exists)

---

### PAY-004: Checkout Session Endpoint (8 points)
**Priority**: P1
**Dependencies**: PAY-002, PROP-001

**Description**:
Create Stripe Checkout session for proposal payment.

**Acceptance Criteria**:
- [ ] POST /api/billing/checkout
- [ ] Proposal must be APPROVED
- [ ] Line items from proposal
- [ ] Success/cancel URLs configured
- [ ] Returns checkout URL
- [ ] Session ID stored for webhook matching

---

### PAY-005: Stripe Webhook Handler (13 points)
**Priority**: P0 (Critical)
**Dependencies**: PAY-002, PAY-001

**Description**:
Handle Stripe webhook events for payment processing.

**Events to Handle**:
- checkout.session.completed
- payment_intent.succeeded
- payment_intent.failed
- invoice.paid
- customer.subscription.updated

**Acceptance Criteria**:
- [ ] POST /api/webhooks/stripe
- [ ] Signature verification (PAY-006)
- [ ] Event type routing
- [ ] Idempotent processing (store event IDs)
- [ ] Create invoice on payment success
- [ ] Update project status
- [ ] Error handling and logging

**Security Review**:
- Signature verification required (OWASP A08)
- IP allowlisting (Stripe IPs) optional
- Replay protection via event ID

---

### PAY-006: Webhook Signature Verification (3 points)
**Priority**: P0 (Critical)
**Dependencies**: PAY-005

**Description**:
Verify Stripe webhook signatures.

**Acceptance Criteria**:
- [ ] Use stripe.Webhook.construct_event()
- [ ] Webhook secret from env
- [ ] Reject invalid signatures with 400
- [ ] Log verification failures
- [ ] Tests for valid/invalid signatures

---

### PAY-007: Invoice Generation on Payment (5 points)
**Priority**: P1
**Dependencies**: PAY-005

**Description**:
Auto-generate invoice when payment succeeds.

**Acceptance Criteria**:
- [ ] Invoice created in database
- [ ] Invoice number generated
- [ ] PDF generated (PDF-003)
- [ ] Email sent to client
- [ ] Audit log entry

---

### PAY-008: Payment UI (Checkout Flow) (8 points)
**Priority**: P1
**Dependencies**: PAY-004

**Description**:
Frontend payment flow from proposal approval.

**Acceptance Criteria**:
- [ ] "Pay Now" button on approved proposal
- [ ] Loading state during checkout creation
- [ ] Redirect to Stripe Checkout
- [ ] Success page after payment
- [ ] Cancel handling

---

### PAY-009: Invoice List/Detail UI (5 points)
**Priority**: P1
**Dependencies**: PAY-001

**Description**:
Frontend pages for viewing invoices.

**Acceptance Criteria**:
- [ ] Invoice list with status badges
- [ ] Filter by status, date range
- [ ] Invoice detail view
- [ ] PDF download button
- [ ] Payment history

---

### PAY-010: Subscription Management (13 points)
**Priority**: P2
**Dependencies**: PAY-002

**Description**:
Recurring billing for ongoing services.

**Acceptance Criteria**:
- [ ] Subscription model
- [ ] Create subscription endpoint
- [ ] Stripe subscription sync
- [ ] Usage-based add-ons
- [ ] Cancellation flow
- [ ] Subscription status UI

---

### PDF-001: PDF Generation Service (8 points)
**Priority**: P1
**Dependencies**: PROP-001

**Description**:
Service for generating PDF documents.

**Technology**: WeasyPrint

**Acceptance Criteria**:
- [ ] WeasyPrint installed
- [ ] PDF service class
- [ ] HTML template rendering
- [ ] CSS styling for print
- [ ] S3/local storage
- [ ] Async generation (background job)

---

### PDF-002: Proposal PDF Template (5 points)
**Priority**: P1
**Dependencies**: PDF-001

**Description**:
PDF template for proposals.

**Acceptance Criteria**:
- [ ] Company branding header
- [ ] Client information
- [ ] Line items table
- [ ] Subtotal, tax, total
- [ ] Terms and conditions
- [ ] Signature block
- [ ] Professional styling

---

### PDF-003: Invoice PDF Template (5 points)
**Priority**: P1
**Dependencies**: PDF-001

**Description**:
PDF template for invoices.

**Acceptance Criteria**:
- [ ] Company branding header
- [ ] Invoice number and date
- [ ] Bill to / Ship to
- [ ] Line items from proposal
- [ ] Payment status
- [ ] Payment instructions
- [ ] Tax details

---

## Stripe Integration Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │────▶│    Stripe    │
│              │     │              │     │              │
│ 1. Click Pay │     │ 2. Create    │     │ 3. Checkout  │
│              │◀────│    Session   │◀────│    Page      │
│ 4. Redirect  │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                             ▲
                             │ 5. Webhook
                             │
                     ┌───────┴───────┐
                     │ payment_intent│
                     │   .succeeded  │
                     └───────────────┘
```

## Webhook Processing Flow

```
POST /api/webhooks/stripe
    │
    ├── Verify Signature
    │   └── Invalid? → 400 Bad Request
    │
    ├── Parse Event
    │
    ├── Check Idempotency (event_id in processed_events?)
    │   └── Already processed? → 200 OK (skip)
    │
    ├── Route by event.type
    │   ├── checkout.session.completed
    │   │   └── Create invoice, update project
    │   ├── payment_intent.succeeded
    │   │   └── Mark invoice paid
    │   ├── payment_intent.failed
    │   │   └── Log failure, notify admin
    │   └── customer.subscription.*
    │       └── Update subscription status
    │
    ├── Store event_id
    │
    └── Return 200 OK
```

## Definition of Done

- [ ] TDD: Tests written FIRST
- [ ] All tests passing
- [ ] Code coverage >= 80%
- [ ] Stripe test mode verified
- [ ] Webhook signature tests
- [ ] Security review (OWASP)
- [ ] Documentation (WHAT/WHY/HOW)
- [ ] Code review approved
