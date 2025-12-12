"""
Custom exception hierarchy for structured error handling.

WHY: Custom exceptions provide:
1. Consistent error handling across the API
2. HTTP status code mapping for FastAPI
3. Structured error responses with contextual data
4. No sensitive data leaks in error messages (OWASP A04)
5. Easier debugging with detailed context

IMPORTANT: NEVER use base Exception class. Always use custom exceptions.
"""

from typing import Any, Dict, Optional


class AppException(Exception):
    """
    Base exception class for all application exceptions.

    WHY: Centralizing exception handling in a base class ensures consistent
    error responses, HTTP status code mapping, and prevents sensitive data
    leaks in error messages.

    All custom exceptions should inherit from this class.
    """

    status_code: int = 500
    default_message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: Optional[str] = None,
        status_code: Optional[int] = None,
        **context: Any,
    ):
        """
        Initialize exception with message and context.

        WHY: Context parameters allow including debugging information
        (user_id, org_id, etc.) without leaking sensitive data like
        passwords or tokens.

        Args:
            message: Human-readable error message
            status_code: HTTP status code (overrides class default)
            **context: Additional context for debugging (filtered in to_dict)
        """
        self.message = message or self.default_message
        if status_code is not None:
            self.status_code = status_code
        self.context = context
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize exception to dictionary for JSON response.

        WHY: Structured error responses allow frontends to handle errors
        consistently and display appropriate messages to users.

        Returns:
            Dictionary with error details (sensitive fields filtered out)
        """
        # WHY: Filter out sensitive fields to prevent data leaks
        sensitive_fields = {"password", "token", "secret", "key", "api_key"}
        filtered_context = {
            k: v for k, v in self.context.items() if k.lower() not in sensitive_fields
        }

        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "status_code": self.status_code,
            "details": filtered_context if filtered_context else None,
        }


# ============================================================================
# Authentication & Authorization Exceptions (OWASP A07)
# ============================================================================


class AuthenticationError(AppException):
    """
    Raised when authentication fails.

    WHY: Separate exception for authentication failures (invalid credentials,
    expired tokens) allows consistent handling and prevents information
    disclosure about which step of authentication failed.

    HTTP Status: 401 Unauthorized
    """

    status_code = 401
    default_message = "Authentication failed"


class AuthorizationError(AppException):
    """
    Raised when user lacks permissions for an action.

    WHY: Distinguishing authorization (403) from authentication (401) helps
    frontends show appropriate messages ("You don't have permission" vs
    "Please log in").

    HTTP Status: 403 Forbidden
    """

    status_code = 403
    default_message = "You do not have permission to perform this action"


class TokenExpiredError(AuthenticationError):
    """
    Raised when JWT token has expired.

    WHY: Specific exception for expired tokens allows frontends to trigger
    automatic token refresh without logging out the user.

    HTTP Status: 401 Unauthorized
    """

    default_message = "Token has expired"


class TokenInvalidError(AuthenticationError):
    """
    Raised when JWT token is malformed or has invalid signature.

    WHY: Separate from TokenExpiredError to distinguish between expired
    (can refresh) and invalid (must re-authenticate) tokens.

    HTTP Status: 401 Unauthorized
    """

    default_message = "Token is invalid"


# ============================================================================
# Validation & Input Exceptions (OWASP A03: Injection Prevention)
# ============================================================================


class ValidationError(AppException):
    """
    Raised when input validation fails.

    WHY: Validation errors should return 400 Bad Request with details
    about which fields failed validation, helping users correct their input.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Validation failed"


class InputError(ValidationError):
    """
    Raised when input is malformed or doesn't meet constraints.

    WHY: More specific than ValidationError for cases where input format
    is incorrect (e.g., invalid email format, string too long).

    HTTP Status: 400 Bad Request
    """

    default_message = "Invalid input"


# ============================================================================
# Resource Exceptions
# ============================================================================


class ResourceNotFoundError(AppException):
    """
    Raised when a requested resource doesn't exist.

    WHY: 404 Not Found is the standard HTTP status for missing resources.
    Including resource type and ID in context helps debugging.

    HTTP Status: 404 Not Found
    """

    status_code = 404
    default_message = "Resource not found"


class ResourceAlreadyExistsError(AppException):
    """
    Raised when attempting to create a resource that already exists.

    WHY: 409 Conflict indicates the request can't be completed due to
    conflicting state (e.g., email already registered).

    HTTP Status: 409 Conflict
    """

    status_code = 409
    default_message = "Resource already exists"


class ResourceDeletedError(AppException):
    """
    Raised when attempting to access a soft-deleted resource.

    WHY: Soft-deleted resources exist in the database but shouldn't be
    accessible. 410 Gone indicates the resource existed but is no longer available.

    HTTP Status: 410 Gone
    """

    status_code = 410
    default_message = "Resource has been deleted"


# ============================================================================
# Business Logic Exceptions
# ============================================================================


class BusinessRuleViolation(AppException):
    """
    Raised when a business rule is violated.

    WHY: Business rules (e.g., "can't approve proposal without payment")
    are different from validation errors. 422 Unprocessable Entity indicates
    the request was well-formed but semantically incorrect.

    HTTP Status: 422 Unprocessable Entity
    """

    status_code = 422
    default_message = "Business rule violation"


class InvalidStateTransitionError(BusinessRuleViolation):
    """
    Raised when an invalid state transition is attempted.

    WHY: State machines (project status, proposal workflow) have valid
    transitions. Attempting invalid transitions (e.g., approving a draft
    proposal) should fail with a clear error message.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Invalid state transition"


class InsufficientPermissionsError(AuthorizationError):
    """
    Raised when user's role doesn't allow an action.

    WHY: More specific than AuthorizationError for role-based access control
    failures, allowing custom error messages based on required role.

    HTTP Status: 403 Forbidden
    """

    default_message = "Insufficient permissions"


# ============================================================================
# External Service Exceptions (OWASP A08: Software Integrity)
# ============================================================================


class ExternalServiceError(AppException):
    """
    Base exception for external service failures.

    WHY: External API failures should return 502 Bad Gateway, indicating
    the problem is with an upstream service, not our application.

    HTTP Status: 502 Bad Gateway
    """

    status_code = 502
    default_message = "External service error"


class StripeError(ExternalServiceError):
    """
    Raised when Stripe API calls fail.

    WHY: Separate exception for Stripe allows catching and handling
    payment failures specifically, including retries and customer notifications.

    HTTP Status: 502 Bad Gateway
    """

    default_message = "Payment processing error"


class N8nError(ExternalServiceError):
    """
    Raised when n8n API calls fail.

    WHY: n8n workflow failures should be retried and logged separately
    from other external service failures.

    HTTP Status: 502 Bad Gateway
    """

    default_message = "Workflow automation error"


class S3Error(ExternalServiceError):
    """
    Raised when S3/object storage operations fail.

    WHY: File storage failures (upload, download) need specific handling
    and user messaging (e.g., "File upload failed, please try again").

    HTTP Status: 502 Bad Gateway
    """

    default_message = "File storage error"


class EmailServiceError(ExternalServiceError):
    """
    Raised when email sending fails (Resend, Postmark).

    WHY: Email failures should be queued for retry without blocking
    the main operation (e.g., user registration succeeds even if
    welcome email fails).

    HTTP Status: 502 Bad Gateway
    """

    default_message = "Email service error"


class SlackNotificationError(ExternalServiceError):
    """
    Raised when Slack webhook calls fail.

    WHY: Slack notification failures should be logged and not block
    the main operation. Notifications are best-effort delivery.

    HTTP Status: 502 Bad Gateway
    """

    default_message = "Slack notification error"


# ============================================================================
# Database Exceptions
# ============================================================================


class DatabaseError(AppException):
    """
    Raised when database operations fail.

    WHY: Database errors should be caught at the DAO layer and converted
    to application exceptions with safe error messages (no SQL exposed).

    HTTP Status: 500 Internal Server Error
    """

    status_code = 500
    default_message = "Database error"


class DatabaseConnectionError(DatabaseError):
    """
    Raised when database connection fails.

    WHY: Connection failures need specific handling (health checks,
    circuit breakers) separate from query errors.

    HTTP Status: 503 Service Unavailable
    """

    status_code = 503
    default_message = "Database connection failed"


# ============================================================================
# Rate Limiting Exceptions (OWASP A05: Security Misconfiguration)
# ============================================================================


class RateLimitExceeded(AppException):
    """
    Raised when rate limit is exceeded.

    WHY: 429 Too Many Requests is the standard status for rate limiting,
    allowing clients to back off and retry later.

    HTTP Status: 429 Too Many Requests
    """

    status_code = 429
    default_message = "Rate limit exceeded"


# ============================================================================
# Organization/Multi-Tenancy Exceptions (OWASP A01: Broken Access Control)
# ============================================================================


class OrganizationAccessDenied(AuthorizationError):
    """
    Raised when attempting to access resources from another organization.

    WHY: Cross-organization access attempts should be logged for security
    monitoring. Using 404 instead of 403 prevents information disclosure
    about resource existence.

    HTTP Status: 404 Not Found (to prevent information leakage)
    """

    status_code = 404
    default_message = "Resource not found"  # WHY: Don't reveal it exists in another org


# ============================================================================
# Project-Specific Exceptions
# ============================================================================


class ProjectNotFoundError(ResourceNotFoundError):
    """Raised when a project doesn't exist."""

    default_message = "Project not found"


class ProposalNotFoundError(ResourceNotFoundError):
    """Raised when a proposal doesn't exist."""

    default_message = "Proposal not found"


class InvoiceNotFoundError(ResourceNotFoundError):
    """Raised when an invoice doesn't exist."""

    default_message = "Invoice not found"


class WorkflowNotFoundError(ResourceNotFoundError):
    """Raised when a workflow doesn't exist."""

    default_message = "Workflow not found"


class TicketNotFoundError(ResourceNotFoundError):
    """Raised when a ticket doesn't exist."""

    default_message = "Ticket not found"


# ============================================================================
# Audit Log Exceptions (OWASP A09: Security Logging)
# ============================================================================


class AuditLogImmutableError(AppException):
    """
    Raised when attempting to update or delete an audit log.

    WHY: Audit logs must be tamper-proof. Once written, they cannot be
    modified or deleted to maintain forensic integrity and compliance
    with security requirements (SOC 2, HIPAA, etc.).

    HTTP Status: 403 Forbidden
    """

    status_code = 403
    default_message = "Audit logs are immutable and cannot be modified"


# ============================================================================
# Encryption Exceptions (OWASP A02: Cryptographic Failures)
# ============================================================================


class EncryptionError(AppException):
    """
    Raised when encryption or decryption operations fail.

    WHY: Encryption failures should not expose sensitive information.
    Error messages must be generic to prevent information leakage
    about the encryption scheme or key status.

    HTTP Status: 500 Internal Server Error
    """

    status_code = 500
    default_message = "Encryption operation failed"


# ============================================================================
# OAuth Exceptions (OWASP A07: Identification and Authentication Failures)
# ============================================================================


class OAuthError(ExternalServiceError):
    """
    Base exception for OAuth-related failures.

    WHY: OAuth errors need specific handling because they involve external
    identity providers (Google, GitHub, etc.) and require user-friendly
    error messages explaining what went wrong with social login.

    HTTP Status: 502 Bad Gateway (default for external service errors)
    """

    default_message = "OAuth authentication failed"


class OAuthProviderError(OAuthError):
    """
    Raised when the OAuth provider (Google, GitHub) returns an error.

    WHY: Provider errors (e.g., user denied consent, server unavailable)
    should be distinguished from our application errors for debugging
    and user messaging.

    HTTP Status: 502 Bad Gateway
    """

    default_message = "OAuth provider returned an error"


class OAuthStateError(OAuthError):
    """
    Raised when OAuth state parameter validation fails.

    WHY: State parameter prevents CSRF attacks in OAuth flows. Invalid
    state indicates either a CSRF attempt or an expired/reused auth flow.
    Use 400 instead of 502 because this is a client-side issue.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Invalid OAuth state - please try again"


class OAuthTokenError(OAuthError):
    """
    Raised when OAuth token exchange or validation fails.

    WHY: Token errors (expired code, invalid code, revoked access) need
    specific handling to guide users through re-authentication.

    HTTP Status: 401 Unauthorized
    """

    status_code = 401
    default_message = "OAuth token invalid or expired"


class OAuthAccountLinkError(AppException):
    """
    Raised when linking/unlinking OAuth accounts fails.

    WHY: Account linking can fail for business reasons (already linked,
    email mismatch, etc.) that aren't external service errors.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Failed to link OAuth account"


class OAuthAccountNotFoundError(ResourceNotFoundError):
    """
    Raised when an OAuth account doesn't exist.

    WHY: Used when trying to unlink an OAuth account that isn't linked
    or when looking up a user by OAuth provider ID fails.

    HTTP Status: 404 Not Found
    """

    default_message = "OAuth account not found"


# ============================================================================
# AI Service Exceptions
# ============================================================================


class AIServiceError(ExternalServiceError):
    """
    Base exception for AI/LLM service failures.

    WHY: AI services (OpenAI, Anthropic) are external dependencies that can fail
    due to rate limits, API issues, or model errors. These need specific handling
    for retries, fallbacks, and user messaging.

    HTTP Status: 502 Bad Gateway
    """

    default_message = "AI service error"


class AIGenerationError(AIServiceError):
    """
    Raised when AI content generation fails.

    WHY: Generation failures (invalid output, parsing errors, model refusals)
    need specific handling to provide useful feedback to users about what
    went wrong with their request.

    HTTP Status: 422 Unprocessable Entity
    """

    status_code = 422
    default_message = "AI generation failed"


class AIRateLimitError(AIServiceError):
    """
    Raised when AI service rate limit is exceeded.

    WHY: Rate limits are common with AI APIs. Users should be informed
    to wait before retrying, and the system should implement backoff.

    HTTP Status: 429 Too Many Requests
    """

    status_code = 429
    default_message = "AI service rate limit exceeded - please try again later"


# ============================================================================
# Workflow Version Exceptions
# ============================================================================


class WorkflowVersionError(AppException):
    """
    Base exception for workflow version operations.

    WHY: Version operations can fail for various reasons including
    invalid version numbers, concurrent modifications, etc.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Workflow version operation failed"


class WorkflowVersionNotFoundError(ResourceNotFoundError):
    """
    Raised when a workflow version doesn't exist.

    WHY: Users may request versions that don't exist, either because
    the version number is wrong or versions were pruned.

    HTTP Status: 404 Not Found
    """

    default_message = "Workflow version not found"


class WorkflowVersionRestoreError(WorkflowVersionError):
    """
    Raised when version restoration fails.

    WHY: Restoration can fail if the version's workflow JSON is
    incompatible with current n8n, or if n8n API fails.

    HTTP Status: 400 Bad Request
    """

    default_message = "Failed to restore workflow version"


# ============================================================================
# Document Exceptions
# ============================================================================


class DocumentError(AppException):
    """
    Base exception for document operations.

    WHY: Document operations involve file I/O and S3,
    which can fail for various reasons.

    HTTP Status: 500 Internal Server Error
    """

    status_code = 500
    default_message = "Document operation failed"


class DocumentNotFoundError(ResourceNotFoundError):
    """
    Raised when document doesn't exist.

    WHY: Documents can be deleted or access can be revoked.

    HTTP Status: 404 Not Found
    """

    default_message = "Document not found"


class DocumentAccessDeniedError(AuthorizationError):
    """
    Raised when user can't access document.

    WHY: Documents have fine-grained access control.
    Users may not have view/download permissions.

    HTTP Status: 403 Forbidden
    """

    default_message = "Document access denied"


class DocumentUploadError(DocumentError):
    """
    Raised when document upload fails.

    WHY: Uploads can fail due to file size, type restrictions,
    or storage service issues.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Document upload failed"


class DocumentStorageError(ExternalServiceError):
    """
    Raised when S3/storage operations fail.

    WHY: S3 operations can fail due to network issues,
    permissions, or service outages.

    HTTP Status: 502 Bad Gateway
    """

    default_message = "Document storage error"


# ============================================================================
# Messaging Exceptions
# ============================================================================


class MessageError(AppException):
    """
    Base exception for messaging operations.

    WHY: Messaging can fail due to invalid recipients,
    rate limits, or database issues.

    HTTP Status: 500 Internal Server Error
    """

    status_code = 500
    default_message = "Messaging error"


class MessageNotFoundError(ResourceNotFoundError):
    """
    Raised when message doesn't exist.

    WHY: Messages can be deleted by sender or recipient.

    HTTP Status: 404 Not Found
    """

    default_message = "Message not found"


class ConversationNotFoundError(ResourceNotFoundError):
    """
    Raised when conversation doesn't exist.

    WHY: Conversations can be deleted or user may not have access.

    HTTP Status: 404 Not Found
    """

    default_message = "Conversation not found"


class NotParticipantError(AuthorizationError):
    """
    Raised when user is not a participant in a conversation.

    WHY: Users can only access conversations they're part of.
    Using 403 Forbidden to indicate access control failure.

    HTTP Status: 403 Forbidden
    """

    default_message = "You are not a participant in this conversation"


class MessageRecipientError(ValidationError):
    """
    Raised when recipient is invalid.

    WHY: Recipients must be valid users in the same organization.

    HTTP Status: 400 Bad Request
    """

    default_message = "Invalid message recipient"


# ============================================================================
# Report Exceptions
# ============================================================================


class ReportError(AppException):
    """
    Base exception for reporting operations.

    WHY: Report generation can fail due to data issues,
    template problems, or output generation failures.

    HTTP Status: 500 Internal Server Error
    """

    status_code = 500
    default_message = "Report generation error"


class ReportNotFoundError(ResourceNotFoundError):
    """
    Raised when report or template doesn't exist.

    WHY: Reports and templates can be deleted or not exist.

    HTTP Status: 404 Not Found
    """

    default_message = "Report not found"


class ReportGenerationError(ReportError):
    """
    Raised when report generation fails.

    WHY: Reports may fail due to data queries, template rendering,
    or PDF/Excel generation issues.

    HTTP Status: 500 Internal Server Error
    """

    default_message = "Failed to generate report"


class ReportScheduleError(ReportError):
    """
    Raised when report scheduling fails.

    WHY: Schedule expressions may be invalid or conflicts may exist.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Invalid report schedule"


# ============================================================================
# Time Tracking Exceptions
# ============================================================================


class TimeEntryError(AppException):
    """
    Base exception for time tracking.

    WHY: Time entries have validation rules around dates,
    durations, and billability.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Time entry error"


class TimeEntryNotFoundError(ResourceNotFoundError):
    """
    Raised when time entry doesn't exist.

    WHY: Time entries can be deleted.

    HTTP Status: 404 Not Found
    """

    default_message = "Time entry not found"


class TimeEntryOverlapError(TimeEntryError):
    """
    Raised when time entries overlap.

    WHY: Time entries for the same user should not overlap
    to maintain accurate tracking.

    HTTP Status: 400 Bad Request
    """

    default_message = "Time entries cannot overlap"


class TimeEntryAlreadyInvoicedError(TimeEntryError):
    """
    Raised when modifying an invoiced time entry.

    WHY: Once time is invoiced, it cannot be modified to
    maintain billing integrity.

    HTTP Status: 403 Forbidden
    """

    status_code = 403
    default_message = "Cannot modify invoiced time entry"


# ============================================================================
# Survey Exceptions
# ============================================================================


class SurveyError(AppException):
    """
    Base exception for survey operations.

    WHY: Surveys have validation rules and response constraints.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Survey error"


class SurveyNotFoundError(ResourceNotFoundError):
    """
    Raised when survey doesn't exist.

    WHY: Surveys can be deleted or deactivated.

    HTTP Status: 404 Not Found
    """

    default_message = "Survey not found"


class SurveyAlreadyRespondedError(SurveyError):
    """
    Raised when user has already responded.

    WHY: Most surveys allow only one response per user.

    HTTP Status: 409 Conflict
    """

    status_code = 409
    default_message = "Survey already completed"


# ============================================================================
# Calendar Integration Exceptions
# ============================================================================


class CalendarIntegrationError(ExternalServiceError):
    """
    Base exception for calendar operations.

    WHY: Calendar APIs (Google, Outlook) can fail due to
    auth issues, rate limits, or service outages.

    HTTP Status: 502 Bad Gateway
    """

    default_message = "Calendar integration error"


class CalendarSyncError(CalendarIntegrationError):
    """
    Raised when calendar sync fails.

    WHY: Sync can fail due to permission changes, token expiration,
    or calendar service issues.

    HTTP Status: 502 Bad Gateway
    """

    default_message = "Calendar sync failed"


class CalendarAuthError(CalendarIntegrationError):
    """
    Raised when calendar authentication fails.

    WHY: OAuth tokens can expire or be revoked.

    HTTP Status: 401 Unauthorized
    """

    status_code = 401
    default_message = "Calendar authentication failed"


# ============================================================================
# Webhook Exceptions
# ============================================================================


class WebhookError(AppException):
    """
    Base exception for webhook operations.

    WHY: Webhooks can fail due to delivery issues,
    invalid endpoints, or signature problems.

    HTTP Status: 500 Internal Server Error
    """

    status_code = 500
    default_message = "Webhook error"


class WebhookNotFoundError(ResourceNotFoundError):
    """
    Raised when webhook doesn't exist.

    WHY: Webhooks can be deleted.

    HTTP Status: 404 Not Found
    """

    default_message = "Webhook not found"


class WebhookDeliveryError(WebhookError):
    """
    Raised when webhook delivery fails.

    WHY: Target endpoints can be down, timeout, or return errors.

    HTTP Status: 502 Bad Gateway
    """

    status_code = 502
    default_message = "Webhook delivery failed"


class WebhookSignatureError(WebhookError):
    """
    Raised when webhook signature is invalid.

    WHY: Signature validation prevents replay attacks
    and ensures webhook authenticity.

    HTTP Status: 401 Unauthorized
    """

    status_code = 401
    default_message = "Invalid webhook signature"


# ============================================================================
# Announcement Exceptions
# ============================================================================


class AnnouncementError(AppException):
    """
    Base exception for announcement operations.

    WHY: Announcements have validation rules for targeting and scheduling.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Announcement error"


class AnnouncementNotFoundError(ResourceNotFoundError):
    """
    Raised when announcement doesn't exist.

    WHY: Announcements can be deleted or expired.

    HTTP Status: 404 Not Found
    """

    default_message = "Announcement not found"


# ============================================================================
# Onboarding Exceptions
# ============================================================================


class OnboardingError(AppException):
    """
    Base exception for onboarding operations.

    WHY: Onboarding flows have validation rules and step dependencies.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Onboarding error"


class OnboardingTemplateNotFoundError(ResourceNotFoundError):
    """
    Raised when onboarding template doesn't exist.

    WHY: Templates can be deleted or deactivated.

    HTTP Status: 404 Not Found
    """

    default_message = "Onboarding template not found"


class OnboardingNotFoundError(ResourceNotFoundError):
    """
    Raised when client onboarding doesn't exist.

    WHY: Onboarding records can be deleted.

    HTTP Status: 404 Not Found
    """

    default_message = "Onboarding not found"


class OnboardingStepError(OnboardingError):
    """
    Raised when onboarding step operation fails.

    WHY: Steps may have prerequisites or validation requirements.

    HTTP Status: 400 Bad Request
    """

    default_message = "Onboarding step error"


# ============================================================================
# Activity Feed Exceptions
# ============================================================================


class ActivityEventError(AppException):
    """
    Base exception for activity feed operations.

    WHY: Activity events have validation rules for event types and entities.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Activity event error"


# ============================================================================
# Email Template Exceptions
# ============================================================================


class EmailTemplateError(AppException):
    """
    Base exception for email template operations.

    WHY: Templates have validation rules for syntax and variables.

    HTTP Status: 400 Bad Request
    """

    status_code = 400
    default_message = "Email template error"


class EmailTemplateNotFoundError(ResourceNotFoundError):
    """
    Raised when email template doesn't exist.

    WHY: Templates can be deleted.

    HTTP Status: 404 Not Found
    """

    default_message = "Email template not found"


class EmailTemplateRenderError(EmailTemplateError):
    """
    Raised when template rendering fails.

    WHY: Templates may have syntax errors or missing variables.

    HTTP Status: 422 Unprocessable Entity
    """

    status_code = 422
    default_message = "Failed to render email template"
