"""
Email service for sending transactional emails.

WHAT: This service provides a unified interface for sending emails using
various email providers (Resend, Postmark) with fallback support.

WHY: Email is critical for:
1. Account verification - Prevent fake account creation (SEC-007)
2. Password reset - Secure account recovery (AUTH-009)
3. Notifications - Keep users informed about important events
4. Security alerts - Notify users of suspicious activity

HOW: Uses the Resend API (primary) with optional Postmark fallback.
The service abstracts provider details and provides:
- Template-based email composition
- Async sending for non-blocking operation
- Error handling with custom exceptions
- Audit logging for email events

Design decisions:
- Provider abstraction: Easy to switch providers
- Template system: Consistent, branded emails
- Fail-safe: Non-critical emails don't break business operations
- Rate limiting: Prevent email spam abuse
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import EmailServiceError
from app.services.email_template_service import get_email_template_service, EmailTemplateService

logger = logging.getLogger(__name__)


# ============================================================================
# Email Types and Templates
# ============================================================================


class EmailType(str, Enum):
    """
    Types of transactional emails.

    WHY: Categorizing emails enables:
    - Different templates per type
    - Tracking and analytics per type
    - Rate limiting per type
    - Preference management (user can opt-out of certain types)
    """

    VERIFICATION = "verification"
    """Account email verification."""

    PASSWORD_RESET = "password_reset"
    """Password reset request."""

    WELCOME = "welcome"
    """Welcome email after registration."""

    PASSWORD_CHANGED = "password_changed"
    """Notification that password was changed."""

    SECURITY_ALERT = "security_alert"
    """Security-related notifications (e.g., new device login)."""

    INVOICE = "invoice"
    """Invoice/payment related emails."""

    PROPOSAL = "proposal"
    """Proposal notifications."""

    TICKET = "ticket"
    """Support ticket updates."""


@dataclass
class EmailMessage:
    """
    Represents an email to be sent.

    WHAT: Data container for email content and metadata.

    WHY: Structured email data ensures:
    - All required fields are present
    - Consistent email formatting
    - Easy serialization for logging/queuing
    """

    to_email: str
    """Recipient email address."""

    subject: str
    """Email subject line."""

    html_content: str
    """HTML email body."""

    text_content: Optional[str] = None
    """Plain text fallback (optional but recommended)."""

    from_email: Optional[str] = None
    """Sender email (defaults to configured sender)."""

    from_name: Optional[str] = None
    """Sender display name."""

    reply_to: Optional[str] = None
    """Reply-to address."""

    email_type: EmailType = EmailType.VERIFICATION
    """Type of email for tracking/logging."""

    metadata: Optional[Dict[str, Any]] = None
    """Additional metadata for tracking."""


@dataclass
class EmailResult:
    """
    Result of an email send operation.

    WHY: Provides feedback on email send status for:
    - Error handling
    - Audit logging
    - Retry logic
    """

    success: bool
    """Whether email was sent successfully."""

    message_id: Optional[str] = None
    """Provider message ID for tracking."""

    error: Optional[str] = None
    """Error message if send failed."""

    provider: Optional[str] = None
    """Which provider was used."""


# ============================================================================
# Email Provider Interface
# ============================================================================


class EmailProvider(ABC):
    """
    Abstract base class for email providers.

    WHY: Provider abstraction allows:
    - Easy switching between providers (Resend, Postmark, SendGrid, etc.)
    - Fallback chains for reliability
    - Testing with mock providers
    """

    @abstractmethod
    async def send(self, message: EmailMessage) -> EmailResult:
        """
        Send an email message.

        Args:
            message: The email message to send

        Returns:
            EmailResult with success status and provider details
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if this provider is properly configured.

        Returns:
            True if API keys/credentials are present
        """
        pass


class ResendProvider(EmailProvider):
    """
    Resend email provider implementation.

    WHY: Resend provides:
    - Simple, developer-friendly API
    - Good deliverability
    - Reasonable pricing
    - Webhook support for delivery tracking
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Resend provider.

        Args:
            api_key: Resend API key (defaults to settings)
        """
        self._api_key = api_key or settings.RESEND_API_KEY
        self._default_from = f"Automation Platform <noreply@{self._get_domain()}>"

    def _get_domain(self) -> str:
        """Get domain from FRONTEND_URL for default sender."""
        from urllib.parse import urlparse

        parsed = urlparse(settings.FRONTEND_URL)
        return parsed.netloc or "localhost"

    def is_configured(self) -> bool:
        """Check if Resend API key is configured."""
        return bool(self._api_key)

    async def send(self, message: EmailMessage) -> EmailResult:
        """
        Send email via Resend API.

        WHAT: Makes HTTP request to Resend API to send email.

        WHY: Resend's simple REST API is easy to integrate and
        provides good deliverability.

        HOW: Uses httpx for async HTTP requests to Resend API.

        Args:
            message: Email message to send

        Returns:
            EmailResult with send status
        """
        if not self.is_configured():
            return EmailResult(
                success=False,
                error="Resend API key not configured",
                provider="resend",
            )

        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": message.from_email or self._default_from,
                        "to": [message.to_email],
                        "subject": message.subject,
                        "html": message.html_content,
                        "text": message.text_content,
                        "reply_to": message.reply_to,
                    },
                    timeout=30.0,
                )

                if response.status_code in (200, 201):
                    data = response.json()
                    return EmailResult(
                        success=True,
                        message_id=data.get("id"),
                        provider="resend",
                    )
                else:
                    return EmailResult(
                        success=False,
                        error=f"Resend API error: {response.status_code} - {response.text}",
                        provider="resend",
                    )

        except Exception as e:
            logger.error(f"Resend send error: {e}")
            return EmailResult(
                success=False,
                error=str(e),
                provider="resend",
            )


class MockEmailProvider(EmailProvider):
    """
    Mock email provider for testing and development.

    WHY: Allows testing email flows without sending real emails.
    Logs emails instead of sending them.
    """

    sent_emails: List[EmailMessage] = []
    """Class-level list to track sent emails for testing."""

    def is_configured(self) -> bool:
        """Mock provider is always configured."""
        return True

    async def send(self, message: EmailMessage) -> EmailResult:
        """
        Mock send - logs email instead of sending.

        Args:
            message: Email message to "send"

        Returns:
            Always returns success
        """
        logger.info(
            f"[MOCK EMAIL] To: {message.to_email}, "
            f"Subject: {message.subject}, "
            f"Type: {message.email_type.value}"
        )

        # Track for testing
        MockEmailProvider.sent_emails.append(message)

        return EmailResult(
            success=True,
            message_id=f"mock-{datetime.utcnow().timestamp()}",
            provider="mock",
        )

    @classmethod
    def clear_sent_emails(cls):
        """Clear sent emails list (for test cleanup)."""
        cls.sent_emails = []


# ============================================================================
# Email Templates
# ============================================================================


class EmailTemplates:
    """
    Email templates for different email types.

    WHY: Centralized templates ensure:
    - Consistent branding across all emails
    - Easy updates to email content
    - Separation of content from sending logic
    """

    @staticmethod
    def _base_template(content: str, title: str = "") -> str:
        """
        Base HTML template wrapper.

        WHY: Consistent styling and structure for all emails.
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 40px auto;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background-color: #2563eb;
                    color: white;
                    padding: 24px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                    font-weight: 600;
                }}
                .content {{
                    padding: 32px;
                }}
                .button {{
                    display: inline-block;
                    background-color: #2563eb;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 500;
                    margin: 16px 0;
                }}
                .button:hover {{
                    background-color: #1d4ed8;
                }}
                .footer {{
                    background-color: #f9fafb;
                    padding: 16px 32px;
                    text-align: center;
                    font-size: 14px;
                    color: #6b7280;
                }}
                .code {{
                    background-color: #f3f4f6;
                    padding: 12px 16px;
                    border-radius: 6px;
                    font-family: monospace;
                    font-size: 18px;
                    letter-spacing: 2px;
                    text-align: center;
                    margin: 16px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Automation Platform</h1>
                </div>
                <div class="content">
                    {content}
                </div>
                <div class="footer">
                    <p>&copy; {datetime.utcnow().year} Automation Platform. All rights reserved.</p>
                    <p>If you didn't request this email, please ignore it.</p>
                </div>
            </div>
        </body>
        </html>
        """

    @classmethod
    def verification_email(
        cls,
        user_name: str,
        verification_url: str,
        verification_code: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """
        Generate email verification email.

        WHY: Email verification prevents:
        - Fake account creation
        - Typo-based account issues
        - Spam account abuse

        Args:
            user_name: User's display name
            verification_url: URL to verify email
            verification_code: Optional 6-digit code

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        subject = "Verify your email address"

        code_section = ""
        if verification_code:
            code_section = f"""
            <p>Or enter this code manually:</p>
            <div class="code">{verification_code}</div>
            """

        content = f"""
        <h2>Welcome, {user_name}!</h2>
        <p>Thank you for creating an account. Please verify your email address
        to complete your registration and access all features.</p>

        <p style="text-align: center;">
            <a href="{verification_url}" class="button">Verify Email Address</a>
        </p>

        {code_section}

        <p>This link will expire in 24 hours.</p>

        <p>If you didn't create an account, you can safely ignore this email.</p>
        """

        html_content = cls._base_template(content, title=subject)

        text_content = f"""
Welcome, {user_name}!

Thank you for creating an account. Please verify your email address
by clicking the link below:

{verification_url}

{"Or enter this code: " + verification_code if verification_code else ""}

This link will expire in 24 hours.

If you didn't create an account, you can safely ignore this email.
        """

        return subject, html_content, text_content

    @classmethod
    def password_reset_email(
        cls,
        user_name: str,
        reset_url: str,
        reset_code: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """
        Generate password reset email.

        WHY: Password reset is critical for:
        - Account recovery when password is forgotten
        - Security when password may be compromised

        Args:
            user_name: User's display name
            reset_url: URL to reset password
            reset_code: Optional 6-digit code

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        subject = "Reset your password"

        code_section = ""
        if reset_code:
            code_section = f"""
            <p>Or enter this code manually:</p>
            <div class="code">{reset_code}</div>
            """

        content = f"""
        <h2>Password Reset Request</h2>
        <p>Hi {user_name},</p>
        <p>We received a request to reset your password. Click the button below
        to create a new password:</p>

        <p style="text-align: center;">
            <a href="{reset_url}" class="button">Reset Password</a>
        </p>

        {code_section}

        <p><strong>This link will expire in 1 hour.</strong></p>

        <p style="color: #dc2626;"><strong>Security Note:</strong> If you didn't
        request this password reset, please ignore this email. Your password will
        remain unchanged.</p>
        """

        html_content = cls._base_template(content, title=subject)

        text_content = f"""
Password Reset Request

Hi {user_name},

We received a request to reset your password. Click the link below
to create a new password:

{reset_url}

{"Or enter this code: " + reset_code if reset_code else ""}

This link will expire in 1 hour.

Security Note: If you didn't request this password reset, please ignore this email.
Your password will remain unchanged.
        """

        return subject, html_content, text_content

    @classmethod
    def password_changed_email(
        cls,
        user_name: str,
    ) -> tuple[str, str, str]:
        """
        Generate password changed notification.

        WHY: Notifying users of password changes helps detect
        unauthorized account access.

        Args:
            user_name: User's display name

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        subject = "Your password has been changed"

        content = f"""
        <h2>Password Changed</h2>
        <p>Hi {user_name},</p>
        <p>Your password was recently changed. If you made this change,
        you can safely ignore this email.</p>

        <p style="color: #dc2626;"><strong>Didn't change your password?</strong>
        If you didn't make this change, your account may be compromised.
        Please reset your password immediately and contact support.</p>

        <p style="text-align: center;">
            <a href="{settings.FRONTEND_URL}/auth/forgot-password" class="button">
                Reset Password
            </a>
        </p>
        """

        html_content = cls._base_template(content, title=subject)

        text_content = f"""
Password Changed

Hi {user_name},

Your password was recently changed. If you made this change,
you can safely ignore this email.

Didn't change your password?
If you didn't make this change, your account may be compromised.
Please reset your password immediately:
{settings.FRONTEND_URL}/auth/forgot-password
        """

        return subject, html_content, text_content


# ============================================================================
# Email Service
# ============================================================================


class EmailService:
    """
    High-level email service for sending transactional emails.

    WHAT: Provides a simple interface for sending various types of
    transactional emails with templates and error handling.

    WHY: Centralizes email logic:
    - Template management
    - Provider abstraction
    - Error handling
    - Logging and audit

    HOW: Uses email providers (Resend/Postmark) with fallback support,
    Jinja2 templates for consistent emails, and async sending for performance.
    """

    def __init__(
        self,
        provider: Optional[EmailProvider] = None,
        template_service: Optional[EmailTemplateService] = None,
    ):
        """
        Initialize email service.

        Args:
            provider: Email provider to use (auto-detected if not provided)
            template_service: Template service for rendering (auto-created if not provided)
        """
        if provider:
            self._provider = provider
        elif settings.RESEND_API_KEY:
            self._provider = ResendProvider()
        else:
            # Use mock provider in development/testing
            logger.warning("No email provider configured, using mock provider")
            self._provider = MockEmailProvider()

        self._template_service = template_service or get_email_template_service()

    async def send_email(self, message: EmailMessage) -> EmailResult:
        """
        Send an email message.

        WHAT: Sends an email using the configured provider.

        WHY: Central entry point for all email sending ensures:
        - Consistent error handling
        - Logging of all emails
        - Future support for queuing/retry

        Args:
            message: Email message to send

        Returns:
            EmailResult with send status

        Raises:
            EmailServiceError: If critical email fails (optional based on type)
        """
        logger.info(
            f"Sending {message.email_type.value} email to {message.to_email}",
            extra={
                "email_type": message.email_type.value,
                "to": message.to_email,
            },
        )

        result = await self._provider.send(message)

        if result.success:
            logger.info(
                f"Email sent successfully: {result.message_id}",
                extra={
                    "message_id": result.message_id,
                    "provider": result.provider,
                },
            )
        else:
            logger.error(
                f"Email send failed: {result.error}",
                extra={
                    "email_type": message.email_type.value,
                    "to": message.to_email,
                    "error": result.error,
                },
            )

        return result

    async def send_verification_email(
        self,
        to_email: str,
        user_name: str,
        verification_token: str,
        verification_code: Optional[str] = None,
    ) -> EmailResult:
        """
        Send email verification email.

        WHAT: Sends email with verification link/code to confirm email ownership.

        WHY: Email verification prevents fake accounts and ensures users
        can receive important communications (OWASP A07).

        HOW: Renders Jinja2 template with user data and sends via provider.

        Args:
            to_email: Recipient email address
            user_name: User's display name
            verification_token: Token for verification URL
            verification_code: Optional 6-digit code

        Returns:
            EmailResult with send status
        """
        verification_url = (
            f"{settings.FRONTEND_URL}/auth/verify-email?token={verification_token}"
        )

        # Use Jinja2 templates for professional emails
        subject, html_content, text_content = self._template_service.render_verification_email(
            user_name=user_name,
            verification_url=verification_url,
            verification_code=verification_code,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.VERIFICATION,
            metadata={
                "user_name": user_name,
                "has_code": verification_code is not None,
            },
        )

        return await self.send_email(message)

    async def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_token: str,
        reset_code: Optional[str] = None,
    ) -> EmailResult:
        """
        Send password reset email.

        WHAT: Sends email with password reset link/code.

        WHY: Secure password recovery for users who forgot their password.

        HOW: Renders Jinja2 template with reset URL and sends via provider.

        Args:
            to_email: Recipient email address
            user_name: User's display name
            reset_token: Token for reset URL
            reset_code: Optional 6-digit code

        Returns:
            EmailResult with send status
        """
        reset_url = (
            f"{settings.FRONTEND_URL}/auth/reset-password?token={reset_token}"
        )

        # Use Jinja2 templates for professional emails
        subject, html_content, text_content = self._template_service.render_password_reset_email(
            user_name=user_name,
            reset_url=reset_url,
            reset_code=reset_code,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.PASSWORD_RESET,
            metadata={
                "user_name": user_name,
                "has_code": reset_code is not None,
            },
        )

        return await self.send_email(message)

    async def send_password_changed_email(
        self,
        to_email: str,
        user_name: str,
        ip_address: Optional[str] = None,
        location: Optional[str] = None,
    ) -> EmailResult:
        """
        Send password changed notification.

        WHAT: Notifies user that their password was changed.

        WHY: Security notification helps detect unauthorized access.

        HOW: Renders Jinja2 template with change details and sends via provider.

        Args:
            to_email: Recipient email address
            user_name: User's display name
            ip_address: IP address where change was made
            location: Approximate location

        Returns:
            EmailResult with send status
        """
        # Use Jinja2 templates for professional emails
        subject, html_content, text_content = self._template_service.render_password_changed_email(
            user_name=user_name,
            ip_address=ip_address,
            location=location,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.PASSWORD_CHANGED,
        )

        return await self.send_email(message)

    async def send_welcome_email(
        self,
        to_email: str,
        user_name: str,
        organization_name: Optional[str] = None,
    ) -> EmailResult:
        """
        Send welcome email after registration/verification.

        WHAT: Welcomes new user and guides them to get started.

        WHY: Improves user onboarding and engagement.

        HOW: Renders Jinja2 template with welcome message and sends via provider.

        Args:
            to_email: Recipient email address
            user_name: User's display name
            organization_name: User's organization name

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = self._template_service.render_welcome_email(
            user_name=user_name,
            organization_name=organization_name,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.WELCOME,
        )

        return await self.send_email(message)

    async def send_ticket_created_email(
        self,
        to_email: str,
        user_name: str,
        ticket_id: int,
        ticket_subject: str,
        ticket_description: Optional[str] = None,
        ticket_priority: str = "medium",
        ticket_category: str = "general",
        sla_response_hours: int = 24,
        sla_resolution_hours: int = 72,
    ) -> EmailResult:
        """
        Send ticket created notification.

        WHAT: Confirms ticket receipt with SLA expectations.

        WHY: Sets customer expectations for response time.

        HOW: Renders Jinja2 template with ticket details and sends via provider.

        Args:
            to_email: Recipient email address
            user_name: User's display name
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            ticket_description: Ticket description
            ticket_priority: Priority level
            ticket_category: Category
            sla_response_hours: SLA response hours
            sla_resolution_hours: SLA resolution hours

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = self._template_service.render_ticket_created_email(
            user_name=user_name,
            ticket_id=ticket_id,
            ticket_subject=ticket_subject,
            ticket_description=ticket_description,
            ticket_priority=ticket_priority,
            ticket_category=ticket_category,
            sla_response_hours=sla_response_hours,
            sla_resolution_hours=sla_resolution_hours,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.TICKET,
            metadata={
                "ticket_id": ticket_id,
                "action": "created",
            },
        )

        return await self.send_email(message)

    async def send_ticket_updated_email(
        self,
        to_email: str,
        user_name: str,
        ticket_id: int,
        ticket_subject: str,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        updated_by: Optional[str] = None,
        update_message: Optional[str] = None,
    ) -> EmailResult:
        """
        Send ticket updated notification.

        WHAT: Notifies user of ticket status or assignment changes.

        WHY: Keeps users informed of ticket progress.

        HOW: Renders Jinja2 template with update details and sends via provider.

        Args:
            to_email: Recipient email address
            user_name: User's display name
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            old_status: Previous status
            new_status: New status
            assigned_to: Assigned agent
            updated_by: Who made the update
            update_message: Optional message

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = self._template_service.render_ticket_updated_email(
            user_name=user_name,
            ticket_id=ticket_id,
            ticket_subject=ticket_subject,
            old_status=old_status,
            new_status=new_status,
            assigned_to=assigned_to,
            updated_by=updated_by,
            update_message=update_message,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.TICKET,
            metadata={
                "ticket_id": ticket_id,
                "action": "updated",
                "new_status": new_status,
            },
        )

        return await self.send_email(message)

    async def send_ticket_comment_email(
        self,
        to_email: str,
        user_name: str,
        ticket_id: int,
        ticket_subject: str,
        comment_author: str,
        comment_author_role: str,
        comment_text: str,
    ) -> EmailResult:
        """
        Send ticket comment notification.

        WHAT: Notifies user of new comment on their ticket.

        WHY: Keeps all parties informed of ticket conversation.

        HOW: Renders Jinja2 template with comment details and sends via provider.

        Args:
            to_email: Recipient email address
            user_name: User's display name
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            comment_author: Comment author name
            comment_author_role: Author role (agent/client)
            comment_text: Comment content

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = self._template_service.render_ticket_comment_email(
            user_name=user_name,
            ticket_id=ticket_id,
            ticket_subject=ticket_subject,
            comment_author=comment_author,
            comment_author_role=comment_author_role,
            comment_text=comment_text,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.TICKET,
            metadata={
                "ticket_id": ticket_id,
                "action": "comment",
            },
        )

        return await self.send_email(message)

    async def send_proposal_sent_email(
        self,
        to_email: str,
        user_name: str,
        proposal_id: int,
        proposal_title: str,
        total_amount: str,
        currency: str = "USD",
        expires_at: Optional[str] = None,
        sender_name: str = "Your service provider",
        organization_name: str = "Automation Platform",
        project_name: Optional[str] = None,
        line_items: Optional[List[Dict[str, Any]]] = None,
    ) -> EmailResult:
        """
        Send proposal sent notification to client.

        WHAT: Notifies client of new proposal requiring review.

        WHY: Prompts client action on proposal.

        HOW: Renders Jinja2 template with proposal details and sends via provider.

        Args:
            to_email: Client email address
            user_name: Client's display name
            proposal_id: Proposal ID
            proposal_title: Proposal title
            total_amount: Total amount (formatted)
            currency: Currency code
            expires_at: Expiration date
            sender_name: Sender name
            organization_name: Organization name
            project_name: Related project name
            line_items: List of line items

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = self._template_service.render_proposal_sent_email(
            user_name=user_name,
            proposal_id=proposal_id,
            proposal_title=proposal_title,
            total_amount=total_amount,
            currency=currency,
            expires_at=expires_at,
            sender_name=sender_name,
            organization_name=organization_name,
            project_name=project_name,
            line_items=line_items,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.PROPOSAL,
            metadata={
                "proposal_id": proposal_id,
                "action": "sent",
            },
        )

        return await self.send_email(message)

    async def send_proposal_approved_email(
        self,
        to_email: str,
        user_name: str,
        proposal_id: int,
        proposal_title: str,
        total_amount: str,
        currency: str = "USD",
        approved_by: str = "Client",
        project_name: Optional[str] = None,
        project_url: Optional[str] = None,
    ) -> EmailResult:
        """
        Send proposal approved notification to service provider.

        WHAT: Notifies service provider that proposal was approved.

        WHY: Enables work to begin on approved proposals.

        HOW: Renders Jinja2 template with approval details and sends via provider.

        Args:
            to_email: Service provider email address
            user_name: Service provider's display name
            proposal_id: Proposal ID
            proposal_title: Proposal title
            total_amount: Total amount (formatted)
            currency: Currency code
            approved_by: Name of approver
            project_name: Related project name
            project_url: URL to project

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = self._template_service.render_proposal_approved_email(
            user_name=user_name,
            proposal_id=proposal_id,
            proposal_title=proposal_title,
            total_amount=total_amount,
            currency=currency,
            approved_by=approved_by,
            project_name=project_name,
            project_url=project_url,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.PROPOSAL,
            metadata={
                "proposal_id": proposal_id,
                "action": "approved",
            },
        )

        return await self.send_email(message)

    async def send_proposal_rejected_email(
        self,
        to_email: str,
        user_name: str,
        proposal_id: int,
        proposal_title: str,
        rejected_by: str = "Client",
        rejection_reason: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> EmailResult:
        """
        Send proposal rejected notification to service provider.

        WHAT: Notifies service provider that proposal was rejected.

        WHY: Enables revision or follow-up on rejected proposals.

        HOW: Renders Jinja2 template with rejection details and sends via provider.

        Args:
            to_email: Service provider email address
            user_name: Service provider's display name
            proposal_id: Proposal ID
            proposal_title: Proposal title
            rejected_by: Name of person who rejected
            rejection_reason: Reason for rejection
            project_name: Related project name

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = self._template_service.render_proposal_rejected_email(
            user_name=user_name,
            proposal_id=proposal_id,
            proposal_title=proposal_title,
            rejected_by=rejected_by,
            rejection_reason=rejection_reason,
            project_name=project_name,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.PROPOSAL,
            metadata={
                "proposal_id": proposal_id,
                "action": "rejected",
            },
        )

        return await self.send_email(message)

    async def send_invoice_created_email(
        self,
        to_email: str,
        user_name: str,
        invoice_id: int,
        invoice_number: str,
        total_amount: str,
        currency: str = "USD",
        due_date: str = "",
        organization_name: str = "Automation Platform",
        project_name: Optional[str] = None,
        line_items: Optional[List[Dict[str, Any]]] = None,
        is_overdue: bool = False,
    ) -> EmailResult:
        """
        Send invoice created notification to client.

        WHAT: Sends invoice with payment details to client.

        WHY: Prompts client payment action.

        HOW: Renders Jinja2 template with invoice details and sends via provider.

        Args:
            to_email: Client email address
            user_name: Client's display name
            invoice_id: Invoice ID
            invoice_number: Display invoice number
            total_amount: Total amount (formatted)
            currency: Currency code
            due_date: Payment due date
            organization_name: Billing organization
            project_name: Related project name
            line_items: List of invoice items
            is_overdue: Whether invoice is overdue

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = self._template_service.render_invoice_created_email(
            user_name=user_name,
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            total_amount=total_amount,
            currency=currency,
            due_date=due_date,
            organization_name=organization_name,
            project_name=project_name,
            line_items=line_items,
            is_overdue=is_overdue,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.INVOICE,
            metadata={
                "invoice_id": invoice_id,
                "invoice_number": invoice_number,
                "action": "created",
            },
        )

        return await self.send_email(message)

    async def send_invoice_paid_email(
        self,
        to_email: str,
        user_name: str,
        invoice_id: int,
        invoice_number: str,
        total_amount: str,
        currency: str = "USD",
        payment_method: Optional[str] = None,
        project_name: Optional[str] = None,
        is_client: bool = True,
    ) -> EmailResult:
        """
        Send invoice paid confirmation.

        WHAT: Confirms payment receipt to client and/or service provider.

        WHY: Confirms successful payment for records.

        HOW: Renders Jinja2 template with payment details and sends via provider.

        Args:
            to_email: Recipient email address
            user_name: Recipient's display name
            invoice_id: Invoice ID
            invoice_number: Display invoice number
            total_amount: Total amount (formatted)
            currency: Currency code
            payment_method: Payment method used
            project_name: Related project name
            is_client: Whether recipient is the paying client

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = self._template_service.render_invoice_paid_email(
            user_name=user_name,
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            total_amount=total_amount,
            currency=currency,
            payment_method=payment_method,
            project_name=project_name,
            is_client=is_client,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.INVOICE,
            metadata={
                "invoice_id": invoice_id,
                "invoice_number": invoice_number,
                "action": "paid",
            },
        )

        return await self.send_email(message)

    async def send_sla_warning_email(
        self,
        to_email: str,
        user_name: str,
        ticket_id: int,
        ticket_subject: str,
        ticket_priority: str,
        sla_type: str,
        sla_status: str,
        due_at: str,
        customer_name: str,
        organization_name: Optional[str] = None,
        assigned_to: Optional[str] = None,
        time_remaining: Optional[str] = None,
    ) -> EmailResult:
        """
        Send SLA warning or breach notification.

        WHAT: Alerts agent/admin of SLA approaching breach or breached.

        WHY: Enables proactive SLA management and escalation.

        HOW: Renders Jinja2 template with SLA details and sends via provider.

        Args:
            to_email: Recipient email address (agent/admin)
            user_name: Recipient's display name
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            ticket_priority: Priority level
            sla_type: "response" or "resolution"
            sla_status: "warning" or "breached"
            due_at: SLA due date/time
            customer_name: Customer who created ticket
            organization_name: Customer's organization
            assigned_to: Currently assigned agent
            time_remaining: Time remaining (formatted)

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = self._template_service.render_sla_warning_email(
            user_name=user_name,
            ticket_id=ticket_id,
            ticket_subject=ticket_subject,
            ticket_priority=ticket_priority,
            sla_type=sla_type,
            sla_status=sla_status,
            due_at=due_at,
            customer_name=customer_name,
            organization_name=organization_name,
            assigned_to=assigned_to,
            time_remaining=time_remaining,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.SECURITY_ALERT,  # Using security alert for urgency
            metadata={
                "ticket_id": ticket_id,
                "sla_type": sla_type,
                "sla_status": sla_status,
            },
        )

        return await self.send_email(message)


# ============================================================================
# Module-level convenience functions
# ============================================================================


_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """
    Get or create the global email service instance.

    WHY: Singleton pattern ensures consistent configuration
    and resource sharing across the application.

    Returns:
        EmailService instance
    """
    global _email_service

    if _email_service is None:
        _email_service = EmailService()

    return _email_service
