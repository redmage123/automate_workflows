"""
Database models package.

WHY: Centralizing model imports ensures Alembic can discover all models
for migration generation and makes it easier to import models elsewhere.
"""

from app.models.base import Base, TimestampMixin, PrimaryKeyMixin
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog, AuditAction
from app.models.verification_token import VerificationToken, TokenType
from app.models.project import Project, ProjectStatus, ProjectPriority
from app.models.proposal import Proposal, ProposalStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.workflow import (
    N8nEnvironment,
    WorkflowTemplate,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowVersion,
    ExecutionLog,
    ExecutionStatus,
)
from app.models.ticket import (
    Ticket,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    TicketComment,
    TicketAttachment,
    SLA_CONFIG,
)
from app.models.notification_preference import (
    NotificationPreference,
    NotificationCategory,
    NotificationChannel,
    NotificationFrequency,
    DEFAULT_PREFERENCES,
)
from app.models.oauth_account import OAuthAccount, OAuthProvider
from app.models.subscription import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    PLAN_LIMITS,
)
from app.models.document import (
    Document,
    DocumentAccess,
    DocumentAccessLevel,
)
from app.models.time_entry import (
    TimeEntry,
    TimeEntryStatus,
    TimeSummary,
)
from app.models.message import (
    Conversation,
    ConversationType,
    ConversationParticipant,
    Message,
    MessageReadReceipt,
)
from app.models.activity import (
    ActivityEvent,
    ActivityType,
    ActivitySubscription,
)
from app.models.announcement import (
    Announcement,
    AnnouncementType,
    AnnouncementPriority,
    AnnouncementStatus,
    AnnouncementRead,
)
from app.models.report import (
    ScheduledReport,
    ReportExecution,
    ReportTemplate,
    ReportType,
    ReportFormat,
    ExecutionStatus as ReportExecutionStatus,
    DeliveryStatus,
)
from app.models.onboarding import (
    OnboardingTemplate,
    ClientOnboarding,
    OnboardingReminder,
    OnboardingStatus,
    StepType,
)
from app.models.survey import (
    Survey,
    SurveyResponse as SurveyResponseModel,
    SurveyInvitation,
    FeedbackScore,
    SurveyType,
    SurveyStatus,
    QuestionType,
)
from app.models.email_template import (
    EmailTemplate,
    EmailTemplateVersion,
    SentEmail,
    EmailCategory,
)
from app.models.push_subscription import PushSubscription
from app.models.integration import (
    CalendarIntegration,
    CalendarProvider,
    WebhookEndpoint,
    WebhookDelivery,
    WebhookEventType,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "PrimaryKeyMixin",
    "Organization",
    "User",
    "UserRole",
    "AuditLog",
    "AuditAction",
    "VerificationToken",
    "TokenType",
    "Project",
    "ProjectStatus",
    "ProjectPriority",
    "Proposal",
    "ProposalStatus",
    "Invoice",
    "InvoiceStatus",
    "N8nEnvironment",
    "WorkflowTemplate",
    "WorkflowInstance",
    "WorkflowStatus",
    "WorkflowVersion",
    "ExecutionLog",
    "ExecutionStatus",
    "Ticket",
    "TicketStatus",
    "TicketPriority",
    "TicketCategory",
    "TicketComment",
    "TicketAttachment",
    "SLA_CONFIG",
    "NotificationPreference",
    "NotificationCategory",
    "NotificationChannel",
    "NotificationFrequency",
    "DEFAULT_PREFERENCES",
    "OAuthAccount",
    "OAuthProvider",
    "Subscription",
    "SubscriptionPlan",
    "SubscriptionStatus",
    "PLAN_LIMITS",
    "Document",
    "DocumentAccess",
    "DocumentAccessLevel",
    "TimeEntry",
    "TimeEntryStatus",
    "TimeSummary",
    "Conversation",
    "ConversationType",
    "ConversationParticipant",
    "Message",
    "MessageReadReceipt",
    "ActivityEvent",
    "ActivityType",
    "ActivitySubscription",
    "Announcement",
    "AnnouncementType",
    "AnnouncementPriority",
    "AnnouncementStatus",
    "AnnouncementRead",
    "ScheduledReport",
    "ReportExecution",
    "ReportTemplate",
    "ReportType",
    "ReportFormat",
    "ReportExecutionStatus",
    "DeliveryStatus",
    "OnboardingTemplate",
    "ClientOnboarding",
    "OnboardingReminder",
    "OnboardingStatus",
    "StepType",
    "Survey",
    "SurveyResponseModel",
    "SurveyInvitation",
    "FeedbackScore",
    "SurveyType",
    "SurveyStatus",
    "QuestionType",
    "EmailTemplate",
    "EmailTemplateVersion",
    "SentEmail",
    "EmailCategory",
    "PushSubscription",
    "CalendarIntegration",
    "CalendarProvider",
    "WebhookEndpoint",
    "WebhookDelivery",
    "WebhookEventType",
]
