"""
Unit tests for EmailTemplateService.

WHAT: Tests for Jinja2 email template rendering.

WHY: Ensures templates render correctly with proper variable substitution
and error handling for missing templates.

HOW: Uses pytest to test each template rendering method with various inputs.
"""

import pytest
from pathlib import Path

from app.services.email_template_service import (
    EmailTemplateService,
    get_email_template_service,
)
from app.core.exceptions import EmailServiceError


class TestEmailTemplateService:
    """Tests for EmailTemplateService class."""

    @pytest.fixture
    def template_service(self) -> EmailTemplateService:
        """Create template service instance."""
        return EmailTemplateService()

    def test_init_default_path(self, template_service: EmailTemplateService):
        """Test initialization with default template path."""
        assert template_service._template_dir.exists()
        assert (template_service._template_dir / "base.html").exists()

    def test_init_custom_path(self, tmp_path: Path):
        """Test initialization with custom template path."""
        # Create a minimal template
        (tmp_path / "test.html").write_text("Hello {{ name }}")

        service = EmailTemplateService(template_dir=tmp_path)
        assert service._template_dir == tmp_path

    def test_render_template_basic(self, template_service: EmailTemplateService):
        """Test basic template rendering."""
        html = template_service.render_template(
            "verification.html",
            {
                "user_name": "John Doe",
                "verification_url": "https://example.com/verify?token=abc123",
                "verification_code": "123456",
                "expires_in": "24 hours",
            },
        )

        assert "John Doe" in html
        assert "https://example.com/verify?token=abc123" in html
        assert "123456" in html
        assert "24 hours" in html

    def test_render_template_not_found(self, template_service: EmailTemplateService):
        """Test rendering non-existent template raises error."""
        with pytest.raises(EmailServiceError) as exc_info:
            template_service.render_template("nonexistent.html", {})

        assert "not found" in str(exc_info.value)

    def test_render_verification_email(self, template_service: EmailTemplateService):
        """Test verification email rendering."""
        subject, html, text = template_service.render_verification_email(
            user_name="Jane Smith",
            verification_url="https://app.example.com/verify?token=xyz789",
            verification_code="654321",
            expires_in="48 hours",
        )

        assert subject == "Verify your email address"
        assert "Jane Smith" in html
        assert "https://app.example.com/verify?token=xyz789" in html
        assert "654321" in html
        assert "48 hours" in html
        assert "Jane Smith" in text
        assert "xyz789" in text

    def test_render_verification_email_without_code(
        self, template_service: EmailTemplateService
    ):
        """Test verification email without optional code."""
        subject, html, text = template_service.render_verification_email(
            user_name="Bob",
            verification_url="https://app.example.com/verify",
        )

        assert subject == "Verify your email address"
        assert "Bob" in html
        assert "24 hours" in html  # Default expires_in

    def test_render_password_reset_email(self, template_service: EmailTemplateService):
        """Test password reset email rendering."""
        subject, html, text = template_service.render_password_reset_email(
            user_name="Alice",
            reset_url="https://app.example.com/reset?token=reset123",
            reset_code="999888",
            expires_in="2 hours",
        )

        assert subject == "Reset your password"
        assert "Alice" in html
        assert "https://app.example.com/reset?token=reset123" in html
        assert "999888" in html
        assert "2 hours" in html
        assert "Alice" in text

    def test_render_password_changed_email(
        self, template_service: EmailTemplateService
    ):
        """Test password changed notification rendering."""
        subject, html, text = template_service.render_password_changed_email(
            user_name="Charlie",
            changed_at="2024-01-15 10:30 UTC",
            ip_address="192.168.1.1",
            location="New York, US",
        )

        assert subject == "Your password has been changed"
        assert "Charlie" in html
        assert "2024-01-15 10:30 UTC" in html
        assert "192.168.1.1" in html
        assert "New York, US" in html
        assert "Charlie" in text

    def test_render_welcome_email(self, template_service: EmailTemplateService):
        """Test welcome email rendering."""
        subject, html, text = template_service.render_welcome_email(
            user_name="David",
            organization_name="Acme Corp",
        )

        assert subject == "Welcome to Automation Platform"
        assert "David" in html
        assert "Acme Corp" in html
        assert "David" in text

    def test_render_ticket_created_email(self, template_service: EmailTemplateService):
        """Test ticket created email rendering."""
        subject, html, text = template_service.render_ticket_created_email(
            user_name="Eve",
            ticket_id=123,
            ticket_subject="Login Issue",
            ticket_description="Cannot login to the application",
            ticket_priority="high",
            ticket_category="bug",
            sla_response_hours=4,
            sla_resolution_hours=24,
        )

        assert "123" in subject
        assert "Login Issue" in subject
        assert "Eve" in html
        assert "123" in html
        assert "Login Issue" in html
        assert "High" in html or "HIGH" in html
        assert "4" in html
        assert "24" in html
        assert "Eve" in text

    def test_render_ticket_updated_email(self, template_service: EmailTemplateService):
        """Test ticket updated email rendering."""
        subject, html, text = template_service.render_ticket_updated_email(
            user_name="Frank",
            ticket_id=456,
            ticket_subject="Server Error",
            old_status="open",
            new_status="in_progress",
            assigned_to="Support Agent",
            updated_by="Admin",
            update_message="Working on this issue",
        )

        assert "456" in subject
        assert "In Progress" in subject
        assert "Frank" in html
        assert "Server Error" in html
        assert "Support Agent" in html
        assert "Working on this issue" in html
        assert "Frank" in text

    def test_render_ticket_comment_email(self, template_service: EmailTemplateService):
        """Test ticket comment email rendering."""
        subject, html, text = template_service.render_ticket_comment_email(
            user_name="Grace",
            ticket_id=789,
            ticket_subject="Feature Request",
            comment_author="John Support",
            comment_author_role="agent",
            comment_text="We are reviewing your request.",
        )

        assert "789" in subject
        assert "Grace" in html
        assert "Feature Request" in html
        assert "John Support" in html
        assert "reviewing your request" in html
        assert "Support Agent" in html  # Role indicator
        assert "Grace" in text

    def test_render_proposal_sent_email(self, template_service: EmailTemplateService):
        """Test proposal sent email rendering."""
        subject, html, text = template_service.render_proposal_sent_email(
            user_name="Henry",
            proposal_id=101,
            proposal_title="Website Redesign",
            total_amount="5,000.00",
            currency="USD",
            expires_at="2024-02-15",
            sender_name="Agency Inc",
            organization_name="Agency Inc",
            project_name="Web Project",
            line_items=[
                {"description": "Design", "amount": "2,000.00"},
                {"description": "Development", "amount": "3,000.00"},
            ],
        )

        assert "Website Redesign" in subject
        assert "Henry" in html
        assert "5,000.00" in html
        assert "USD" in html
        assert "2024-02-15" in html
        assert "Agency Inc" in html
        assert "Design" in html
        assert "Development" in html
        assert "Henry" in text

    def test_render_proposal_approved_email(
        self, template_service: EmailTemplateService
    ):
        """Test proposal approved email rendering."""
        subject, html, text = template_service.render_proposal_approved_email(
            user_name="Ivy",
            proposal_id=202,
            proposal_title="Mobile App",
            total_amount="10,000.00",
            currency="USD",
            approved_by="Client Name",
            project_name="App Project",
            project_url="https://app.example.com/projects/1",
        )

        assert "Approved" in subject
        assert "Mobile App" in subject
        assert "Ivy" in html
        assert "10,000.00" in html
        assert "Client Name" in html
        assert "Ivy" in text

    def test_render_proposal_rejected_email(
        self, template_service: EmailTemplateService
    ):
        """Test proposal rejected email rendering."""
        subject, html, text = template_service.render_proposal_rejected_email(
            user_name="Jack",
            proposal_id=303,
            proposal_title="Consulting Services",
            rejected_by="Client",
            rejection_reason="Budget constraints",
            project_name="Consulting",
        )

        assert "Update" in subject
        assert "Jack" in html
        assert "Consulting Services" in html
        assert "Budget constraints" in html
        assert "Jack" in text

    def test_render_invoice_created_email(
        self, template_service: EmailTemplateService
    ):
        """Test invoice created email rendering."""
        subject, html, text = template_service.render_invoice_created_email(
            user_name="Kate",
            invoice_id=1001,
            invoice_number="INV-2024-001",
            total_amount="1,500.00",
            currency="USD",
            due_date="2024-02-28",
            organization_name="Billing Corp",
            project_name="Website",
            line_items=[
                {"description": "Services", "quantity": 1, "amount": "1,500.00"},
            ],
        )

        assert "INV-2024-001" in subject
        assert "Kate" in html
        assert "1,500.00" in html
        assert "2024-02-28" in html
        assert "Billing Corp" in html
        assert "Kate" in text

    def test_render_invoice_created_email_overdue(
        self, template_service: EmailTemplateService
    ):
        """Test invoice created email with overdue flag."""
        subject, html, text = template_service.render_invoice_created_email(
            user_name="Leo",
            invoice_id=1002,
            invoice_number="INV-2024-002",
            total_amount="2,000.00",
            due_date="2024-01-01",
            is_overdue=True,
        )

        assert "INV-2024-002" in subject
        assert "OVERDUE" in html
        assert "Leo" in text

    def test_render_invoice_paid_email(self, template_service: EmailTemplateService):
        """Test invoice paid email rendering."""
        subject, html, text = template_service.render_invoice_paid_email(
            user_name="Mike",
            invoice_id=1003,
            invoice_number="INV-2024-003",
            total_amount="3,000.00",
            currency="USD",
            payment_method="Credit Card ending in 4242",
            project_name="Consulting",
            is_client=True,
        )

        assert "Payment Received" in subject
        assert "INV-2024-003" in subject
        assert "Mike" in html
        assert "3,000.00" in html
        assert "4242" in html
        assert "Mike" in text

    def test_render_sla_warning_email(self, template_service: EmailTemplateService):
        """Test SLA warning email rendering."""
        subject, html, text = template_service.render_sla_warning_email(
            user_name="Nancy",
            ticket_id=555,
            ticket_subject="Urgent Issue",
            ticket_priority="urgent",
            sla_type="response",
            sla_status="warning",
            due_at="2024-01-15 14:00 UTC",
            customer_name="Important Client",
            organization_name="Big Corp",
            assigned_to="Agent Smith",
            time_remaining="30m",
        )

        assert "Warning" in subject
        assert "555" in subject
        assert "Nancy" in html
        assert "Urgent Issue" in html
        assert "Important Client" in html
        assert "30m" in html
        assert "Nancy" in text

    def test_render_sla_breach_email(self, template_service: EmailTemplateService):
        """Test SLA breach email rendering."""
        subject, html, text = template_service.render_sla_warning_email(
            user_name="Oscar",
            ticket_id=666,
            ticket_subject="Critical Bug",
            ticket_priority="high",
            sla_type="resolution",
            sla_status="breached",
            due_at="2024-01-14 10:00 UTC",
            customer_name="VIP Client",
            assigned_to=None,  # Unassigned
        )

        assert "BREACH" in subject
        assert "666" in subject
        assert "Oscar" in html
        assert "Critical Bug" in html
        assert "UNASSIGNED" in html  # Should show unassigned warning
        assert "Oscar" in text

    def test_base_context_includes_year_and_url(
        self, template_service: EmailTemplateService
    ):
        """Test that base context variables are included."""
        html = template_service.render_template(
            "verification.html",
            {
                "user_name": "Test",
                "verification_url": "https://example.com",
            },
        )

        # Should include copyright year from base template
        from datetime import datetime

        current_year = str(datetime.utcnow().year)
        assert current_year in html

    def test_truncate_filter(self, template_service: EmailTemplateService):
        """Test truncate filter works correctly."""
        result = template_service._truncate_filter(
            "This is a very long text that should be truncated",
            length=20,
        )
        assert len(result) == 20
        assert result.endswith("...")

    def test_truncate_filter_short_text(self, template_service: EmailTemplateService):
        """Test truncate filter doesn't truncate short text."""
        result = template_service._truncate_filter("Short", length=20)
        assert result == "Short"


class TestGetEmailTemplateService:
    """Tests for the singleton getter function."""

    def test_returns_singleton(self):
        """Test that get_email_template_service returns same instance."""
        service1 = get_email_template_service()
        service2 = get_email_template_service()
        assert service1 is service2

    def test_returns_email_template_service(self):
        """Test that it returns EmailTemplateService instance."""
        service = get_email_template_service()
        assert isinstance(service, EmailTemplateService)
