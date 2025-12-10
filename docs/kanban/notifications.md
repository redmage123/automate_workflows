# Notifications Sub-Board

**Parent**: Master Kanban Board
**Sprint**: 6 (Ticketing & Notifications)
**Focus**: Email notifications, Slack integration, notification preferences

---

## 🔴 Blocked

*None currently*

---

## 🟡 In Progress

*None currently*

---

## ⚪ Todo (Priority Order)

### NOTIFY-001: Email Service (Resend) (5 points)
**Priority**: P2
**Dependencies**: None

**Description**:
Configure Resend SDK for transactional emails.

**Acceptance Criteria**:
- [ ] resend-python installed
- [ ] API key from environment
- [ ] EmailService class created
- [ ] send_email(to, subject, html) method
- [ ] Error handling (EmailServiceError)
- [ ] Async sending via background job
- [ ] Unit tests with mocked API

---

### NOTIFY-002: Email Templates (5 points)
**Priority**: P2
**Dependencies**: NOTIFY-001

**Description**:
Create HTML email templates for transactional emails.

**Templates**:
- welcome - New user registration
- verify_email - Email verification link
- password_reset - Password reset link
- proposal_sent - Proposal ready for review
- proposal_approved - Proposal accepted
- payment_received - Payment confirmation
- invoice_created - New invoice available
- ticket_created - Support ticket opened
- ticket_updated - Ticket status change

**Acceptance Criteria**:
- [ ] Base template with branding
- [ ] All templates created
- [ ] Variable substitution
- [ ] Responsive design
- [ ] Plain text fallback
- [ ] Preview/test endpoint (dev only)

---

### NOTIFY-003: Slack Webhook Integration (3 points)
**Priority**: P3
**Dependencies**: None

**Description**:
Send notifications to Slack channels.

**Acceptance Criteria**:
- [ ] Slack webhook URL from env
- [ ] SlackService class
- [ ] send_message(channel, message, blocks)
- [ ] Block Kit formatting
- [ ] Error handling
- [ ] Channel configuration per event type

---

### NOTIFY-004: Notification Preferences Model (3 points)
**Priority**: P3
**Dependencies**: AUTH-001

**Description**:
Store user notification preferences.

**Fields**:
- user_id
- email_on_proposal_sent (boolean)
- email_on_payment (boolean)
- email_on_ticket_update (boolean)
- slack_channel (optional)

**Acceptance Criteria**:
- [ ] Model with all fields
- [ ] DAO with CRUD operations
- [ ] Default preferences on user creation
- [ ] Preferences checked before sending

---

### NOTIFY-005: SLA Breach Email Notification (3 points)
**Priority**: P2
**Dependencies**: TICKET-006, NOTIFY-001

**Description**:
Send email when SLA is approaching or breached.

**Acceptance Criteria**:
- [ ] Template for SLA warning (75%)
- [ ] Template for SLA breach (100%)
- [ ] Sent to assigned admin
- [ ] CC support email
- [ ] Includes ticket link

---

### NOTIFY-006: Payment Confirmation Email (3 points)
**Priority**: P2
**Dependencies**: PAY-005, NOTIFY-001

**Description**:
Send email when payment is received.

**Acceptance Criteria**:
- [ ] Template with receipt details
- [ ] Invoice PDF attached
- [ ] Sent to billing contact
- [ ] Copy to admin

---

### NOTIFY-007: Project Status Update Email (3 points)
**Priority**: P2
**Dependencies**: PROJ-004, NOTIFY-001

**Description**:
Send email when project status changes.

**Acceptance Criteria**:
- [ ] Template with new status
- [ ] Previous status included
- [ ] Link to project
- [ ] Sent to org users

---

### NOTIFY-008: Proposal Ready for Review Email (3 points)
**Priority**: P2
**Dependencies**: PROP-003, NOTIFY-001

**Description**:
Send email when proposal is sent to client.

**Acceptance Criteria**:
- [ ] Template with proposal summary
- [ ] Direct link to view proposal
- [ ] Proposal PDF attached
- [ ] Sent to org billing contact

---

### NOTIFY-009: Ticket Created Email (3 points)
**Priority**: P2
**Dependencies**: TICKET-002, NOTIFY-001

**Description**:
Send email when new ticket is created.

**Acceptance Criteria**:
- [ ] Template with ticket details
- [ ] Priority indicator
- [ ] Link to ticket
- [ ] Sent to support team

---

### NOTIFY-010: Notification Preferences UI (5 points)
**Priority**: P3
**Dependencies**: NOTIFY-004

**Description**:
User interface for managing notification preferences.

**Acceptance Criteria**:
- [ ] Settings page section
- [ ] Toggle for each notification type
- [ ] Email/Slack preference per type
- [ ] Save button
- [ ] Confirmation toast

---

## Email Template Structure

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    /* Inline CSS for email clients */
  </style>
</head>
<body>
  <!-- Header with logo -->
  <table class="header">
    <tr>
      <td><img src="logo.png" alt="Automation Platform" /></td>
    </tr>
  </table>

  <!-- Main content -->
  <table class="content">
    <tr>
      <td>
        <h1>{{ title }}</h1>
        <p>{{ message }}</p>

        <!-- Action button -->
        <a href="{{ action_url }}" class="button">{{ action_text }}</a>
      </td>
    </tr>
  </table>

  <!-- Footer -->
  <table class="footer">
    <tr>
      <td>
        <p>{{ company_name }} | {{ company_address }}</p>
        <p><a href="{{ unsubscribe_url }}">Unsubscribe</a></p>
      </td>
    </tr>
  </table>
</body>
</html>
```

## Notification Events

| Event | Email | Slack | Priority |
|-------|-------|-------|----------|
| User Registration | ✅ | ❌ | P0 |
| Email Verification | ✅ | ❌ | P0 |
| Password Reset | ✅ | ❌ | P0 |
| Proposal Sent | ✅ | ✅ | P1 |
| Proposal Approved | ✅ | ✅ | P1 |
| Payment Received | ✅ | ✅ | P1 |
| Invoice Created | ✅ | ❌ | P1 |
| Ticket Created | ✅ | ✅ | P2 |
| Ticket Updated | ✅ | ❌ | P2 |
| SLA Warning (75%) | ✅ | ✅ | P1 |
| SLA Breach (100%) | ✅ | ✅ | P0 |
| Project Status Change | ✅ | ❌ | P2 |
| New Client Signup | ❌ | ✅ | P2 |

## Notification Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Event     │────▶│ Notification│────▶│   Queue     │
│  Triggered  │     │   Service   │     │ (Dramatiq)  │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                    ┌──────────────────────────┼──────────┐
                    │                          │          │
                    ▼                          ▼          ▼
            ┌─────────────┐          ┌─────────────┐ ┌─────────┐
            │   Check     │          │   Email     │ │  Slack  │
            │ Preferences │          │   Worker    │ │  Worker │
            └─────────────┘          └─────────────┘ └─────────┘
                    │                          │          │
                    │                          ▼          ▼
                    │               ┌──────────────────────────┐
                    └──────────────▶│    Send Notification     │
                                    └──────────────────────────┘
```

## Definition of Done

- [ ] TDD: Tests written FIRST
- [ ] All tests passing
- [ ] Code coverage >= 80%
- [ ] Email templates responsive
- [ ] Plain text fallbacks
- [ ] Preferences respected
- [ ] Async via background job
- [ ] Documentation (WHAT/WHY/HOW)
- [ ] Code review approved
