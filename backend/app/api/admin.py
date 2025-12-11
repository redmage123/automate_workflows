"""
Admin Portal API endpoints.

WHAT: RESTful API for administrative operations.

WHY: Administrators need centralized access to:
1. User management across all organizations
2. Organization management and health monitoring
3. Audit log viewing for security compliance
4. System-wide operations

HOW: FastAPI router with ADMIN role requirement on all endpoints.
All operations are logged for audit purposes.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, EmailStr, Field

from app.core.deps import require_role
from app.core.auth import hash_password
from app.core.exceptions import (
    ResourceNotFoundError,
    ResourceAlreadyExistsError,
    ValidationError,
)
from app.db.session import get_db
from app.dao.user import UserDAO
from app.dao.audit_log import AuditLogDAO
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.audit_log import AuditLog, AuditAction
from app.services.audit import AuditService


router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# Schemas
# ============================================================================


class UserListItem(BaseModel):
    """User summary for list views."""
    id: int
    email: str
    name: Optional[str]
    role: str
    is_active: bool
    email_verified: bool
    org_id: int
    org_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated user list response."""
    items: List[UserListItem]
    total: int
    skip: int
    limit: int


class UserDetailResponse(BaseModel):
    """Full user details for admin view."""
    id: int
    email: str
    name: Optional[str]
    role: str
    is_active: bool
    email_verified: bool
    org_id: int
    org_name: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    """Admin-initiated user creation."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)
    org_id: int
    role: str = Field(default="CLIENT", pattern="^(ADMIN|CLIENT)$")


class UserUpdateRequest(BaseModel):
    """Admin user update."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[str] = Field(None, pattern="^(ADMIN|CLIENT)$")
    is_active: Optional[bool] = None


class OrganizationListItem(BaseModel):
    """Organization summary for list views."""
    id: int
    name: str
    is_active: bool
    created_at: datetime
    user_count: int
    project_count: int

    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    """Paginated organization list response."""
    items: List[OrganizationListItem]
    total: int
    skip: int
    limit: int


class OrganizationDetailResponse(BaseModel):
    """Full organization details for admin view."""
    id: int
    name: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    user_count: int
    project_count: int
    ticket_count: int
    total_revenue: float

    class Config:
        from_attributes = True


class OrganizationUpdateRequest(BaseModel):
    """Admin organization update."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class AuditLogItem(BaseModel):
    """Audit log entry for viewer."""
    id: int
    actor_user_id: Optional[int]
    actor_email: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[int]
    org_id: Optional[int]
    org_name: Optional[str]
    changes: Optional[dict]
    extra_data: Optional[dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Paginated audit log response."""
    items: List[AuditLogItem]
    total: int
    skip: int
    limit: int


# ============================================================================
# User Management Endpoints (ADMIN-002)
# ============================================================================


@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all users",
    description="Get paginated list of all users across organizations (ADMIN only)",
)
async def list_users(
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum items to return"),
    org_id: Optional[int] = Query(default=None, description="Filter by organization"),
    role: Optional[str] = Query(default=None, description="Filter by role (ADMIN/CLIENT)"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search by email or name"),
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """
    List all users with optional filtering.

    WHAT: Returns paginated list of users across all organizations.

    WHY: Administrators need to view and manage all platform users.

    Args:
        skip: Pagination offset
        limit: Page size
        org_id: Filter by organization
        role: Filter by user role
        is_active: Filter by active status
        search: Search term for email/name
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Paginated user list
    """
    # Build base query
    query = select(User).join(Organization, User.org_id == Organization.id)
    count_query = select(func.count(User.id))

    # Apply filters
    if org_id is not None:
        query = query.where(User.org_id == org_id)
        count_query = count_query.where(User.org_id == org_id)

    if role is not None:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_term)) | (User.name.ilike(search_term))
        )
        count_query = count_query.where(
            (User.email.ilike(search_term)) | (User.name.ilike(search_term))
        )

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results
    query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    # Build response items
    items = []
    for user in users:
        org = await db.get(Organization, user.org_id)
        items.append(
            UserListItem(
                id=user.id,
                email=user.email,
                name=user.name,
                role=user.role.value if hasattr(user.role, 'value') else user.role,
                is_active=user.is_active,
                email_verified=user.email_verified,
                org_id=user.org_id,
                org_name=org.name if org else None,
                created_at=user.created_at,
            )
        )

    return UserListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/users/{user_id}",
    response_model=UserDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user details",
    description="Get detailed information about a specific user (ADMIN only)",
)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> UserDetailResponse:
    """
    Get detailed user information.

    WHAT: Returns full user details including organization info.

    WHY: Admins need to view user details for support and management.

    Args:
        user_id: User ID
        current_user: Current authenticated admin
        db: Database session

    Returns:
        User details

    Raises:
        ResourceNotFoundError: If user not found
    """
    user = await db.get(User, user_id)
    if not user:
        raise ResourceNotFoundError(
            message=f"User with id {user_id} not found",
            resource_type="User",
            resource_id=user_id,
        )

    org = await db.get(Organization, user.org_id)

    return UserDetailResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value if hasattr(user.role, 'value') else user.role,
        is_active=user.is_active,
        email_verified=user.email_verified,
        org_id=user.org_id,
        org_name=org.name if org else None,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post(
    "/users",
    response_model=UserDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a new user (ADMIN only)",
)
async def create_user(
    data: UserCreateRequest,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> UserDetailResponse:
    """
    Create a new user.

    WHAT: Admin-initiated user creation.

    WHY: Admins can create users directly without registration flow.

    Args:
        data: User creation data
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Created user details

    Raises:
        ResourceAlreadyExistsError: If email already exists
        ResourceNotFoundError: If organization not found
    """
    # Verify organization exists
    org = await db.get(Organization, data.org_id)
    if not org:
        raise ResourceNotFoundError(
            message=f"Organization with id {data.org_id} not found",
            resource_type="Organization",
            resource_id=data.org_id,
        )

    user_dao = UserDAO(User, db)

    # Create user
    try:
        user = await user_dao.create_user(
            email=data.email,
            hashed_password=hash_password(data.password),
            name=data.name,
            org_id=data.org_id,
            role=data.role,
        )
    except ResourceAlreadyExistsError:
        raise

    # Set verified since admin created
    user.email_verified = True
    await db.flush()

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="user",
        resource_id=user.id,
        actor_user_id=current_user.id,
        org_id=data.org_id,
        extra_data={"email": data.email, "role": data.role},
    )

    return UserDetailResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value if hasattr(user.role, 'value') else user.role,
        is_active=user.is_active,
        email_verified=user.email_verified,
        org_id=user.org_id,
        org_name=org.name,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.put(
    "/users/{user_id}",
    response_model=UserDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user",
    description="Update user details (ADMIN only)",
)
async def update_user(
    user_id: int,
    data: UserUpdateRequest,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> UserDetailResponse:
    """
    Update user details.

    WHAT: Updates user name, role, or active status.

    WHY: Admins need to manage user accounts.

    Args:
        user_id: User ID
        data: Update data
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Updated user details

    Raises:
        ResourceNotFoundError: If user not found
    """
    user = await db.get(User, user_id)
    if not user:
        raise ResourceNotFoundError(
            message=f"User with id {user_id} not found",
            resource_type="User",
            resource_id=user_id,
        )

    # Track changes for audit
    changes = {}

    if data.name is not None and data.name != user.name:
        changes["name"] = {"old": user.name, "new": data.name}
        user.name = data.name

    if data.role is not None and data.role != user.role:
        changes["role"] = {"old": user.role, "new": data.role}
        user.role = data.role

    if data.is_active is not None and data.is_active != user.is_active:
        changes["is_active"] = {"old": user.is_active, "new": data.is_active}
        user.is_active = data.is_active

    if changes:
        user.updated_at = datetime.utcnow()
        await db.flush()

        # Audit log
        audit_service = AuditService(db)
        await audit_service.log_update(
            resource_type="user",
            resource_id=user_id,
            actor_user_id=current_user.id,
            org_id=user.org_id,
            changes=changes,
        )

    org = await db.get(Organization, user.org_id)

    return UserDetailResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value if hasattr(user.role, 'value') else user.role,
        is_active=user.is_active,
        email_verified=user.email_verified,
        org_id=user.org_id,
        org_name=org.name if org else None,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate user",
    description="Deactivate a user (soft delete, ADMIN only)",
)
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Deactivate a user (soft delete).

    WHAT: Sets is_active to False.

    WHY: Soft deletion preserves data for audit and allows reactivation.

    Args:
        user_id: User ID
        current_user: Current authenticated admin
        db: Database session

    Raises:
        ResourceNotFoundError: If user not found
        ValidationError: If trying to deactivate self
    """
    if user_id == current_user.id:
        raise ValidationError(
            message="Cannot deactivate your own account",
            user_id=user_id,
        )

    user = await db.get(User, user_id)
    if not user:
        raise ResourceNotFoundError(
            message=f"User with id {user_id} not found",
            resource_type="User",
            resource_id=user_id,
        )

    user.is_active = False
    user.updated_at = datetime.utcnow()
    await db.flush()

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_delete(
        resource_type="user",
        resource_id=user_id,
        actor_user_id=current_user.id,
        org_id=user.org_id,
    )


@router.post(
    "/users/{user_id}/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Force password reset",
    description="Force a password reset for a user (ADMIN only)",
)
async def force_password_reset(
    user_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Force password reset for a user.

    WHAT: Generates a new temporary password.

    WHY: Admins need to reset passwords for locked-out users.

    Note: In a real system, this would send an email with reset link.
    For now, we just log the action.

    Args:
        user_id: User ID
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Success message

    Raises:
        ResourceNotFoundError: If user not found
    """
    user = await db.get(User, user_id)
    if not user:
        raise ResourceNotFoundError(
            message=f"User with id {user_id} not found",
            resource_type="User",
            resource_id=user_id,
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="user",
        resource_id=user_id,
        actor_user_id=current_user.id,
        org_id=user.org_id,
        changes={"password_reset": {"initiated_by": current_user.email}},
    )

    return {"message": "Password reset initiated", "user_id": user_id}


# ============================================================================
# Organization Management Endpoints (ADMIN-003)
# ============================================================================


@router.get(
    "/organizations",
    response_model=OrganizationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all organizations",
    description="Get paginated list of all organizations (ADMIN only)",
)
async def list_organizations(
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum items to return"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search by name"),
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> OrganizationListResponse:
    """
    List all organizations with stats.

    WHAT: Returns paginated list of organizations with user/project counts.

    WHY: Administrators need to view and manage all organizations.

    Args:
        skip: Pagination offset
        limit: Page size
        is_active: Filter by active status
        search: Search term for name
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Paginated organization list with stats
    """
    from app.models.project import Project

    # Build base query
    query = select(Organization)
    count_query = select(func.count(Organization.id))

    if is_active is not None:
        query = query.where(Organization.is_active == is_active)
        count_query = count_query.where(Organization.is_active == is_active)

    if search:
        search_term = f"%{search}%"
        query = query.where(Organization.name.ilike(search_term))
        count_query = count_query.where(Organization.name.ilike(search_term))

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results
    query = query.order_by(Organization.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    orgs = result.scalars().all()

    # Build response items with counts
    items = []
    for org in orgs:
        # Count users
        user_count_result = await db.execute(
            select(func.count(User.id)).where(User.org_id == org.id)
        )
        user_count = user_count_result.scalar_one()

        # Count projects
        project_count_result = await db.execute(
            select(func.count(Project.id)).where(Project.org_id == org.id)
        )
        project_count = project_count_result.scalar_one()

        items.append(
            OrganizationListItem(
                id=org.id,
                name=org.name,
                is_active=org.is_active,
                created_at=org.created_at,
                user_count=user_count,
                project_count=project_count,
            )
        )

    return OrganizationListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get organization details",
    description="Get detailed information about an organization (ADMIN only)",
)
async def get_organization(
    org_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> OrganizationDetailResponse:
    """
    Get detailed organization information.

    WHAT: Returns full organization details with metrics.

    WHY: Admins need to view organization health and usage.

    Args:
        org_id: Organization ID
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Organization details with metrics

    Raises:
        ResourceNotFoundError: If organization not found
    """
    from app.models.project import Project
    from app.models.ticket import Ticket
    from app.models.invoice import Invoice

    org = await db.get(Organization, org_id)
    if not org:
        raise ResourceNotFoundError(
            message=f"Organization with id {org_id} not found",
            resource_type="Organization",
            resource_id=org_id,
        )

    # Count users
    user_count_result = await db.execute(
        select(func.count(User.id)).where(User.org_id == org_id)
    )
    user_count = user_count_result.scalar_one()

    # Count projects
    project_count_result = await db.execute(
        select(func.count(Project.id)).where(Project.org_id == org_id)
    )
    project_count = project_count_result.scalar_one()

    # Count tickets
    ticket_count_result = await db.execute(
        select(func.count(Ticket.id)).where(Ticket.org_id == org_id)
    )
    ticket_count = ticket_count_result.scalar_one()

    # Calculate total revenue from paid invoices
    revenue_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount_paid), 0.0)).where(
            Invoice.org_id == org_id,
            Invoice.status == "paid",
        )
    )
    total_revenue = float(revenue_result.scalar_one() or 0.0)

    return OrganizationDetailResponse(
        id=org.id,
        name=org.name,
        is_active=org.is_active,
        created_at=org.created_at,
        updated_at=org.updated_at,
        user_count=user_count,
        project_count=project_count,
        ticket_count=ticket_count,
        total_revenue=total_revenue,
    )


@router.put(
    "/organizations/{org_id}",
    response_model=OrganizationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update organization",
    description="Update organization details (ADMIN only)",
)
async def update_organization(
    org_id: int,
    data: OrganizationUpdateRequest,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> OrganizationDetailResponse:
    """
    Update organization details.

    WHAT: Updates organization name or active status.

    WHY: Admins need to manage organization settings.

    Args:
        org_id: Organization ID
        data: Update data
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Updated organization details

    Raises:
        ResourceNotFoundError: If organization not found
    """
    org = await db.get(Organization, org_id)
    if not org:
        raise ResourceNotFoundError(
            message=f"Organization with id {org_id} not found",
            resource_type="Organization",
            resource_id=org_id,
        )

    # Track changes for audit
    changes = {}

    if data.name is not None and data.name != org.name:
        changes["name"] = {"old": org.name, "new": data.name}
        org.name = data.name

    if data.is_active is not None and data.is_active != org.is_active:
        changes["is_active"] = {"old": org.is_active, "new": data.is_active}
        org.is_active = data.is_active

    if changes:
        org.updated_at = datetime.utcnow()
        await db.flush()

        # Audit log
        audit_service = AuditService(db)
        await audit_service.log_update(
            resource_type="organization",
            resource_id=org_id,
            actor_user_id=current_user.id,
            org_id=org_id,
            changes=changes,
        )

    # Return full details
    return await get_organization(org_id, current_user, db)


@router.post(
    "/organizations/{org_id}/suspend",
    status_code=status.HTTP_200_OK,
    summary="Suspend organization",
    description="Suspend an organization (ADMIN only)",
)
async def suspend_organization(
    org_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Suspend an organization.

    WHAT: Deactivates organization and all its users.

    WHY: Admins need to suspend problematic or non-paying organizations.

    Args:
        org_id: Organization ID
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Success message

    Raises:
        ResourceNotFoundError: If organization not found
    """
    org = await db.get(Organization, org_id)
    if not org:
        raise ResourceNotFoundError(
            message=f"Organization with id {org_id} not found",
            resource_type="Organization",
            resource_id=org_id,
        )

    org.is_active = False
    org.updated_at = datetime.utcnow()

    # Deactivate all users in the organization
    users_result = await db.execute(
        select(User).where(User.org_id == org_id, User.is_active == True)
    )
    users = users_result.scalars().all()
    for user in users:
        user.is_active = False
        user.updated_at = datetime.utcnow()

    await db.flush()

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="organization",
        resource_id=org_id,
        actor_user_id=current_user.id,
        org_id=org_id,
        changes={
            "is_active": {"old": True, "new": False},
            "suspended_users": len(users),
        },
    )

    return {
        "message": "Organization suspended",
        "org_id": org_id,
        "users_affected": len(users),
    }


@router.post(
    "/organizations/{org_id}/activate",
    status_code=status.HTTP_200_OK,
    summary="Activate organization",
    description="Reactivate a suspended organization (ADMIN only)",
)
async def activate_organization(
    org_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Reactivate an organization.

    WHAT: Reactivates organization (users must be individually reactivated).

    WHY: Admins need to restore previously suspended organizations.

    Args:
        org_id: Organization ID
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Success message

    Raises:
        ResourceNotFoundError: If organization not found
    """
    org = await db.get(Organization, org_id)
    if not org:
        raise ResourceNotFoundError(
            message=f"Organization with id {org_id} not found",
            resource_type="Organization",
            resource_id=org_id,
        )

    org.is_active = True
    org.updated_at = datetime.utcnow()
    await db.flush()

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="organization",
        resource_id=org_id,
        actor_user_id=current_user.id,
        org_id=org_id,
        changes={"is_active": {"old": False, "new": True}},
    )

    return {"message": "Organization activated", "org_id": org_id}


# ============================================================================
# Audit Log Viewer Endpoints (ADMIN-005)
# ============================================================================


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List audit logs",
    description="Get paginated list of audit logs with filtering (ADMIN only)",
)
async def list_audit_logs(
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum items to return"),
    user_id: Optional[int] = Query(default=None, description="Filter by actor user"),
    org_id: Optional[int] = Query(default=None, description="Filter by organization"),
    action: Optional[str] = Query(default=None, description="Filter by action type"),
    resource_type: Optional[str] = Query(default=None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(default=None, description="Filter from date"),
    end_date: Optional[datetime] = Query(default=None, description="Filter to date"),
    ip_address: Optional[str] = Query(default=None, description="Filter by IP address"),
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """
    List audit logs with filtering.

    WHAT: Returns paginated audit logs with various filters.

    WHY: Security compliance requires audit log access for investigations.

    Args:
        skip: Pagination offset
        limit: Page size
        user_id: Filter by actor
        org_id: Filter by organization
        action: Filter by action type
        resource_type: Filter by resource
        start_date: Filter from date
        end_date: Filter to date
        ip_address: Filter by IP
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Paginated audit log list
    """
    # Build query
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if user_id is not None:
        query = query.where(AuditLog.actor_user_id == user_id)
        count_query = count_query.where(AuditLog.actor_user_id == user_id)

    if org_id is not None:
        query = query.where(AuditLog.org_id == org_id)
        count_query = count_query.where(AuditLog.org_id == org_id)

    if action is not None:
        try:
            action_enum = AuditAction(action)
            query = query.where(AuditLog.action == action_enum)
            count_query = count_query.where(AuditLog.action == action_enum)
        except ValueError:
            pass  # Invalid action, ignore filter

    if resource_type is not None:
        query = query.where(AuditLog.resource_type == resource_type)
        count_query = count_query.where(AuditLog.resource_type == resource_type)

    if start_date is not None:
        query = query.where(AuditLog.created_at >= start_date)
        count_query = count_query.where(AuditLog.created_at >= start_date)

    if end_date is not None:
        query = query.where(AuditLog.created_at <= end_date)
        count_query = count_query.where(AuditLog.created_at <= end_date)

    if ip_address is not None:
        query = query.where(AuditLog.ip_address == ip_address)
        count_query = count_query.where(AuditLog.ip_address == ip_address)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results
    query = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    # Build response items
    items = []
    for log in logs:
        # Get actor email
        actor_email = None
        if log.actor_user_id:
            actor = await db.get(User, log.actor_user_id)
            actor_email = actor.email if actor else None

        # Get org name
        org_name = None
        if log.org_id:
            org = await db.get(Organization, log.org_id)
            org_name = org.name if org else None

        items.append(
            AuditLogItem(
                id=log.id,
                actor_user_id=log.actor_user_id,
                actor_email=actor_email,
                action=log.action.value,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                org_id=log.org_id,
                org_name=org_name,
                changes=log.changes,
                extra_data=log.extra_data,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                created_at=log.created_at,
            )
        )

    return AuditLogListResponse(items=items, total=total, skip=skip, limit=limit)
