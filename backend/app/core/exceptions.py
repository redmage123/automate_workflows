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
