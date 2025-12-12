"""
Data Access Object (DAO) package.

WHY: DAOs provide a clean separation between database operations and business logic,
making the codebase more testable and maintainable.
"""

from app.dao.base import BaseDAO
from app.dao.user import UserDAO
from app.dao.audit_log import AuditLogDAO
from app.dao.project import ProjectDAO
from app.dao.proposal import ProposalDAO
from app.dao.invoice import InvoiceDAO
from app.dao.n8n_environment import N8nEnvironmentDAO
from app.dao.workflow_template import WorkflowTemplateDAO
from app.dao.workflow_instance import WorkflowInstanceDAO
from app.dao.workflow_version import WorkflowVersionDAO
from app.dao.execution_log import ExecutionLogDAO
from app.dao.ticket import TicketDAO, TicketCommentDAO, TicketAttachmentDAO
from app.dao.notification_preference import NotificationPreferenceDAO
from app.dao.oauth_account import OAuthAccountDAO
from app.dao.subscription import SubscriptionDAO
from app.dao.document import DocumentDAO, DocumentAccessDAO
from app.dao.time_entry import TimeEntryDAO, TimeSummaryDAO
from app.dao.message import (
    ConversationDAO,
    ConversationParticipantDAO,
    MessageDAO,
    MessageReadReceiptDAO,
)
from app.dao.activity import ActivityEventDAO, ActivitySubscriptionDAO
from app.dao.announcement import AnnouncementDAO, AnnouncementReadDAO
from app.dao.report import ScheduledReportDAO, ReportExecutionDAO, ReportTemplateDAO
from app.dao.onboarding import (
    OnboardingTemplateDAO,
    ClientOnboardingDAO,
    OnboardingReminderDAO,
)
from app.dao.survey import (
    SurveyDAO,
    SurveyResponseDAO,
    SurveyInvitationDAO,
    FeedbackScoreDAO,
)
from app.dao.email_template import (
    EmailTemplateDAO,
    EmailTemplateVersionDAO,
    SentEmailDAO,
)
from app.dao.push_subscription import PushSubscriptionDAO
from app.dao.integration import (
    CalendarIntegrationDAO,
    WebhookEndpointDAO,
    WebhookDeliveryDAO,
)

__all__ = [
    "BaseDAO",
    "UserDAO",
    "AuditLogDAO",
    "ProjectDAO",
    "ProposalDAO",
    "InvoiceDAO",
    "N8nEnvironmentDAO",
    "WorkflowTemplateDAO",
    "WorkflowInstanceDAO",
    "WorkflowVersionDAO",
    "ExecutionLogDAO",
    "TicketDAO",
    "TicketCommentDAO",
    "TicketAttachmentDAO",
    "NotificationPreferenceDAO",
    "OAuthAccountDAO",
    "SubscriptionDAO",
    "DocumentDAO",
    "DocumentAccessDAO",
    "TimeEntryDAO",
    "TimeSummaryDAO",
    "ConversationDAO",
    "ConversationParticipantDAO",
    "MessageDAO",
    "MessageReadReceiptDAO",
    "ActivityEventDAO",
    "ActivitySubscriptionDAO",
    "AnnouncementDAO",
    "AnnouncementReadDAO",
    "ScheduledReportDAO",
    "ReportExecutionDAO",
    "ReportTemplateDAO",
    "OnboardingTemplateDAO",
    "ClientOnboardingDAO",
    "OnboardingReminderDAO",
    "SurveyDAO",
    "SurveyResponseDAO",
    "SurveyInvitationDAO",
    "FeedbackScoreDAO",
    "EmailTemplateDAO",
    "EmailTemplateVersionDAO",
    "SentEmailDAO",
    "PushSubscriptionDAO",
    "CalendarIntegrationDAO",
    "WebhookEndpointDAO",
    "WebhookDeliveryDAO",
]
