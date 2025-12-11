# ADR-006: Notification System (Slack Integration)

## Status
Accepted

## Context

The Automation Services Platform needs to notify stakeholders about important events:
- Ticket creation and SLA breaches
- Proposal submissions and approvals
- Payment receipts
- Project status changes

We need a flexible notification system that can deliver messages through multiple channels
(initially Slack webhooks, with email support planned) while respecting user preferences.

## Decision

We will implement a notification system with the following architecture:

### 1. Slack Webhook Integration (NOTIFY-003)

**SlackService Class** (`app/services/slack_service.py`):
- Send messages to configured Slack channels
- Support Block Kit formatting for rich messages
- Handle errors gracefully with retries
- Configuration via environment variables

**Configuration**:
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_WEBHOOK_ENABLED=true
```

### 2. Notification Events

| Event | Slack Channel | Priority |
|-------|--------------|----------|
| Ticket Created | #support-tickets | P2 |
| SLA Warning (75%) | #support-urgent | P1 |
| SLA Breach (100%) | #support-urgent | P0 |
| Proposal Sent | #sales | P1 |
| Proposal Approved | #sales | P1 |
| Payment Received | #billing | P1 |
| New Client Signup | #new-clients | P2 |

### 3. Message Formatting

Use Slack Block Kit for structured messages:

```json
{
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "New Support Ticket"
      }
    },
    {
      "type": "section",
      "fields": [
        { "type": "mrkdwn", "text": "*Priority:*\nHigh" },
        { "type": "mrkdwn", "text": "*Status:*\nOpen" }
      ]
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Subject:* Cannot access dashboard"
      }
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": { "type": "plain_text", "text": "View Ticket" },
          "url": "https://app.example.com/tickets/123"
        }
      ]
    }
  ]
}
```

### 4. NotificationService Architecture

```
NotificationService
├── send_ticket_created(ticket: Ticket)
├── send_sla_warning(ticket: Ticket, threshold: float)
├── send_sla_breach(ticket: Ticket)
├── send_proposal_sent(proposal: Proposal)
├── send_proposal_approved(proposal: Proposal)
├── send_payment_received(payment: Payment)
└── send_new_client(org: Organization)
```

Each method:
1. Formats the event data into a Slack message
2. Calls SlackService.send_message()
3. Logs success/failure for auditing

### 5. Error Handling

- Wrap httpx exceptions in `SlackNotificationError`
- Retry up to 3 times with exponential backoff
- Log failures without blocking the main operation
- Fire-and-forget (async background task)

## Consequences

### Positive
- Real-time team visibility into platform events
- Standardized notification format across events
- Easy to add new notification types
- No additional infrastructure (uses Slack's webhook API)

### Negative
- Requires Slack webhook URL configuration
- Message delivery depends on Slack's availability
- No delivery guarantees (best-effort)

### Mitigation
- Notification failures don't block main operations
- Audit logging captures notification attempts
- Future: Add queue-based delivery for guaranteed notifications

## Implementation Guide

### Phase 1: Slack Service (This ADR)

1. Create `app/services/slack_service.py`:
   - `SlackService` class
   - `send_message(text, blocks)` method
   - Webhook URL from settings
   - Error handling with `SlackNotificationError`

2. Create `app/services/notification_service.py`:
   - `NotificationService` class
   - Event-specific send methods
   - Block Kit message builders
   - Inject SlackService dependency

3. Add configuration to settings:
   - `SLACK_WEBHOOK_URL`
   - `SLACK_WEBHOOK_ENABLED`
   - `APP_BASE_URL` (for action buttons)

4. Integrate with ticket API:
   - Call notification on ticket create
   - Call notification on SLA events

5. Write tests:
   - Unit tests with mocked HTTP client
   - Test message formatting
   - Test error handling

### Phase 2: Notification Preferences (Future ADR)

- NotificationPreference model
- Per-user channel preferences
- Check preferences before sending

### Phase 3: Email Integration (Future ADR)

- Resend SDK integration
- Email templates
- Async email sending

## Security Considerations

1. **Webhook URL Protection**:
   - Store in environment variable (not in code)
   - Never log the full webhook URL
   - Validate URL format on startup

2. **Information Disclosure**:
   - Don't include sensitive data in Slack messages
   - Use IDs and links instead of full content
   - Consider data sensitivity per channel

3. **Rate Limiting**:
   - Respect Slack's rate limits
   - Implement backoff on 429 responses
   - Consider message batching for high-volume events
