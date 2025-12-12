"""
Onboarding API Routes.

WHAT: FastAPI router for client onboarding wizard endpoints.

WHY: Onboarding provides:
1. Guided setup for new clients
2. Customizable multi-step flows
3. Progress tracking and completion
4. Data collection at each step

HOW: Exposes REST endpoints for:
- Template management (admin)
- User onboarding flow (start, progress, complete steps)
- Admin overview and statistics
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_roles
from app.core.exceptions import OnboardingNotFoundError
from app.models.user import User
from app.services.onboarding_service import OnboardingService
from app.schemas.onboarding import (
    OnboardingTemplateCreateRequest,
    OnboardingTemplateUpdateRequest,
    OnboardingTemplateResponse,
    OnboardingTemplateListResponse,
    OnboardingStartRequest,
    StepCompleteRequest,
    ClientOnboardingResponse,
    ClientOnboardingListResponse,
    OnboardingProgressResponse,
    OnboardingStatsResponse,
    OnboardingStatus,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ============================================================================
# Template Management Endpoints (Admin)
# ============================================================================


@router.post(
    "/templates",
    response_model=OnboardingTemplateResponse,
    summary="Create onboarding template",
    description="""
    Create a new onboarding template.

    **Admin only**: Requires ADMIN role.

    Templates define the steps and requirements for client onboarding.
    Each template can have multiple steps of different types:
    - info: Informational/welcome content
    - form: Data collection forms
    - upload: Document upload requirements
    - choice: Selection/preference steps
    - verification: Email/phone verification
    - integration: Third-party connections
    - review: Summary/confirmation
    """,
)
async def create_template(
    request: OnboardingTemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> OnboardingTemplateResponse:
    """
    Create a new onboarding template.

    WHAT: Creates a template with defined steps for client onboarding.

    WHY: Admins need to define customized onboarding flows for different
    client types or service offerings.

    HOW: Validates the template structure, creates the database record,
    and optionally sets it as the default template.

    Args:
        request: Template creation data including steps
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Created template with full details
    """
    service = OnboardingService(db)
    template = await service.create_template(
        org_id=current_user.org_id,
        name=request.name,
        description=request.description,
        slug=request.slug,
        steps=request.steps,
        is_active=request.is_active,
        is_default=request.is_default,
        auto_assign=request.auto_assign,
        target_roles=request.target_roles,
    )

    return _template_to_response(template)


@router.get(
    "/templates",
    response_model=OnboardingTemplateListResponse,
    summary="List onboarding templates",
    description="List all onboarding templates for the organization.",
)
async def list_templates(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    active_only: bool = Query(False, description="Filter to active templates only"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> OnboardingTemplateListResponse:
    """
    List onboarding templates.

    WHAT: Retrieves paginated list of templates.

    WHY: Admins need to view and manage available templates.

    HOW: Queries templates with optional active filter and pagination.

    Args:
        skip: Pagination offset
        limit: Maximum results
        active_only: Filter to active templates
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Paginated list of templates
    """
    service = OnboardingService(db)
    templates, total = await service.list_templates(
        org_id=current_user.org_id,
        skip=skip,
        limit=limit,
        active_only=active_only,
    )

    return OnboardingTemplateListResponse(
        items=[_template_to_response(t) for t in templates],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/templates/{template_id}",
    response_model=OnboardingTemplateResponse,
    summary="Get onboarding template",
    description="Get details of a specific onboarding template.",
)
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> OnboardingTemplateResponse:
    """
    Get a specific template.

    WHAT: Retrieves full template details including all steps.

    WHY: Admins need to view template configuration.

    HOW: Fetches template by ID with organization scope.

    Args:
        template_id: Template ID
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Template with full details

    Raises:
        OnboardingNotFoundError: If template not found
    """
    service = OnboardingService(db)
    template = await service.get_template(
        template_id=template_id,
        org_id=current_user.org_id,
    )

    if not template:
        raise OnboardingNotFoundError(
            message="Onboarding template not found",
            details={"template_id": template_id},
        )

    return _template_to_response(template)


@router.put(
    "/templates/{template_id}",
    response_model=OnboardingTemplateResponse,
    summary="Update onboarding template",
    description="Update an existing onboarding template.",
)
async def update_template(
    template_id: int,
    request: OnboardingTemplateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> OnboardingTemplateResponse:
    """
    Update an onboarding template.

    WHAT: Updates template properties and/or steps.

    WHY: Admins need to modify templates as requirements change.

    HOW: Validates updates and applies changes to existing template.

    Args:
        template_id: Template ID to update
        request: Update data (partial updates supported)
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Updated template

    Raises:
        OnboardingNotFoundError: If template not found
    """
    service = OnboardingService(db)
    template = await service.update_template(
        template_id=template_id,
        org_id=current_user.org_id,
        **request.model_dump(exclude_unset=True),
    )

    return _template_to_response(template)


@router.delete(
    "/templates/{template_id}",
    summary="Delete onboarding template",
    description="Delete an onboarding template. Cannot delete if in use.",
)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> dict:
    """
    Delete an onboarding template.

    WHAT: Removes a template from the system.

    WHY: Admins need to clean up unused templates.

    HOW: Checks for active onboardings using the template,
    then deletes if safe.

    Args:
        template_id: Template ID to delete
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Success message

    Raises:
        OnboardingNotFoundError: If template not found
        ValidationError: If template is in use
    """
    service = OnboardingService(db)
    await service.delete_template(
        template_id=template_id,
        org_id=current_user.org_id,
    )

    return {"message": "Template deleted successfully"}


# ============================================================================
# User Onboarding Flow Endpoints
# ============================================================================


@router.post(
    "/start",
    response_model=ClientOnboardingResponse,
    summary="Start onboarding",
    description="""
    Start the onboarding process for the current user.

    Uses the default template if no template_id is specified.
    If the user already has an in-progress onboarding, returns that instead.
    """,
)
async def start_onboarding(
    request: OnboardingStartRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClientOnboardingResponse:
    """
    Start onboarding for current user.

    WHAT: Initiates the onboarding process.

    WHY: Users need to complete onboarding after registration.

    HOW: Creates or retrieves existing onboarding record,
    associates with template, and sets initial step.

    Args:
        request: Optional template specification
        db: Database session
        current_user: Authenticated user

    Returns:
        Onboarding record with current progress
    """
    service = OnboardingService(db)
    template_id = request.template_id if request else None

    onboarding = await service.start_onboarding(
        org_id=current_user.org_id,
        user_id=current_user.id,
        template_id=template_id,
    )

    return await _onboarding_to_response(service, onboarding)


@router.get(
    "/progress",
    response_model=OnboardingProgressResponse,
    summary="Get onboarding progress",
    description="Get the current user's onboarding progress with step details.",
)
async def get_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OnboardingProgressResponse:
    """
    Get current user's onboarding progress.

    WHAT: Retrieves detailed progress information for wizard UI.

    WHY: Frontend needs current step, progress percentage, and
    collected data to render the onboarding wizard.

    HOW: Fetches onboarding record with template, calculates
    progress, and returns current step details.

    Args:
        db: Database session
        current_user: Authenticated user

    Returns:
        Progress details with current step information

    Raises:
        OnboardingNotFoundError: If no onboarding found
    """
    service = OnboardingService(db)
    progress = await service.get_onboarding_progress(
        user_id=current_user.id,
        org_id=current_user.org_id,
    )

    if not progress:
        raise OnboardingNotFoundError(
            message="No active onboarding found",
        )

    return OnboardingProgressResponse(**progress)


@router.post(
    "/steps/{step_id}/complete",
    response_model=OnboardingProgressResponse,
    summary="Complete onboarding step",
    description="Mark a step as completed and optionally submit step data.",
)
async def complete_step(
    step_id: str,
    request: StepCompleteRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OnboardingProgressResponse:
    """
    Complete an onboarding step.

    WHAT: Marks a step as completed and saves any collected data.

    WHY: Users progress through onboarding by completing steps.

    HOW: Validates step is current, saves data, updates progress,
    and advances to next step.

    Args:
        step_id: ID of step to complete
        request: Optional step data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated progress with next step

    Raises:
        OnboardingNotFoundError: If no onboarding found
        ValidationError: If step order invalid
    """
    service = OnboardingService(db)

    # Get user's onboarding first
    onboarding = await service.get_user_onboarding(
        user_id=current_user.id,
        org_id=current_user.org_id,
    )
    if not onboarding:
        raise OnboardingNotFoundError(
            message="No active onboarding found",
        )

    step_data = request.step_data if request else None

    await service.complete_step(
        onboarding_id=onboarding.id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        step_id=step_id,
        step_data=step_data,
    )

    # Return updated progress
    progress = await service.get_onboarding_progress(
        user_id=current_user.id,
        org_id=current_user.org_id,
    )

    return OnboardingProgressResponse(**progress)


@router.post(
    "/steps/{step_id}/skip",
    response_model=OnboardingProgressResponse,
    summary="Skip onboarding step",
    description="Skip an optional step and move to the next one.",
)
async def skip_step(
    step_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OnboardingProgressResponse:
    """
    Skip an onboarding step.

    WHAT: Marks an optional step as skipped.

    WHY: Users may want to skip optional steps to complete faster.

    HOW: Validates step is skippable, marks as skipped,
    and advances to next step.

    Args:
        step_id: ID of step to skip
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated progress with next step

    Raises:
        OnboardingNotFoundError: If no onboarding found
        ValidationError: If step cannot be skipped
    """
    service = OnboardingService(db)

    # Get user's onboarding first
    onboarding = await service.get_user_onboarding(
        user_id=current_user.id,
        org_id=current_user.org_id,
    )
    if not onboarding:
        raise OnboardingNotFoundError(
            message="No active onboarding found",
        )

    await service.skip_step(
        onboarding_id=onboarding.id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        step_id=step_id,
    )

    # Return updated progress
    progress = await service.get_onboarding_progress(
        user_id=current_user.id,
        org_id=current_user.org_id,
    )

    return OnboardingProgressResponse(**progress)


# ============================================================================
# Admin Onboarding Management Endpoints
# ============================================================================


@router.get(
    "/admin/list",
    response_model=ClientOnboardingListResponse,
    summary="List all onboardings (Admin)",
    description="List all client onboardings with filtering options.",
)
async def list_onboardings(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    status: Optional[OnboardingStatus] = Query(None, description="Filter by status"),
    template_id: Optional[int] = Query(None, description="Filter by template"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> ClientOnboardingListResponse:
    """
    List all onboardings (admin view).

    WHAT: Retrieves paginated list of all client onboardings.

    WHY: Admins need to monitor onboarding progress across clients.

    HOW: Queries onboardings with optional filters and pagination.

    Args:
        skip: Pagination offset
        limit: Maximum results
        status: Optional status filter
        template_id: Optional template filter
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Paginated list of onboardings
    """
    service = OnboardingService(db)
    onboardings, total = await service.list_onboardings(
        org_id=current_user.org_id,
        skip=skip,
        limit=limit,
        status=status.value if status else None,
        template_id=template_id,
    )

    items = [await _onboarding_to_response(service, o) for o in onboardings]

    return ClientOnboardingListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/admin/stats",
    response_model=OnboardingStatsResponse,
    summary="Get onboarding statistics",
    description="Get aggregated onboarding statistics for analytics.",
)
async def get_stats(
    template_id: Optional[int] = Query(None, description="Filter by template"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> OnboardingStatsResponse:
    """
    Get onboarding statistics.

    WHAT: Retrieves aggregated onboarding metrics.

    WHY: Admins need analytics to understand onboarding effectiveness.

    HOW: Aggregates counts by status and calculates completion rate.

    Args:
        template_id: Optional template filter
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Aggregated statistics
    """
    service = OnboardingService(db)
    stats = await service.get_onboarding_stats(
        org_id=current_user.org_id,
        template_id=template_id,
    )

    return stats


@router.get(
    "/admin/{onboarding_id}",
    response_model=ClientOnboardingResponse,
    summary="Get onboarding details (Admin)",
    description="Get detailed view of a specific client's onboarding.",
)
async def get_onboarding(
    onboarding_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> ClientOnboardingResponse:
    """
    Get specific onboarding details.

    WHAT: Retrieves full onboarding details for admin view.

    WHY: Admins need to view individual client onboarding progress.

    HOW: Fetches onboarding with template and user details.

    Args:
        onboarding_id: Onboarding ID
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Full onboarding details

    Raises:
        OnboardingNotFoundError: If onboarding not found
    """
    service = OnboardingService(db)
    onboarding = await service.get_onboarding(
        onboarding_id=onboarding_id,
        org_id=current_user.org_id,
    )

    if not onboarding:
        raise OnboardingNotFoundError(
            message="Onboarding not found",
            details={"onboarding_id": onboarding_id},
        )

    return await _onboarding_to_response(service, onboarding)


@router.post(
    "/admin/{onboarding_id}/reset",
    response_model=ClientOnboardingResponse,
    summary="Reset onboarding (Admin)",
    description="Reset a client's onboarding progress to the beginning.",
)
async def reset_onboarding(
    onboarding_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> ClientOnboardingResponse:
    """
    Reset onboarding progress.

    WHAT: Resets onboarding to initial state.

    WHY: Admins may need to restart onboarding for a client.

    HOW: Clears completed steps, resets status, and sets
    current step to first step.

    Args:
        onboarding_id: Onboarding ID to reset
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Reset onboarding record

    Raises:
        OnboardingNotFoundError: If onboarding not found
    """
    service = OnboardingService(db)
    onboarding = await service.reset_onboarding(
        onboarding_id=onboarding_id,
        org_id=current_user.org_id,
    )

    return await _onboarding_to_response(service, onboarding)


# ============================================================================
# Helper Functions
# ============================================================================


def _template_to_response(template) -> OnboardingTemplateResponse:
    """
    Convert template model to response schema.

    WHAT: Transforms SQLAlchemy model to Pydantic response.

    WHY: API responses need structured schema format.

    HOW: Maps model attributes to response fields,
    including computed properties.

    Args:
        template: OnboardingTemplate model instance

    Returns:
        OnboardingTemplateResponse schema
    """
    # Convert steps to schema format
    from app.schemas.onboarding import StepSchema

    steps = []
    if isinstance(template.steps, list):
        for step_dict in template.steps:
            steps.append(StepSchema(**step_dict))

    return OnboardingTemplateResponse(
        id=template.id,
        org_id=template.org_id,
        name=template.name,
        description=template.description,
        slug=template.slug,
        steps=steps,
        step_count=template.step_count,
        required_step_count=template.required_step_count,
        is_active=template.is_active,
        is_default=template.is_default,
        auto_assign=template.auto_assign,
        target_roles=template.target_roles,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


async def _onboarding_to_response(
    service: OnboardingService,
    onboarding,
) -> ClientOnboardingResponse:
    """
    Convert onboarding model to response schema.

    WHAT: Transforms SQLAlchemy model to Pydantic response.

    WHY: API responses need structured schema format.

    HOW: Maps model attributes to response fields,
    including related template and user data.

    Args:
        service: OnboardingService instance for loading relations
        onboarding: ClientOnboarding model instance

    Returns:
        ClientOnboardingResponse schema
    """
    from app.schemas.onboarding import OnboardingStatus as SchemaStatus, UserResponse

    # Load template if needed
    template_response = None
    if onboarding.template:
        template_response = _template_to_response(onboarding.template)

    # Load user if needed
    user_response = None
    if onboarding.user:
        user_response = UserResponse(
            id=onboarding.user.id,
            name=onboarding.user.name,
            email=onboarding.user.email,
        )

    return ClientOnboardingResponse(
        id=onboarding.id,
        org_id=onboarding.org_id,
        user_id=onboarding.user_id,
        template_id=onboarding.template_id,
        status=SchemaStatus(onboarding.status),
        current_step=onboarding.current_step,
        completed_steps=onboarding.completed_steps or [],
        skipped_steps=onboarding.skipped_steps or [],
        progress_percent=onboarding.progress_percent,
        step_data=onboarding.step_data,
        started_at=onboarding.started_at,
        completed_at=onboarding.completed_at,
        last_activity_at=onboarding.last_activity_at,
        created_at=onboarding.created_at,
        updated_at=onboarding.updated_at,
        template=template_response,
        user=user_response,
    )
