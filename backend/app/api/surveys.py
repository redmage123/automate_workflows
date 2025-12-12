"""
Survey API Routes.

WHAT: FastAPI router for survey and feedback endpoints.

WHY: Surveys enable:
1. Collecting client feedback (NPS, CSAT)
2. Custom satisfaction surveys
3. Post-project reviews
4. Continuous improvement metrics

HOW: Exposes REST endpoints for:
- Survey management (admin)
- Response collection (users)
- Analytics and metrics
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_roles
from app.core.exceptions import SurveyNotFoundError
from app.models.user import User
from app.services.survey_service import SurveyService
from app.schemas.survey import (
    SurveyCreateRequest,
    SurveyUpdateRequest,
    SurveyResponse,
    SurveyListResponse,
    ResponseSubmitRequest,
    ResponseUpdateRequest,
    SurveyResponseDetail,
    SurveyResponseListResponse,
    InvitationCreateRequest,
    InvitationResponse,
    InvitationListResponse,
    NPSResponse,
    RatingResponse,
    FeedbackScoreHistoryResponse,
    FeedbackScoreResponse,
    SurveyStatsResponse,
    SurveyStatus,
    SurveyType,
    QuestionSchema,
    UserResponse as UserSchemaResponse,
)

router = APIRouter(prefix="/surveys", tags=["surveys"])


# ============================================================================
# Survey Management Endpoints (Admin)
# ============================================================================


@router.post(
    "",
    response_model=SurveyResponse,
    summary="Create survey",
    description="""
    Create a new survey.

    **Admin only**: Requires ADMIN role.

    Surveys can be of different types:
    - NPS: Net Promoter Score (0-10 scale)
    - CSAT: Customer Satisfaction (rating scale)
    - CES: Customer Effort Score
    - Custom: Any combination of question types
    """,
)
async def create_survey(
    request: SurveyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> SurveyResponse:
    """
    Create a new survey.

    WHAT: Creates a survey with questions.

    WHY: Admins define surveys for feedback collection.

    HOW: Validates survey structure and creates database record.

    Args:
        request: Survey creation data
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Created survey
    """
    service = SurveyService(db)

    # Convert question schemas to dicts
    questions = [q.model_dump() for q in request.questions]

    survey = await service.create_survey(
        org_id=current_user.org_id,
        created_by_id=current_user.id,
        title=request.title,
        description=request.description,
        survey_type=request.survey_type.value,
        questions=questions,
        is_anonymous=request.is_anonymous,
        allow_multiple_responses=request.allow_multiple_responses,
        show_progress=request.show_progress,
        project_id=request.project_id,
        starts_at=request.starts_at,
        ends_at=request.ends_at,
    )

    return await _survey_to_response(service, survey)


@router.get(
    "",
    response_model=SurveyListResponse,
    summary="List surveys",
    description="List all surveys with optional filters.",
)
async def list_surveys(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    status: Optional[SurveyStatus] = Query(None, description="Filter by status"),
    survey_type: Optional[SurveyType] = Query(None, description="Filter by type"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> SurveyListResponse:
    """
    List surveys.

    WHAT: Retrieves paginated list of surveys.

    WHY: Admins need to view and manage surveys.

    HOW: Queries surveys with optional filters and pagination.

    Args:
        skip: Pagination offset
        limit: Maximum results
        status: Optional status filter
        survey_type: Optional type filter
        project_id: Optional project filter
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Paginated list of surveys
    """
    service = SurveyService(db)
    surveys, total = await service.list_surveys(
        org_id=current_user.org_id,
        status=status.value if status else None,
        survey_type=survey_type.value if survey_type else None,
        project_id=project_id,
        skip=skip,
        limit=limit,
    )

    items = [await _survey_to_response(service, s) for s in surveys]

    return SurveyListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/stats",
    response_model=SurveyStatsResponse,
    summary="Get survey statistics",
    description="Get aggregated survey statistics for dashboard.",
)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> SurveyStatsResponse:
    """
    Get survey statistics.

    WHAT: Retrieves aggregated survey metrics.

    WHY: Dashboard overview of feedback program.

    HOW: Aggregates counts and scores.

    Args:
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Aggregated statistics
    """
    service = SurveyService(db)
    stats = await service.get_survey_stats(org_id=current_user.org_id)

    return SurveyStatsResponse(
        total_surveys=stats["total_surveys"],
        active_surveys=stats["active_surveys"],
        total_responses=stats["total_responses"],
        completion_rate=stats["completion_rate"],
        nps=NPSResponse(**stats["nps"]) if stats.get("nps") else None,
        csat=RatingResponse(
            average=stats["csat"]["average"] if stats.get("csat") else None,
            min=None,
            max=None,
            response_count=stats["csat"]["response_count"] if stats.get("csat") else 0,
            distribution={},
        ) if stats.get("csat") else None,
    )


@router.get(
    "/active",
    response_model=SurveyListResponse,
    summary="Get active surveys",
    description="Get surveys available for the current user to respond to.",
)
async def get_active_surveys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SurveyListResponse:
    """
    Get active surveys for user.

    WHAT: Lists surveys user can respond to.

    WHY: Show available surveys to users.

    HOW: Filters active surveys user hasn't completed.

    Args:
        db: Database session
        current_user: Authenticated user

    Returns:
        List of active surveys
    """
    service = SurveyService(db)
    surveys = await service.get_active_surveys(
        org_id=current_user.org_id,
        user_id=current_user.id,
    )

    items = [await _survey_to_response(service, s) for s in surveys]

    return SurveyListResponse(
        items=items,
        total=len(items),
        skip=0,
        limit=len(items),
    )


@router.get(
    "/{survey_id}",
    response_model=SurveyResponse,
    summary="Get survey",
    description="Get details of a specific survey.",
)
async def get_survey(
    survey_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SurveyResponse:
    """
    Get a specific survey.

    WHAT: Retrieves full survey details.

    WHY: View survey for responding or admin.

    HOW: Fetches survey by ID with organization scope.

    Args:
        survey_id: Survey ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Survey details

    Raises:
        SurveyNotFoundError: If survey not found
    """
    service = SurveyService(db)
    survey = await service.get_survey(
        survey_id=survey_id,
        org_id=current_user.org_id,
    )

    return await _survey_to_response(service, survey)


@router.put(
    "/{survey_id}",
    response_model=SurveyResponse,
    summary="Update survey",
    description="Update an existing survey.",
)
async def update_survey(
    survey_id: int,
    request: SurveyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> SurveyResponse:
    """
    Update a survey.

    WHAT: Updates survey properties.

    WHY: Modify survey configuration.

    HOW: Validates updates and applies changes.

    Args:
        survey_id: Survey ID
        request: Update data
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Updated survey
    """
    service = SurveyService(db)

    update_data = request.model_dump(exclude_unset=True)
    if "questions" in update_data and update_data["questions"]:
        update_data["questions"] = [q.model_dump() if hasattr(q, 'model_dump') else q for q in update_data["questions"]]

    survey = await service.update_survey(
        survey_id=survey_id,
        org_id=current_user.org_id,
        **update_data,
    )

    return await _survey_to_response(service, survey)


@router.delete(
    "/{survey_id}",
    summary="Delete survey",
    description="Delete a survey and all its responses.",
)
async def delete_survey(
    survey_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> dict:
    """
    Delete a survey.

    WHAT: Removes survey and responses.

    WHY: Clean up unused surveys.

    HOW: Cascades delete to responses and invitations.

    Args:
        survey_id: Survey ID
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Success message
    """
    service = SurveyService(db)
    await service.delete_survey(
        survey_id=survey_id,
        org_id=current_user.org_id,
    )

    return {"message": "Survey deleted successfully"}


@router.post(
    "/{survey_id}/publish",
    response_model=SurveyResponse,
    summary="Publish survey",
    description="Publish a draft survey to start accepting responses.",
)
async def publish_survey(
    survey_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> SurveyResponse:
    """
    Publish a survey.

    WHAT: Changes status to active.

    WHY: Start collecting responses.

    HOW: Updates status and validates survey is ready.

    Args:
        survey_id: Survey ID
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Published survey
    """
    service = SurveyService(db)
    survey = await service.publish_survey(
        survey_id=survey_id,
        org_id=current_user.org_id,
    )

    return await _survey_to_response(service, survey)


@router.post(
    "/{survey_id}/close",
    response_model=SurveyResponse,
    summary="Close survey",
    description="Close a survey to stop accepting responses.",
)
async def close_survey(
    survey_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> SurveyResponse:
    """
    Close a survey.

    WHAT: Changes status to closed.

    WHY: Stop collecting responses.

    HOW: Updates status to prevent new responses.

    Args:
        survey_id: Survey ID
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Closed survey
    """
    service = SurveyService(db)
    survey = await service.close_survey(
        survey_id=survey_id,
        org_id=current_user.org_id,
    )

    return await _survey_to_response(service, survey)


# ============================================================================
# Response Endpoints
# ============================================================================


@router.post(
    "/{survey_id}/responses",
    response_model=SurveyResponseDetail,
    summary="Start response",
    description="Start a new survey response.",
)
async def start_response(
    survey_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SurveyResponseDetail:
    """
    Start a survey response.

    WHAT: Creates a new response record.

    WHY: Begin responding to a survey.

    HOW: Creates response and tracks metadata.

    Args:
        survey_id: Survey ID
        request: HTTP request for metadata
        db: Database session
        current_user: Authenticated user

    Returns:
        New response record
    """
    service = SurveyService(db)

    response = await service.start_response(
        survey_id=survey_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    return _response_to_detail(response)


@router.patch(
    "/{survey_id}/responses/{response_id}",
    response_model=SurveyResponseDetail,
    summary="Update response",
    description="Update response answers (save progress).",
)
async def update_response(
    survey_id: int,
    response_id: int,
    request: ResponseUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SurveyResponseDetail:
    """
    Update response answers.

    WHAT: Saves partial answers.

    WHY: Allow saving progress.

    HOW: Merges new answers with existing.

    Args:
        survey_id: Survey ID
        response_id: Response ID
        request: Answer updates
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated response
    """
    service = SurveyService(db)

    response = await service.update_response(
        response_id=response_id,
        org_id=current_user.org_id,
        answers=request.answers,
    )

    return _response_to_detail(response)


@router.post(
    "/{survey_id}/responses/{response_id}/submit",
    response_model=SurveyResponseDetail,
    summary="Submit response",
    description="Submit a completed survey response.",
)
async def submit_response(
    survey_id: int,
    response_id: int,
    request: ResponseSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SurveyResponseDetail:
    """
    Submit completed response.

    WHAT: Finalizes survey response.

    WHY: Mark response as complete.

    HOW: Validates required questions and marks complete.

    Args:
        survey_id: Survey ID
        response_id: Response ID
        request: Final answers
        db: Database session
        current_user: Authenticated user

    Returns:
        Completed response
    """
    service = SurveyService(db)

    response = await service.submit_response(
        response_id=response_id,
        org_id=current_user.org_id,
        answers=request.answers,
        time_taken_seconds=request.time_taken_seconds,
    )

    return _response_to_detail(response)


@router.get(
    "/{survey_id}/responses",
    response_model=SurveyResponseListResponse,
    summary="List responses",
    description="List all responses for a survey (Admin only).",
)
async def list_responses(
    survey_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    is_complete: Optional[bool] = Query(None, description="Filter by completion"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> SurveyResponseListResponse:
    """
    List survey responses.

    WHAT: Retrieves all responses for analysis.

    WHY: View and analyze feedback.

    HOW: Lists responses with optional filters.

    Args:
        survey_id: Survey ID
        skip: Pagination offset
        limit: Maximum results
        is_complete: Optional completion filter
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Paginated list of responses
    """
    service = SurveyService(db)
    responses, total = await service.list_responses(
        survey_id=survey_id,
        org_id=current_user.org_id,
        is_complete=is_complete,
        skip=skip,
        limit=limit,
    )

    items = [_response_to_detail(r) for r in responses]

    return SurveyResponseListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


# ============================================================================
# Analytics Endpoints
# ============================================================================


@router.get(
    "/{survey_id}/analytics/nps",
    response_model=NPSResponse,
    summary="Get NPS",
    description="Get Net Promoter Score for a survey.",
)
async def get_nps(
    survey_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> NPSResponse:
    """
    Get NPS metrics.

    WHAT: Calculates Net Promoter Score.

    WHY: Standard satisfaction metric.

    HOW: Aggregates responses into NPS calculation.

    Args:
        survey_id: Survey ID
        db: Database session
        current_user: Authenticated admin user

    Returns:
        NPS data
    """
    service = SurveyService(db)
    nps = await service.get_nps(
        survey_id=survey_id,
        org_id=current_user.org_id,
    )

    return NPSResponse(**nps)


@router.get(
    "/{survey_id}/analytics/rating",
    response_model=RatingResponse,
    summary="Get rating",
    description="Get average rating metrics for a survey.",
)
async def get_rating(
    survey_id: int,
    question_id: Optional[str] = Query(None, description="Specific question ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> RatingResponse:
    """
    Get rating metrics.

    WHAT: Calculates average ratings.

    WHY: CSAT and other rating analysis.

    HOW: Aggregates rating responses.

    Args:
        survey_id: Survey ID
        question_id: Optional specific question
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Rating data
    """
    service = SurveyService(db)
    rating = await service.get_rating(
        survey_id=survey_id,
        org_id=current_user.org_id,
        question_id=question_id,
    )

    return RatingResponse(**rating)


@router.get(
    "/analytics/history/{score_type}",
    response_model=FeedbackScoreHistoryResponse,
    summary="Get score history",
    description="Get historical feedback scores.",
)
async def get_score_history(
    score_type: str,
    project_id: Optional[int] = Query(None, description="Filter by project"),
    periods: int = Query(12, ge=1, le=52, description="Number of periods"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> FeedbackScoreHistoryResponse:
    """
    Get score history.

    WHAT: Retrieves historical scores.

    WHY: Track improvement trends.

    HOW: Queries pre-computed scores.

    Args:
        score_type: Score type (nps, csat, ces)
        project_id: Optional project filter
        periods: Number of periods
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Score history with trend
    """
    service = SurveyService(db)
    history = await service.get_score_history(
        org_id=current_user.org_id,
        score_type=score_type,
        project_id=project_id,
        periods=periods,
    )

    scores = [FeedbackScoreResponse.model_validate(s) for s in history["scores"]]

    return FeedbackScoreHistoryResponse(
        scores=scores,
        current_score=history["current_score"],
        trend=history["trend"],
    )


# ============================================================================
# Invitation Endpoints
# ============================================================================


@router.post(
    "/{survey_id}/invitations",
    response_model=InvitationListResponse,
    summary="Create invitations",
    description="Create survey invitations for users.",
)
async def create_invitations(
    survey_id: int,
    request: InvitationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
) -> InvitationListResponse:
    """
    Create survey invitations.

    WHAT: Creates invitations for users.

    WHY: Distribute survey.

    HOW: Creates invitation records with unique tokens.

    Args:
        survey_id: Survey ID
        request: User IDs to invite
        db: Database session
        current_user: Authenticated admin user

    Returns:
        Created invitations
    """
    service = SurveyService(db)
    invitations = await service.create_invitations(
        survey_id=survey_id,
        org_id=current_user.org_id,
        user_ids=request.user_ids,
    )

    items = [_invitation_to_response(inv) for inv in invitations]

    return InvitationListResponse(
        items=items,
        total=len(items),
    )


# ============================================================================
# Helper Functions
# ============================================================================


async def _survey_to_response(service: SurveyService, survey) -> SurveyResponse:
    """
    Convert survey model to response schema.

    WHAT: Transforms SQLAlchemy model to Pydantic response.

    WHY: API responses need structured schema format.

    HOW: Maps model attributes to response fields.

    Args:
        service: SurveyService instance
        survey: Survey model instance

    Returns:
        SurveyResponse schema
    """
    questions = []
    if isinstance(survey.questions, list):
        for q in survey.questions:
            questions.append(QuestionSchema(**q))

    created_by = None
    if survey.created_by:
        created_by = UserSchemaResponse(
            id=survey.created_by.id,
            name=survey.created_by.name,
            email=survey.created_by.email,
        )

    response_count = await service.survey_dao.get_response_count(survey.id)

    return SurveyResponse(
        id=survey.id,
        org_id=survey.org_id,
        title=survey.title,
        description=survey.description,
        survey_type=SurveyType(survey.survey_type),
        questions=questions,
        question_count=survey.question_count,
        required_question_count=survey.required_question_count,
        status=SurveyStatus(survey.status),
        is_anonymous=survey.is_anonymous,
        allow_multiple_responses=survey.allow_multiple_responses,
        show_progress=survey.show_progress,
        project_id=survey.project_id,
        starts_at=survey.starts_at,
        ends_at=survey.ends_at,
        is_active=survey.is_active,
        response_count=response_count,
        created_by=created_by,
        created_at=survey.created_at,
        updated_at=survey.updated_at,
    )


def _response_to_detail(response) -> SurveyResponseDetail:
    """
    Convert response model to detail schema.

    WHAT: Transforms SQLAlchemy model to Pydantic response.

    WHY: API responses need structured schema format.

    HOW: Maps model attributes to response fields.

    Args:
        response: SurveyResponse model instance

    Returns:
        SurveyResponseDetail schema
    """
    respondent = None
    if response.respondent:
        respondent = UserSchemaResponse(
            id=response.respondent.id,
            name=response.respondent.name,
            email=response.respondent.email,
        )

    return SurveyResponseDetail(
        id=response.id,
        org_id=response.org_id,
        survey_id=response.survey_id,
        respondent=respondent,
        answers=response.answers or {},
        is_complete=response.is_complete,
        completed_at=response.completed_at,
        time_taken_seconds=response.time_taken_seconds,
        created_at=response.created_at,
    )


def _invitation_to_response(invitation) -> InvitationResponse:
    """
    Convert invitation model to response schema.

    WHAT: Transforms SQLAlchemy model to Pydantic response.

    WHY: API responses need structured schema format.

    HOW: Maps model attributes to response fields.

    Args:
        invitation: SurveyInvitation model instance

    Returns:
        InvitationResponse schema
    """
    user = None
    if invitation.user:
        user = UserSchemaResponse(
            id=invitation.user.id,
            name=invitation.user.name,
            email=invitation.user.email,
        )

    return InvitationResponse(
        id=invitation.id,
        survey_id=invitation.survey_id,
        user_id=invitation.user_id,
        token=invitation.token,
        sent_at=invitation.sent_at,
        opened_at=invitation.opened_at,
        responded_at=invitation.responded_at,
        user=user,
        created_at=invitation.created_at,
    )
