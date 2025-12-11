"""
Workflow automation API endpoints.

WHAT: RESTful API for n8n environments, workflow templates, and workflow instances.

WHY: Provides workflow automation management:
1. N8n environment configuration (ADMIN only)
2. Workflow template library (public + org-specific)
3. Workflow instance lifecycle management
4. Execution triggering and monitoring

HOW: FastAPI router with:
- Org-scoped queries (multi-tenancy)
- RBAC (ADMIN for management, all auth users for viewing)
- Pagination for list endpoints
- Audit logging for mutations

Security Considerations:
- API keys encrypted at rest, never returned in responses
- Org scoping enforced on all queries
- SSRF prevention in n8n client
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    N8nError,
)
from app.db.session import get_db
from app.dao.n8n_environment import N8nEnvironmentDAO
from app.dao.workflow_template import WorkflowTemplateDAO
from app.dao.workflow_instance import WorkflowInstanceDAO
from app.dao.execution_log import ExecutionLogDAO
from app.models.user import User
from app.models.workflow import (
    WorkflowStatus as WorkflowStatusModel,
    ExecutionStatus as ExecutionStatusModel,
)
from app.schemas.workflow import (
    # N8n Environment
    N8nEnvironmentCreate,
    N8nEnvironmentUpdate,
    N8nEnvironmentResponse,
    N8nEnvironmentListResponse,
    N8nHealthCheckResponse,
    # Workflow Template
    WorkflowTemplateCreate,
    WorkflowTemplateUpdate,
    WorkflowTemplateResponse,
    WorkflowTemplateListResponse,
    # Workflow Instance
    WorkflowInstanceCreate,
    WorkflowInstanceUpdate,
    WorkflowStatusUpdate,
    WorkflowInstanceResponse,
    WorkflowInstanceListResponse,
    WorkflowStats,
    WorkflowStatus,
    # Execution
    ExecutionTriggerRequest,
    ExecutionLogResponse,
    ExecutionLogListResponse,
    ExecutionStats,
    ExecutionStatus,
)
from app.services.audit import AuditService
from app.services.n8n_client import create_n8n_client


router = APIRouter(prefix="/workflows", tags=["workflows"])


# ============================================================================
# Helper Functions
# ============================================================================


def _env_to_response(env) -> N8nEnvironmentResponse:
    """Convert N8nEnvironment model to response schema."""
    return N8nEnvironmentResponse(
        id=env.id,
        org_id=env.org_id,
        name=env.name,
        base_url=env.base_url,
        is_active=env.is_active,
        webhook_url=env.webhook_url,
        created_at=env.created_at,
        updated_at=env.updated_at,
    )


def _template_to_response(template) -> WorkflowTemplateResponse:
    """Convert WorkflowTemplate model to response schema."""
    return WorkflowTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        n8n_template_id=template.n8n_template_id,
        default_parameters=template.default_parameters,
        is_public=template.is_public,
        created_by_org_id=template.created_by_org_id,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _instance_to_response(instance) -> WorkflowInstanceResponse:
    """Convert WorkflowInstance model to response schema."""
    return WorkflowInstanceResponse(
        id=instance.id,
        org_id=instance.org_id,
        name=instance.name,
        status=WorkflowStatus(instance.status.value),
        template_id=instance.template_id,
        project_id=instance.project_id,
        n8n_environment_id=instance.n8n_environment_id,
        n8n_workflow_id=instance.n8n_workflow_id,
        parameters=instance.parameters,
        last_execution_at=instance.last_execution_at,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
        is_active=instance.is_active,
        can_execute=instance.can_execute,
    )


def _log_to_response(log) -> ExecutionLogResponse:
    """Convert ExecutionLog model to response schema."""
    return ExecutionLogResponse(
        id=log.id,
        workflow_instance_id=log.workflow_instance_id,
        n8n_execution_id=log.n8n_execution_id,
        status=ExecutionStatus(log.status.value),
        started_at=log.started_at,
        finished_at=log.finished_at,
        input_data=log.input_data,
        output_data=log.output_data,
        error_message=log.error_message,
        duration_seconds=log.duration_seconds,
        is_complete=log.is_complete,
    )


# ============================================================================
# N8n Environment Endpoints
# ============================================================================


@router.post(
    "/environments",
    response_model=N8nEnvironmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create n8n environment",
    description="Create a new n8n environment for the organization (ADMIN only)",
)
async def create_environment(
    data: N8nEnvironmentCreate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> N8nEnvironmentResponse:
    """
    Create a new n8n environment.

    WHAT: Configures an n8n instance for the organization.

    WHY: Organizations may have multiple n8n environments:
    - Production vs staging
    - Different n8n versions
    - Isolated workflows

    RBAC: Requires ADMIN role.
    Security: API key is encrypted before storage.
    """
    env_dao = N8nEnvironmentDAO(db)

    env = await env_dao.create_environment(
        org_id=current_user.org_id,
        name=data.name,
        base_url=data.base_url,
        api_key=data.api_key,
        webhook_url=data.webhook_url,
        is_active=data.is_active,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="n8n_environment",
        resource_id=env.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"name": data.name, "base_url": data.base_url},
    )

    return _env_to_response(env)


@router.get(
    "/environments",
    response_model=N8nEnvironmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List n8n environments",
    description="Get list of n8n environments for the organization",
)
async def list_environments(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum items to return"),
    active_only: bool = Query(False, description="Only return active environments"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> N8nEnvironmentListResponse:
    """List n8n environments for the organization."""
    env_dao = N8nEnvironmentDAO(db)

    if active_only:
        environments = await env_dao.get_active_environments(
            org_id=current_user.org_id,
            skip=skip,
            limit=limit,
        )
    else:
        environments = await env_dao.get_by_org(
            org_id=current_user.org_id,
            skip=skip,
            limit=limit,
        )

    total = await env_dao.count_by_org(current_user.org_id)

    return N8nEnvironmentListResponse(
        items=[_env_to_response(e) for e in environments],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/environments/{environment_id}",
    response_model=N8nEnvironmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get n8n environment",
    description="Get details of a specific n8n environment",
)
async def get_environment(
    environment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> N8nEnvironmentResponse:
    """Get n8n environment by ID."""
    env_dao = N8nEnvironmentDAO(db)
    env = await env_dao.get_by_id_and_org(environment_id, current_user.org_id)

    if not env:
        raise ResourceNotFoundError(
            message="N8n environment not found",
            resource_type="n8n_environment",
            resource_id=environment_id,
        )

    return _env_to_response(env)


@router.patch(
    "/environments/{environment_id}",
    response_model=N8nEnvironmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update n8n environment",
    description="Update n8n environment configuration (ADMIN only)",
)
async def update_environment(
    environment_id: int,
    data: N8nEnvironmentUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> N8nEnvironmentResponse:
    """Update n8n environment."""
    env_dao = N8nEnvironmentDAO(db)

    env = await env_dao.update_environment(
        environment_id=environment_id,
        org_id=current_user.org_id,
        name=data.name,
        base_url=data.base_url,
        api_key=data.api_key,
        webhook_url=data.webhook_url,
        is_active=data.is_active,
    )

    if not env:
        raise ResourceNotFoundError(
            message="N8n environment not found",
            resource_type="n8n_environment",
            resource_id=environment_id,
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="n8n_environment",
        resource_id=env.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"updated_fields": [k for k, v in data.model_dump().items() if v is not None]},
    )

    return _env_to_response(env)


@router.delete(
    "/environments/{environment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete n8n environment",
    description="Delete n8n environment (ADMIN only)",
)
async def delete_environment(
    environment_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete n8n environment."""
    env_dao = N8nEnvironmentDAO(db)

    # Verify ownership
    env = await env_dao.get_by_id_and_org(environment_id, current_user.org_id)
    if not env:
        raise ResourceNotFoundError(
            message="N8n environment not found",
            resource_type="n8n_environment",
            resource_id=environment_id,
        )

    # Audit log before delete
    audit_service = AuditService(db)
    await audit_service.log_delete(
        resource_type="n8n_environment",
        resource_id=environment_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"name": env.name},
    )

    await env_dao.delete(environment_id)


@router.get(
    "/environments/{environment_id}/health",
    response_model=N8nHealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check n8n environment health",
    description="Test connectivity to n8n instance",
)
async def check_environment_health(
    environment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> N8nHealthCheckResponse:
    """Check if n8n instance is accessible."""
    env_dao = N8nEnvironmentDAO(db)
    env = await env_dao.get_by_id_and_org(environment_id, current_user.org_id)

    if not env:
        raise ResourceNotFoundError(
            message="N8n environment not found",
            resource_type="n8n_environment",
            resource_id=environment_id,
        )

    # Create client and test connectivity
    client = create_n8n_client(
        base_url=env.base_url,
        api_key_encrypted=env.api_key_encrypted,
    )
    is_healthy = await client.health_check()

    return N8nHealthCheckResponse(
        environment_id=environment_id,
        is_healthy=is_healthy,
        checked_at=datetime.utcnow(),
    )


# ============================================================================
# Workflow Template Endpoints
# ============================================================================


@router.post(
    "/templates",
    response_model=WorkflowTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workflow template",
    description="Create a new workflow template (ADMIN only)",
)
async def create_template(
    data: WorkflowTemplateCreate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> WorkflowTemplateResponse:
    """Create a new workflow template."""
    template_dao = WorkflowTemplateDAO(db)

    template = await template_dao.create_template(
        name=data.name,
        description=data.description,
        category=data.category,
        n8n_template_id=data.n8n_template_id,
        default_parameters=data.default_parameters,
        is_public=data.is_public,
        created_by_org_id=current_user.org_id,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="workflow_template",
        resource_id=template.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"name": data.name, "is_public": data.is_public},
    )

    return _template_to_response(template)


@router.get(
    "/templates",
    response_model=WorkflowTemplateListResponse,
    status_code=status.HTTP_200_OK,
    summary="List workflow templates",
    description="Get list of available workflow templates",
)
async def list_templates(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum items to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowTemplateListResponse:
    """List available workflow templates (public + org's private)."""
    template_dao = WorkflowTemplateDAO(db)

    templates = await template_dao.get_available_templates(
        org_id=current_user.org_id,
        category=category,
        skip=skip,
        limit=limit,
    )

    categories = await template_dao.get_categories(
        include_private_for_org=current_user.org_id
    )

    return WorkflowTemplateListResponse(
        items=[_template_to_response(t) for t in templates],
        total=len(templates),  # TODO: Add count method
        skip=skip,
        limit=limit,
        categories=categories,
    )


@router.get(
    "/templates/{template_id}",
    response_model=WorkflowTemplateResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workflow template",
    description="Get details of a specific workflow template",
)
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowTemplateResponse:
    """Get workflow template by ID."""
    template_dao = WorkflowTemplateDAO(db)
    template = await template_dao.get_by_id(template_id)

    if not template:
        raise ResourceNotFoundError(
            message="Workflow template not found",
            resource_type="workflow_template",
            resource_id=template_id,
        )

    # Check access: must be public or owned by org
    if not template.is_public and template.created_by_org_id != current_user.org_id:
        raise ResourceNotFoundError(
            message="Workflow template not found",
            resource_type="workflow_template",
            resource_id=template_id,
        )

    return _template_to_response(template)


@router.patch(
    "/templates/{template_id}",
    response_model=WorkflowTemplateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update workflow template",
    description="Update workflow template (owner org ADMIN only)",
)
async def update_template(
    template_id: int,
    data: WorkflowTemplateUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> WorkflowTemplateResponse:
    """Update workflow template."""
    template_dao = WorkflowTemplateDAO(db)

    # Verify ownership
    if not await template_dao.can_org_modify(template_id, current_user.org_id):
        raise ResourceNotFoundError(
            message="Workflow template not found or not owned by your organization",
            resource_type="workflow_template",
            resource_id=template_id,
        )

    template = await template_dao.update_template(
        template_id=template_id,
        name=data.name,
        description=data.description,
        category=data.category,
        n8n_template_id=data.n8n_template_id,
        default_parameters=data.default_parameters,
        is_public=data.is_public,
    )

    if not template:
        raise ResourceNotFoundError(
            message="Workflow template not found",
            resource_type="workflow_template",
            resource_id=template_id,
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="workflow_template",
        resource_id=template.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
    )

    return _template_to_response(template)


# ============================================================================
# Workflow Instance Endpoints
# ============================================================================


@router.post(
    "/instances",
    response_model=WorkflowInstanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workflow instance",
    description="Create a new workflow instance (ADMIN only)",
)
async def create_instance(
    data: WorkflowInstanceCreate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> WorkflowInstanceResponse:
    """Create a new workflow instance."""
    instance_dao = WorkflowInstanceDAO(db)

    instance = await instance_dao.create_instance(
        org_id=current_user.org_id,
        name=data.name,
        template_id=data.template_id,
        project_id=data.project_id,
        n8n_environment_id=data.n8n_environment_id,
        parameters=data.parameters,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="workflow_instance",
        resource_id=instance.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"name": data.name, "template_id": data.template_id},
    )

    return _instance_to_response(instance)


@router.get(
    "/instances",
    response_model=WorkflowInstanceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List workflow instances",
    description="Get list of workflow instances for the organization",
)
async def list_instances(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum items to return"),
    status_filter: Optional[WorkflowStatus] = Query(
        None, alias="status", description="Filter by status"
    ),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowInstanceListResponse:
    """List workflow instances for the organization."""
    instance_dao = WorkflowInstanceDAO(db)

    if status_filter:
        instances = await instance_dao.get_by_status(
            org_id=current_user.org_id,
            status=WorkflowStatusModel(status_filter.value),
            skip=skip,
            limit=limit,
        )
    elif project_id:
        instances = await instance_dao.get_by_project(
            org_id=current_user.org_id,
            project_id=project_id,
            skip=skip,
            limit=limit,
        )
    else:
        instances = await instance_dao.get_non_deleted(
            org_id=current_user.org_id,
            skip=skip,
            limit=limit,
        )

    return WorkflowInstanceListResponse(
        items=[_instance_to_response(i) for i in instances],
        total=len(instances),  # TODO: Add count method
        skip=skip,
        limit=limit,
    )


@router.get(
    "/instances/{instance_id}",
    response_model=WorkflowInstanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workflow instance",
    description="Get details of a specific workflow instance",
)
async def get_instance(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowInstanceResponse:
    """Get workflow instance by ID."""
    instance_dao = WorkflowInstanceDAO(db)
    instance = await instance_dao.get_by_id_and_org(instance_id, current_user.org_id)

    if not instance:
        raise ResourceNotFoundError(
            message="Workflow instance not found",
            resource_type="workflow_instance",
            resource_id=instance_id,
        )

    return _instance_to_response(instance)


@router.patch(
    "/instances/{instance_id}",
    response_model=WorkflowInstanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update workflow instance",
    description="Update workflow instance (ADMIN only)",
)
async def update_instance(
    instance_id: int,
    data: WorkflowInstanceUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> WorkflowInstanceResponse:
    """Update workflow instance."""
    instance_dao = WorkflowInstanceDAO(db)

    instance = await instance_dao.get_by_id_and_org(instance_id, current_user.org_id)
    if not instance:
        raise ResourceNotFoundError(
            message="Workflow instance not found",
            resource_type="workflow_instance",
            resource_id=instance_id,
        )

    # Update fields
    if data.name is not None:
        instance.name = data.name
    if data.project_id is not None:
        instance.project_id = data.project_id
    if data.n8n_environment_id is not None:
        instance.n8n_environment_id = data.n8n_environment_id
    if data.parameters is not None:
        instance.parameters = data.parameters

    instance.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(instance)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="workflow_instance",
        resource_id=instance.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
    )

    return _instance_to_response(instance)


@router.post(
    "/instances/{instance_id}/status",
    response_model=WorkflowInstanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update workflow status",
    description="Change workflow instance status (ADMIN only)",
)
async def update_instance_status(
    instance_id: int,
    data: WorkflowStatusUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> WorkflowInstanceResponse:
    """Update workflow instance status."""
    instance_dao = WorkflowInstanceDAO(db)

    instance = await instance_dao.update_status(
        instance_id=instance_id,
        org_id=current_user.org_id,
        new_status=WorkflowStatusModel(data.status.value),
    )

    if not instance:
        raise ResourceNotFoundError(
            message="Workflow instance not found",
            resource_type="workflow_instance",
            resource_id=instance_id,
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="workflow_instance",
        resource_id=instance.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"new_status": data.status.value},
    )

    return _instance_to_response(instance)


@router.delete(
    "/instances/{instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workflow instance",
    description="Soft-delete workflow instance (ADMIN only)",
)
async def delete_instance(
    instance_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete workflow instance."""
    instance_dao = WorkflowInstanceDAO(db)

    instance = await instance_dao.soft_delete(instance_id, current_user.org_id)
    if not instance:
        raise ResourceNotFoundError(
            message="Workflow instance not found",
            resource_type="workflow_instance",
            resource_id=instance_id,
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_delete(
        resource_type="workflow_instance",
        resource_id=instance_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
    )


@router.get(
    "/instances/{instance_id}/stats",
    response_model=WorkflowStats,
    status_code=status.HTTP_200_OK,
    summary="Get workflow statistics",
    description="Get execution statistics for a workflow instance",
)
async def get_instance_stats(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowStats:
    """Get workflow instance statistics."""
    instance_dao = WorkflowInstanceDAO(db)
    log_dao = ExecutionLogDAO(db)

    instance = await instance_dao.get_by_id_and_org(instance_id, current_user.org_id)
    if not instance:
        raise ResourceNotFoundError(
            message="Workflow instance not found",
            resource_type="workflow_instance",
            resource_id=instance_id,
        )

    # Get execution stats
    counts = await log_dao.count_by_status(instance_id)
    success_rate = await log_dao.get_success_rate(instance_id)
    total = await log_dao.count_total(instance_id)

    # Get org-wide stats
    org_counts = await instance_dao.count_by_status(current_user.org_id)
    active_count = await instance_dao.count_active(current_user.org_id)

    return WorkflowStats(
        total=sum(org_counts.values()),
        active=active_count,
        by_status=org_counts,
        total_executions=total,
        success_rate=success_rate,
    )


# ============================================================================
# Execution Log Endpoints
# ============================================================================


@router.post(
    "/instances/{instance_id}/execute",
    response_model=ExecutionLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger workflow execution",
    description="Trigger a workflow execution (ADMIN only)",
)
async def trigger_execution(
    instance_id: int,
    data: ExecutionTriggerRequest,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ExecutionLogResponse:
    """Trigger workflow execution."""
    instance_dao = WorkflowInstanceDAO(db)
    log_dao = ExecutionLogDAO(db)
    env_dao = N8nEnvironmentDAO(db)

    # Get instance
    instance = await instance_dao.get_by_id_and_org(instance_id, current_user.org_id)
    if not instance:
        raise ResourceNotFoundError(
            message="Workflow instance not found",
            resource_type="workflow_instance",
            resource_id=instance_id,
        )

    # Check if can execute
    if not instance.can_execute:
        raise ValidationError(
            message="Workflow cannot be executed. Check status and n8n deployment.",
            status=instance.status.value,
            n8n_workflow_id=instance.n8n_workflow_id,
        )

    # Get environment
    env = await env_dao.get_by_id_and_org(instance.n8n_environment_id, current_user.org_id)
    if not env or not env.is_active:
        raise ValidationError(
            message="N8n environment is not available",
            n8n_environment_id=instance.n8n_environment_id,
        )

    # Create execution log
    log = await log_dao.create_log(
        workflow_instance_id=instance_id,
        input_data=data.input_data,
    )

    # Trigger execution in n8n
    try:
        client = create_n8n_client(
            base_url=env.base_url,
            api_key_encrypted=env.api_key_encrypted,
        )
        result = await client.trigger_workflow(
            workflow_id=instance.n8n_workflow_id,
            input_data=data.input_data,
        )

        # Update log with n8n execution ID
        log.n8n_execution_id = result.get("executionId")
        await db.flush()
        await db.refresh(log)

        # Update last execution time
        await instance_dao.update_last_execution(instance_id, current_user.org_id)

    except N8nError as e:
        # Mark execution as failed
        await log_dao.complete_execution(
            log_id=log.id,
            status=ExecutionStatusModel.FAILED,
            error_message=str(e),
        )
        raise

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="execution_log",
        resource_id=log.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"workflow_instance_id": instance_id},
    )

    return _log_to_response(log)


@router.get(
    "/instances/{instance_id}/executions",
    response_model=ExecutionLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List workflow executions",
    description="Get execution history for a workflow instance",
)
async def list_executions(
    instance_id: int,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum items to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionLogListResponse:
    """List executions for a workflow instance."""
    instance_dao = WorkflowInstanceDAO(db)
    log_dao = ExecutionLogDAO(db)

    # Verify instance access
    instance = await instance_dao.get_by_id_and_org(instance_id, current_user.org_id)
    if not instance:
        raise ResourceNotFoundError(
            message="Workflow instance not found",
            resource_type="workflow_instance",
            resource_id=instance_id,
        )

    logs = await log_dao.get_by_instance(
        workflow_instance_id=instance_id,
        skip=skip,
        limit=limit,
    )

    total = await log_dao.count_total(instance_id)

    return ExecutionLogListResponse(
        items=[_log_to_response(l) for l in logs],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/instances/{instance_id}/executions/{execution_id}",
    response_model=ExecutionLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Get execution details",
    description="Get details of a specific execution",
)
async def get_execution(
    instance_id: int,
    execution_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionLogResponse:
    """Get execution details."""
    instance_dao = WorkflowInstanceDAO(db)
    log_dao = ExecutionLogDAO(db)

    # Verify instance access
    instance = await instance_dao.get_by_id_and_org(instance_id, current_user.org_id)
    if not instance:
        raise ResourceNotFoundError(
            message="Workflow instance not found",
            resource_type="workflow_instance",
            resource_id=instance_id,
        )

    log = await log_dao.get_by_id(execution_id)
    if not log or log.workflow_instance_id != instance_id:
        raise ResourceNotFoundError(
            message="Execution log not found",
            resource_type="execution_log",
            resource_id=execution_id,
        )

    return _log_to_response(log)


@router.get(
    "/instances/{instance_id}/executions/stats",
    response_model=ExecutionStats,
    status_code=status.HTTP_200_OK,
    summary="Get execution statistics",
    description="Get execution statistics for a workflow instance",
)
async def get_execution_stats(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionStats:
    """Get execution statistics for a workflow instance."""
    instance_dao = WorkflowInstanceDAO(db)
    log_dao = ExecutionLogDAO(db)

    # Verify instance access
    instance = await instance_dao.get_by_id_and_org(instance_id, current_user.org_id)
    if not instance:
        raise ResourceNotFoundError(
            message="Workflow instance not found",
            resource_type="workflow_instance",
            resource_id=instance_id,
        )

    # Get stats
    counts = await log_dao.count_by_status(instance_id)
    success_rate = await log_dao.get_success_rate(instance_id)
    avg_duration = await log_dao.get_average_duration(instance_id)
    total = await log_dao.count_total(instance_id)
    successful = await log_dao.count_successful(instance_id)
    failed = await log_dao.count_failed(instance_id)

    return ExecutionStats(
        total=total,
        success=successful,
        failed=failed,
        running=counts.get("running", 0),
        success_rate=success_rate,
        average_duration=avg_duration,
    )
