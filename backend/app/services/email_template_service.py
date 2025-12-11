"""
Email Template Service for rendering Jinja2 email templates.

WHAT: Service for loading and rendering email templates using Jinja2.

WHY: Template-based emails provide:
- Consistent branding across all email types
- Easy content updates without code changes
- Template inheritance for DRY principle
- Designer-friendly HTML editing
- Separation of content from logic

HOW: Uses Jinja2 environment with FileSystemLoader to load templates
from the templates/email directory. Provides convenience methods for
each email type with proper variable handling.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound

from app.core.config import settings
from app.core.exceptions import EmailServiceError


logger = logging.getLogger(__name__)


class EmailTemplateService:
    """
    Service for rendering email templates.

    WHAT: Loads and renders Jinja2 templates for transactional emails.

    WHY: Centralizes template rendering:
    - Single point for template configuration
    - Caching for performance
    - Error handling for missing templates
    - Default variable injection

    HOW: Uses Jinja2 with FileSystemLoader, caches compiled templates,
    and provides type-safe methods for each email type.

    Example:
        template_service = EmailTemplateService()
        subject, html, text = template_service.render_verification_email(
            user_name="John",
            verification_url="https://...",
        )
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize template service.

        Args:
            template_dir: Path to templates directory (defaults to backend/templates/email)
        """
        if template_dir is None:
            # Default to templates/email relative to backend root
            template_dir = Path(__file__).parent.parent.parent / "templates" / "email"

        self._template_dir = template_dir
        self._env = self._create_environment()

    def _create_environment(self) -> Environment:
        """
        Create Jinja2 environment with proper configuration.

        WHAT: Sets up Jinja2 with security and convenience features.

        WHY: Proper configuration ensures:
        - Auto-escaping for XSS prevention
        - Template caching for performance
        - Useful template functions

        Returns:
            Configured Jinja2 Environment
        """
        env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        env.filters["truncate"] = self._truncate_filter

        return env

    @staticmethod
    def _truncate_filter(text: str, length: int = 200, suffix: str = "...") -> str:
        """
        Truncate text to specified length.

        Args:
            text: Text to truncate
            length: Maximum length
            suffix: Suffix to add if truncated

        Returns:
            Truncated text
        """
        if len(text) <= length:
            return text
        return text[: length - len(suffix)] + suffix

    def _get_base_context(self) -> Dict[str, Any]:
        """
        Get base context variables for all templates.

        WHAT: Returns common variables needed by all templates.

        WHY: Consistent footer, branding, and URLs across emails.

        Returns:
            Dict with base context variables
        """
        return {
            "year": datetime.utcnow().year,
            "frontend_url": settings.FRONTEND_URL,
            "platform_name": "Automation Platform",
        }

    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Render a template with given context.

        WHAT: Loads and renders a named template.

        WHY: Generic method for custom templates or testing.

        HOW: Merges base context, loads template, renders with context.

        Args:
            template_name: Name of template file (e.g., "verification.html")
            context: Template variables

        Returns:
            Rendered HTML string

        Raises:
            EmailServiceError: If template not found or render fails
        """
        try:
            template = self._env.get_template(template_name)
            full_context = {**self._get_base_context(), **context}
            return template.render(**full_context)
        except TemplateNotFound:
            logger.error(f"Email template not found: {template_name}")
            raise EmailServiceError(
                message=f"Email template not found: {template_name}",
                details={"template": template_name},
            )
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            raise EmailServiceError(
                message="Failed to render email template",
                details={"template": template_name, "error": str(e)},
            )

    def render_verification_email(
        self,
        user_name: str,
        verification_url: str,
        verification_code: Optional[str] = None,
        expires_in: str = "24 hours",
    ) -> tuple[str, str, str]:
        """
        Render email verification email.

        Args:
            user_name: User's display name
            verification_url: URL to verify email
            verification_code: Optional 6-digit code
            expires_in: Expiration time string

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        context = {
            "user_name": user_name,
            "verification_url": verification_url,
            "verification_code": verification_code,
            "expires_in": expires_in,
        }

        html = self.render_template("verification.html", context)
        text = self._generate_text_version(
            f"Welcome, {user_name}!\n\n"
            f"Please verify your email address by clicking the link below:\n\n"
            f"{verification_url}\n\n"
            + (f"Or enter this code: {verification_code}\n\n" if verification_code else "")
            + f"This link will expire in {expires_in}.\n\n"
            f"If you didn't create an account, please ignore this email."
        )

        return "Verify your email address", html, text

    def render_password_reset_email(
        self,
        user_name: str,
        reset_url: str,
        reset_code: Optional[str] = None,
        expires_in: str = "1 hour",
    ) -> tuple[str, str, str]:
        """
        Render password reset email.

        Args:
            user_name: User's display name
            reset_url: URL to reset password
            reset_code: Optional 6-digit code
            expires_in: Expiration time string

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        context = {
            "user_name": user_name,
            "reset_url": reset_url,
            "reset_code": reset_code,
            "expires_in": expires_in,
        }

        html = self.render_template("password_reset.html", context)
        text = self._generate_text_version(
            f"Hi {user_name},\n\n"
            f"We received a request to reset your password.\n\n"
            f"Click this link to reset: {reset_url}\n\n"
            + (f"Or enter this code: {reset_code}\n\n" if reset_code else "")
            + f"This link will expire in {expires_in}.\n\n"
            f"If you didn't request this, please ignore this email."
        )

        return "Reset your password", html, text

    def render_password_changed_email(
        self,
        user_name: str,
        changed_at: Optional[str] = None,
        ip_address: Optional[str] = None,
        location: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """
        Render password changed notification.

        Args:
            user_name: User's display name
            changed_at: Timestamp of change
            ip_address: IP address of change
            location: Approximate location

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        reset_url = f"{settings.FRONTEND_URL}/auth/forgot-password"
        context = {
            "user_name": user_name,
            "changed_at": changed_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "ip_address": ip_address,
            "location": location,
            "reset_url": reset_url,
        }

        html = self.render_template("password_changed.html", context)
        text = self._generate_text_version(
            f"Hi {user_name},\n\n"
            f"Your password was changed on {context['changed_at']}.\n\n"
            f"If you made this change, no action is needed.\n\n"
            f"If you didn't change your password, please reset it immediately:\n"
            f"{reset_url}"
        )

        return "Your password has been changed", html, text

    def render_welcome_email(
        self,
        user_name: str,
        organization_name: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """
        Render welcome email after verification.

        Args:
            user_name: User's display name
            organization_name: User's organization name

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        context = {
            "user_name": user_name,
            "organization_name": organization_name,
            "dashboard_url": f"{settings.FRONTEND_URL}/dashboard",
            "help_url": f"{settings.FRONTEND_URL}/help",
        }

        html = self.render_template("welcome.html", context)
        text = self._generate_text_version(
            f"Welcome to Automation Platform, {user_name}!\n\n"
            + (f"Your organization: {organization_name}\n\n" if organization_name else "")
            + f"Get started at: {context['dashboard_url']}\n\n"
            f"Features:\n"
            f"- Create and manage projects\n"
            f"- Automate workflows with n8n\n"
            f"- Generate professional proposals\n"
            f"- Track support tickets\n\n"
            f"Need help? Visit: {context['help_url']}"
        )

        return "Welcome to Automation Platform", html, text

    def render_ticket_created_email(
        self,
        user_name: str,
        ticket_id: int,
        ticket_subject: str,
        ticket_description: Optional[str] = None,
        ticket_priority: str = "medium",
        ticket_category: str = "general",
        sla_response_hours: int = 24,
        sla_resolution_hours: int = 72,
        created_at: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """
        Render ticket created notification.

        Args:
            user_name: User's display name
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            ticket_description: Ticket description
            ticket_priority: Priority level
            ticket_category: Category
            sla_response_hours: SLA response hours
            sla_resolution_hours: SLA resolution hours
            created_at: Creation timestamp

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        ticket_url = f"{settings.FRONTEND_URL}/tickets/{ticket_id}"
        context = {
            "user_name": user_name,
            "ticket_id": ticket_id,
            "ticket_subject": ticket_subject,
            "ticket_description": ticket_description,
            "ticket_priority": ticket_priority,
            "ticket_category": ticket_category,
            "ticket_url": ticket_url,
            "sla_response_hours": sla_response_hours,
            "sla_resolution_hours": sla_resolution_hours,
            "created_at": created_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }

        html = self.render_template("ticket_created.html", context)
        text = self._generate_text_version(
            f"Hi {user_name},\n\n"
            f"Your support ticket #{ticket_id} has been created.\n\n"
            f"Subject: {ticket_subject}\n"
            f"Priority: {ticket_priority.upper()}\n"
            f"Category: {ticket_category}\n\n"
            f"SLA:\n"
            f"- First response within {sla_response_hours} hours\n"
            f"- Resolution target: {sla_resolution_hours} hours\n\n"
            f"View ticket: {ticket_url}"
        )

        return f"Ticket #{ticket_id} Created: {ticket_subject}", html, text

    def render_ticket_updated_email(
        self,
        user_name: str,
        ticket_id: int,
        ticket_subject: str,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        updated_by: Optional[str] = None,
        update_message: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """
        Render ticket updated notification.

        Args:
            user_name: User's display name
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            old_status: Previous status
            new_status: New status
            assigned_to: Assigned agent
            updated_by: Who made the update
            update_message: Optional message

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        ticket_url = f"{settings.FRONTEND_URL}/tickets/{ticket_id}"
        context = {
            "user_name": user_name,
            "ticket_id": ticket_id,
            "ticket_subject": ticket_subject,
            "ticket_url": ticket_url,
            "old_status": old_status,
            "new_status": new_status,
            "assigned_to": assigned_to,
            "updated_by": updated_by,
            "update_message": update_message,
        }

        html = self.render_template("ticket_updated.html", context)
        text = self._generate_text_version(
            f"Hi {user_name},\n\n"
            f"Ticket #{ticket_id} has been updated.\n\n"
            f"Subject: {ticket_subject}\n"
            + (f"Status: {old_status} -> {new_status}\n" if old_status and new_status else "")
            + (f"Assigned to: {assigned_to}\n" if assigned_to else "")
            + (f"\nNote: {update_message}\n" if update_message else "")
            + f"\nView ticket: {ticket_url}"
        )

        subject_status = f" [{new_status.replace('_', ' ').title()}]" if new_status else ""
        return f"Ticket #{ticket_id} Updated{subject_status}", html, text

    def render_ticket_comment_email(
        self,
        user_name: str,
        ticket_id: int,
        ticket_subject: str,
        comment_author: str,
        comment_author_role: str,
        comment_text: str,
        commented_at: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """
        Render ticket comment notification.

        Args:
            user_name: User's display name
            ticket_id: Ticket ID
            ticket_subject: Ticket subject
            comment_author: Comment author name
            comment_author_role: Author role (agent/client)
            comment_text: Comment content
            commented_at: Comment timestamp

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        ticket_url = f"{settings.FRONTEND_URL}/tickets/{ticket_id}"
        context = {
            "user_name": user_name,
            "ticket_id": ticket_id,
            "ticket_subject": ticket_subject,
            "ticket_url": ticket_url,
            "comment_author": comment_author,
            "comment_author_role": comment_author_role,
            "comment_text": comment_text,
            "commented_at": commented_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }

        html = self.render_template("ticket_comment.html", context)
        role_label = " (Support)" if comment_author_role == "agent" else ""
        text = self._generate_text_version(
            f"Hi {user_name},\n\n"
            f"New comment on ticket #{ticket_id}: {ticket_subject}\n\n"
            f"From: {comment_author}{role_label}\n"
            f"---\n{comment_text}\n---\n\n"
            f"View ticket: {ticket_url}"
        )

        return f"New Comment on Ticket #{ticket_id}", html, text

    def render_proposal_sent_email(
        self,
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
    ) -> tuple[str, str, str]:
        """
        Render proposal sent notification.

        Args:
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
            Tuple of (subject, html_content, text_content)
        """
        proposal_url = f"{settings.FRONTEND_URL}/proposals/{proposal_id}"
        context = {
            "user_name": user_name,
            "proposal_id": proposal_id,
            "proposal_title": proposal_title,
            "proposal_url": proposal_url,
            "total_amount": total_amount,
            "currency": currency,
            "expires_at": expires_at or "30 days from now",
            "sender_name": sender_name,
            "organization_name": organization_name,
            "project_name": project_name,
            "line_items": line_items,
        }

        html = self.render_template("proposal_sent.html", context)
        text = self._generate_text_version(
            f"Hi {user_name},\n\n"
            f"You have a new proposal from {organization_name}.\n\n"
            f"Proposal: {proposal_title}\n"
            f"Amount: {currency} {total_amount}\n"
            f"Valid until: {context['expires_at']}\n\n"
            f"Review proposal: {proposal_url}"
        )

        return f"New Proposal: {proposal_title}", html, text

    def render_proposal_approved_email(
        self,
        user_name: str,
        proposal_id: int,
        proposal_title: str,
        total_amount: str,
        currency: str = "USD",
        approved_by: str = "Client",
        approved_at: Optional[str] = None,
        project_name: Optional[str] = None,
        project_url: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """
        Render proposal approved notification.

        Args:
            user_name: Service provider's display name
            proposal_id: Proposal ID
            proposal_title: Proposal title
            total_amount: Total amount (formatted)
            currency: Currency code
            approved_by: Name of approver
            approved_at: Approval timestamp
            project_name: Related project name
            project_url: URL to project

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        proposal_url = f"{settings.FRONTEND_URL}/proposals/{proposal_id}"
        context = {
            "user_name": user_name,
            "proposal_id": proposal_id,
            "proposal_title": proposal_title,
            "proposal_url": proposal_url,
            "total_amount": total_amount,
            "currency": currency,
            "approved_by": approved_by,
            "approved_at": approved_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "project_name": project_name,
            "project_url": project_url,
        }

        html = self.render_template("proposal_approved.html", context)
        text = self._generate_text_version(
            f"Hi {user_name},\n\n"
            f"Great news! Your proposal has been approved.\n\n"
            f"Proposal: {proposal_title}\n"
            f"Amount: {currency} {total_amount}\n"
            f"Approved by: {approved_by}\n\n"
            + (f"View project: {project_url}" if project_url else f"View proposal: {proposal_url}")
        )

        return f"Proposal Approved: {proposal_title}", html, text

    def render_proposal_rejected_email(
        self,
        user_name: str,
        proposal_id: int,
        proposal_title: str,
        rejected_by: str = "Client",
        rejected_at: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """
        Render proposal rejected notification.

        Args:
            user_name: Service provider's display name
            proposal_id: Proposal ID
            proposal_title: Proposal title
            rejected_by: Name of person who rejected
            rejected_at: Rejection timestamp
            rejection_reason: Reason for rejection
            project_name: Related project name

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        proposal_url = f"{settings.FRONTEND_URL}/proposals/{proposal_id}"
        context = {
            "user_name": user_name,
            "proposal_id": proposal_id,
            "proposal_title": proposal_title,
            "proposal_url": proposal_url,
            "rejected_by": rejected_by,
            "rejected_at": rejected_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "rejection_reason": rejection_reason,
            "project_name": project_name,
        }

        html = self.render_template("proposal_rejected.html", context)
        text = self._generate_text_version(
            f"Hi {user_name},\n\n"
            f"Your proposal was not approved.\n\n"
            f"Proposal: {proposal_title}\n"
            f"Rejected by: {rejected_by}\n"
            + (f"\nFeedback: {rejection_reason}\n" if rejection_reason else "")
            + f"\nView proposal: {proposal_url}"
        )

        return f"Proposal Update: {proposal_title}", html, text

    def render_invoice_created_email(
        self,
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
    ) -> tuple[str, str, str]:
        """
        Render invoice created notification.

        Args:
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
            Tuple of (subject, html_content, text_content)
        """
        invoice_url = f"{settings.FRONTEND_URL}/invoices/{invoice_id}"
        payment_url = f"{settings.FRONTEND_URL}/invoices/{invoice_id}/pay"
        context = {
            "user_name": user_name,
            "invoice_id": invoice_id,
            "invoice_number": invoice_number,
            "invoice_url": invoice_url,
            "payment_url": payment_url,
            "total_amount": total_amount,
            "currency": currency,
            "due_date": due_date,
            "organization_name": organization_name,
            "project_name": project_name,
            "line_items": line_items,
            "is_overdue": is_overdue,
        }

        html = self.render_template("invoice_created.html", context)
        text = self._generate_text_version(
            f"Hi {user_name},\n\n"
            f"You have a new invoice from {organization_name}.\n\n"
            f"Invoice: {invoice_number}\n"
            f"Amount: {currency} {total_amount}\n"
            f"Due: {due_date}\n\n"
            f"Pay now: {payment_url}\n"
            f"View invoice: {invoice_url}"
        )

        return f"Invoice {invoice_number}", html, text

    def render_invoice_paid_email(
        self,
        user_name: str,
        invoice_id: int,
        invoice_number: str,
        total_amount: str,
        currency: str = "USD",
        paid_at: Optional[str] = None,
        payment_method: Optional[str] = None,
        project_name: Optional[str] = None,
        is_client: bool = True,
    ) -> tuple[str, str, str]:
        """
        Render invoice paid confirmation.

        Args:
            user_name: User's display name
            invoice_id: Invoice ID
            invoice_number: Display invoice number
            total_amount: Total amount (formatted)
            currency: Currency code
            paid_at: Payment timestamp
            payment_method: Payment method used
            project_name: Related project name
            is_client: Whether recipient is the paying client

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        receipt_url = f"{settings.FRONTEND_URL}/invoices/{invoice_id}/receipt"
        context = {
            "user_name": user_name,
            "invoice_id": invoice_id,
            "invoice_number": invoice_number,
            "receipt_url": receipt_url,
            "total_amount": total_amount,
            "currency": currency,
            "paid_at": paid_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "payment_method": payment_method,
            "project_name": project_name,
            "is_client": is_client,
        }

        html = self.render_template("invoice_paid.html", context)
        text = self._generate_text_version(
            f"Hi {user_name},\n\n"
            + ("Thank you for your payment!\n\n" if is_client else "Payment received!\n\n")
            + f"Invoice: {invoice_number}\n"
            f"Amount: {currency} {total_amount}\n"
            f"Paid: {context['paid_at']}\n\n"
            f"View receipt: {receipt_url}"
        )

        return f"Payment Received - Invoice {invoice_number}", html, text

    def render_sla_warning_email(
        self,
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
    ) -> tuple[str, str, str]:
        """
        Render SLA warning/breach notification.

        Args:
            user_name: Recipient's display name (agent/admin)
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
            Tuple of (subject, html_content, text_content)
        """
        ticket_url = f"{settings.FRONTEND_URL}/tickets/{ticket_id}"
        context = {
            "user_name": user_name,
            "ticket_id": ticket_id,
            "ticket_subject": ticket_subject,
            "ticket_url": ticket_url,
            "ticket_priority": ticket_priority,
            "sla_type": sla_type,
            "sla_status": sla_status,
            "due_at": due_at,
            "customer_name": customer_name,
            "organization_name": organization_name,
            "assigned_to": assigned_to,
            "time_remaining": time_remaining,
        }

        html = self.render_template("sla_warning.html", context)

        status_text = "BREACHED" if sla_status == "breached" else "AT RISK"
        text = self._generate_text_version(
            f"SLA {status_text}: Ticket #{ticket_id}\n\n"
            f"Hi {user_name},\n\n"
            f"The {sla_type} SLA for ticket #{ticket_id} is {sla_status}.\n\n"
            f"Subject: {ticket_subject}\n"
            f"Priority: {ticket_priority.upper()}\n"
            f"Customer: {customer_name}\n"
            + (f"Assigned: {assigned_to}\n" if assigned_to else "Assigned: UNASSIGNED\n")
            + f"Due: {due_at}\n"
            + (f"Time remaining: {time_remaining}\n" if time_remaining else "")
            + f"\nView ticket: {ticket_url}"
        )

        if sla_status == "breached":
            subject = f"SLA BREACH: Ticket #{ticket_id} - {sla_type.title()} SLA"
        else:
            subject = f"SLA Warning: Ticket #{ticket_id} - {sla_type.title()} approaching deadline"

        return subject, html, text

    @staticmethod
    def _generate_text_version(content: str) -> str:
        """
        Generate plain text email version.

        WHAT: Creates plain text fallback from content.

        WHY: Some email clients don't support HTML or users prefer text.

        Args:
            content: Text content

        Returns:
            Formatted plain text email
        """
        footer = (
            "\n\n---\n"
            "Automation Platform\n"
            f"If you didn't expect this email, please ignore it."
        )
        return content.strip() + footer


# Module-level singleton
_template_service: Optional[EmailTemplateService] = None


def get_email_template_service() -> EmailTemplateService:
    """
    Get or create the global template service instance.

    WHY: Singleton pattern ensures template caching is effective
    and consistent configuration across the application.

    Returns:
        EmailTemplateService instance
    """
    global _template_service

    if _template_service is None:
        _template_service = EmailTemplateService()

    return _template_service
