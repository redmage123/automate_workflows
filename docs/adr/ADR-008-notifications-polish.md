# ADR-008: Notifications & Polish Sprint

## Status
Accepted

## Context

Sprint 8 focuses on completing the notification system and polishing the application for production readiness. The foundation has been laid in previous sprints:
- Sprint 2: Email service with provider abstraction (Resend)
- Sprint 6: SLA service for ticket management, Slack notifications

However, several notification features remain incomplete:
1. **Email Templates**: Currently using inline HTML templates. Need Jinja2-based templates for maintainability.
2. **Notification Preferences**: Users cannot control which notifications they receive.
3. **SLA Breach Background Job**: SLA breach detection is passive (checked on request). Need proactive monitoring.
4. **Organization Settings UI**: Missing from Sprint 2 (ORG-003).
5. **Form Validation Polish**: Improve form validation UX across the application.
6. **Responsive Design**: Ensure mobile-friendly layouts.

### Business Requirements

1. **Email Templates (NOTIFY-002)**
   - Professional, branded email templates
   - Template inheritance for consistent headers/footers
   - Easy to update without code changes
   - Support for all email types (verification, reset, tickets, proposals, invoices)

2. **Notification Preferences (NOTIFY-004)**
   - Per-user notification settings
   - Channel selection (email, Slack, in-app)
   - Frequency controls (immediate, daily digest, weekly)
   - Category toggles (tickets, proposals, invoices, security)

3. **SLA Breach Background Job (TICKET-BG)**
   - Periodic check for SLA breaches (every 5 minutes)
   - Send notifications when:
     - Response SLA enters warning zone (75% elapsed)
     - Response SLA is breached
     - Resolution SLA enters warning zone
     - Resolution SLA is breached
   - Prevent duplicate notifications
   - Escalation chain support

4. **Organization Settings UI (ORG-003)**
   - View/edit organization details
   - Manage organization preferences
   - View member list (admin only)
   - Billing/subscription info display

## Decision

### 1. Email Templates with Jinja2

**Choice**: Use Jinja2 templates stored in `backend/templates/email/`

**Why**:
- Jinja2 is already a FastAPI dependency
- Template inheritance reduces duplication
- Designers can edit templates without Python knowledge
- Easy to add new templates

**Template Structure**:
```
backend/templates/email/
├── base.html            # Base template with header/footer
├── verification.html    # Email verification
├── password_reset.html  # Password reset
├── password_changed.html
├── welcome.html
├── ticket_created.html
├── ticket_updated.html
├── ticket_comment.html
├── proposal_sent.html
├── proposal_approved.html
├── proposal_rejected.html
├── invoice_created.html
├── invoice_paid.html
└── sla_warning.html     # SLA approaching breach
```

### 2. Notification Preferences Model

**Choice**: New `NotificationPreference` model linked to User

**Schema**:
```python
class NotificationChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    IN_APP = "in_app"

class NotificationCategory(str, Enum):
    SECURITY = "security"      # Password changes, logins
    TICKETS = "tickets"        # Ticket updates
    PROPOSALS = "proposals"    # Proposal workflow
    INVOICES = "invoices"      # Payment notifications
    SYSTEM = "system"          # System announcements

class NotificationPreference(Base):
    user_id: int               # FK to users
    category: NotificationCategory
    channel_email: bool = True
    channel_slack: bool = False
    channel_in_app: bool = True
    frequency: str = "immediate"  # immediate, daily, weekly
    is_enabled: bool = True
```

**Why**:
- Per-category, per-channel control
- Respects user preferences in all notification sends
- Security category cannot be disabled (always email)

### 3. SLA Breach Background Job

**Choice**: Use APScheduler with Redis job store

**Why**:
- APScheduler integrates well with FastAPI
- Redis job store survives restarts
- Built-in job locking prevents duplicate runs

**Job Logic**:
```python
async def check_sla_breaches():
    """Run every 5 minutes to check SLA status."""
    # 1. Get all tickets in warning zone or breached
    # 2. Check notification_sent flags
    # 3. Send notifications for new breaches/warnings
    # 4. Update notification_sent flags
    # 5. Log all actions for audit
```

**New Fields on Ticket Model**:
```python
# Notification tracking to prevent duplicates
sla_response_warning_sent_at: Optional[datetime]
sla_response_breach_sent_at: Optional[datetime]
sla_resolution_warning_sent_at: Optional[datetime]
sla_resolution_breach_sent_at: Optional[datetime]
```

### 4. Organization Settings Page

**Choice**: React page at `/settings/organization`

**Features**:
- Organization name, logo, contact info
- Business address
- Timezone settings
- Notification defaults
- Member list (admin only)
- Billing overview link

### 5. Form Validation Improvements

**Choice**: Enhance existing React Hook Form setup

**Improvements**:
- Inline validation errors
- Real-time validation feedback
- Consistent error styling
- Accessibility (ARIA attributes)
- Loading states during submission

### 6. Responsive Design

**Choice**: Tailwind responsive utilities

**Breakpoints**:
- Mobile-first approach
- sm: 640px, md: 768px, lg: 1024px, xl: 1280px
- Focus on sidebar collapse, table scrolling, form stacking

## Consequences

### Positive

1. **Maintainable Templates**: Jinja2 templates are easy to update and localize
2. **User Control**: Notification preferences give users control over communications
3. **Proactive SLA**: Background job catches breaches before customers notice
4. **Complete Feature Set**: Organization settings completes Sprint 2 scope
5. **Better UX**: Form validation and responsive design improve user experience
6. **Production Ready**: Polish items prepare app for deployment

### Negative

1. **Complexity**: APScheduler adds another component to monitor
2. **Email Spam Risk**: More notification types could overwhelm users
3. **Migration Required**: New preference model needs database migration

### Mitigations

1. **APScheduler**: Health check endpoint, logging, alerting
2. **Email Spam**: Default to sensible frequencies, clear preference UI
3. **Migration**: Backwards compatible, defaults for existing users

## Implementation Guide

### Phase 1: Email Templates (NOTIFY-002)

1. Create `backend/templates/email/` directory structure
2. Create `base.html` template with header/footer
3. Create individual templates for each email type
4. Update `EmailService` to use Jinja2 templates
5. Add template loading with caching
6. Update existing email methods to use templates
7. Write unit tests for template rendering
8. Integration tests for email sending

### Phase 2: Notification Preferences (NOTIFY-004)

1. Create `NotificationPreference` model
2. Create migration `008_add_notification_preferences.py`
3. Create `NotificationPreferenceDAO` with CRUD operations
4. Create API endpoints:
   - `GET /api/users/me/notification-preferences`
   - `PUT /api/users/me/notification-preferences`
5. Create `NotificationService` that respects preferences
6. Frontend: Notification settings page
7. Unit and integration tests

### Phase 3: SLA Background Job (TICKET-BG)

1. Add notification tracking fields to Ticket model
2. Create migration `009_add_sla_notification_tracking.py`
3. Install and configure APScheduler
4. Create `SLABackgroundService` with job logic
5. Add job registration in app startup
6. Create SLA notification templates
7. Add health check for job status
8. Integration tests with time mocking

### Phase 4: Organization Settings (ORG-003)

1. Create `/settings/organization` route
2. Create `OrganizationSettingsPage.tsx`
3. Add organization update API (if not exists)
4. Display member list for admins
5. Add timezone selection
6. Integration tests

### Phase 5: Polish (POLISH-004, POLISH-005)

1. Audit all forms for validation improvements
2. Add inline error messages
3. Test on mobile viewports
4. Fix sidebar collapse behavior
5. Add table horizontal scroll on mobile
6. Form input stacking on mobile
7. Accessibility audit with jest-axe

### Phase 6: Testing (POLISH-006)

1. Run full test suite
2. Fix any failing tests
3. Manual QA pass
4. Performance testing
5. Security review
6. Documentation update

## Testing Strategy

### Unit Tests
- Email template rendering
- Notification preference logic
- SLA breach detection
- Form validation helpers

### Integration Tests
- Email sending with templates
- Preference CRUD operations
- Background job execution
- Organization settings API

### E2E Tests
- User notification preferences flow
- Organization settings update
- Form validation UX
- Mobile responsive behavior

## Security Considerations

1. **Email Templates**: No user-controlled content in template names
2. **Preferences**: Users can only modify their own preferences
3. **SLA Jobs**: Job runs with service account, not user context
4. **Organization Settings**: Admin-only for sensitive fields
5. **Form Validation**: Server-side validation always, client-side is UX only

## Dependencies

- Jinja2 (already in FastAPI)
- APScheduler (new dependency)
- Redis (already deployed)

## Migration Path

1. Deploy with feature flags disabled
2. Run migrations
3. Enable email templates
4. Enable notification preferences (default settings for existing users)
5. Enable SLA background job
6. Monitor for issues

## References

- [Jinja2 Template Designer Documentation](https://jinja.palletsprojects.com/en/3.1.x/templates/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/en/stable/)
- [OWASP Notification Security](https://cheatsheetseries.owasp.org/cheatsheets/Notification_Security_Cheat_Sheet.html)
- [WCAG Form Guidelines](https://www.w3.org/WAI/tutorials/forms/)
