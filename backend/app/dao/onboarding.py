"""
Onboarding Data Access Object (DAO).

WHAT: Database operations for onboarding models.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for onboarding operations
3. Enforces org-scoping for multi-tenancy
4. Handles progress tracking queries

HOW: Extends BaseDAO with onboarding-specific queries:
- Template management
- Progress tracking
- Reminder management
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.onboarding import (
    OnboardingTemplate,
    ClientOnboarding,
    OnboardingReminder,
    OnboardingStatus,
)


class OnboardingTemplateDAO(BaseDAO[OnboardingTemplate]):
    """
    Data Access Object for OnboardingTemplate model.

    WHAT: Provides operations for onboarding templates.

    WHY: Centralizes template management.

    HOW: Extends BaseDAO with template-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize OnboardingTemplateDAO."""
        super().__init__(OnboardingTemplate, session)

    async def get_by_slug(
        self,
        org_id: int,
        slug: str,
    ) -> Optional[OnboardingTemplate]:
        """
        Get template by slug.

        WHAT: Finds template by unique slug.

        WHY: Slugs are used in URLs and API calls.

        Args:
            org_id: Organization ID
            slug: Template slug

        Returns:
            Template if found
        """
        result = await self.session.execute(
            select(OnboardingTemplate).where(
                OnboardingTemplate.org_id == org_id,
                OnboardingTemplate.slug == slug,
            )
        )
        return result.scalar_one_or_none()

    async def get_org_templates(
        self,
        org_id: int,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[OnboardingTemplate]:
        """
        Get all templates for an organization.

        WHAT: Lists templates with optional filters.

        WHY: Admin management view.

        Args:
            org_id: Organization ID
            is_active: Optional active filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of templates
        """
        query = (
            select(OnboardingTemplate)
            .where(OnboardingTemplate.org_id == org_id)
        )

        if is_active is not None:
            query = query.where(OnboardingTemplate.is_active == is_active)

        query = query.order_by(OnboardingTemplate.name.asc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_default_template(
        self,
        org_id: int,
    ) -> Optional[OnboardingTemplate]:
        """
        Get the default template for an organization.

        WHAT: Finds the template marked as default.

        WHY: Auto-assign to new users.

        Args:
            org_id: Organization ID

        Returns:
            Default template if exists
        """
        result = await self.session.execute(
            select(OnboardingTemplate).where(
                OnboardingTemplate.org_id == org_id,
                OnboardingTemplate.is_active == True,
                OnboardingTemplate.is_default == True,
            )
        )
        return result.scalar_one_or_none()

    async def set_default(
        self,
        template_id: int,
        org_id: int,
    ) -> Optional[OnboardingTemplate]:
        """
        Set a template as the default.

        WHAT: Makes one template the default.

        WHY: Only one template can be default.

        Args:
            template_id: Template to make default
            org_id: Organization ID

        Returns:
            Updated template
        """
        # Unset any existing default
        await self.session.execute(
            update(OnboardingTemplate)
            .where(
                OnboardingTemplate.org_id == org_id,
                OnboardingTemplate.is_default == True,
            )
            .values(is_default=False)
        )

        # Set new default
        template = await self.get_by_id_and_org(template_id, org_id)
        if template:
            template.is_default = True
            await self.session.flush()
            await self.session.refresh(template)

        return template


class ClientOnboardingDAO(BaseDAO[ClientOnboarding]):
    """
    Data Access Object for ClientOnboarding model.

    WHAT: Provides operations for client onboarding progress.

    WHY: Tracks individual user onboarding.

    HOW: Extends BaseDAO with progress-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize ClientOnboardingDAO."""
        super().__init__(ClientOnboarding, session)

    async def get_by_user_and_template(
        self,
        user_id: int,
        template_id: int,
    ) -> Optional[ClientOnboarding]:
        """
        Get onboarding for a user and template.

        WHAT: Finds existing onboarding record.

        WHY: Each user has one onboarding per template.

        Args:
            user_id: User ID
            template_id: Template ID

        Returns:
            Onboarding if exists
        """
        result = await self.session.execute(
            select(ClientOnboarding)
            .where(
                ClientOnboarding.user_id == user_id,
                ClientOnboarding.template_id == template_id,
            )
            .options(selectinload(ClientOnboarding.template))
        )
        return result.scalar_one_or_none()

    async def get_user_onboarding(
        self,
        user_id: int,
        org_id: int,
    ) -> Optional[ClientOnboarding]:
        """
        Get active onboarding for a user.

        WHAT: Finds user's current onboarding.

        WHY: Show onboarding progress.

        Args:
            user_id: User ID
            org_id: Organization ID

        Returns:
            Active onboarding if exists
        """
        result = await self.session.execute(
            select(ClientOnboarding)
            .where(
                ClientOnboarding.user_id == user_id,
                ClientOnboarding.org_id == org_id,
                ClientOnboarding.status.in_([
                    OnboardingStatus.NOT_STARTED.value,
                    OnboardingStatus.IN_PROGRESS.value,
                ]),
            )
            .options(selectinload(ClientOnboarding.template))
            .order_by(ClientOnboarding.created_at.desc())
        )
        return result.scalars().first()

    async def get_org_onboardings(
        self,
        org_id: int,
        status: Optional[str] = None,
        template_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ClientOnboarding]:
        """
        Get all onboardings for an organization.

        WHAT: Lists onboardings with filters.

        WHY: Admin view of onboarding status.

        Args:
            org_id: Organization ID
            status: Optional status filter
            template_id: Optional template filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of onboardings
        """
        query = (
            select(ClientOnboarding)
            .where(ClientOnboarding.org_id == org_id)
            .options(
                selectinload(ClientOnboarding.user),
                selectinload(ClientOnboarding.template),
            )
        )

        if status:
            query = query.where(ClientOnboarding.status == status)

        if template_id:
            query = query.where(ClientOnboarding.template_id == template_id)

        query = query.order_by(ClientOnboarding.created_at.desc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def start_onboarding(
        self,
        onboarding_id: int,
        first_step: str,
    ) -> Optional[ClientOnboarding]:
        """
        Start an onboarding.

        WHAT: Marks onboarding as started.

        WHY: Track when user begins.

        Args:
            onboarding_id: Onboarding ID
            first_step: First step ID

        Returns:
            Updated onboarding
        """
        onboarding = await self.get_by_id(onboarding_id)
        if not onboarding:
            return None

        onboarding.status = OnboardingStatus.IN_PROGRESS.value
        onboarding.current_step = first_step
        onboarding.started_at = datetime.utcnow()
        onboarding.last_activity_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(onboarding)
        return onboarding

    async def complete_step(
        self,
        onboarding_id: int,
        step_id: str,
        step_data: Optional[Dict[str, Any]] = None,
        next_step: Optional[str] = None,
    ) -> Optional[ClientOnboarding]:
        """
        Complete a step in onboarding.

        WHAT: Marks step as complete and stores data.

        WHY: Track progress and collect data.

        Args:
            onboarding_id: Onboarding ID
            step_id: Completed step ID
            step_data: Data collected in step
            next_step: Next step ID (None if complete)

        Returns:
            Updated onboarding
        """
        onboarding = await self.get_by_id(onboarding_id)
        if not onboarding:
            return None

        # Add to completed steps
        completed = onboarding.completed_steps or []
        if step_id not in completed:
            completed.append(step_id)
        onboarding.completed_steps = completed

        # Store step data
        if step_data:
            data = onboarding.step_data or {}
            data[step_id] = step_data
            onboarding.step_data = data

        # Update current step
        onboarding.current_step = next_step
        onboarding.last_activity_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(onboarding)
        return onboarding

    async def skip_step(
        self,
        onboarding_id: int,
        step_id: str,
        next_step: Optional[str] = None,
    ) -> Optional[ClientOnboarding]:
        """
        Skip a step in onboarding.

        WHAT: Marks step as skipped.

        WHY: Allow optional steps to be skipped.

        Args:
            onboarding_id: Onboarding ID
            step_id: Skipped step ID
            next_step: Next step ID

        Returns:
            Updated onboarding
        """
        onboarding = await self.get_by_id(onboarding_id)
        if not onboarding:
            return None

        # Add to skipped steps
        skipped = onboarding.skipped_steps or []
        if step_id not in skipped:
            skipped.append(step_id)
        onboarding.skipped_steps = skipped

        # Update current step
        onboarding.current_step = next_step
        onboarding.last_activity_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(onboarding)
        return onboarding

    async def complete_onboarding(
        self,
        onboarding_id: int,
    ) -> Optional[ClientOnboarding]:
        """
        Complete an onboarding.

        WHAT: Marks onboarding as complete.

        WHY: Track completion.

        Args:
            onboarding_id: Onboarding ID

        Returns:
            Updated onboarding
        """
        onboarding = await self.get_by_id(onboarding_id)
        if not onboarding:
            return None

        onboarding.status = OnboardingStatus.COMPLETED.value
        onboarding.completed_at = datetime.utcnow()
        onboarding.current_step = None
        onboarding.progress_percent = 100

        await self.session.flush()
        await self.session.refresh(onboarding)
        return onboarding

    async def update_progress(
        self,
        onboarding_id: int,
        progress_percent: int,
    ) -> Optional[ClientOnboarding]:
        """
        Update progress percentage.

        WHAT: Updates calculated progress.

        WHY: Display progress to user.

        Args:
            onboarding_id: Onboarding ID
            progress_percent: Progress (0-100)

        Returns:
            Updated onboarding
        """
        onboarding = await self.get_by_id(onboarding_id)
        if not onboarding:
            return None

        onboarding.progress_percent = min(100, max(0, progress_percent))

        await self.session.flush()
        await self.session.refresh(onboarding)
        return onboarding

    async def get_stalled_onboardings(
        self,
        org_id: int,
        stalled_after_hours: int = 48,
    ) -> List[ClientOnboarding]:
        """
        Get onboardings that have stalled.

        WHAT: Finds in-progress onboardings without recent activity.

        WHY: Send reminders to users.

        Args:
            org_id: Organization ID
            stalled_after_hours: Hours of inactivity

        Returns:
            List of stalled onboardings
        """
        cutoff = datetime.utcnow() - timedelta(hours=stalled_after_hours)

        result = await self.session.execute(
            select(ClientOnboarding)
            .where(
                ClientOnboarding.org_id == org_id,
                ClientOnboarding.status == OnboardingStatus.IN_PROGRESS.value,
                or_(
                    ClientOnboarding.last_activity_at < cutoff,
                    and_(
                        ClientOnboarding.last_activity_at.is_(None),
                        ClientOnboarding.created_at < cutoff,
                    ),
                ),
            )
            .options(
                selectinload(ClientOnboarding.user),
                selectinload(ClientOnboarding.template),
            )
        )
        return list(result.scalars().all())

    async def get_completion_stats(
        self,
        org_id: int,
        template_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Get onboarding completion statistics.

        WHAT: Aggregates onboarding status counts.

        WHY: Analytics dashboard.

        Args:
            org_id: Organization ID
            template_id: Optional template filter

        Returns:
            Stats dict
        """
        query = select(
            ClientOnboarding.status,
            func.count(ClientOnboarding.id).label("count"),
        ).where(ClientOnboarding.org_id == org_id)

        if template_id:
            query = query.where(ClientOnboarding.template_id == template_id)

        query = query.group_by(ClientOnboarding.status)

        result = await self.session.execute(query)

        stats = {
            "not_started": 0,
            "in_progress": 0,
            "completed": 0,
            "abandoned": 0,
            "skipped": 0,
            "total": 0,
        }

        for row in result:
            stats[row.status] = row.count
            stats["total"] += row.count

        return stats


class OnboardingReminderDAO(BaseDAO[OnboardingReminder]):
    """
    Data Access Object for OnboardingReminder model.

    WHAT: Provides operations for onboarding reminders.

    WHY: Track reminder history.

    HOW: Extends BaseDAO with reminder-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize OnboardingReminderDAO."""
        super().__init__(OnboardingReminder, session)

    async def get_reminders_for_onboarding(
        self,
        onboarding_id: int,
    ) -> List[OnboardingReminder]:
        """
        Get all reminders sent for an onboarding.

        WHAT: Lists reminder history.

        WHY: Prevent excessive reminders.

        Args:
            onboarding_id: Onboarding ID

        Returns:
            List of reminders
        """
        result = await self.session.execute(
            select(OnboardingReminder)
            .where(OnboardingReminder.onboarding_id == onboarding_id)
            .order_by(OnboardingReminder.sent_at.desc())
        )
        return list(result.scalars().all())

    async def get_recent_reminder(
        self,
        onboarding_id: int,
        reminder_type: str,
        within_hours: int = 24,
    ) -> Optional[OnboardingReminder]:
        """
        Check for recent reminder.

        WHAT: Finds recent reminder of same type.

        WHY: Prevent duplicate reminders.

        Args:
            onboarding_id: Onboarding ID
            reminder_type: Type of reminder
            within_hours: Time window

        Returns:
            Recent reminder if exists
        """
        cutoff = datetime.utcnow() - timedelta(hours=within_hours)

        result = await self.session.execute(
            select(OnboardingReminder).where(
                OnboardingReminder.onboarding_id == onboarding_id,
                OnboardingReminder.reminder_type == reminder_type,
                OnboardingReminder.sent_at > cutoff,
            )
        )
        return result.scalar_one_or_none()

    async def record_open(
        self,
        reminder_id: int,
    ) -> Optional[OnboardingReminder]:
        """
        Record that reminder was opened.

        WHAT: Tracks email open.

        WHY: Engagement analytics.

        Args:
            reminder_id: Reminder ID

        Returns:
            Updated reminder
        """
        reminder = await self.get_by_id(reminder_id)
        if reminder and not reminder.opened_at:
            reminder.opened_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(reminder)
        return reminder

    async def record_click(
        self,
        reminder_id: int,
    ) -> Optional[OnboardingReminder]:
        """
        Record that reminder link was clicked.

        WHAT: Tracks click-through.

        WHY: Engagement analytics.

        Args:
            reminder_id: Reminder ID

        Returns:
            Updated reminder
        """
        reminder = await self.get_by_id(reminder_id)
        if reminder:
            if not reminder.opened_at:
                reminder.opened_at = datetime.utcnow()
            reminder.clicked_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(reminder)
        return reminder
