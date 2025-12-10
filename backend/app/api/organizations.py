"""
Organization management API endpoints.

WHY: These endpoints provide organization CRUD operations:
1. GET /me - Get current user's organization
2. GET /{org_id} - Get organization by ID (with org-scoping)
3. POST / - Create new organization (ADMIN only)
4. PUT /{org_id} - Update organization (ADMIN only)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.core.exceptions import ResourceNotFoundError, OrganizationAccessDenied
from app.db.session import get_db
from app.dao.base import BaseDAO
from app.models.user import User
from app.models.organization import Organization
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
)


router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get(
    "/me",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user's organization",
    description="Get organization details for the currently authenticated user",
)
async def get_current_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """
    Get current user's organization.

    WHY: Users need to view their organization details for settings,
    billing information, and team management.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Organization data

    Raises:
        ResourceNotFoundError (404): If organization not found
    """
    org_dao = BaseDAO(Organization, db)
    organization = await org_dao.get_by_id(current_user.org_id)

    if not organization:
        raise ResourceNotFoundError(
            message=f"Organization with id {current_user.org_id} not found",
            resource_type="Organization",
            resource_id=current_user.org_id,
        )

    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        description=organization.description,
        settings=organization.settings or {},
        is_active=organization.is_active,
        created_at=organization.created_at.isoformat(),
        updated_at=organization.updated_at.isoformat(),
    )


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get organization by ID",
    description="Get organization details by ID (must be user's own organization)",
)
async def get_organization(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """
    Get organization by ID.

    WHY: Allows fetching organization by ID, but enforces org-scoping
    to prevent users from accessing other organizations.

    Args:
        org_id: Organization ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Organization data

    Raises:
        OrganizationAccessDenied (403): If trying to access another organization
        ResourceNotFoundError (404): If organization not found
    """
    # Org-scoping check
    # WHY: Users can only access their own organization (OWASP A01: Broken Access Control)
    if org_id != current_user.org_id:
        raise OrganizationAccessDenied(
            message="You don't have permission to access this organization",
            user_id=current_user.id,
            org_id=org_id,
        )

    org_dao = BaseDAO(Organization, db)
    organization = await org_dao.get_by_id(org_id)

    if not organization:
        raise ResourceNotFoundError(
            message=f"Organization with id {org_id} not found",
            resource_type="Organization",
            resource_id=org_id,
        )

    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        description=organization.description,
        settings=organization.settings or {},
        is_active=organization.is_active,
        created_at=organization.created_at.isoformat(),
        updated_at=organization.updated_at.isoformat(),
    )


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization",
    description="Create a new organization (ADMIN only)",
)
async def create_organization(
    data: OrganizationCreate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """
    Create a new organization.

    WHY: Admins need to create organizations for new clients or
    internal projects. This is typically a platform admin feature.

    RBAC: Requires ADMIN role.

    Args:
        data: Organization creation data
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Created organization data
    """
    org_dao = BaseDAO(Organization, db)

    # Create organization
    organization = await org_dao.create(
        name=data.name,
        description=data.description or f"Organization for {data.name}",
        settings={},
        is_active=True,
    )

    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        description=organization.description,
        settings=organization.settings or {},
        is_active=organization.is_active,
        created_at=organization.created_at.isoformat(),
        updated_at=organization.updated_at.isoformat(),
    )


@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update organization",
    description="Update organization details (ADMIN only, own org)",
)
async def update_organization(
    org_id: int,
    data: OrganizationUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """
    Update organization details.

    WHY: Admins need to update organization settings, name, description, etc.

    RBAC: Requires ADMIN role and org-scoping (can only update own org).

    Args:
        org_id: Organization ID to update
        data: Organization update data
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated organization data

    Raises:
        OrganizationAccessDenied (403): If trying to update another organization
        ResourceNotFoundError (404): If organization not found
    """
    # Org-scoping check
    # WHY: Admins can only update their own organization
    if org_id != current_user.org_id:
        raise OrganizationAccessDenied(
            message="You don't have permission to update this organization",
            user_id=current_user.id,
            org_id=org_id,
        )

    org_dao = BaseDAO(Organization, db)

    # Prepare update data (only include non-None fields)
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description
    if data.settings is not None:
        update_data["settings"] = data.settings

    # Update organization
    organization = await org_dao.update(org_id, **update_data)

    if not organization:
        raise ResourceNotFoundError(
            message=f"Organization with id {org_id} not found",
            resource_type="Organization",
            resource_id=org_id,
        )

    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        description=organization.description,
        settings=organization.settings or {},
        is_active=organization.is_active,
        created_at=organization.created_at.isoformat(),
        updated_at=organization.updated_at.isoformat(),
    )
