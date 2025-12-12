"""
Email Template Management Service.

WHAT: Business logic for database-backed email template management.

WHY: Database-backed templates enable:
1. Dynamic template creation by organization admins
2. Version control with rollback capability
3. Template customization per organization
4. Analytics and tracking for sent emails

HOW: Orchestrates EmailTemplate DAOs and provides:
- Template CRUD with versioning
- Variable substitution via Jinja2
- Email sending through providers
- Tracking for open/click analytics

NOTE: This is separate from EmailTemplateService which handles
file-based system templates. This service handles organization-specific
database-backed templates.
"""

import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from jinja2 import Environment, BaseLoader, TemplateSyntaxError, UndefinedError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.dao.email_template import (
    EmailTemplateDAO,
    EmailTemplateVersionDAO,
    SentEmailDAO,
)
from app.models.email_template import (
    EmailTemplate,
    EmailTemplateVersion,
    SentEmail,
    EmailCategory,
)


class EmailTemplateManagementError(AppException):
    """
    Email template management specific error.

    WHAT: Base error for template management operations.

    WHY: Provides specific context for template errors.
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 400,
    ):
        super().__init__(message=message, details=details, status_code=status_code)


class TemplateNotFoundError(NotFoundError):
    """
    Template not found error.

    WHAT: Raised when a template cannot be found.

    WHY: Specific error type for missing templates.
    """

    def __init__(self, message: str = "Email template not found", **kwargs):
        super().__init__(message=message, **kwargs)


class TemplateRenderError(EmailTemplateManagementError):
    """
    Template rendering error.

    WHAT: Raised when template rendering fails.

    WHY: Captures rendering-specific issues like missing variables.
    """

    def __init__(
        self,
        message: str = "Failed to render template",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message=message, details=details, status_code=400)


class EmailSendError(EmailTemplateManagementError):
    """
    Email sending error.

    WHAT: Raised when email sending fails.

    WHY: Captures provider-specific send failures.
    """

    def __init__(
        self,
        message: str = "Failed to send email",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message=message, details=details, status_code=500)


class EmailTemplateManagementService:
    """
    Service for database-backed email template management.

    WHAT: Manages org-specific email templates, rendering, and sending.

    WHY: Centralizes template management for:
    - Per-organization customizable templates
    - Version control with audit trail
    - Analytics on email performance

    HOW: Uses DAOs for persistence and Jinja2 for rendering.

    NOTE: Unlike the file-based EmailTemplateService, this service
    works with templates stored in the database, allowing admins
    to create and customize templates.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize EmailTemplateManagementService.

        WHAT: Sets up DAOs and Jinja2 environment.

        Args:
            session: Database session
        """
        self.session = session
        self.template_dao = EmailTemplateDAO(session)
        self.version_dao = EmailTemplateVersionDAO(session)
        self.sent_dao = SentEmailDAO(session)
        self.jinja_env = Environment(loader=BaseLoader(), autoescape=True)

    # =========================================================================
    # Template Management
    # =========================================================================

    async def create_template(
        self,
        org_id: int,
        name: str,
        slug: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        description: Optional[str] = None,
        category: str = EmailCategory.SYSTEM.value,
        variables: Optional[Dict[str, Any]] = None,
        created_by_id: Optional[int] = None,
    ) -> EmailTemplate:
        """
        Create a new email template.

        WHAT: Creates a template with initial version.

        WHY: Templates enable consistent, branded emails
        with variable substitution.

        HOW: Validates uniqueness, creates template,
        and stores initial version.

        Args:
            org_id: Organization ID
            name: Template display name
            slug: URL-friendly identifier
            subject: Email subject line (supports variables)
            html_body: HTML email content (supports variables)
            text_body: Optional plain text version
            description: Template description
            category: Template category
            variables: Variable definitions
            created_by_id: Creator user ID

        Returns:
            Created EmailTemplate

        Raises:
            ConflictError: If slug already exists
            ValidationError: If template content is invalid
        """
        # Check slug uniqueness
        existing = await self.template_dao.get_by_slug(org_id, slug)
        if existing:
            raise ConflictError(
                message="Template with this slug already exists",
                details={"slug": slug},
            )

        # Validate template syntax
        await self._validate_template_syntax(subject, html_body, text_body)

        # Extract variables from template if not provided
        if variables is None:
            variables = self._extract_variables(subject, html_body, text_body)

        # Create template
        template = EmailTemplate(
            org_id=org_id,
            name=name,
            slug=slug,
            description=description,
            category=category,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            variables=variables,
            version=1,
            is_active=True,
            is_system=False,
            created_by_id=created_by_id,
        )

        self.session.add(template)
        await self.session.flush()
        await self.session.refresh(template)

        # Create initial version
        await self.template_dao.create_version(
            template=template,
            changed_by_id=created_by_id,
            change_note="Initial version",
        )

        return template

    async def update_template(
        self,
        template_id: int,
        org_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        subject: Optional[str] = None,
        html_body: Optional[str] = None,
        text_body: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        change_note: Optional[str] = None,
        updated_by_id: Optional[int] = None,
    ) -> EmailTemplate:
        """
        Update an email template.

        WHAT: Updates template and creates version.

        WHY: Version control enables rollback and audit.

        HOW: Saves current state as version, then updates.

        Args:
            template_id: Template ID
            org_id: Organization ID
            name: New name
            description: New description
            category: New category
            subject: New subject
            html_body: New HTML body
            text_body: New text body
            variables: New variables
            change_note: Description of change
            updated_by_id: User making change

        Returns:
            Updated EmailTemplate

        Raises:
            TemplateNotFoundError: If template not found
            ValidationError: If updates are invalid
        """
        template = await self.template_dao.get_by_id_and_org(template_id, org_id)
        if not template:
            raise TemplateNotFoundError(details={"template_id": template_id})

        # Check if content is changing
        content_changed = any([
            subject is not None and subject != template.subject,
            html_body is not None and html_body != template.html_body,
            text_body is not None and text_body != template.text_body,
        ])

        # Validate new content if provided
        new_subject = subject if subject is not None else template.subject
        new_html = html_body if html_body is not None else template.html_body
        new_text = text_body if text_body is not None else template.text_body

        if content_changed:
            await self._validate_template_syntax(new_subject, new_html, new_text)

        # Save version before updating if content changed
        if content_changed:
            await self.template_dao.create_version(
                template=template,
                changed_by_id=updated_by_id,
                change_note=change_note or "Updated template",
            )
            template.version += 1

        # Apply updates
        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if category is not None:
            template.category = category
        if subject is not None:
            template.subject = subject
        if html_body is not None:
            template.html_body = html_body
        if text_body is not None:
            template.text_body = text_body
        if variables is not None:
            template.variables = variables
        elif content_changed:
            # Re-extract variables if content changed
            template.variables = self._extract_variables(
                template.subject, template.html_body, template.text_body
            )

        template.updated_by_id = updated_by_id

        await self.session.flush()
        await self.session.refresh(template)

        return template

    async def get_template(
        self,
        template_id: int,
        org_id: int,
    ) -> EmailTemplate:
        """
        Get a template by ID.

        WHAT: Retrieves template with full details.

        Args:
            template_id: Template ID
            org_id: Organization ID

        Returns:
            EmailTemplate

        Raises:
            TemplateNotFoundError: If not found
        """
        template = await self.template_dao.get_by_id_and_org(template_id, org_id)
        if not template:
            raise TemplateNotFoundError(details={"template_id": template_id})
        return template

    async def get_template_by_slug(
        self,
        org_id: int,
        slug: str,
    ) -> EmailTemplate:
        """
        Get a template by slug.

        WHAT: Retrieves template by URL-friendly slug.

        Args:
            org_id: Organization ID
            slug: Template slug

        Returns:
            EmailTemplate

        Raises:
            TemplateNotFoundError: If not found
        """
        template = await self.template_dao.get_by_slug(org_id, slug)
        if not template:
            raise TemplateNotFoundError(details={"slug": slug})
        return template

    async def list_templates(
        self,
        org_id: int,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[EmailTemplate], int]:
        """
        List templates for an organization.

        WHAT: Returns paginated template list.

        Args:
            org_id: Organization ID
            category: Optional category filter
            is_active: Optional active status filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (templates, total_count)
        """
        templates = await self.template_dao.get_org_templates(
            org_id=org_id,
            category=category,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )

        # Get total count (simplified - in production use count query)
        all_templates = await self.template_dao.get_org_templates(
            org_id=org_id,
            category=category,
            is_active=is_active,
            skip=0,
            limit=10000,
        )
        total = len(all_templates)

        return templates, total

    async def deactivate_template(
        self,
        template_id: int,
        org_id: int,
    ) -> EmailTemplate:
        """
        Deactivate a template.

        WHAT: Soft-deletes template.

        WHY: Preserves historical data and sent emails.

        Args:
            template_id: Template ID
            org_id: Organization ID

        Returns:
            Deactivated template

        Raises:
            TemplateNotFoundError: If not found
        """
        template = await self.template_dao.deactivate(template_id, org_id)
        if not template:
            raise TemplateNotFoundError(details={"template_id": template_id})
        return template

    async def activate_template(
        self,
        template_id: int,
        org_id: int,
    ) -> EmailTemplate:
        """
        Reactivate a deactivated template.

        WHAT: Restores a soft-deleted template.

        Args:
            template_id: Template ID
            org_id: Organization ID

        Returns:
            Activated template

        Raises:
            TemplateNotFoundError: If not found
        """
        template = await self.template_dao.get_by_id_and_org(template_id, org_id)
        if not template:
            raise TemplateNotFoundError(details={"template_id": template_id})

        template.is_active = True
        await self.session.flush()
        await self.session.refresh(template)

        return template

    # =========================================================================
    # Version Management
    # =========================================================================

    async def get_template_versions(
        self,
        template_id: int,
        org_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[EmailTemplateVersion], int]:
        """
        Get version history for a template.

        WHAT: Lists all versions of a template.

        WHY: Enables viewing and restoring previous versions.

        Args:
            template_id: Template ID
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (versions, total_count)

        Raises:
            TemplateNotFoundError: If template not found
        """
        # Verify template exists and belongs to org
        template = await self.template_dao.get_by_id_and_org(template_id, org_id)
        if not template:
            raise TemplateNotFoundError(details={"template_id": template_id})

        versions = await self.version_dao.get_template_versions(
            template_id=template_id,
            skip=skip,
            limit=limit,
        )

        # Get total count
        all_versions = await self.version_dao.get_template_versions(
            template_id=template_id,
            skip=0,
            limit=10000,
        )
        total = len(all_versions)

        return versions, total

    async def restore_version(
        self,
        template_id: int,
        version_number: int,
        org_id: int,
        restored_by_id: Optional[int] = None,
    ) -> EmailTemplate:
        """
        Restore template to a previous version.

        WHAT: Reverts template content to historical version.

        WHY: Enables undoing unwanted changes.

        HOW: Copies version content to current template,
        creating a new version for the restore action.

        Args:
            template_id: Template ID
            version_number: Version to restore
            org_id: Organization ID
            restored_by_id: User performing restore

        Returns:
            Updated template

        Raises:
            TemplateNotFoundError: If template or version not found
        """
        template = await self.template_dao.get_by_id_and_org(template_id, org_id)
        if not template:
            raise TemplateNotFoundError(details={"template_id": template_id})

        version = await self.version_dao.get_specific_version(
            template_id=template_id,
            version=version_number,
        )
        if not version:
            raise NotFoundError(
                message="Version not found",
                details={"template_id": template_id, "version": version_number},
            )

        # Save current state as version
        await self.template_dao.create_version(
            template=template,
            changed_by_id=restored_by_id,
            change_note=f"Before restoring to version {version_number}",
        )

        # Restore content from version
        template.subject = version.subject
        template.html_body = version.html_body
        template.text_body = version.text_body
        template.variables = version.variables
        template.version += 1
        template.updated_by_id = restored_by_id

        await self.session.flush()

        # Create version for restore
        await self.template_dao.create_version(
            template=template,
            changed_by_id=restored_by_id,
            change_note=f"Restored from version {version_number}",
        )

        await self.session.refresh(template)

        return template

    # =========================================================================
    # Template Rendering
    # =========================================================================

    async def render_template(
        self,
        template_id: int,
        org_id: int,
        variables: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Render a template with variables.

        WHAT: Substitutes variables into template.

        WHY: Preview email before sending.

        Args:
            template_id: Template ID
            org_id: Organization ID
            variables: Variable values

        Returns:
            Dict with rendered subject, html_body, text_body

        Raises:
            TemplateNotFoundError: If template not found
            TemplateRenderError: If rendering fails
        """
        template = await self.template_dao.get_by_id_and_org(template_id, org_id)
        if not template:
            raise TemplateNotFoundError(details={"template_id": template_id})

        return self._render(
            subject=template.subject,
            html_body=template.html_body,
            text_body=template.text_body,
            variables=variables,
        )

    async def render_template_by_slug(
        self,
        org_id: int,
        slug: str,
        variables: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Render a template by slug.

        WHAT: Renders template identified by slug.

        Args:
            org_id: Organization ID
            slug: Template slug
            variables: Variable values

        Returns:
            Dict with rendered content

        Raises:
            TemplateNotFoundError: If not found
            TemplateRenderError: If rendering fails
        """
        template = await self.template_dao.get_by_slug(org_id, slug)
        if not template:
            raise TemplateNotFoundError(details={"slug": slug})

        return self._render(
            subject=template.subject,
            html_body=template.html_body,
            text_body=template.text_body,
            variables=variables,
        )

    def _render(
        self,
        subject: str,
        html_body: str,
        text_body: Optional[str],
        variables: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Internal rendering helper.

        WHAT: Renders template strings with Jinja2.

        Args:
            subject: Subject template
            html_body: HTML template
            text_body: Optional text template
            variables: Variable values

        Returns:
            Rendered content dict

        Raises:
            TemplateRenderError: On rendering failure
        """
        try:
            rendered_subject = self.jinja_env.from_string(subject).render(variables)
            rendered_html = self.jinja_env.from_string(html_body).render(variables)
            rendered_text = None
            if text_body:
                rendered_text = self.jinja_env.from_string(text_body).render(variables)

            return {
                "subject": rendered_subject,
                "html_body": rendered_html,
                "text_body": rendered_text,
            }
        except UndefinedError as e:
            raise TemplateRenderError(
                message="Missing required variable",
                details={"error": str(e), "provided_variables": list(variables.keys())},
            )
        except TemplateSyntaxError as e:
            raise TemplateRenderError(
                message="Template syntax error",
                details={"error": str(e), "line": e.lineno},
            )
        except Exception as e:
            raise TemplateRenderError(
                message="Template rendering failed",
                details={"error": str(e)},
            )

    # =========================================================================
    # Email Sending
    # =========================================================================

    async def send_email(
        self,
        org_id: int,
        template_slug: str,
        to_email: str,
        variables: Dict[str, Any],
        to_name: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> SentEmail:
        """
        Send an email using a template.

        WHAT: Renders and sends email, logs result.

        WHY: Provides consistent email sending with tracking.

        HOW: Renders template, sends via provider, logs result.

        Args:
            org_id: Organization ID
            template_slug: Template to use
            to_email: Recipient email
            variables: Template variables
            to_name: Recipient name
            from_name: Override sender name

        Returns:
            SentEmail log record

        Raises:
            TemplateNotFoundError: If template not found
            EmailSendError: If sending fails
        """
        # Get template
        template = await self.template_dao.get_by_slug(org_id, template_slug)
        if not template:
            raise TemplateNotFoundError(details={"slug": template_slug})

        # Render template
        rendered = self._render(
            subject=template.subject,
            html_body=template.html_body,
            text_body=template.text_body,
            variables=variables,
        )

        # Get sender info from settings
        from_email = getattr(settings, "MAIL_FROM", "noreply@example.com")
        sender_name = from_name or getattr(settings, "MAIL_FROM_NAME", "Automation Platform")

        # Log email as pending
        sent_email = await self.sent_dao.log_email(
            org_id=org_id,
            to_email=to_email,
            from_email=from_email,
            subject=rendered["subject"],
            template_id=template.id,
            template_slug=template_slug,
            to_name=to_name,
            from_name=sender_name,
            variables_used=variables,
            status="pending",
            provider="smtp",  # Would be dynamic based on config
        )

        # Send email via provider
        try:
            message_id = await self._send_via_provider(
                to_email=to_email,
                to_name=to_name,
                from_email=from_email,
                from_name=sender_name,
                subject=rendered["subject"],
                html_body=rendered["html_body"],
                text_body=rendered.get("text_body"),
            )

            # Update status to sent
            await self.sent_dao.update_status(
                email_id=sent_email.id,
                status="sent",
                sent_at=datetime.utcnow(),
            )
            sent_email.message_id = message_id
            sent_email.status = "sent"
            sent_email.sent_at = datetime.utcnow()

        except Exception as e:
            # Update status to failed
            await self.sent_dao.update_status(
                email_id=sent_email.id,
                status="failed",
                error_message=str(e),
            )
            sent_email.status = "failed"
            sent_email.error_message = str(e)

            raise EmailSendError(
                message="Failed to send email",
                details={"to_email": to_email, "error": str(e)},
            )

        return sent_email

    async def _send_via_provider(
        self,
        to_email: str,
        to_name: Optional[str],
        from_email: str,
        from_name: str,
        subject: str,
        html_body: str,
        text_body: Optional[str],
    ) -> str:
        """
        Send email via configured provider.

        WHAT: Abstract email sending to providers.

        WHY: Supports multiple providers (SMTP, SendGrid, etc).

        HOW: Currently implements basic SMTP, can be extended.

        Args:
            to_email: Recipient email
            to_name: Recipient name
            from_email: Sender email
            from_name: Sender name
            subject: Email subject
            html_body: HTML content
            text_body: Plain text content

        Returns:
            Message ID from provider

        Raises:
            Exception: On send failure
        """
        # Get email provider settings
        provider = getattr(settings, "EMAIL_PROVIDER", "console")

        if provider == "console":
            # Development mode - log to console
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"Email sent (console mode):\n"
                f"  To: {to_name} <{to_email}>\n"
                f"  From: {from_name} <{from_email}>\n"
                f"  Subject: {subject}\n"
            )
            return f"console-{datetime.utcnow().timestamp()}"

        elif provider == "smtp":
            # SMTP sending
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            import uuid

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{from_name} <{from_email}>"
            msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
            msg["Message-ID"] = f"<{uuid.uuid4()}@{from_email.split('@')[1]}>"

            if text_body:
                msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            smtp_host = getattr(settings, "SMTP_HOST", "localhost")
            smtp_port = getattr(settings, "SMTP_PORT", 587)
            smtp_user = getattr(settings, "SMTP_USER", None)
            smtp_password = getattr(settings, "SMTP_PASSWORD", None)
            smtp_tls = getattr(settings, "SMTP_TLS", True)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_tls:
                    server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(from_email, [to_email], msg.as_string())

            return msg["Message-ID"]

        else:
            raise EmailSendError(
                message=f"Unknown email provider: {provider}",
                details={"provider": provider},
            )

    # =========================================================================
    # Sent Email Management
    # =========================================================================

    async def get_sent_emails(
        self,
        org_id: int,
        status: Optional[str] = None,
        template_id: Optional[int] = None,
        to_email: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[SentEmail], int]:
        """
        Get sent email history.

        WHAT: Lists sent emails with filters.

        Args:
            org_id: Organization ID
            status: Optional status filter
            template_id: Optional template filter
            to_email: Optional recipient filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (emails, total_count)
        """
        emails = await self.sent_dao.get_org_emails(
            org_id=org_id,
            status=status,
            template_id=template_id,
            to_email=to_email,
            skip=skip,
            limit=limit,
        )

        # Get total count
        all_emails = await self.sent_dao.get_org_emails(
            org_id=org_id,
            status=status,
            template_id=template_id,
            to_email=to_email,
            skip=0,
            limit=10000,
        )
        total = len(all_emails)

        return emails, total

    async def get_email_stats(
        self,
        org_id: int,
        template_id: Optional[int] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get email delivery statistics.

        WHAT: Aggregates email metrics.

        WHY: Analytics for email performance.

        Args:
            org_id: Organization ID
            template_id: Optional template filter
            days: Time range in days

        Returns:
            Statistics dict
        """
        return await self.sent_dao.get_email_stats(
            org_id=org_id,
            template_id=template_id,
            days=days,
        )

    async def record_open(self, message_id: str) -> Optional[SentEmail]:
        """
        Record email open event.

        WHAT: Tracks when email was opened.

        WHY: Engagement analytics.

        Args:
            message_id: Provider message ID

        Returns:
            Updated SentEmail if found
        """
        return await self.sent_dao.record_open(message_id)

    async def record_click(self, message_id: str) -> Optional[SentEmail]:
        """
        Record email link click.

        WHAT: Tracks when link was clicked.

        WHY: Engagement analytics.

        Args:
            message_id: Provider message ID

        Returns:
            Updated SentEmail if found
        """
        return await self.sent_dao.record_click(message_id)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _validate_template_syntax(
        self,
        subject: str,
        html_body: str,
        text_body: Optional[str],
    ) -> None:
        """
        Validate Jinja2 template syntax.

        WHAT: Ensures template syntax is valid.

        WHY: Catch errors before saving.

        Args:
            subject: Subject template
            html_body: HTML template
            text_body: Optional text template

        Raises:
            ValidationError: If syntax is invalid
        """
        try:
            self.jinja_env.parse(subject)
            self.jinja_env.parse(html_body)
            if text_body:
                self.jinja_env.parse(text_body)
        except TemplateSyntaxError as e:
            raise ValidationError(
                message="Invalid template syntax",
                details={"error": str(e), "line": e.lineno},
            )

    def _extract_variables(
        self,
        subject: str,
        html_body: str,
        text_body: Optional[str],
    ) -> Dict[str, Dict[str, str]]:
        """
        Extract variables from template content.

        WHAT: Finds all {{ variable }} patterns.

        WHY: Auto-document available variables.

        Args:
            subject: Subject template
            html_body: HTML template
            text_body: Optional text template

        Returns:
            Dict of variable definitions
        """
        # Regex to find Jinja2 variables
        pattern = r"\{\{\s*(\w+)\s*\}\}"

        variables = set()
        variables.update(re.findall(pattern, subject))
        variables.update(re.findall(pattern, html_body))
        if text_body:
            variables.update(re.findall(pattern, text_body))

        # Create variable definitions
        return {
            var: {
                "type": "string",
                "description": f"Variable: {var}",
                "required": True,
            }
            for var in variables
        }
