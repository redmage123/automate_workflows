"""
Project management API endpoints.

WHAT: RESTful API for project CRUD operations.

WHY: Projects are the central business entity that:
1. Connect clients to automation work
2. Track project lifecycle from draft to completion
3. Enable resource allocation and time tracking
4. Link to proposals, invoices, and workflows

HOW: FastAPI router with:
- Org-scoped queries (multi-tenancy)
- RBAC (ADMIN can create/modify, all auth users can view)
- Pagination for list endpoints
- Audit logging for mutations
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.core.exceptions import (
    ResourceNotFoundError,
    OrganizationAccessDenied,
    ValidationError,
)
from app.db.session import get_db
from app.dao.project import ProjectDAO
from app.models.user import User
from app.models.project import ProjectStatus as ProjectStatusModel, ProjectPriority as ProjectPriorityModel
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectStatusUpdate,
    ProjectResponse,
    ProjectListResponse,
    ProjectStats,
    ProjectStatus,
    ProjectPriority,
)
from app.services.audit import AuditService


router = APIRouter(prefix="/projects", tags=["projects"])


def _project_to_response(project) -> ProjectResponse:
    """
    Convert Project model to ProjectResponse schema.

    WHY: Centralized conversion ensures consistent response format
    and proper handling of computed properties.

    Args:
        project: Project model instance

    Returns:
        ProjectResponse schema instance
    """
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=ProjectStatus(project.status.value),
        priority=ProjectPriority(project.priority.value),
        org_id=project.org_id,
        estimated_hours=project.estimated_hours,
        actual_hours=project.actual_hours,
        start_date=project.start_date,
        due_date=project.due_date,
        completed_at=project.completed_at,
        created_at=project.created_at,
        updated_at=project.updated_at,
        is_active=project.is_active,
        is_overdue=project.is_overdue,
        hours_remaining=project.hours_remaining,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new project for the current organization (ADMIN only)",
)
async def create_project(
    data: ProjectCreate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Create a new project.

    WHAT: Creates a project in DRAFT status for the user's organization.

    WHY: ADMINs create projects to:
    - Start tracking new client work
    - Create a container for proposals
    - Plan and allocate resources

    RBAC: Requires ADMIN role.

    Args:
        data: Project creation data
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Created project data

    Raises:
        ValidationError (400): If data validation fails
    """
    project_dao = ProjectDAO(db)

    # Create project with user's org_id
    project = await project_dao.create(
        name=data.name,
        description=data.description,
        priority=ProjectPriorityModel(data.priority.value),
        org_id=current_user.org_id,
        estimated_hours=data.estimated_hours,
        start_date=data.start_date,
        due_date=data.due_date,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="project",
        resource_id=project.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"name": data.name, "priority": data.priority.value},
    )

    return _project_to_response(project)


@router.get(
    "",
    response_model=ProjectListResponse,
    status_code=status.HTTP_200_OK,
    summary="List projects",
    description="Get paginated list of projects for the current organization",
)
async def list_projects(
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum items to return"),
    status_filter: Optional[ProjectStatus] = Query(
        default=None,
        alias="status",
        description="Filter by project status",
    ),
    priority_filter: Optional[ProjectPriority] = Query(
        default=None,
        alias="priority",
        description="Filter by project priority",
    ),
    active_only: bool = Query(
        default=False,
        description="Only return active projects (not completed/cancelled)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """
    List projects for current organization.

    WHAT: Returns paginated list of projects with optional filters.

    WHY: Users need to:
    - Browse all projects in their organization
    - Filter by status for dashboard views
    - Filter by priority for resource planning

    Args:
        skip: Pagination offset
        limit: Maximum items per page
        status_filter: Optional status filter
        priority_filter: Optional priority filter
        active_only: If True, exclude completed/cancelled
        current_user: Current authenticated user
        db: Database session

    Returns:
        Paginated list of projects
    """
    project_dao = ProjectDAO(db)
    org_id = current_user.org_id

    # Get projects based on filters
    if active_only:
        projects = await project_dao.get_active_projects(org_id, skip=skip, limit=limit)
        total = await project_dao.count_active(org_id)
    elif status_filter:
        status_enum = ProjectStatusModel(status_filter.value)
        projects = await project_dao.get_by_status(org_id, status_enum, skip=skip, limit=limit)
        # Count for this specific status
        status_counts = await project_dao.count_by_status(org_id)
        total = status_counts.get(status_filter.value, 0)
    elif priority_filter:
        priority_enum = ProjectPriorityModel(priority_filter.value)
        projects = await project_dao.get_by_priority(org_id, priority_enum, skip=skip, limit=limit)
        # For priority filter, we need total count (not built into DAO)
        all_projects = await project_dao.get_by_org(org_id)
        total = len([p for p in all_projects if p.priority == priority_enum])
    else:
        projects = await project_dao.get_by_org(org_id, skip=skip, limit=limit)
        total = await project_dao.count(org_id=org_id)

    return ProjectListResponse(
        items=[_project_to_response(p) for p in projects],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/stats",
    response_model=ProjectStats,
    status_code=status.HTTP_200_OK,
    summary="Get project statistics",
    description="Get aggregated project statistics for the current organization",
)
async def get_project_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectStats:
    """
    Get project statistics.

    WHAT: Returns aggregated metrics for dashboard widgets.

    WHY: Quick overview without fetching all project data:
    - Total projects
    - Active vs completed counts
    - Status breakdown
    - Overdue count

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Project statistics
    """
    project_dao = ProjectDAO(db)
    org_id = current_user.org_id

    # Get counts
    by_status = await project_dao.count_by_status(org_id)
    active = await project_dao.count_active(org_id)
    overdue = len(await project_dao.get_overdue_projects(org_id, limit=1000))
    total = sum(by_status.values())

    return ProjectStats(
        total=total,
        active=active,
        by_status=by_status,
        overdue=overdue,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project",
    description="Get project details by ID (org-scoped)",
)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Get project by ID.

    WHAT: Returns project details for a specific project.

    WHY: Users need to view project details for:
    - Project management
    - Status tracking
    - Proposal creation

    Security: Enforces org-scoping to prevent cross-org access.

    Args:
        project_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Project data

    Raises:
        ResourceNotFoundError (404): If project not found in user's org
    """
    project_dao = ProjectDAO(db)

    # Get project with org-scoping
    project = await project_dao.get_by_id_and_org(project_id, current_user.org_id)

    if not project:
        raise ResourceNotFoundError(
            message=f"Project with id {project_id} not found",
            resource_type="Project",
            resource_id=project_id,
        )

    return _project_to_response(project)


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project",
    description="Update project details (ADMIN only)",
)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Update project details.

    WHAT: Updates project fields (not status - use PATCH /status).

    WHY: ADMINs update projects to:
    - Correct project information
    - Update time estimates
    - Adjust priority and dates

    RBAC: Requires ADMIN role.
    Security: Enforces org-scoping.

    Args:
        project_id: Project ID
        data: Update data (partial update)
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated project data

    Raises:
        ResourceNotFoundError (404): If project not found
    """
    project_dao = ProjectDAO(db)

    # Verify project exists in user's org
    project = await project_dao.get_by_id_and_org(project_id, current_user.org_id)
    if not project:
        raise ResourceNotFoundError(
            message=f"Project with id {project_id} not found",
            resource_type="Project",
            resource_id=project_id,
        )

    # Build update dict from non-None fields
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description
    if data.priority is not None:
        update_data["priority"] = ProjectPriorityModel(data.priority.value)
    if data.estimated_hours is not None:
        update_data["estimated_hours"] = data.estimated_hours
    if data.actual_hours is not None:
        update_data["actual_hours"] = data.actual_hours
    if data.start_date is not None:
        update_data["start_date"] = data.start_date
    if data.due_date is not None:
        update_data["due_date"] = data.due_date

    # Update project
    if update_data:
        project = await project_dao.update(project_id, **update_data)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="project",
        resource_id=project_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes=update_data,
    )

    return _project_to_response(project)


@router.patch(
    "/{project_id}/status",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project status",
    description="Update project status with workflow tracking (ADMIN only)",
)
async def update_project_status(
    project_id: int,
    data: ProjectStatusUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Update project status.

    WHAT: Changes project status with proper timestamp handling.

    WHY: Separate endpoint for status because:
    - Status changes have business implications
    - COMPLETED status sets completed_at timestamp
    - Enables audit logging of status transitions
    - Future: Status transition validation

    RBAC: Requires ADMIN role.
    Security: Enforces org-scoping.

    Args:
        project_id: Project ID
        data: Status update data
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated project data

    Raises:
        ResourceNotFoundError (404): If project not found
    """
    project_dao = ProjectDAO(db)

    # Update status (DAO handles completed_at timestamp)
    status_enum = ProjectStatusModel(data.status.value)
    project = await project_dao.update_status(
        project_id,
        current_user.org_id,
        status_enum,
    )

    if not project:
        raise ResourceNotFoundError(
            message=f"Project with id {project_id} not found",
            resource_type="Project",
            resource_id=project_id,
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="project",
        resource_id=project_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        changes={"status": data.status.value},
    )

    return _project_to_response(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Delete a project (ADMIN only, cascades to proposals)",
)
async def delete_project(
    project_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a project.

    WHAT: Permanently deletes a project and all related data.

    WHY: ADMINs may need to delete:
    - Cancelled projects
    - Test/duplicate projects
    - Projects created in error

    CAUTION: This cascades to proposals. Consider soft delete for production.

    RBAC: Requires ADMIN role.
    Security: Enforces org-scoping.

    Args:
        project_id: Project ID
        current_user: Current authenticated admin user
        db: Database session

    Raises:
        ResourceNotFoundError (404): If project not found
    """
    project_dao = ProjectDAO(db)

    # Verify project exists in user's org
    project = await project_dao.get_by_id_and_org(project_id, current_user.org_id)
    if not project:
        raise ResourceNotFoundError(
            message=f"Project with id {project_id} not found",
            resource_type="Project",
            resource_id=project_id,
        )

    # Audit log BEFORE deletion
    audit_service = AuditService(db)
    await audit_service.log_delete(
        resource_type="project",
        resource_id=project_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"name": project.name, "status": project.status.value},
    )

    # Delete project (cascades to proposals)
    await project_dao.delete(project_id)


@router.get(
    "/{project_id}/proposals",
    response_model=list,
    status_code=status.HTTP_200_OK,
    summary="Get project proposals",
    description="Get all proposals for a project",
)
async def get_project_proposals(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get proposals for a project.

    WHAT: Returns all proposals associated with a project.

    WHY: Users need to see:
    - All proposal versions for a project
    - Approval history
    - Current active proposal

    Args:
        project_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of proposals for the project

    Raises:
        ResourceNotFoundError (404): If project not found
    """
    project_dao = ProjectDAO(db)

    # Get project with proposals eagerly loaded
    project = await project_dao.get_with_proposals(project_id, current_user.org_id)

    if not project:
        raise ResourceNotFoundError(
            message=f"Project with id {project_id} not found",
            resource_type="Project",
            resource_id=project_id,
        )

    # Return proposals (will be converted by Proposal router's response model)
    # For now, return raw data - this endpoint should ideally return ProposalResponse list
    return [
        {
            "id": p.id,
            "title": p.title,
            "status": p.status.value,
            "version": p.version,
            "total": float(p.total),
            "created_at": p.created_at.isoformat(),
        }
        for p in project.proposals
    ]


@router.get(
    "/search/{query}",
    response_model=ProjectListResponse,
    status_code=status.HTTP_200_OK,
    summary="Search projects",
    description="Search projects by name or description",
)
async def search_projects(
    query: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """
    Search projects by name or description.

    WHAT: Full-text search across project name and description.

    WHY: Users need to quickly find projects without browsing lists.

    Args:
        query: Search query string
        skip: Pagination offset
        limit: Maximum items per page
        current_user: Current authenticated user
        db: Database session

    Returns:
        Matching projects
    """
    if len(query) < 2:
        raise ValidationError(
            message="Search query must be at least 2 characters",
            field="query",
        )

    project_dao = ProjectDAO(db)

    projects = await project_dao.search_projects(
        current_user.org_id,
        query,
        skip=skip,
        limit=limit,
    )

    return ProjectListResponse(
        items=[_project_to_response(p) for p in projects],
        total=len(projects),  # Approximate for search
        skip=skip,
        limit=limit,
    )
