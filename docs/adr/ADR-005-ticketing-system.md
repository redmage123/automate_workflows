# ADR-005: Ticketing System

## Status

Accepted

## Context

The Automation Services Platform needs a support ticketing system that allows:
1. Clients to submit support requests related to their projects
2. Admins to manage and respond to tickets
3. SLA (Service Level Agreement) tracking for response and resolution times
4. Integration with notification systems (email, Slack)

Key requirements:
- Tickets linked to projects for context
- Priority-based SLA timers
- Status workflow (open → in_progress → waiting → resolved → closed)
- Comment/reply threading
- File attachments support
- SLA breach alerting

## Decision

### 1. Data Model

```
Ticket
├── id (PK)
├── org_id (FK → organizations)
├── project_id (FK → projects, optional)
├── created_by_user_id (FK → users)
├── assigned_to_user_id (FK → users, optional)
├── subject (string)
├── description (text)
├── status (enum: open, in_progress, waiting, resolved, closed)
├── priority (enum: low, medium, high, urgent)
├── category (enum: bug, feature, question, support)
├── sla_response_due_at (datetime, nullable)
├── sla_resolution_due_at (datetime, nullable)
├── first_response_at (datetime, nullable)
├── resolved_at (datetime, nullable)
├── closed_at (datetime, nullable)
├── created_at (datetime)
└── updated_at (datetime)

TicketComment
├── id (PK)
├── ticket_id (FK → tickets)
├── user_id (FK → users)
├── content (text)
├── is_internal (bool) -- internal notes not visible to clients
├── created_at (datetime)
└── updated_at (datetime)

TicketAttachment
├── id (PK)
├── ticket_id (FK → tickets)
├── comment_id (FK → ticket_comments, optional)
├── filename (string)
├── file_path (string)
├── file_size (int)
├── mime_type (string)
├── uploaded_by_user_id (FK → users)
├── created_at (datetime)
└── updated_at (datetime)
```

### 2. Status Workflow

```
                    ┌──────────────┐
                    │    OPEN      │
                    └──────┬───────┘
                           │ assign/respond
                           ▼
                    ┌──────────────┐
              ┌─────│ IN_PROGRESS  │─────┐
              │     └──────┬───────┘     │
    waiting   │            │             │ resolve
    for client│            │             │
              ▼            │             ▼
       ┌──────────────┐    │      ┌──────────────┐
       │   WAITING    │────┘      │   RESOLVED   │
       └──────────────┘           └──────┬───────┘
              │                          │
              └──────────────────────────┤ close
                                         ▼
                                  ┌──────────────┐
                                  │    CLOSED    │
                                  └──────────────┘
```

Valid transitions:
- OPEN → IN_PROGRESS, CLOSED
- IN_PROGRESS → WAITING, RESOLVED, OPEN
- WAITING → IN_PROGRESS, CLOSED
- RESOLVED → CLOSED, IN_PROGRESS (reopen)
- CLOSED → OPEN (reopen)

### 3. SLA Configuration

SLA timers are based on priority:

| Priority | First Response | Resolution |
|----------|---------------|------------|
| Urgent   | 1 hour        | 4 hours    |
| High     | 4 hours       | 24 hours   |
| Medium   | 8 hours       | 72 hours   |
| Low      | 24 hours      | 168 hours  |

SLA timers:
- Only count business hours (configurable)
- Pause when status is WAITING (waiting for client)
- Resume when client responds

### 4. API Endpoints

```
# Tickets
POST   /api/tickets                    # Create ticket
GET    /api/tickets                    # List tickets (with filters)
GET    /api/tickets/{id}               # Get ticket details
PATCH  /api/tickets/{id}               # Update ticket
POST   /api/tickets/{id}/assign        # Assign ticket
POST   /api/tickets/{id}/status        # Change status

# Comments
POST   /api/tickets/{id}/comments      # Add comment
GET    /api/tickets/{id}/comments      # List comments
PATCH  /api/tickets/{id}/comments/{cid}# Edit comment
DELETE /api/tickets/{id}/comments/{cid}# Delete comment

# Attachments
POST   /api/tickets/{id}/attachments   # Upload attachment
GET    /api/tickets/{id}/attachments   # List attachments
DELETE /api/tickets/{id}/attachments/{aid} # Delete attachment

# Stats
GET    /api/tickets/stats              # Ticket statistics
```

### 5. Access Control

| Action | ADMIN | CLIENT |
|--------|-------|--------|
| Create ticket | ✓ | ✓ (own org) |
| View ticket | ✓ | ✓ (own org) |
| Update ticket | ✓ | ✓ (own tickets, limited fields) |
| Assign ticket | ✓ | ✗ |
| Add comment | ✓ | ✓ (own org tickets) |
| Internal notes | ✓ | ✗ (hidden from clients) |
| Close ticket | ✓ | ✓ (own tickets) |
| Delete ticket | ✓ | ✗ |

### 6. Notifications

Trigger notifications on:
- Ticket created → notify assigned user (email + Slack)
- Ticket assigned → notify assignee (email + Slack)
- Comment added → notify ticket participants (email)
- Status changed → notify creator (email)
- SLA warning (75% elapsed) → notify assignee (Slack)
- SLA breach → notify assignee + admin (email + Slack)

### 7. Slack Integration

Slack webhook integration for real-time notifications:
- Post to configurable channel per org
- Rich message formatting with ticket details
- Action buttons for quick responses

## Consequences

### Positive

1. **Full ticket lifecycle** - Complete workflow from creation to closure
2. **SLA compliance** - Automated tracking prevents missed deadlines
3. **Project context** - Tickets linked to projects for full visibility
4. **Collaboration** - Comments and internal notes for team communication
5. **Multi-channel notifications** - Email and Slack integration
6. **Audit trail** - Full history of ticket changes

### Negative

1. **Complexity** - SLA calculations require careful implementation
2. **Storage** - Attachments require file storage solution
3. **Real-time** - Slack integration requires webhook configuration

## Implementation Guide

### Phase 1: Core Ticketing (TICKET-001 to TICKET-004)

1. Create Ticket, TicketComment, TicketAttachment models
2. Create migration with indexes
3. Implement TicketDAO with CRUD + status workflow
4. Create Pydantic schemas
5. Implement API endpoints

### Phase 2: SLA System (TICKET-005, TICKET-006)

1. Create SLA configuration model or constants
2. Implement SLA timer calculation service
3. Add SLA due dates on ticket creation/update
4. Create background job for SLA breach detection
5. Integrate with notification system

### Phase 3: UI (TICKET-007, TICKET-008)

1. Create ticket list page with filters
2. Create ticket detail page with comments
3. Create ticket form (create/edit)
4. Add SLA indicators and warnings

### Phase 4: Notifications (NOTIFY-002 to NOTIFY-004)

1. Create email templates for ticket events
2. Implement Slack webhook service
3. Add notification preferences per user/org

## Security Considerations

- **File uploads**: Validate file types, scan for malware, limit sizes
- **XSS prevention**: Sanitize comment content
- **Access control**: Strict org-scoping, internal notes hidden from clients
- **Rate limiting**: Prevent spam ticket creation
- **Audit logging**: Log all ticket operations

## References

- Sprint 6 Kanban: `docs/kanban/master-board.md`
- Email Service: `app/services/email_service.py`
- Notification patterns: Similar to audit logging middleware
