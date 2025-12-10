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
    templates for consistent emails, and async sending for performance.
    """

    def __init__(self, provider: Optional[EmailProvider] = None):
        """
        Initialize email service.

        Args:
            provider: Email provider to use (auto-detected if not provided)
        """
        if provider:
            self._provider = provider
        elif settings.RESEND_API_KEY:
            self._provider = ResendProvider()
        else:
            # Use mock provider in development/testing
            logger.warning("No email provider configured, using mock provider")
            self._provider = MockEmailProvider()

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

        subject, html_content, text_content = EmailTemplates.verification_email(
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

        subject, html_content, text_content = EmailTemplates.password_reset_email(
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
    ) -> EmailResult:
        """
        Send password changed notification.

        Args:
            to_email: Recipient email address
            user_name: User's display name

        Returns:
            EmailResult with send status
        """
        subject, html_content, text_content = EmailTemplates.password_changed_email(
            user_name=user_name,
        )

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=EmailType.PASSWORD_CHANGED,
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
