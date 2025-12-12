"""
Email Template Data Access Object (DAO).

WHAT: Database operations for email template models.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for template operations
3. Enforces org-scoping for multi-tenancy
4. Handles version management

HOW: Extends BaseDAO with template-specific queries:
- Template CRUD with versioning
- Sent email logging
- Analytics queries
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.email_template import (
    EmailTemplate,
    EmailTemplateVersion,
    SentEmail,
    EmailCategory,
)


class EmailTemplateDAO(BaseDAO[EmailTemplate]):
    """
    Data Access Object for EmailTemplate model.

    WHAT: Provides operations for email templates.

    WHY: Centralizes template management with versioning.

    HOW: Extends BaseDAO with template-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize EmailTemplateDAO."""
        super().__init__(EmailTemplate, session)

    async def get_by_slug(
        self,
        org_id: int,
        slug: str,
    ) -> Optional[EmailTemplate]:
        """
        Get template by slug.

        WHAT: Finds template by unique slug.

        WHY: Slugs identify templates in code.

        Args:
            org_id: Organization ID
            slug: Template slug

        Returns:
            Template if found
        """
        result = await self.session.execute(
            select(EmailTemplate).where(
                EmailTemplate.org_id == org_id,
                EmailTemplate.slug == slug,
                EmailTemplate.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_org_templates(
        self,
        org_id: int,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[EmailTemplate]:
        """
        Get templates for an organization.

        WHAT: Lists templates with optional filters.

        WHY: Admin management view.

        Args:
            org_id: Organization ID
            category: Optional category filter
            is_active: Optional active filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of templates
        """
        query = (
            select(EmailTemplate)
            .where(EmailTemplate.org_id == org_id)
            .options(selectinload(EmailTemplate.created_by))
        )

        if category:
            query = query.where(EmailTemplate.category == category)

        if is_active is not None:
            query = query.where(EmailTemplate.is_active == is_active)

        query = query.order_by(EmailTemplate.category, EmailTemplate.name)

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create_version(
        self,
        template: EmailTemplate,
        changed_by_id: Optional[int] = None,
        change_note: Optional[str] = None,
    ) -> EmailTemplateVersion:
        """
        Create a version snapshot.

        WHAT: Saves current template state as version.

        WHY: Enable rollback and audit trail.

        Args:
            template: Template to version
            changed_by_id: User making change
            change_note: Description of change

        Returns:
            Created version
        """
        version = EmailTemplateVersion(
            template_id=template.id,
            version=template.version,
            subject=template.subject,
            html_body=template.html_body,
            text_body=template.text_body,
            variables=template.variables,
            changed_by_id=changed_by_id,
            change_note=change_note,
        )

        self.session.add(version)
        await self.session.flush()
        await self.session.refresh(version)
        return version

    async def increment_version(
        self,
        template_id: int,
    ) -> Optional[EmailTemplate]:
        """
        Increment template version.

        WHAT: Updates version number.

        WHY: Track changes.

        Args:
            template_id: Template ID

        Returns:
            Updated template
        """
        template = await self.get_by_id(template_id)
        if not template:
            return None

        template.version += 1

        await self.session.flush()
        await self.session.refresh(template)
        return template

    async def deactivate(
        self,
        template_id: int,
        org_id: int,
    ) -> Optional[EmailTemplate]:
        """
        Deactivate a template.

        WHAT: Marks template as inactive.

        WHY: Soft delete for templates.

        Args:
            template_id: Template ID
            org_id: Organization ID

        Returns:
            Updated template
        """
        template = await self.get_by_id_and_org(template_id, org_id)
        if not template:
            return None

        template.is_active = False

        await self.session.flush()
        await self.session.refresh(template)
        return template


class EmailTemplateVersionDAO(BaseDAO[EmailTemplateVersion]):
    """
    Data Access Object for EmailTemplateVersion model.

    WHAT: Provides operations for template versions.

    WHY: Version management for templates.

    HOW: Extends BaseDAO with version-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize EmailTemplateVersionDAO."""
        super().__init__(EmailTemplateVersion, session)

    async def get_template_versions(
        self,
        template_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> List[EmailTemplateVersion]:
        """
        Get versions for a template.

        WHAT: Lists version history.

        WHY: View change history.

        Args:
            template_id: Template ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of versions
        """
        result = await self.session.execute(
            select(EmailTemplateVersion)
            .where(EmailTemplateVersion.template_id == template_id)
            .options(selectinload(EmailTemplateVersion.changed_by))
            .order_by(EmailTemplateVersion.version.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_specific_version(
        self,
        template_id: int,
        version: int,
    ) -> Optional[EmailTemplateVersion]:
        """
        Get a specific version.

        WHAT: Retrieves particular version.

        WHY: View or restore specific version.

        Args:
            template_id: Template ID
            version: Version number

        Returns:
            Version if found
        """
        result = await self.session.execute(
            select(EmailTemplateVersion).where(
                EmailTemplateVersion.template_id == template_id,
                EmailTemplateVersion.version == version,
            )
        )
        return result.scalar_one_or_none()


class SentEmailDAO(BaseDAO[SentEmail]):
    """
    Data Access Object for SentEmail model.

    WHAT: Provides operations for sent email logs.

    WHY: Email delivery tracking and analytics.

    HOW: Extends BaseDAO with logging-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize SentEmailDAO."""
        super().__init__(SentEmail, session)

    async def log_email(
        self,
        org_id: int,
        to_email: str,
        from_email: str,
        subject: str,
        template_id: Optional[int] = None,
        template_slug: Optional[str] = None,
        to_name: Optional[str] = None,
        from_name: Optional[str] = None,
        variables_used: Optional[Dict[str, Any]] = None,
        status: str = "pending",
        message_id: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> SentEmail:
        """
        Log a sent email.

        WHAT: Creates sent email record.

        WHY: Track all outgoing emails.

        Args:
            org_id: Organization ID
            to_email: Recipient email
            from_email: Sender email
            subject: Email subject
            template_id: Optional template ID
            template_slug: Optional template slug
            to_name: Recipient name
            from_name: Sender name
            variables_used: Variables passed to template
            status: Delivery status
            message_id: Provider message ID
            provider: Email provider used

        Returns:
            Created SentEmail record
        """
        sent_email = SentEmail(
            org_id=org_id,
            to_email=to_email,
            from_email=from_email,
            subject=subject,
            template_id=template_id,
            template_slug=template_slug,
            to_name=to_name,
            from_name=from_name,
            variables_used=variables_used,
            status=status,
            message_id=message_id,
            provider=provider,
        )

        self.session.add(sent_email)
        await self.session.flush()
        await self.session.refresh(sent_email)
        return sent_email

    async def update_status(
        self,
        email_id: int,
        status: str,
        error_message: Optional[str] = None,
        sent_at: Optional[datetime] = None,
    ) -> Optional[SentEmail]:
        """
        Update email delivery status.

        WHAT: Records delivery outcome.

        WHY: Track delivery success/failure.

        Args:
            email_id: SentEmail ID
            status: New status
            error_message: Optional error message
            sent_at: When email was sent

        Returns:
            Updated SentEmail
        """
        email = await self.get_by_id(email_id)
        if not email:
            return None

        email.status = status
        if error_message:
            email.error_message = error_message
        if sent_at:
            email.sent_at = sent_at
        elif status == "sent":
            email.sent_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(email)
        return email

    async def record_open(
        self,
        message_id: str,
    ) -> Optional[SentEmail]:
        """
        Record email open.

        WHAT: Tracks when email was opened.

        WHY: Engagement analytics.

        Args:
            message_id: Provider message ID

        Returns:
            Updated SentEmail
        """
        result = await self.session.execute(
            select(SentEmail).where(SentEmail.message_id == message_id)
        )
        email = result.scalar_one_or_none()

        if email and not email.opened_at:
            email.opened_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(email)

        return email

    async def record_click(
        self,
        message_id: str,
    ) -> Optional[SentEmail]:
        """
        Record email link click.

        WHAT: Tracks when link was clicked.

        WHY: Engagement analytics.

        Args:
            message_id: Provider message ID

        Returns:
            Updated SentEmail
        """
        result = await self.session.execute(
            select(SentEmail).where(SentEmail.message_id == message_id)
        )
        email = result.scalar_one_or_none()

        if email:
            if not email.opened_at:
                email.opened_at = datetime.utcnow()
            email.clicked_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(email)

        return email

    async def get_org_emails(
        self,
        org_id: int,
        status: Optional[str] = None,
        template_id: Optional[int] = None,
        to_email: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[SentEmail]:
        """
        Get sent emails for an organization.

        WHAT: Lists sent email logs.

        WHY: Admin view of email history.

        Args:
            org_id: Organization ID
            status: Optional status filter
            template_id: Optional template filter
            to_email: Optional recipient filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of sent emails
        """
        query = (
            select(SentEmail)
            .where(SentEmail.org_id == org_id)
        )

        if status:
            query = query.where(SentEmail.status == status)

        if template_id:
            query = query.where(SentEmail.template_id == template_id)

        if to_email:
            query = query.where(SentEmail.to_email.ilike(f"%{to_email}%"))

        query = query.order_by(SentEmail.created_at.desc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_email_stats(
        self,
        org_id: int,
        template_id: Optional[int] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get email delivery statistics.

        WHAT: Aggregates email metrics.

        WHY: Analytics dashboard.

        Args:
            org_id: Organization ID
            template_id: Optional template filter
            days: Time range in days

        Returns:
            Stats dict
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        query = select(
            SentEmail.status,
            func.count(SentEmail.id).label("count"),
        ).where(
            SentEmail.org_id == org_id,
            SentEmail.created_at >= cutoff,
        )

        if template_id:
            query = query.where(SentEmail.template_id == template_id)

        query = query.group_by(SentEmail.status)

        result = await self.session.execute(query)

        stats = {
            "pending": 0,
            "sent": 0,
            "delivered": 0,
            "bounced": 0,
            "failed": 0,
            "total": 0,
        }

        for row in result:
            stats[row.status] = row.count
            stats["total"] += row.count

        # Get open and click counts
        engagement_query = select(
            func.count(SentEmail.id).filter(SentEmail.opened_at.isnot(None)).label("opens"),
            func.count(SentEmail.id).filter(SentEmail.clicked_at.isnot(None)).label("clicks"),
        ).where(
            SentEmail.org_id == org_id,
            SentEmail.created_at >= cutoff,
        )

        if template_id:
            engagement_query = engagement_query.where(SentEmail.template_id == template_id)

        engagement_result = await self.session.execute(engagement_query)
        engagement = engagement_result.one()

        stats["opens"] = engagement.opens or 0
        stats["clicks"] = engagement.clicks or 0

        # Calculate rates
        delivered = stats["sent"] + stats["delivered"]
        stats["open_rate"] = stats["opens"] / delivered if delivered > 0 else 0.0
        stats["click_rate"] = stats["clicks"] / stats["opens"] if stats["opens"] > 0 else 0.0
        stats["delivery_rate"] = delivered / stats["total"] if stats["total"] > 0 else 0.0

        return stats
