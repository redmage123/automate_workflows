"""
API endpoints for AI-powered workflow generation.

WHAT: REST API for natural language workflow creation.

WHY: Allows users to describe workflows in plain English
and have the system generate n8n-compatible JSON.

Security Considerations (OWASP):
- A01 Broken Access Control: Require authentication
- A03 Injection: Input sanitized by service layer
- A04 Insecure Design: Rate limiting to prevent abuse
- A07 Auth Failures: JWT validation required

HOW: FastAPI router with endpoints for:
- Generate workflow from description
- Refine existing workflow
- Validate workflow structure
- Check AI service status
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.config import settings
from app.core.exceptions import (
    AIServiceError,
    AIGenerationError,
    AIRateLimitError,
    ValidationError,
)
from app.models.user import User
from app.schemas.workflow_ai import (
    WorkflowGenerateRequest,
    WorkflowRefineRequest,
    WorkflowValidateRequest,
    WorkflowGenerationResponse,
    WorkflowValidationResponse,
    AIServiceStatusResponse,
)
from app.services.workflow_ai_service import WorkflowAIService, get_workflow_ai_service
from app.services.audit import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflow-ai", tags=["Workflow AI"])


# ============================================================================
# Dependencies
# ============================================================================


async def get_ai_service() -> WorkflowAIService:
    """
    Dependency to get workflow AI service.

    WHAT: Provides AI service instance to endpoints.

    WHY: Dependency injection for testability.
    """
    return get_workflow_ai_service()


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=AIServiceStatusResponse)
async def get_ai_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> AIServiceStatusResponse:
    """
    Check AI service availability.

    WHAT: Returns whether AI workflow generation is available.

    WHY: Frontend can show/hide AI features based on this.
    Users shouldn't see features they can't use.

    HOW: Checks if OpenAI API key is configured.

    Returns:
        AIServiceStatusResponse with availability status
    """
    if settings.OPENAI_API_KEY:
        return AIServiceStatusResponse(
            available=True,
            model=settings.OPENAI_MODEL,
            message="AI workflow generation is available",
        )
    else:
        return AIServiceStatusResponse(
            available=False,
            model=None,
            message="AI service not configured - OPENAI_API_KEY not set",
        )


@router.post("/generate", response_model=WorkflowGenerationResponse)
async def generate_workflow(
    request: WorkflowGenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ai_service: Annotated[WorkflowAIService, Depends(get_ai_service)],
) -> WorkflowGenerationResponse:
    """
    Generate workflow from natural language description.

    WHAT: Converts plain text to n8n workflow JSON.

    WHY: Main entry point for AI-powered workflow creation.
    Enables non-technical users to create automations.

    HOW:
    1. Validate request
    2. Call AI service
    3. Audit log the generation
    4. Return result

    Args:
        request: Description and optional context
        current_user: Authenticated user
        db: Database session for audit logging
        ai_service: AI service instance

    Returns:
        Generated workflow with metadata

    Raises:
        HTTPException: If generation fails
    """
    try:
        logger.info(
            f"User {current_user.id} generating workflow from description: "
            f"{request.description[:100]}..."
        )

        result = await ai_service.generate_workflow(
            description=request.description,
            context=request.context,
        )

        # Audit log the generation
        audit_service = AuditService(db)
        await audit_service.log(
            user_id=current_user.id,
            org_id=current_user.org_id,
            action="workflow_ai_generate",
            resource_type="workflow",
            details={
                "description_length": len(request.description),
                "workflow_name": result.name,
                "node_count": len(result.nodes),
                "confidence": result.confidence,
            },
        )

        return WorkflowGenerationResponse(
            name=result.name,
            nodes=result.nodes,
            connections=result.connections,
            settings=result.settings,
            explanation=result.explanation,
            confidence=result.confidence,
            suggestions=result.suggestions,
        )

    except ValidationError as e:
        logger.warning(f"Validation error in workflow generation: {e.message}")
        raise HTTPException(status_code=400, detail=e.message)
    except AIRateLimitError as e:
        logger.warning(f"AI rate limit exceeded for user {current_user.id}")
        raise HTTPException(status_code=429, detail=e.message)
    except AIGenerationError as e:
        logger.error(f"AI generation error: {e.message}")
        raise HTTPException(status_code=422, detail=e.message)
    except AIServiceError as e:
        logger.error(f"AI service error: {e.message}")
        raise HTTPException(status_code=502, detail=e.message)


@router.post("/refine", response_model=WorkflowGenerationResponse)
async def refine_workflow(
    request: WorkflowRefineRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ai_service: Annotated[WorkflowAIService, Depends(get_ai_service)],
) -> WorkflowGenerationResponse:
    """
    Refine existing workflow based on feedback.

    WHAT: Modifies workflow according to user instructions.

    WHY: Allows iterative improvement without starting over.
    Users can request specific changes to generated workflows.

    HOW:
    1. Validate request
    2. Call AI service with workflow and feedback
    3. Audit log the refinement
    4. Return updated result

    Args:
        request: Current workflow and refinement feedback
        current_user: Authenticated user
        db: Database session for audit logging
        ai_service: AI service instance

    Returns:
        Updated workflow with metadata

    Raises:
        HTTPException: If refinement fails
    """
    try:
        logger.info(
            f"User {current_user.id} refining workflow with feedback: "
            f"{request.feedback[:100]}..."
        )

        result = await ai_service.refine_workflow(
            workflow=request.workflow,
            feedback=request.feedback,
        )

        # Audit log the refinement
        audit_service = AuditService(db)
        await audit_service.log(
            user_id=current_user.id,
            org_id=current_user.org_id,
            action="workflow_ai_refine",
            resource_type="workflow",
            details={
                "feedback_length": len(request.feedback),
                "workflow_name": result.name,
                "node_count": len(result.nodes),
                "confidence": result.confidence,
            },
        )

        return WorkflowGenerationResponse(
            name=result.name,
            nodes=result.nodes,
            connections=result.connections,
            settings=result.settings,
            explanation=result.explanation,
            confidence=result.confidence,
            suggestions=result.suggestions,
        )

    except ValidationError as e:
        logger.warning(f"Validation error in workflow refinement: {e.message}")
        raise HTTPException(status_code=400, detail=e.message)
    except AIRateLimitError as e:
        logger.warning(f"AI rate limit exceeded for user {current_user.id}")
        raise HTTPException(status_code=429, detail=e.message)
    except AIGenerationError as e:
        logger.error(f"AI generation error: {e.message}")
        raise HTTPException(status_code=422, detail=e.message)
    except AIServiceError as e:
        logger.error(f"AI service error: {e.message}")
        raise HTTPException(status_code=502, detail=e.message)


@router.post("/validate", response_model=WorkflowValidationResponse)
async def validate_workflow(
    request: WorkflowValidateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    ai_service: Annotated[WorkflowAIService, Depends(get_ai_service)],
) -> WorkflowValidationResponse:
    """
    Validate workflow structure.

    WHAT: Checks workflow JSON for errors and warnings.

    WHY: Catches problems before deploying to n8n.
    Better to show validation errors in UI than have
    n8n deployment fail with unclear errors.

    HOW:
    1. Call AI service validation
    2. Return errors and warnings

    Args:
        request: Workflow JSON to validate
        current_user: Authenticated user
        ai_service: AI service instance

    Returns:
        Validation result with errors and warnings
    """
    logger.info(f"User {current_user.id} validating workflow")

    result = ai_service.validate_workflow(request.workflow)

    return WorkflowValidationResponse(
        valid=result.valid,
        errors=result.errors,
        warnings=result.warnings,
    )
