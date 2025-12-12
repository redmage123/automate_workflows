"""
Email Template Management API endpoints.

WHAT: REST API for database-backed email template management.

WHY: Enables organization admins to:
1. Create and customize email templates
2. Manage template versions
3. Preview emails before sending
4. Track sent email analytics

HOW: FastAPI router with:
- Template CRUD with versioning
- Template rendering/preview
- Email sending
- Analytics endpoints
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_role
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.services.email_template_management_service import (
    EmailTemplateManagementService,
    TemplateNotFoundError,
)
from app.schemas.email_template import (
    EmailCategory,
    EmailTemplateCreateRequest,
    EmailTemplateUpdateRequest,
    RenderTemplateRequest,
    SendEmailRequest,
    EmailTemplateResponse,
    EmailTemplateListResponse,
    EmailTemplateVersionResponse,
    EmailTemplateVersionListResponse,
    RenderedEmailResponse,
    SentEmailResponse,
    SentEmailListResponse,
    EmailStatsResponse,
)


router = APIRouter(prefix="/email-templates", tags=["email-templates"])


# =============================================================================
# Template Management Endpoints
# =============================================================================


@router.post(
    "",
    response_model=EmailTemplateResponse,
    status_code=201,
    summary="Create email template",
    description="Create a new email template for the organization.",
)
async def create_template(
    request: EmailTemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> EmailTemplateResponse:
    """
    Create a new email template.

    WHAT: Creates org-specific email template with versioning.

    WHY: Custom templates enable branded communications.

    Requirements:
        - ADMIN role required
        - Unique slug per organization

    Args:
        request: Template creation data
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Created template details
    """
    service = EmailTemplateManagementService(db)

    template = await service.create_template(
        org_id=current_user.org_id,
        name=request.name,
        slug=request.slug,
        subject=request.subject,
        html_body=request.html_body,
        text_body=request.text_body,
        description=request.description,
        category=request.category.value if request.category else "system",
        variables=request.variables.model_dump() if request.variables else None,
        created_by_id=current_user.id,
    )

    await db.commit()

    return EmailTemplateResponse(
        id=template.id,
        org_id=template.org_id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        category=EmailCategory(template.category),
        subject=template.subject,
        html_body=template.html_body,
        text_body=template.text_body,
        variables=template.variables,
        variable_names=template.variable_names,
        is_active=template.is_active,
        is_system=template.is_system,
        version=template.version,
        created_by=None,  # Would load relationship
        updated_by=None,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get(
    "",
    response_model=EmailTemplateListResponse,
    summary="List email templates",
    description="Get paginated list of email templates for the organization.",
)
async def list_templates(
    category: Optional[EmailCategory] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> EmailTemplateListResponse:
    """
    List email templates.

    WHAT: Returns paginated template list.

    WHY: Admin template management view.

    Args:
        category: Optional category filter
        is_active: Optional active status filter
        skip: Pagination offset
        limit: Pagination limit
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Paginated template list
    """
    service = EmailTemplateManagementService(db)

    templates, total = await service.list_templates(
        org_id=current_user.org_id,
        category=category.value if category else None,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )

    items = [
        EmailTemplateResponse(
            id=t.id,
            org_id=t.org_id,
            name=t.name,
            slug=t.slug,
            description=t.description,
            category=EmailCategory(t.category),
            subject=t.subject,
            html_body=t.html_body,
            text_body=t.text_body,
            variables=t.variables,
            variable_names=t.variable_names,
            is_active=t.is_active,
            is_system=t.is_system,
            version=t.version,
            created_by=None,
            updated_by=None,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in templates
    ]

    return EmailTemplateListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{template_id}",
    response_model=EmailTemplateResponse,
    summary="Get email template",
    description="Get a specific email template by ID.",
)
async def get_template(
    template_id: int = Path(..., description="Template ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> EmailTemplateResponse:
    """
    Get template by ID.

    WHAT: Retrieves full template details.

    Args:
        template_id: Template ID
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Template details

    Raises:
        404: Template not found
    """
    service = EmailTemplateManagementService(db)

    template = await service.get_template(
        template_id=template_id,
        org_id=current_user.org_id,
    )

    return EmailTemplateResponse(
        id=template.id,
        org_id=template.org_id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        category=EmailCategory(template.category),
        subject=template.subject,
        html_body=template.html_body,
        text_body=template.text_body,
        variables=template.variables,
        variable_names=template.variable_names,
        is_active=template.is_active,
        is_system=template.is_system,
        version=template.version,
        created_by=None,
        updated_by=None,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get(
    "/slug/{slug}",
    response_model=EmailTemplateResponse,
    summary="Get email template by slug",
    description="Get a specific email template by slug.",
)
async def get_template_by_slug(
    slug: str = Path(..., description="Template slug"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> EmailTemplateResponse:
    """
    Get template by slug.

    WHAT: Retrieves template by URL-friendly identifier.

    Args:
        slug: Template slug
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Template details

    Raises:
        404: Template not found
    """
    service = EmailTemplateManagementService(db)

    template = await service.get_template_by_slug(
        org_id=current_user.org_id,
        slug=slug,
    )

    return EmailTemplateResponse(
        id=template.id,
        org_id=template.org_id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        category=EmailCategory(template.category),
        subject=template.subject,
        html_body=template.html_body,
        text_body=template.text_body,
        variables=template.variables,
        variable_names=template.variable_names,
        is_active=template.is_active,
        is_system=template.is_system,
        version=template.version,
        created_by=None,
        updated_by=None,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.patch(
    "/{template_id}",
    response_model=EmailTemplateResponse,
    summary="Update email template",
    description="Update an existing email template. Creates a new version.",
)
async def update_template(
    template_id: int = Path(..., description="Template ID"),
    request: EmailTemplateUpdateRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> EmailTemplateResponse:
    """
    Update email template.

    WHAT: Updates template with versioning.

    WHY: Changes create versions for rollback.

    Args:
        template_id: Template ID
        request: Update data
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Updated template details

    Raises:
        404: Template not found
    """
    service = EmailTemplateManagementService(db)

    variables_dict = None
    if request.variables:
        variables_dict = {k: v.model_dump() for k, v in request.variables.items()}

    template = await service.update_template(
        template_id=template_id,
        org_id=current_user.org_id,
        name=request.name,
        description=request.description,
        category=request.category.value if request.category else None,
        subject=request.subject,
        html_body=request.html_body,
        text_body=request.text_body,
        variables=variables_dict,
        change_note=request.change_note,
        updated_by_id=current_user.id,
    )

    await db.commit()

    return EmailTemplateResponse(
        id=template.id,
        org_id=template.org_id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        category=EmailCategory(template.category),
        subject=template.subject,
        html_body=template.html_body,
        text_body=template.text_body,
        variables=template.variables,
        variable_names=template.variable_names,
        is_active=template.is_active,
        is_system=template.is_system,
        version=template.version,
        created_by=None,
        updated_by=None,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.delete(
    "/{template_id}",
    response_model=EmailTemplateResponse,
    summary="Deactivate email template",
    description="Soft-delete (deactivate) an email template.",
)
async def deactivate_template(
    template_id: int = Path(..., description="Template ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> EmailTemplateResponse:
    """
    Deactivate email template.

    WHAT: Soft-deletes template.

    WHY: Preserves history and sent emails.

    Args:
        template_id: Template ID
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Deactivated template

    Raises:
        404: Template not found
    """
    service = EmailTemplateManagementService(db)

    template = await service.deactivate_template(
        template_id=template_id,
        org_id=current_user.org_id,
    )

    await db.commit()

    return EmailTemplateResponse(
        id=template.id,
        org_id=template.org_id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        category=EmailCategory(template.category),
        subject=template.subject,
        html_body=template.html_body,
        text_body=template.text_body,
        variables=template.variables,
        variable_names=template.variable_names,
        is_active=template.is_active,
        is_system=template.is_system,
        version=template.version,
        created_by=None,
        updated_by=None,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.post(
    "/{template_id}/activate",
    response_model=EmailTemplateResponse,
    summary="Activate email template",
    description="Reactivate a deactivated email template.",
)
async def activate_template(
    template_id: int = Path(..., description="Template ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> EmailTemplateResponse:
    """
    Activate email template.

    WHAT: Restores deactivated template.

    Args:
        template_id: Template ID
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Activated template

    Raises:
        404: Template not found
    """
    service = EmailTemplateManagementService(db)

    template = await service.activate_template(
        template_id=template_id,
        org_id=current_user.org_id,
    )

    await db.commit()

    return EmailTemplateResponse(
        id=template.id,
        org_id=template.org_id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        category=EmailCategory(template.category),
        subject=template.subject,
        html_body=template.html_body,
        text_body=template.text_body,
        variables=template.variables,
        variable_names=template.variable_names,
        is_active=template.is_active,
        is_system=template.is_system,
        version=template.version,
        created_by=None,
        updated_by=None,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


# =============================================================================
# Version Management Endpoints
# =============================================================================


@router.get(
    "/{template_id}/versions",
    response_model=EmailTemplateVersionListResponse,
    summary="Get template versions",
    description="Get version history for an email template.",
)
async def get_template_versions(
    template_id: int = Path(..., description="Template ID"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> EmailTemplateVersionListResponse:
    """
    Get template version history.

    WHAT: Lists all versions of a template.

    WHY: View and restore previous versions.

    Args:
        template_id: Template ID
        skip: Pagination offset
        limit: Pagination limit
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Version history list

    Raises:
        404: Template not found
    """
    service = EmailTemplateManagementService(db)

    versions, total = await service.get_template_versions(
        template_id=template_id,
        org_id=current_user.org_id,
        skip=skip,
        limit=limit,
    )

    items = [
        EmailTemplateVersionResponse(
            id=v.id,
            template_id=v.template_id,
            version=v.version,
            subject=v.subject,
            html_body=v.html_body,
            text_body=v.text_body,
            variables=v.variables,
            changed_by=None,
            change_note=v.change_note,
            created_at=v.created_at,
        )
        for v in versions
    ]

    return EmailTemplateVersionListResponse(
        items=items,
        total=total,
    )


@router.post(
    "/{template_id}/versions/{version}/restore",
    response_model=EmailTemplateResponse,
    summary="Restore template version",
    description="Restore a template to a previous version.",
)
async def restore_version(
    template_id: int = Path(..., description="Template ID"),
    version: int = Path(..., description="Version number to restore"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> EmailTemplateResponse:
    """
    Restore template to previous version.

    WHAT: Reverts template to historical version.

    WHY: Undo unwanted changes.

    Args:
        template_id: Template ID
        version: Version number to restore
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Restored template

    Raises:
        404: Template or version not found
    """
    service = EmailTemplateManagementService(db)

    template = await service.restore_version(
        template_id=template_id,
        version_number=version,
        org_id=current_user.org_id,
        restored_by_id=current_user.id,
    )

    await db.commit()

    return EmailTemplateResponse(
        id=template.id,
        org_id=template.org_id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        category=EmailCategory(template.category),
        subject=template.subject,
        html_body=template.html_body,
        text_body=template.text_body,
        variables=template.variables,
        variable_names=template.variable_names,
        is_active=template.is_active,
        is_system=template.is_system,
        version=template.version,
        created_by=None,
        updated_by=None,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


# =============================================================================
# Rendering and Sending Endpoints
# =============================================================================


@router.post(
    "/{template_id}/render",
    response_model=RenderedEmailResponse,
    summary="Render email template",
    description="Preview an email template with variables substituted.",
)
async def render_template(
    template_id: int = Path(..., description="Template ID"),
    request: RenderTemplateRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> RenderedEmailResponse:
    """
    Render template preview.

    WHAT: Substitutes variables into template.

    WHY: Preview before sending.

    Args:
        template_id: Template ID
        request: Variables for rendering
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Rendered email content

    Raises:
        404: Template not found
        400: Rendering error
    """
    service = EmailTemplateManagementService(db)

    rendered = await service.render_template(
        template_id=template_id,
        org_id=current_user.org_id,
        variables=request.variables,
    )

    return RenderedEmailResponse(
        subject=rendered["subject"],
        html_body=rendered["html_body"],
        text_body=rendered.get("text_body"),
    )


@router.post(
    "/send",
    response_model=SentEmailResponse,
    summary="Send templated email",
    description="Send an email using a template.",
)
async def send_email(
    request: SendEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> SentEmailResponse:
    """
    Send email using template.

    WHAT: Renders and sends email.

    WHY: Send consistent branded emails.

    Args:
        request: Send email request
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Sent email record

    Raises:
        404: Template not found
        500: Send failed
    """
    service = EmailTemplateManagementService(db)

    sent_email = await service.send_email(
        org_id=current_user.org_id,
        template_slug=request.template_slug,
        to_email=request.to_email,
        variables=request.variables,
        to_name=request.to_name,
        from_name=request.from_name,
    )

    await db.commit()

    return SentEmailResponse(
        id=sent_email.id,
        org_id=sent_email.org_id,
        template_id=sent_email.template_id,
        template_slug=sent_email.template_slug,
        to_email=sent_email.to_email,
        to_name=sent_email.to_name,
        from_email=sent_email.from_email,
        from_name=sent_email.from_name,
        subject=sent_email.subject,
        status=sent_email.status,
        error_message=sent_email.error_message,
        message_id=sent_email.message_id,
        provider=sent_email.provider,
        sent_at=sent_email.sent_at,
        opened_at=sent_email.opened_at,
        clicked_at=sent_email.clicked_at,
        created_at=sent_email.created_at,
    )


# =============================================================================
# Sent Email History Endpoints
# =============================================================================


@router.get(
    "/sent",
    response_model=SentEmailListResponse,
    summary="List sent emails",
    description="Get sent email history with optional filters.",
)
async def list_sent_emails(
    status: Optional[str] = Query(None, description="Filter by status"),
    template_id: Optional[int] = Query(None, description="Filter by template"),
    to_email: Optional[str] = Query(None, description="Filter by recipient"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> SentEmailListResponse:
    """
    List sent emails.

    WHAT: Returns sent email history.

    WHY: Email audit and debugging.

    Args:
        status: Optional status filter
        template_id: Optional template filter
        to_email: Optional recipient filter
        skip: Pagination offset
        limit: Pagination limit
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Paginated sent email list
    """
    service = EmailTemplateManagementService(db)

    emails, total = await service.get_sent_emails(
        org_id=current_user.org_id,
        status=status,
        template_id=template_id,
        to_email=to_email,
        skip=skip,
        limit=limit,
    )

    items = [
        SentEmailResponse(
            id=e.id,
            org_id=e.org_id,
            template_id=e.template_id,
            template_slug=e.template_slug,
            to_email=e.to_email,
            to_name=e.to_name,
            from_email=e.from_email,
            from_name=e.from_name,
            subject=e.subject,
            status=e.status,
            error_message=e.error_message,
            message_id=e.message_id,
            provider=e.provider,
            sent_at=e.sent_at,
            opened_at=e.opened_at,
            clicked_at=e.clicked_at,
            created_at=e.created_at,
        )
        for e in emails
    ]

    return SentEmailListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# Analytics Endpoints
# =============================================================================


@router.get(
    "/stats",
    response_model=EmailStatsResponse,
    summary="Get email statistics",
    description="Get email delivery and engagement statistics.",
)
async def get_email_stats(
    template_id: Optional[int] = Query(None, description="Filter by template"),
    days: int = Query(30, ge=1, le=365, description="Time range in days"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
) -> EmailStatsResponse:
    """
    Get email statistics.

    WHAT: Aggregates email metrics.

    WHY: Analytics dashboard.

    Args:
        template_id: Optional template filter
        days: Time range in days
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Email statistics
    """
    service = EmailTemplateManagementService(db)

    stats = await service.get_email_stats(
        org_id=current_user.org_id,
        template_id=template_id,
        days=days,
    )

    return EmailStatsResponse(
        total=stats.get("total", 0),
        pending=stats.get("pending", 0),
        sent=stats.get("sent", 0),
        delivered=stats.get("delivered", 0),
        bounced=stats.get("bounced", 0),
        failed=stats.get("failed", 0),
        opens=stats.get("opens", 0),
        clicks=stats.get("clicks", 0),
        delivery_rate=stats.get("delivery_rate", 0.0),
        open_rate=stats.get("open_rate", 0.0),
        click_rate=stats.get("click_rate", 0.0),
    )


# =============================================================================
# Webhook Endpoints (for email provider callbacks)
# =============================================================================


@router.post(
    "/webhooks/open/{message_id}",
    summary="Record email open",
    description="Webhook endpoint for tracking pixel opens.",
)
async def record_open(
    message_id: str = Path(..., description="Message ID"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Record email open.

    WHAT: Tracks email open events.

    WHY: Engagement analytics.

    NOTE: This would typically be called by a tracking pixel or provider webhook.

    Args:
        message_id: Provider message ID
        db: Database session

    Returns:
        Success status
    """
    service = EmailTemplateManagementService(db)
    await service.record_open(message_id)
    await db.commit()
    return {"status": "ok"}


@router.post(
    "/webhooks/click/{message_id}",
    summary="Record email click",
    description="Webhook endpoint for link click tracking.",
)
async def record_click(
    message_id: str = Path(..., description="Message ID"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Record email click.

    WHAT: Tracks link click events.

    WHY: Engagement analytics.

    NOTE: This would typically be called by click tracking redirect.

    Args:
        message_id: Provider message ID
        db: Database session

    Returns:
        Success status
    """
    service = EmailTemplateManagementService(db)
    await service.record_click(message_id)
    await db.commit()
    return {"status": "ok"}
