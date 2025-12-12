# ADR-011: Comprehensive Platform Enhancements

## Status
Accepted

## Context

The Automation Services Platform has a solid foundation with authentication, projects, proposals, billing, ticketing, workflows, and notifications. To evolve into a complete SaaS solution, the platform requires enhancements across multiple areas:

1. **Workflow AI Improvements**: Enhanced AI-powered workflow generation
2. **n8n Integration Enhancements**: Better workflow management and monitoring
3. **Client Portal Improvements**: Better client experience
4. **Reporting & Analytics**: Business intelligence and insights
5. **Communication Features**: Improved collaboration
6. **Billing Enhancements**: Advanced payment options
7. **Mobile PWA**: Mobile-first experience
8. **External Integrations**: Third-party connectivity
9. **Advanced Features**: Enterprise capabilities

### Requirements

#### Workflow AI Improvements (WF-001 to WF-005)
- WF-001: Pre-built workflow templates for common use cases
- WF-002: Workflow versioning and history
- WF-003: AI confidence threshold settings
- WF-004: Workflow generation from example descriptions
- WF-005: Multi-step workflow wizard

#### n8n Integration Enhancements (N8N-001 to N8N-005)
- N8N-001: Workflow import/export between environments
- N8N-002: Real-time execution monitoring dashboard
- N8N-003: Credential management UI
- N8N-004: Workflow testing sandbox
- N8N-005: Execution retry and error handling

#### Client Portal Improvements (CP-001 to CP-005)
- CP-001: Client onboarding wizard
- CP-002: Personalized client dashboard
- CP-003: Document management (upload/download)
- CP-004: Service request forms
- CP-005: Client feedback and satisfaction surveys

#### Reporting & Analytics (RA-001 to RA-005)
- RA-001: Scheduled report generation and delivery
- RA-002: Custom report builder
- RA-003: Export to PDF/Excel/CSV
- RA-004: Revenue forecasting
- RA-005: Client activity analytics

#### Communication Features (CM-001 to CM-005)
- CM-001: In-app messaging between users
- CM-002: Notification center with filtering
- CM-003: Activity feed/timeline
- CM-004: Email templates management
- CM-005: Announcement broadcasts

#### Billing Enhancements (BL-001 to BL-005)
- BL-001: Recurring billing and subscriptions
- BL-002: Payment plans and installments
- BL-003: Time tracking integration
- BL-004: Invoice templates
- BL-005: Tax calculation and management

#### Mobile PWA (MW-001 to MW-005)
- MW-001: Progressive Web App manifest
- MW-002: Offline capability with service worker
- MW-003: Push notifications
- MW-004: Touch-optimized UI components
- MW-005: Mobile-specific navigation

#### External Integrations (EI-001 to EI-005)
- EI-001: Calendar sync (Google Calendar, Outlook)
- EI-002: Zapier/Make.com webhooks
- EI-003: CRM integration (HubSpot, Salesforce)
- EI-004: Accounting software (QuickBooks, Xero)
- EI-005: Custom webhook endpoints

#### Advanced Features (AF-001 to AF-005)
- AF-001: Internationalization (i18n)
- AF-002: White-label/branding customization
- AF-003: Client API for automation
- AF-004: Audit log export
- AF-005: Data retention policies

## Decision

### 1. Database Schema Extensions

#### 1.1 Workflow Templates (Enhanced)

```python
class WorkflowTemplateCategory(Base):
    """
    Categories for organizing workflow templates.

    WHAT: Hierarchical categorization of workflow templates.

    WHY: Makes it easier for users to discover relevant templates
    and organize them by use case (sales, marketing, operations, etc.).
    """
    __tablename__ = "workflow_template_categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    icon = Column(String(50))  # Icon identifier for UI
    parent_id = Column(Integer, ForeignKey("workflow_template_categories.id"))
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    # Self-referential relationship for subcategories
    parent = relationship("WorkflowTemplateCategory", remote_side=[id])
    children = relationship("WorkflowTemplateCategory", back_populates="parent")


class WorkflowVersion(Base):
    """
    Version history for workflows.

    WHAT: Tracks all versions of a workflow with change descriptions.

    WHY: Enables rollback, audit trail, and understanding of workflow evolution.
    Critical for production workflows where changes must be traceable.
    """
    __tablename__ = "workflow_versions"

    id = Column(Integer, primary_key=True)
    workflow_instance_id = Column(Integer, ForeignKey("workflow_instances.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    workflow_json = Column(JSON, nullable=False)
    change_description = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    is_current = Column(Boolean, default=False)

    # Relationships
    workflow_instance = relationship("WorkflowInstance", back_populates="versions")
    creator = relationship("User")

    __table_args__ = (
        UniqueConstraint('workflow_instance_id', 'version_number', name='uq_workflow_version'),
    )
```

#### 1.2 Document Management

```python
class Document(Base):
    """
    Document storage for client files.

    WHAT: Metadata for uploaded documents with S3 storage.

    WHY: Clients need to share documents (contracts, specifications, assets)
    with service providers. S3 provides scalable, secure storage.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # File metadata
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    s3_key = Column(String(500), nullable=False)
    s3_bucket = Column(String(100), nullable=False)

    # Organization
    folder = Column(String(255), default="/")
    tags = Column(ARRAY(String), default=[])
    description = Column(Text)

    # Associations (polymorphic)
    entity_type = Column(String(50))  # 'project', 'proposal', 'ticket', etc.
    entity_id = Column(Integer)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    # Relationships
    organization = relationship("Organization")
    uploader = relationship("User")


class DocumentAccess(Base):
    """
    Access control for documents.

    WHAT: Tracks who can view/download specific documents.

    WHY: Documents may contain sensitive information. Fine-grained
    access control ensures only authorized users can access them.
    """
    __tablename__ = "document_access"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    access_level = Column(String(20), default="view")  # view, download, edit
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    granted_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime)

    document = relationship("Document")
    user = relationship("User", foreign_keys=[user_id])
    grantor = relationship("User", foreign_keys=[granted_by])
```

#### 1.3 Messaging System

```python
class Message(Base):
    """
    In-app messaging between users.

    WHAT: Direct messages and conversation threads.

    WHY: Reduces reliance on external communication tools,
    keeps all project-related communication in one place.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Thread grouping
    thread_id = Column(String(36))  # UUID for conversation thread
    parent_message_id = Column(Integer, ForeignKey("messages.id"))

    # Content
    subject = Column(String(255))
    body = Column(Text, nullable=False)

    # Status
    read_at = Column(DateTime)
    archived_by_sender = Column(Boolean, default=False)
    archived_by_recipient = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime)

    # Relationships
    organization = relationship("Organization")
    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])
    parent = relationship("Message", remote_side=[id])


class Announcement(Base):
    """
    System-wide or organization announcements.

    WHAT: Broadcast messages to multiple users.

    WHY: Admins need to communicate important updates (maintenance,
    new features, policy changes) to all users or specific groups.
    """
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"))  # Null = system-wide
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    priority = Column(String(20), default="normal")  # low, normal, high, urgent

    # Targeting
    target_roles = Column(ARRAY(String))  # Null = all roles

    # Scheduling
    starts_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    creator = relationship("User")


class AnnouncementRead(Base):
    """
    Tracks which users have read announcements.

    WHAT: Read receipts for announcements.

    WHY: Allows UI to show unread badge and ensures users see important updates.
    """
    __tablename__ = "announcement_reads"

    id = Column(Integer, primary_key=True)
    announcement_id = Column(Integer, ForeignKey("announcements.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    read_at = Column(DateTime, server_default=func.now())

    announcement = relationship("Announcement")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint('announcement_id', 'user_id', name='uq_announcement_user'),
    )
```

#### 1.4 Scheduled Reports

```python
class ScheduledReport(Base):
    """
    Configuration for automated report generation.

    WHAT: Defines reports that run on a schedule and deliver to users.

    WHY: Managers and clients need regular updates without manual effort.
    Automation reduces workload and ensures consistent reporting.
    """
    __tablename__ = "scheduled_reports"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(Text)
    report_type = Column(String(50), nullable=False)  # revenue, activity, project, etc.

    # Report configuration
    parameters = Column(JSON, default={})  # Filters, date ranges, etc.
    output_format = Column(String(20), default="pdf")  # pdf, excel, csv

    # Schedule (cron expression)
    schedule = Column(String(100), nullable=False)  # "0 9 * * 1" = Every Monday 9am
    timezone = Column(String(50), default="UTC")

    # Delivery
    recipients = Column(ARRAY(Integer))  # User IDs
    email_subject = Column(String(255))
    email_body = Column(Text)

    # Status
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization")
    creator = relationship("User")


class ReportExecution(Base):
    """
    History of report executions.

    WHAT: Tracks each time a scheduled report runs.

    WHY: Audit trail for report generation, debugging failed reports,
    and allowing users to access historical reports.
    """
    __tablename__ = "report_executions"

    id = Column(Integer, primary_key=True)
    scheduled_report_id = Column(Integer, ForeignKey("scheduled_reports.id"), nullable=False)

    status = Column(String(20), nullable=False)  # pending, running, completed, failed
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Output
    output_file_key = Column(String(500))  # S3 key if stored
    output_size = Column(BigInteger)
    error_message = Column(Text)

    # Delivery status
    delivery_status = Column(String(20))  # sent, failed, partial
    delivery_error = Column(Text)

    scheduled_report = relationship("ScheduledReport")
```

#### 1.5 Time Tracking

```python
class TimeEntry(Base):
    """
    Time tracking for billable hours.

    WHAT: Records time spent on projects/tickets.

    WHY: Many service businesses bill by hour. Accurate time tracking
    enables fair billing and project cost analysis.
    """
    __tablename__ = "time_entries"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # What was worked on (polymorphic)
    entity_type = Column(String(50), nullable=False)  # project, ticket
    entity_id = Column(Integer, nullable=False)

    # Time data
    description = Column(Text)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime)
    duration_minutes = Column(Integer)  # Calculated or manual

    # Billing
    is_billable = Column(Boolean, default=True)
    hourly_rate = Column(Numeric(10, 2))  # Override default rate
    invoice_id = Column(Integer, ForeignKey("invoices.id"))  # When invoiced

    # Status
    status = Column(String(20), default="draft")  # draft, submitted, approved, invoiced
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization")
    user = relationship("User", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approved_by])
    invoice = relationship("Invoice")
```

#### 1.6 Activity Feed

```python
class ActivityEvent(Base):
    """
    Unified activity feed for all platform events.

    WHAT: Records all significant actions in the platform.

    WHY: Users need visibility into what's happening across their
    organization. Activity feeds provide context and transparency.
    """
    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))  # Null for system events

    # Event classification
    event_type = Column(String(50), nullable=False)  # created, updated, deleted, etc.
    entity_type = Column(String(50), nullable=False)  # project, ticket, invoice, etc.
    entity_id = Column(Integer, nullable=False)

    # Event details
    title = Column(String(255), nullable=False)
    description = Column(Text)
    metadata = Column(JSON, default={})  # Additional event-specific data

    # Visibility
    is_public = Column(Boolean, default=True)  # Visible to all org members
    visible_to = Column(ARRAY(Integer))  # Specific user IDs if not public

    # Timestamp
    created_at = Column(DateTime, server_default=func.now())

    organization = relationship("Organization")
    actor = relationship("User")
```

#### 1.7 Client Onboarding

```python
class OnboardingTemplate(Base):
    """
    Templates for client onboarding flows.

    WHAT: Defines steps and requirements for new client onboarding.

    WHY: Consistent onboarding improves client experience and ensures
    all necessary information is collected upfront.
    """
    __tablename__ = "onboarding_templates"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(Text)

    # Steps definition
    steps = Column(JSON, nullable=False)
    # [
    #   {"id": "welcome", "title": "Welcome", "type": "info", "content": "..."},
    #   {"id": "profile", "title": "Company Profile", "type": "form", "fields": [...]},
    #   {"id": "docs", "title": "Documents", "type": "upload", "required_docs": [...]},
    # ]

    # Settings
    is_active = Column(Boolean, default=True)
    auto_assign = Column(Boolean, default=False)  # Auto-assign to new clients

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization")


class ClientOnboarding(Base):
    """
    Tracks individual client onboarding progress.

    WHAT: Records a client's progress through onboarding steps.

    WHY: Allows tracking incomplete onboardings, sending reminders,
    and understanding where clients get stuck.
    """
    __tablename__ = "client_onboardings"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("onboarding_templates.id"), nullable=False)

    # Progress tracking
    current_step = Column(String(50))
    completed_steps = Column(ARRAY(String), default=[])
    step_data = Column(JSON, default={})  # Data collected at each step

    # Status
    status = Column(String(20), default="in_progress")  # in_progress, completed, abandoned
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)

    organization = relationship("Organization")
    user = relationship("User")
    template = relationship("OnboardingTemplate")
```

#### 1.8 Survey/Feedback

```python
class Survey(Base):
    """
    Client satisfaction surveys.

    WHAT: Configurable surveys for collecting feedback.

    WHY: Understanding client satisfaction helps improve services
    and identify issues before they become problems.
    """
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(Text)

    # Questions definition
    questions = Column(JSON, nullable=False)
    # [
    #   {"id": "q1", "type": "rating", "text": "How satisfied are you?", "scale": 5},
    #   {"id": "q2", "type": "text", "text": "Any additional feedback?"},
    # ]

    # Trigger conditions
    trigger_type = Column(String(50))  # manual, project_complete, ticket_closed
    trigger_entity_type = Column(String(50))

    # Settings
    is_active = Column(Boolean, default=True)
    is_anonymous = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization")
    creator = relationship("User")


class SurveyResponse(Base):
    """
    Individual survey responses.

    WHAT: A client's answers to a survey.

    WHY: Collects and stores feedback for analysis and follow-up.
    """
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))  # Null if anonymous

    # Response data
    answers = Column(JSON, nullable=False)
    # {"q1": 4, "q2": "Great service!"}

    # Context
    entity_type = Column(String(50))
    entity_id = Column(Integer)

    # Metadata
    submitted_at = Column(DateTime, server_default=func.now())
    ip_address = Column(String(45))  # For anonymous responses

    survey = relationship("Survey")
    user = relationship("User")
```

#### 1.9 Email Templates

```python
class EmailTemplate(Base):
    """
    Customizable email templates.

    WHAT: HTML/text templates for system emails.

    WHY: Organizations need to customize email branding and content
    while maintaining consistent structure.
    """
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"))  # Null = system default

    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False)  # welcome, invoice, reminder, etc.
    description = Column(Text)

    # Template content
    subject_template = Column(String(255), nullable=False)
    html_template = Column(Text, nullable=False)
    text_template = Column(Text)  # Plain text fallback

    # Variables documentation
    available_variables = Column(JSON)  # {"user_name": "Recipient's name", ...}

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint('org_id', 'slug', name='uq_email_template_slug'),
    )
```

### 2. New Custom Exceptions

```python
# In app/core/exceptions.py

# Document Exceptions
class DocumentError(AppException):
    """Base exception for document operations."""
    status_code = 500
    default_message = "Document operation failed"


class DocumentNotFoundError(ResourceNotFoundError):
    """Raised when document doesn't exist."""
    default_message = "Document not found"


class DocumentAccessDeniedError(AuthorizationError):
    """Raised when user can't access document."""
    default_message = "Document access denied"


class DocumentUploadError(DocumentError):
    """Raised when document upload fails."""
    status_code = 400
    default_message = "Document upload failed"


class DocumentStorageError(ExternalServiceError):
    """Raised when S3/storage operations fail."""
    default_message = "Document storage error"


# Messaging Exceptions
class MessageError(AppException):
    """Base exception for messaging operations."""
    status_code = 500
    default_message = "Messaging error"


class MessageNotFoundError(ResourceNotFoundError):
    """Raised when message doesn't exist."""
    default_message = "Message not found"


class MessageRecipientError(ValidationError):
    """Raised when recipient is invalid."""
    default_message = "Invalid message recipient"


# Report Exceptions
class ReportError(AppException):
    """Base exception for reporting operations."""
    status_code = 500
    default_message = "Report generation error"


class ReportGenerationError(ReportError):
    """Raised when report generation fails."""
    status_code = 500
    default_message = "Failed to generate report"


class ReportScheduleError(ReportError):
    """Raised when report scheduling fails."""
    status_code = 400
    default_message = "Invalid report schedule"


# Time Tracking Exceptions
class TimeEntryError(AppException):
    """Base exception for time tracking."""
    status_code = 400
    default_message = "Time entry error"


class TimeEntryOverlapError(TimeEntryError):
    """Raised when time entries overlap."""
    default_message = "Time entries cannot overlap"


class TimeEntryAlreadyInvoicedError(TimeEntryError):
    """Raised when modifying an invoiced time entry."""
    status_code = 403
    default_message = "Cannot modify invoiced time entry"


# Survey Exceptions
class SurveyError(AppException):
    """Base exception for survey operations."""
    status_code = 400
    default_message = "Survey error"


class SurveyNotFoundError(ResourceNotFoundError):
    """Raised when survey doesn't exist."""
    default_message = "Survey not found"


class SurveyAlreadyRespondedError(SurveyError):
    """Raised when user has already responded."""
    status_code = 409
    default_message = "Survey already completed"


# Calendar Integration Exceptions
class CalendarIntegrationError(ExternalServiceError):
    """Base exception for calendar operations."""
    default_message = "Calendar integration error"


class CalendarSyncError(CalendarIntegrationError):
    """Raised when calendar sync fails."""
    default_message = "Calendar sync failed"


# Webhook Exceptions
class WebhookError(AppException):
    """Base exception for webhook operations."""
    status_code = 500
    default_message = "Webhook error"


class WebhookDeliveryError(WebhookError):
    """Raised when webhook delivery fails."""
    default_message = "Webhook delivery failed"


class WebhookSignatureError(WebhookError):
    """Raised when webhook signature is invalid."""
    status_code = 401
    default_message = "Invalid webhook signature"
```

### 3. API Endpoints Structure

```
# Workflow AI (enhanced)
POST   /api/workflow-ai/generate              # Generate from description
POST   /api/workflow-ai/refine                # Refine existing
POST   /api/workflow-ai/validate              # Validate workflow
GET    /api/workflow-ai/templates             # Get AI templates
GET    /api/workflow-ai/status                # Service status

# Workflow Versions
GET    /api/workflows/instances/{id}/versions         # List versions
GET    /api/workflows/instances/{id}/versions/{v}     # Get specific version
POST   /api/workflows/instances/{id}/versions         # Create new version
POST   /api/workflows/instances/{id}/versions/{v}/restore  # Restore version

# Documents
GET    /api/documents                         # List documents
POST   /api/documents                         # Upload document
GET    /api/documents/{id}                    # Get document metadata
GET    /api/documents/{id}/download           # Download document
DELETE /api/documents/{id}                    # Delete document
POST   /api/documents/{id}/share              # Share document

# Messages
GET    /api/messages                          # List conversations
GET    /api/messages/thread/{thread_id}       # Get thread
POST   /api/messages                          # Send message
PUT    /api/messages/{id}/read                # Mark as read
DELETE /api/messages/{id}                     # Delete message

# Announcements
GET    /api/announcements                     # List announcements
POST   /api/announcements                     # Create announcement
PUT    /api/announcements/{id}                # Update announcement
DELETE /api/announcements/{id}                # Delete announcement
POST   /api/announcements/{id}/read           # Mark as read

# Reports
GET    /api/reports/scheduled                 # List scheduled reports
POST   /api/reports/scheduled                 # Create scheduled report
PUT    /api/reports/scheduled/{id}            # Update scheduled report
DELETE /api/reports/scheduled/{id}            # Delete scheduled report
POST   /api/reports/generate                  # Generate ad-hoc report
GET    /api/reports/executions                # List report executions
GET    /api/reports/executions/{id}/download  # Download report

# Time Tracking
GET    /api/time-entries                      # List time entries
POST   /api/time-entries                      # Create time entry
PUT    /api/time-entries/{id}                 # Update time entry
DELETE /api/time-entries/{id}                 # Delete time entry
POST   /api/time-entries/bulk-approve         # Approve multiple entries
GET    /api/time-entries/summary              # Time summary

# Activity Feed
GET    /api/activity                          # Get activity feed
GET    /api/activity/entity/{type}/{id}       # Activity for entity

# Client Onboarding
GET    /api/onboarding/templates              # List templates
POST   /api/onboarding/templates              # Create template
GET    /api/onboarding/current                # Get current user's onboarding
PUT    /api/onboarding/current/step           # Update step progress
POST   /api/onboarding/current/complete       # Complete onboarding

# Surveys
GET    /api/surveys                           # List surveys
POST   /api/surveys                           # Create survey
GET    /api/surveys/{id}                      # Get survey
PUT    /api/surveys/{id}                      # Update survey
DELETE /api/surveys/{id}                      # Delete survey
POST   /api/surveys/{id}/respond              # Submit response
GET    /api/surveys/{id}/responses            # Get responses

# Email Templates
GET    /api/email-templates                   # List templates
GET    /api/email-templates/{slug}            # Get template
PUT    /api/email-templates/{slug}            # Update template
POST   /api/email-templates/{slug}/preview    # Preview with data

# Calendar Integration
POST   /api/integrations/calendar/connect     # Connect calendar
DELETE /api/integrations/calendar/disconnect  # Disconnect calendar
GET    /api/integrations/calendar/events      # Get calendar events
POST   /api/integrations/calendar/sync        # Trigger sync

# Webhooks
GET    /api/webhooks                          # List webhooks
POST   /api/webhooks                          # Create webhook
PUT    /api/webhooks/{id}                     # Update webhook
DELETE /api/webhooks/{id}                     # Delete webhook
GET    /api/webhooks/{id}/deliveries          # Get delivery history
POST   /api/webhooks/{id}/test                # Test webhook
```

### 4. Service Layer Architecture

Each feature area will have:
1. **DAO** - Data access layer following existing BaseDAO pattern
2. **Service** - Business logic with proper exception handling
3. **API Router** - FastAPI endpoints with auth and validation
4. **Schemas** - Pydantic request/response models

Example structure for Documents:

```python
# app/dao/document.py
class DocumentDAO(BaseDAO[Document]):
    async def get_by_entity(self, entity_type: str, entity_id: int, org_id: int) -> List[Document]
    async def get_accessible_for_user(self, user_id: int, org_id: int) -> List[Document]
    async def soft_delete(self, id: int) -> Optional[Document]

# app/services/document_service.py
class DocumentService:
    async def upload(self, file: UploadFile, org_id: int, user_id: int, ...) -> Document
    async def download(self, document_id: int, user_id: int) -> bytes
    async def share(self, document_id: int, user_ids: List[int], access_level: str) -> List[DocumentAccess]
    async def delete(self, document_id: int, user_id: int) -> None

# app/api/documents.py
router = APIRouter(prefix="/documents", tags=["Documents"])
```

### 5. Frontend Components

New React components will follow existing patterns:
- Use React Query for data fetching
- Use Tailwind CSS for styling
- Use TypeScript for type safety
- Implement proper loading/error states

Key new components:
- `DocumentUpload`, `DocumentList`, `DocumentViewer`
- `MessageComposer`, `MessageThread`, `MessageList`
- `AnnouncementBanner`, `AnnouncementList`
- `ReportBuilder`, `ReportScheduler`, `ReportViewer`
- `TimeEntryForm`, `TimeEntryList`, `TimeSummary`
- `ActivityFeed`, `ActivityItem`
- `OnboardingWizard`, `OnboardingStep`
- `SurveyForm`, `SurveyResults`

### 6. PWA Implementation

```javascript
// public/manifest.json
{
  "name": "Automation Services Platform",
  "short_name": "ASP",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#3b82f6",
  "icons": [
    {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}
  ]
}

// Service worker for offline support
// public/sw.js
```

### 7. Testing Strategy

For each feature:
1. **Unit Tests** (pytest) - DAO methods, service logic
2. **Integration Tests** (pytest) - API endpoints with real database
3. **E2E Tests** (Playwright) - Full user flows
4. **Regression Tests** - Ensure existing features still work

## Consequences

### Positive
- Comprehensive feature set for enterprise clients
- Better client engagement through portal improvements
- Improved visibility through reporting and analytics
- Enhanced collaboration through messaging
- Mobile accessibility through PWA
- Third-party connectivity through integrations

### Negative
- Significant development effort required
- Increased system complexity
- Additional external dependencies (S3, calendar APIs)
- Higher testing and maintenance burden

### Risks
- Feature creep extending timelines
- Integration complexity with third-party services
- Performance impact with activity logging

## Implementation Guide

### Phase 1: Core Enhancements (Sprint 10)
1. Workflow versioning
2. Document management
3. Time tracking

### Phase 2: Communication (Sprint 11)
1. In-app messaging
2. Activity feed
3. Announcements

### Phase 3: Reporting (Sprint 12)
1. Report builder
2. Scheduled reports
3. Export functionality

### Phase 4: Client Experience (Sprint 13)
1. Onboarding wizard
2. Surveys/feedback
3. Email templates

### Phase 5: Mobile & Integrations (Sprint 14)
1. PWA implementation
2. Calendar integration
3. Webhook system

### Phase 6: Advanced Features (Sprint 15)
1. i18n framework
2. White-label support
3. Client API

## References
- Existing ADRs: ADR-001 through ADR-010
- CLAUDE.md coding standards
- OWASP Top 10 compliance requirements
