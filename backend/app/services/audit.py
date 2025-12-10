"""
Audit logging service.

WHAT: Service layer for creating audit log entries with proper context.

WHY: OWASP A09 (Security Logging and Monitoring) requires comprehensive
security event logging. This service provides:
- Simplified interface for logging common events
- Automatic context extraction from request middleware
- Type-safe event logging with proper validation
- Background-safe logging that won't break if context is missing

HOW: Uses the AuditLogDAO for persistence and RequestContext middleware
for automatic IP/user-agent capture. Provides convenience methods for
common event patterns (auth, data changes, admin actions).
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.audit_log import AuditLogDAO
from app.models.audit_log import AuditLog, AuditAction
from app.middleware.request_context import get_request_context


# Logger for audit service errors (not audit events themselves)
logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for creating audit log entries.

    WHAT: Business logic layer for audit logging.

    WHY: Centralizes audit logging logic with:
    - Automatic request context extraction
    - Consistent event formatting
    - Error handling that won't break business operations
    - Type-safe method signatures for common events

    HOW: Wraps AuditLogDAO with convenience methods and automatic
    context injection from the RequestContextMiddleware.

    Example:
        async def login(credentials, db):
            audit = AuditService(db)
            user = await authenticate(credentials)
            if user:
                await audit.log_login_success(user.id)
            else:
                await audit.log_login_failure(credentials.email)
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize audit service with database session.

        Args:
            session: Async database session for audit log persistence
        """
        self.dao = AuditLogDAO(session)
        self._session = session

    def _get_context(self) -> tuple[Optional[str], Optional[str]]:
        """
        Get IP address and user agent from request context.

        WHAT: Extracts request context for audit logging.

        WHY: Automatically captures client information without
        requiring callers to pass it explicitly.

        Returns:
            Tuple of (ip_address, user_agent), both may be None
        """
        ctx = get_request_context()
        if ctx:
            return ctx.ip_address, ctx.user_agent
        return None, None

    async def log_event(
        self,
        action: AuditAction,
        resource_type: str,
        actor_user_id: Optional[int] = None,
        resource_id: Optional[int] = None,
        org_id: Optional[int] = None,
        changes: Optional[Dict[str, Any]] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Log a generic audit event.

        WHAT: Creates an audit log entry with full context.

        WHY: Base method for all audit logging, with automatic
        context extraction and error handling.

        Args:
            action: Type of event (from AuditAction enum)
            resource_type: Category of affected resource
            actor_user_id: User who performed the action
            resource_id: Specific resource ID (optional)
            org_id: Organization context (optional)
            changes: Before/after values for mutations
            extra_data: Additional context
            ip_address: Override auto-detected IP
            user_agent: Override auto-detected user agent

        Returns:
            Created AuditLog or None if logging failed

        Note:
            This method never raises exceptions to prevent audit
            logging from breaking business operations. Errors are
            logged to the application logger instead.
        """
        try:
            # Get context from middleware if not provided
            if ip_address is None or user_agent is None:
                ctx_ip, ctx_ua = self._get_context()
                ip_address = ip_address or ctx_ip
                user_agent = user_agent or ctx_ua

            log = await self.dao.create(
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                org_id=org_id,
                changes=changes,
                extra_data=extra_data,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return log

        except Exception as e:
            # Log error but don't raise - audit logging should never break business logic
            # WHY: Security logging is critical, but a logging failure shouldn't
            # prevent users from logging in or performing other operations
            logger.error(f"Failed to create audit log: {e}", exc_info=True)
            return None

    # =========================================================================
    # Authentication Events
    # =========================================================================

    async def log_login_success(
        self,
        user_id: int,
        org_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[AuditLog]:
        """
        Log a successful login event.

        WHAT: Records a successful authentication.

        WHY: Tracking successful logins helps detect:
        - Account sharing (multiple locations)
        - Compromised accounts (unusual locations)
        - Usage patterns for security analysis

        Args:
            user_id: ID of the authenticated user
            org_id: User's organization ID
            extra_data: Additional context (e.g., login method)

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="auth",
            actor_user_id=user_id,
            org_id=org_id,
            extra_data=extra_data,
        )

    async def log_login_failure(
        self,
        attempted_email: str,
        user_id: Optional[int] = None,
        reason: str = "Invalid credentials",
    ) -> Optional[AuditLog]:
        """
        Log a failed login attempt.

        WHAT: Records a failed authentication attempt.

        WHY: Failed logins are critical for detecting:
        - Brute force attacks
        - Credential stuffing
        - Account takeover attempts
        - User enumeration attacks

        Args:
            attempted_email: Email used in the login attempt
            user_id: User ID if email exists (optional)
            reason: Reason for failure (for internal use)

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.LOGIN_FAILURE,
            resource_type="auth",
            actor_user_id=user_id,
            extra_data={
                "attempted_email": attempted_email,
                "reason": reason,
            },
        )

    async def log_logout(
        self,
        user_id: int,
        org_id: Optional[int] = None,
    ) -> Optional[AuditLog]:
        """
        Log a user logout.

        WHAT: Records when a user explicitly logs out.

        WHY: Logout events help:
        - Track session duration
        - Detect forced logouts (security concern)
        - Verify token blacklisting works

        Args:
            user_id: ID of the logging out user
            org_id: User's organization ID

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.LOGOUT,
            resource_type="auth",
            actor_user_id=user_id,
            org_id=org_id,
        )

    async def log_password_change(
        self,
        user_id: int,
        org_id: Optional[int] = None,
    ) -> Optional[AuditLog]:
        """
        Log a password change.

        WHAT: Records when a user changes their password.

        WHY: Password changes are security-critical events:
        - May indicate account compromise if unexpected
        - Compliance requires tracking password lifecycle
        - Helps support teams troubleshoot access issues

        Args:
            user_id: ID of the user changing password
            org_id: User's organization ID

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.PASSWORD_CHANGE,
            resource_type="auth",
            actor_user_id=user_id,
            org_id=org_id,
        )

    async def log_password_reset_request(
        self,
        email: str,
        user_id: Optional[int] = None,
    ) -> Optional[AuditLog]:
        """
        Log a password reset request.

        WHAT: Records when someone requests a password reset.

        WHY: Reset requests may indicate:
        - Legitimate user forgot password
        - Attacker trying to take over account
        - Phishing attack preparation

        Args:
            email: Email address for reset request
            user_id: User ID if email exists

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.PASSWORD_RESET_REQUEST,
            resource_type="auth",
            actor_user_id=user_id,
            extra_data={"email": email},
        )

    async def log_password_reset_complete(
        self,
        user_id: int,
        org_id: Optional[int] = None,
    ) -> Optional[AuditLog]:
        """
        Log a completed password reset.

        WHAT: Records when a password reset is completed.

        WHY: Completed resets are important for:
        - Verifying reset flow completion
        - Detecting unauthorized password changes
        - Compliance auditing

        Args:
            user_id: ID of the user who reset password
            org_id: User's organization ID

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.PASSWORD_RESET_COMPLETE,
            resource_type="auth",
            actor_user_id=user_id,
            org_id=org_id,
        )

    # =========================================================================
    # Account Events
    # =========================================================================

    async def log_account_created(
        self,
        user_id: int,
        org_id: int,
        created_by: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[AuditLog]:
        """
        Log account creation.

        WHAT: Records when a new user account is created.

        WHY: Account creation is tracked for:
        - User growth analytics
        - Detecting automated account creation (spam/abuse)
        - Compliance auditing

        Args:
            user_id: ID of the new user
            org_id: Organization the user joined
            created_by: ID of user who created the account (for admin creation)
            extra_data: Additional context (e.g., registration source)

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.ACCOUNT_CREATED,
            resource_type="user",
            actor_user_id=created_by or user_id,
            resource_id=user_id,
            org_id=org_id,
            extra_data=extra_data,
        )

    async def log_email_verified(
        self,
        user_id: int,
        org_id: Optional[int] = None,
    ) -> Optional[AuditLog]:
        """
        Log email verification.

        WHAT: Records when a user verifies their email.

        WHY: Email verification is important for:
        - Confirming user owns the email address
        - Enabling email-based features
        - Compliance requirements

        Args:
            user_id: ID of the user who verified email
            org_id: User's organization ID

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.EMAIL_VERIFIED,
            resource_type="user",
            actor_user_id=user_id,
            resource_id=user_id,
            org_id=org_id,
        )

    async def log_email_verification_sent(
        self,
        user_id: int,
        email: str,
    ) -> Optional[AuditLog]:
        """
        Log when an email verification email is sent.

        WHAT: Records email verification email dispatch.

        WHY: Tracking verification emails helps:
        - Debug email delivery issues
        - Detect abuse of verification system
        - Support troubleshooting

        Args:
            user_id: ID of the user
            email: Email address the verification was sent to

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.EMAIL_VERIFICATION_SENT,
            resource_type="user",
            actor_user_id=user_id,
            resource_id=user_id,
            extra_data={"email": email},
        )

    # =========================================================================
    # Organization Events
    # =========================================================================

    async def log_org_created(
        self,
        org_id: int,
        created_by_user_id: int,
        org_name: str,
    ) -> Optional[AuditLog]:
        """
        Log organization creation.

        WHAT: Records when a new organization is created.

        WHY: Organization creation is tracked for:
        - Multi-tenant auditing
        - Billing/subscription events
        - Growth analytics

        Args:
            org_id: ID of the new organization
            created_by_user_id: User who created the org
            org_name: Name of the organization

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.ORG_CREATED,
            resource_type="organization",
            actor_user_id=created_by_user_id,
            resource_id=org_id,
            org_id=org_id,
            extra_data={"org_name": org_name},
        )

    async def log_user_joined_org(
        self,
        user_id: int,
        org_id: int,
        added_by: Optional[int] = None,
    ) -> Optional[AuditLog]:
        """
        Log user joining an organization.

        WHAT: Records when a user joins an organization.

        WHY: Membership changes are important for:
        - Access control auditing
        - Security compliance
        - Team management

        Args:
            user_id: ID of the user joining
            org_id: Organization being joined
            added_by: User who added them (if invited)

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.USER_JOINED_ORG,
            resource_type="organization",
            actor_user_id=added_by or user_id,
            resource_id=user_id,
            org_id=org_id,
        )

    # =========================================================================
    # Role and Permission Events
    # =========================================================================

    async def log_role_change(
        self,
        user_id: int,
        changed_by_user_id: int,
        old_role: str,
        new_role: str,
        org_id: Optional[int] = None,
    ) -> Optional[AuditLog]:
        """
        Log a role change.

        WHAT: Records when a user's role is changed.

        WHY: Role changes are security-critical:
        - Privilege escalation detection
        - Compliance auditing
        - Access control verification

        Args:
            user_id: ID of the user whose role changed
            changed_by_user_id: User who made the change
            old_role: Previous role
            new_role: New role
            org_id: Organization context

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.ROLE_CHANGE,
            resource_type="user",
            actor_user_id=changed_by_user_id,
            resource_id=user_id,
            org_id=org_id,
            changes={
                "role": {
                    "before": old_role,
                    "after": new_role,
                }
            },
        )

    # =========================================================================
    # Data Mutation Events
    # =========================================================================

    async def log_create(
        self,
        resource_type: str,
        resource_id: int,
        actor_user_id: int,
        org_id: int,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[AuditLog]:
        """
        Log resource creation.

        WHAT: Records when any resource is created.

        WHY: Creation events provide complete audit trail of data.

        Args:
            resource_type: Type of resource (e.g., "project", "proposal")
            resource_id: ID of the created resource
            actor_user_id: User who created it
            org_id: Organization owning the resource
            extra_data: Additional context about the resource

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.CREATE,
            resource_type=resource_type,
            actor_user_id=actor_user_id,
            resource_id=resource_id,
            org_id=org_id,
            extra_data=extra_data,
        )

    async def log_update(
        self,
        resource_type: str,
        resource_id: int,
        actor_user_id: int,
        org_id: int,
        changes: Dict[str, Any],
    ) -> Optional[AuditLog]:
        """
        Log resource update.

        WHAT: Records when any resource is updated with before/after values.

        WHY: Update events with changes provide:
        - Complete audit trail
        - Ability to reverse changes
        - Debugging/troubleshooting support

        Args:
            resource_type: Type of resource (e.g., "project", "proposal")
            resource_id: ID of the updated resource
            actor_user_id: User who made the update
            org_id: Organization owning the resource
            changes: Dict with field names as keys and {"before": x, "after": y} as values

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.UPDATE,
            resource_type=resource_type,
            actor_user_id=actor_user_id,
            resource_id=resource_id,
            org_id=org_id,
            changes=changes,
        )

    async def log_delete(
        self,
        resource_type: str,
        resource_id: int,
        actor_user_id: int,
        org_id: int,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[AuditLog]:
        """
        Log resource deletion.

        WHAT: Records when any resource is deleted.

        WHY: Deletion events are critical for:
        - Compliance (knowing what was deleted and when)
        - Recovery investigations
        - Security auditing

        Args:
            resource_type: Type of resource
            resource_id: ID of the deleted resource
            actor_user_id: User who deleted it
            org_id: Organization that owned the resource
            extra_data: Additional context (e.g., resource name for recovery)

        Returns:
            Created AuditLog or None if logging failed
        """
        return await self.log_event(
            action=AuditAction.DELETE,
            resource_type=resource_type,
            actor_user_id=actor_user_id,
            resource_id=resource_id,
            org_id=org_id,
            extra_data=extra_data,
        )


# Dependency for FastAPI routes
async def get_audit_service(session: AsyncSession) -> AuditService:
    """
    FastAPI dependency for getting audit service.

    WHAT: Creates an AuditService instance with the current session.

    WHY: Allows using AuditService as a FastAPI dependency with
    automatic session management.

    Example:
        @router.post("/login")
        async def login(
            db: AsyncSession = Depends(get_db),
            audit: AuditService = Depends(lambda db=Depends(get_db): AuditService(db))
        ):
            ...
    """
    return AuditService(session)
