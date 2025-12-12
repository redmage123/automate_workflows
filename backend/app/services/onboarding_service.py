"""
Onboarding Service.

WHAT: Business logic for client onboarding operations.

WHY: The service layer:
1. Encapsulates onboarding business logic
2. Coordinates between DAOs
3. Enforces business rules
4. Handles step progression and validation

HOW: Orchestrates OnboardingTemplateDAO, ClientOnboardingDAO, OnboardingReminderDAO
while validating operations against business rules.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.onboarding import (
    OnboardingTemplateDAO,
    ClientOnboardingDAO,
    OnboardingReminderDAO,
)
from app.models.onboarding import (
    OnboardingTemplate,
    ClientOnboarding,
    OnboardingReminder,
    OnboardingStatus,
    StepType,
)
from app.core.exceptions import (
    OnboardingError,
    OnboardingTemplateNotFoundError,
    OnboardingNotFoundError,
    OnboardingStepError,
    ValidationError,
)


class OnboardingService:
    """
    Service for onboarding operations.

    WHAT: Provides business logic for onboarding.

    WHY: Onboarding enables:
    - Guided setup for new clients
    - Customizable multi-step flows
    - Progress tracking and completion
    - Data collection at each step

    HOW: Coordinates DAOs and enforces business rules.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize OnboardingService.

        Args:
            session: Async database session
        """
        self.session = session
        self.template_dao = OnboardingTemplateDAO(session)
        self.onboarding_dao = ClientOnboardingDAO(session)
        self.reminder_dao = OnboardingReminderDAO(session)

    # =========================================================================
    # Template Management
    # =========================================================================

    async def create_template(
        self,
        org_id: int,
        name: str,
        slug: str,
        steps: List[Dict[str, Any]],
        description: Optional[str] = None,
        is_active: bool = True,
        is_default: bool = False,
        auto_assign: bool = False,
        target_roles: Optional[List[str]] = None,
    ) -> OnboardingTemplate:
        """
        Create a new onboarding template.

        WHAT: Creates a template defining onboarding flow.

        WHY: Templates standardize onboarding process.

        Args:
            org_id: Organization ID
            name: Template name
            slug: URL-friendly slug
            steps: List of step definitions
            description: Template description
            is_active: Is active
            is_default: Is default template
            auto_assign: Auto-assign to new users
            target_roles: Target user roles

        Returns:
            Created OnboardingTemplate

        Raises:
            ValidationError: If validation fails
        """
        # Check for duplicate slug
        existing = await self.template_dao.get_by_slug(org_id, slug)
        if existing:
            raise ValidationError(
                message="Template with this slug already exists",
                details={"slug": slug},
            )

        # Validate steps
        self._validate_steps(steps)

        # If setting as default, unset other defaults
        if is_default:
            await self.template_dao.set_default(0, org_id)  # Unset all

        template = await self.template_dao.create(
            org_id=org_id,
            name=name,
            slug=slug,
            description=description,
            steps=steps,
            is_active=is_active,
            is_default=is_default,
            auto_assign=auto_assign,
            target_roles=target_roles,
        )

        return template

    def _validate_steps(self, steps: List[Dict[str, Any]]) -> None:
        """
        Validate step definitions.

        WHAT: Ensures steps are properly formatted.

        WHY: Invalid steps cause runtime errors.

        Args:
            steps: List of step definitions

        Raises:
            ValidationError: If validation fails
        """
        if not steps:
            raise ValidationError(
                message="At least one step is required",
            )

        step_ids = set()
        for i, step in enumerate(steps):
            if "id" not in step:
                raise ValidationError(
                    message=f"Step {i} missing 'id' field",
                    details={"step_index": i},
                )

            if step["id"] in step_ids:
                raise ValidationError(
                    message=f"Duplicate step ID: {step['id']}",
                    details={"step_id": step["id"]},
                )
            step_ids.add(step["id"])

            if "title" not in step:
                raise ValidationError(
                    message=f"Step {step['id']} missing 'title' field",
                    details={"step_id": step["id"]},
                )

            if "type" not in step:
                raise ValidationError(
                    message=f"Step {step['id']} missing 'type' field",
                    details={"step_id": step["id"]},
                )

            # Validate step type is valid
            valid_types = [t.value for t in StepType]
            if step["type"] not in valid_types:
                raise ValidationError(
                    message=f"Invalid step type: {step['type']}",
                    details={"step_id": step["id"], "valid_types": valid_types},
                )

    async def get_template(
        self,
        template_id: int,
        org_id: int,
    ) -> OnboardingTemplate:
        """
        Get a template by ID.

        WHAT: Retrieves template details.

        WHY: View template configuration.

        Args:
            template_id: Template ID
            org_id: Organization ID

        Returns:
            OnboardingTemplate

        Raises:
            OnboardingTemplateNotFoundError: If not found
        """
        template = await self.template_dao.get_by_id_and_org(template_id, org_id)
        if not template:
            raise OnboardingTemplateNotFoundError(
                message="Onboarding template not found",
                details={"template_id": template_id},
            )
        return template

    async def update_template(
        self,
        template_id: int,
        org_id: int,
        **kwargs,
    ) -> OnboardingTemplate:
        """
        Update a template.

        WHAT: Updates template configuration.

        WHY: Modify onboarding flow.

        Args:
            template_id: Template ID
            org_id: Organization ID
            **kwargs: Fields to update

        Returns:
            Updated OnboardingTemplate
        """
        template = await self.get_template(template_id, org_id)

        # Validate steps if being updated
        if "steps" in kwargs:
            self._validate_steps(kwargs["steps"])

        # Handle default flag
        if kwargs.get("is_default") and not template.is_default:
            await self.template_dao.set_default(template_id, org_id)
            kwargs.pop("is_default")  # Already handled

        for key, value in kwargs.items():
            if value is not None and hasattr(template, key):
                setattr(template, key, value)

        await self.session.flush()
        await self.session.refresh(template)
        return template

    async def delete_template(
        self,
        template_id: int,
        org_id: int,
    ) -> None:
        """
        Delete a template.

        WHAT: Removes template.

        WHY: Clean up unused templates.

        Args:
            template_id: Template ID
            org_id: Organization ID

        Raises:
            OnboardingTemplateNotFoundError: If not found
            OnboardingError: If template has active onboardings
        """
        template = await self.get_template(template_id, org_id)

        # Check for active onboardings using this template
        onboardings = await self.onboarding_dao.get_org_onboardings(
            org_id, template_id=template_id
        )
        active = [o for o in onboardings if o.status in [
            OnboardingStatus.NOT_STARTED.value,
            OnboardingStatus.IN_PROGRESS.value,
        ]]

        if active:
            raise OnboardingError(
                message="Cannot delete template with active onboardings",
                details={"active_count": len(active)},
            )

        await self.template_dao.delete(template_id)

    async def list_templates(
        self,
        org_id: int,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[OnboardingTemplate], int]:
        """
        List templates for an organization.

        WHAT: Lists templates with filters.

        WHY: Admin management view.

        Args:
            org_id: Organization ID
            active_only: Filter to active templates only
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (templates list, total count)
        """
        is_active = True if active_only else None
        templates = await self.template_dao.get_org_templates(
            org_id=org_id,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )

        # Get total count
        all_templates = await self.template_dao.get_org_templates(
            org_id=org_id,
            is_active=is_active,
            skip=0,
            limit=10000,
        )

        return templates, len(all_templates)

    # =========================================================================
    # Client Onboarding
    # =========================================================================

    async def start_onboarding(
        self,
        org_id: int,
        user_id: int,
        template_id: Optional[int] = None,
    ) -> ClientOnboarding:
        """
        Start onboarding for a user.

        WHAT: Creates or returns existing onboarding.

        WHY: Begin onboarding process.

        Args:
            org_id: Organization ID
            user_id: User ID
            template_id: Optional template ID (uses default if not specified)

        Returns:
            ClientOnboarding

        Raises:
            OnboardingTemplateNotFoundError: If no template available
        """
        # Get template
        if template_id:
            template = await self.get_template(template_id, org_id)
        else:
            template = await self.template_dao.get_default_template(org_id)
            if not template:
                raise OnboardingTemplateNotFoundError(
                    message="No default onboarding template available",
                )

        # Check for existing onboarding
        existing = await self.onboarding_dao.get_by_user_and_template(
            user_id, template.id
        )
        if existing:
            return existing

        # Get first step
        steps = template.steps if isinstance(template.steps, list) else []
        first_step = steps[0]["id"] if steps else None

        # Create onboarding
        onboarding = await self.onboarding_dao.create(
            org_id=org_id,
            user_id=user_id,
            template_id=template.id,
            status=OnboardingStatus.IN_PROGRESS.value,
            current_step=first_step,
            completed_steps=[],
            skipped_steps=[],
            step_data={},
            progress_percent=0,
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
        )

        return onboarding

    async def get_user_onboarding(
        self,
        user_id: int,
        org_id: int,
    ) -> Optional[ClientOnboarding]:
        """
        Get active onboarding for current user.

        WHAT: Retrieves user's onboarding progress.

        WHY: Show onboarding wizard.

        Args:
            user_id: User ID
            org_id: Organization ID

        Returns:
            ClientOnboarding if exists
        """
        return await self.onboarding_dao.get_user_onboarding(user_id, org_id)

    async def get_onboarding(
        self,
        onboarding_id: int,
        org_id: int,
    ) -> ClientOnboarding:
        """
        Get an onboarding by ID.

        WHAT: Retrieves onboarding details.

        WHY: View onboarding progress.

        Args:
            onboarding_id: Onboarding ID
            org_id: Organization ID

        Returns:
            ClientOnboarding

        Raises:
            OnboardingNotFoundError: If not found
        """
        onboarding = await self.onboarding_dao.get_by_id(onboarding_id)
        if not onboarding or onboarding.org_id != org_id:
            raise OnboardingNotFoundError(
                message="Onboarding not found",
                details={"onboarding_id": onboarding_id},
            )
        return onboarding

    async def complete_step(
        self,
        onboarding_id: int,
        org_id: int,
        user_id: int,
        step_id: str,
        step_data: Optional[Dict[str, Any]] = None,
    ) -> ClientOnboarding:
        """
        Complete a step in onboarding.

        WHAT: Marks step as complete and advances.

        WHY: Progress through onboarding.

        Args:
            onboarding_id: Onboarding ID
            org_id: Organization ID
            user_id: User ID (for authorization)
            step_id: Step ID to complete
            step_data: Data collected in step

        Returns:
            Updated ClientOnboarding

        Raises:
            OnboardingNotFoundError: If not found
            OnboardingStepError: If step error
        """
        onboarding = await self.get_onboarding(onboarding_id, org_id)

        # Verify user owns this onboarding
        if onboarding.user_id != user_id:
            raise OnboardingNotFoundError(
                message="Onboarding not found",
                details={"onboarding_id": onboarding_id},
            )

        # Get template steps
        template = await self.template_dao.get_by_id(onboarding.template_id)
        if not template:
            raise OnboardingTemplateNotFoundError(
                message="Onboarding template not found",
            )

        steps = template.steps if isinstance(template.steps, list) else []
        step_ids = [s["id"] for s in steps]

        # Verify step exists
        if step_id not in step_ids:
            raise OnboardingStepError(
                message="Invalid step ID",
                details={"step_id": step_id},
            )

        # Verify this is the current step (or allow any step in some cases)
        if onboarding.current_step and onboarding.current_step != step_id:
            # Allow completing previous steps if revisiting
            completed = onboarding.completed_steps or []
            if step_id not in completed:
                raise OnboardingStepError(
                    message="Cannot complete this step out of order",
                    details={
                        "step_id": step_id,
                        "current_step": onboarding.current_step,
                    },
                )

        # Find next step
        current_index = step_ids.index(step_id)
        next_step = step_ids[current_index + 1] if current_index + 1 < len(step_ids) else None

        # Complete step
        onboarding = await self.onboarding_dao.complete_step(
            onboarding_id, step_id, step_data, next_step
        )

        # Update progress
        progress = onboarding.calculate_progress(steps)
        await self.onboarding_dao.update_progress(onboarding_id, progress)

        # Check if complete
        if not next_step:
            onboarding = await self.complete_onboarding(onboarding_id, org_id, user_id)

        return onboarding

    async def skip_step(
        self,
        onboarding_id: int,
        org_id: int,
        user_id: int,
        step_id: str,
    ) -> ClientOnboarding:
        """
        Skip a step in onboarding.

        WHAT: Marks step as skipped and advances.

        WHY: Allow optional steps to be skipped.

        Args:
            onboarding_id: Onboarding ID
            org_id: Organization ID
            user_id: User ID
            step_id: Step ID to skip

        Returns:
            Updated ClientOnboarding

        Raises:
            OnboardingStepError: If step cannot be skipped
        """
        onboarding = await self.get_onboarding(onboarding_id, org_id)

        if onboarding.user_id != user_id:
            raise OnboardingNotFoundError(
                message="Onboarding not found",
                details={"onboarding_id": onboarding_id},
            )

        # Get template steps
        template = await self.template_dao.get_by_id(onboarding.template_id)
        if not template:
            raise OnboardingTemplateNotFoundError(
                message="Onboarding template not found",
            )

        steps = template.steps if isinstance(template.steps, list) else []
        step_ids = [s["id"] for s in steps]

        # Find step definition
        step_def = next((s for s in steps if s["id"] == step_id), None)
        if not step_def:
            raise OnboardingStepError(
                message="Invalid step ID",
                details={"step_id": step_id},
            )

        # Check if step can be skipped
        if step_def.get("is_required", True) and not step_def.get("can_skip", False):
            raise OnboardingStepError(
                message="This step cannot be skipped",
                details={"step_id": step_id},
            )

        # Find next step
        current_index = step_ids.index(step_id)
        next_step = step_ids[current_index + 1] if current_index + 1 < len(step_ids) else None

        # Skip step
        onboarding = await self.onboarding_dao.skip_step(
            onboarding_id, step_id, next_step
        )

        # Update progress
        progress = onboarding.calculate_progress(steps)
        await self.onboarding_dao.update_progress(onboarding_id, progress)

        # Check if complete
        if not next_step:
            onboarding = await self.complete_onboarding(onboarding_id, org_id, user_id)

        return onboarding

    async def complete_onboarding(
        self,
        onboarding_id: int,
        org_id: int,
        user_id: int,
    ) -> ClientOnboarding:
        """
        Mark onboarding as complete.

        WHAT: Finalizes onboarding process.

        WHY: Track completion.

        Args:
            onboarding_id: Onboarding ID
            org_id: Organization ID
            user_id: User ID

        Returns:
            Updated ClientOnboarding
        """
        onboarding = await self.get_onboarding(onboarding_id, org_id)

        if onboarding.user_id != user_id:
            raise OnboardingNotFoundError(
                message="Onboarding not found",
                details={"onboarding_id": onboarding_id},
            )

        return await self.onboarding_dao.complete_onboarding(onboarding_id)

    async def get_onboarding_progress(
        self,
        user_id: int,
        org_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed progress for user's onboarding.

        WHAT: Returns progress with current step details.

        WHY: Power onboarding wizard UI.

        Args:
            user_id: User ID
            org_id: Organization ID

        Returns:
            Progress dict or None if no active onboarding
        """
        onboarding = await self.onboarding_dao.get_user_onboarding(user_id, org_id)
        if not onboarding:
            return None

        template = await self.template_dao.get_by_id(onboarding.template_id)
        if not template:
            return None

        steps = template.steps if isinstance(template.steps, list) else []
        step_ids = [s["id"] for s in steps]

        # Find current step details
        current_step = None
        current_index = 0
        if onboarding.current_step:
            for i, step in enumerate(steps):
                if step["id"] == onboarding.current_step:
                    current_step = step
                    current_index = i
                    break

        return {
            "id": onboarding.id,
            "status": onboarding.status,
            "progress_percent": onboarding.progress_percent,
            "current_step": current_step,
            "current_step_index": current_index,
            "total_steps": len(steps),
            "completed_steps": onboarding.completed_steps or [],
            "skipped_steps": onboarding.skipped_steps or [],
            "step_data": onboarding.step_data or {},
            "template_name": template.name,
            "template_description": template.description,
        }

    # =========================================================================
    # Admin Operations
    # =========================================================================

    async def list_onboardings(
        self,
        org_id: int,
        status: Optional[str] = None,
        template_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[ClientOnboarding], int]:
        """
        List all onboardings for an organization.

        WHAT: Lists onboardings with filters.

        WHY: Admin view of onboarding status.

        Args:
            org_id: Organization ID
            status: Optional status filter
            template_id: Optional template filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (onboardings list, total count)
        """
        onboardings = await self.onboarding_dao.get_org_onboardings(
            org_id=org_id,
            status=status,
            template_id=template_id,
            skip=skip,
            limit=limit,
        )

        # Get total count
        all_onboardings = await self.onboarding_dao.get_org_onboardings(
            org_id=org_id,
            status=status,
            template_id=template_id,
            skip=0,
            limit=10000,
        )

        return onboardings, len(all_onboardings)

    async def reset_onboarding(
        self,
        onboarding_id: int,
        org_id: int,
    ) -> ClientOnboarding:
        """
        Reset an onboarding to initial state.

        WHAT: Clears progress and restarts onboarding.

        WHY: Admin may need to restart client onboarding.

        Args:
            onboarding_id: Onboarding ID
            org_id: Organization ID

        Returns:
            Reset ClientOnboarding

        Raises:
            OnboardingNotFoundError: If not found
        """
        onboarding = await self.get_onboarding(onboarding_id, org_id)

        # Get template to find first step
        template = await self.template_dao.get_by_id(onboarding.template_id)
        if not template:
            raise OnboardingTemplateNotFoundError(
                message="Onboarding template not found",
            )

        steps = template.steps if isinstance(template.steps, list) else []
        first_step = steps[0]["id"] if steps else None

        # Reset onboarding state
        onboarding.status = OnboardingStatus.IN_PROGRESS.value
        onboarding.current_step = first_step
        onboarding.completed_steps = []
        onboarding.skipped_steps = []
        onboarding.step_data = {}
        onboarding.progress_percent = 0
        onboarding.completed_at = None
        onboarding.last_activity_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(onboarding)

        return onboarding

    async def get_onboarding_stats(
        self,
        org_id: int,
        template_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get onboarding statistics.

        WHAT: Aggregated completion stats.

        WHY: Analytics dashboard.

        Args:
            org_id: Organization ID
            template_id: Optional template filter

        Returns:
            Stats dict with completion rate
        """
        stats = await self.onboarding_dao.get_completion_stats(org_id, template_id)

        # Calculate completion rate
        total = stats["total"]
        completed = stats["completed"]
        completion_rate = completed / total if total > 0 else 0.0

        return {
            **stats,
            "completion_rate": completion_rate,
        }

    # =========================================================================
    # Reminder Management
    # =========================================================================

    async def get_stalled_onboardings(
        self,
        org_id: int,
        stalled_after_hours: int = 48,
    ) -> List[ClientOnboarding]:
        """
        Get stalled onboardings for reminders.

        WHAT: Finds onboardings without recent activity.

        WHY: Send reminder emails.

        Args:
            org_id: Organization ID
            stalled_after_hours: Hours of inactivity

        Returns:
            List of stalled onboardings
        """
        return await self.onboarding_dao.get_stalled_onboardings(
            org_id, stalled_after_hours
        )

    async def send_reminder(
        self,
        onboarding_id: int,
        reminder_type: str,
        email: str,
    ) -> OnboardingReminder:
        """
        Record a reminder being sent.

        WHAT: Creates reminder record.

        WHY: Track reminder history.

        Args:
            onboarding_id: Onboarding ID
            reminder_type: Type of reminder
            email: Email sent to

        Returns:
            OnboardingReminder record
        """
        # Check for recent reminder
        recent = await self.reminder_dao.get_recent_reminder(
            onboarding_id, reminder_type
        )
        if recent:
            raise OnboardingError(
                message="Reminder already sent recently",
                details={"last_sent": recent.sent_at.isoformat()},
            )

        return await self.reminder_dao.create(
            onboarding_id=onboarding_id,
            reminder_type=reminder_type,
            sent_to_email=email,
        )
