"""
Survey Service.

WHAT: Business logic for survey operations.

WHY: The service layer:
1. Encapsulates survey business logic
2. Coordinates between DAOs
3. Enforces business rules
4. Handles NPS/CSAT calculations

HOW: Orchestrates SurveyDAO, SurveyResponseDAO, and related DAOs
while validating operations against business rules.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.survey import (
    SurveyDAO,
    SurveyResponseDAO,
    SurveyInvitationDAO,
    FeedbackScoreDAO,
)
from app.models.survey import (
    Survey,
    SurveyResponse,
    SurveyInvitation,
    FeedbackScore,
    SurveyStatus,
    SurveyType,
    QuestionType,
)
from app.core.exceptions import (
    SurveyError,
    SurveyNotFoundError,
    SurveyAlreadyRespondedError,
    ValidationError,
)


class SurveyService:
    """
    Service for survey operations.

    WHAT: Provides business logic for surveys.

    WHY: Surveys enable:
    - Client feedback collection (NPS, CSAT)
    - Custom satisfaction surveys
    - Post-project reviews
    - Continuous improvement metrics

    HOW: Coordinates DAOs and enforces business rules.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize SurveyService.

        Args:
            session: Async database session
        """
        self.session = session
        self.survey_dao = SurveyDAO(session)
        self.response_dao = SurveyResponseDAO(session)
        self.invitation_dao = SurveyInvitationDAO(session)
        self.score_dao = FeedbackScoreDAO(session)

    # =========================================================================
    # Survey Management
    # =========================================================================

    async def create_survey(
        self,
        org_id: int,
        created_by_id: int,
        title: str,
        questions: List[Dict[str, Any]],
        description: Optional[str] = None,
        survey_type: str = SurveyType.CUSTOM.value,
        is_anonymous: bool = False,
        allow_multiple_responses: bool = False,
        show_progress: bool = True,
        project_id: Optional[int] = None,
        starts_at: Optional[datetime] = None,
        ends_at: Optional[datetime] = None,
    ) -> Survey:
        """
        Create a new survey.

        WHAT: Creates a survey with questions.

        WHY: Collect structured feedback.

        Args:
            org_id: Organization ID
            created_by_id: Creator user ID
            title: Survey title
            questions: List of question definitions
            description: Survey description
            survey_type: Type of survey (nps, csat, custom)
            is_anonymous: Allow anonymous responses
            allow_multiple_responses: Allow multiple per user
            show_progress: Show progress bar
            project_id: Optional associated project
            starts_at: Optional start time
            ends_at: Optional end time

        Returns:
            Created Survey

        Raises:
            ValidationError: If validation fails
        """
        # Validate questions
        self._validate_questions(questions)

        # Validate dates
        if starts_at and ends_at and starts_at >= ends_at:
            raise ValidationError(
                message="End date must be after start date",
                details={"starts_at": str(starts_at), "ends_at": str(ends_at)},
            )

        # Convert questions to list format expected by model
        question_list = [q if isinstance(q, dict) else q.dict() for q in questions]

        survey = await self.survey_dao.create(
            org_id=org_id,
            created_by_id=created_by_id,
            title=title,
            description=description,
            survey_type=survey_type,
            questions=question_list,
            status=SurveyStatus.DRAFT.value,
            is_anonymous=is_anonymous,
            allow_multiple_responses=allow_multiple_responses,
            show_progress=show_progress,
            project_id=project_id,
            starts_at=starts_at,
            ends_at=ends_at,
        )

        return survey

    def _validate_questions(self, questions: List[Dict[str, Any]]) -> None:
        """
        Validate question definitions.

        WHAT: Ensures questions are properly formatted.

        WHY: Invalid questions cause runtime errors.

        Args:
            questions: List of question definitions

        Raises:
            ValidationError: If validation fails
        """
        if not questions:
            raise ValidationError(
                message="At least one question is required",
            )

        question_ids = set()
        valid_types = [t.value for t in QuestionType]

        for i, question in enumerate(questions):
            q = question if isinstance(question, dict) else question.dict()

            if "id" not in q:
                raise ValidationError(
                    message=f"Question {i} missing 'id' field",
                    details={"question_index": i},
                )

            if q["id"] in question_ids:
                raise ValidationError(
                    message=f"Duplicate question ID: {q['id']}",
                    details={"question_id": q["id"]},
                )
            question_ids.add(q["id"])

            if "text" not in q:
                raise ValidationError(
                    message=f"Question {q['id']} missing 'text' field",
                    details={"question_id": q["id"]},
                )

            if "type" not in q:
                raise ValidationError(
                    message=f"Question {q['id']} missing 'type' field",
                    details={"question_id": q["id"]},
                )

            if q["type"] not in valid_types:
                raise ValidationError(
                    message=f"Invalid question type: {q['type']}",
                    details={"question_id": q["id"], "valid_types": valid_types},
                )

            # Validate choice questions have options
            if q["type"] in ["single_choice", "multiple_choice"]:
                if not q.get("options"):
                    raise ValidationError(
                        message=f"Choice question {q['id']} requires options",
                        details={"question_id": q["id"]},
                    )

    async def get_survey(
        self,
        survey_id: int,
        org_id: int,
    ) -> Survey:
        """
        Get a survey by ID.

        WHAT: Retrieves survey details.

        WHY: View survey configuration.

        Args:
            survey_id: Survey ID
            org_id: Organization ID

        Returns:
            Survey

        Raises:
            SurveyNotFoundError: If not found
        """
        survey = await self.survey_dao.get_by_id_and_org(survey_id, org_id)
        if not survey:
            raise SurveyNotFoundError(
                message="Survey not found",
                details={"survey_id": survey_id},
            )
        return survey

    async def update_survey(
        self,
        survey_id: int,
        org_id: int,
        **kwargs,
    ) -> Survey:
        """
        Update a survey.

        WHAT: Updates survey configuration.

        WHY: Modify survey before publishing.

        Args:
            survey_id: Survey ID
            org_id: Organization ID
            **kwargs: Fields to update

        Returns:
            Updated Survey

        Raises:
            SurveyNotFoundError: If not found
            SurveyError: If survey has responses
        """
        survey = await self.get_survey(survey_id, org_id)

        # Check if survey has responses (restrict certain updates)
        response_count = await self.survey_dao.get_response_count(survey_id)
        if response_count > 0 and "questions" in kwargs:
            raise SurveyError(
                message="Cannot modify questions after responses received",
                details={"response_count": response_count},
            )

        # Validate questions if being updated
        if "questions" in kwargs:
            self._validate_questions(kwargs["questions"])
            # Convert to list format
            kwargs["questions"] = [
                q if isinstance(q, dict) else q.dict() for q in kwargs["questions"]
            ]

        for key, value in kwargs.items():
            if value is not None and hasattr(survey, key):
                setattr(survey, key, value)

        await self.session.flush()
        await self.session.refresh(survey)
        return survey

    async def delete_survey(
        self,
        survey_id: int,
        org_id: int,
    ) -> None:
        """
        Delete a survey.

        WHAT: Removes survey and responses.

        WHY: Clean up unused surveys.

        Args:
            survey_id: Survey ID
            org_id: Organization ID

        Raises:
            SurveyNotFoundError: If not found
        """
        survey = await self.get_survey(survey_id, org_id)
        await self.survey_dao.delete(survey_id)

    async def list_surveys(
        self,
        org_id: int,
        status: Optional[str] = None,
        survey_type: Optional[str] = None,
        project_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[Survey], int]:
        """
        List surveys for an organization.

        WHAT: Lists surveys with filters.

        WHY: Admin management view.

        Args:
            org_id: Organization ID
            status: Optional status filter
            survey_type: Optional type filter
            project_id: Optional project filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (surveys list, total count)
        """
        surveys = await self.survey_dao.get_org_surveys(
            org_id=org_id,
            status=status,
            survey_type=survey_type,
            project_id=project_id,
            skip=skip,
            limit=limit,
        )

        # Get total count
        all_surveys = await self.survey_dao.get_org_surveys(
            org_id=org_id,
            status=status,
            survey_type=survey_type,
            project_id=project_id,
            skip=0,
            limit=10000,
        )

        # Add response counts
        for survey in surveys:
            survey.response_count = await self.survey_dao.get_response_count(survey.id)

        return surveys, len(all_surveys)

    async def publish_survey(
        self,
        survey_id: int,
        org_id: int,
    ) -> Survey:
        """
        Publish a survey.

        WHAT: Changes status to active.

        WHY: Start accepting responses.

        Args:
            survey_id: Survey ID
            org_id: Organization ID

        Returns:
            Updated Survey

        Raises:
            SurveyNotFoundError: If not found
            SurveyError: If already published
        """
        survey = await self.get_survey(survey_id, org_id)

        if survey.status not in [SurveyStatus.DRAFT.value, SurveyStatus.PAUSED.value]:
            raise SurveyError(
                message="Survey cannot be published in current state",
                details={"current_status": survey.status},
            )

        return await self.survey_dao.publish_survey(survey_id, org_id)

    async def close_survey(
        self,
        survey_id: int,
        org_id: int,
    ) -> Survey:
        """
        Close a survey.

        WHAT: Changes status to closed.

        WHY: Stop accepting responses.

        Args:
            survey_id: Survey ID
            org_id: Organization ID

        Returns:
            Updated Survey
        """
        survey = await self.get_survey(survey_id, org_id)
        return await self.survey_dao.close_survey(survey_id, org_id)

    # =========================================================================
    # Response Management
    # =========================================================================

    async def get_active_surveys(
        self,
        org_id: int,
        user_id: int,
    ) -> List[Survey]:
        """
        Get active surveys for a user.

        WHAT: Lists surveys user can respond to.

        WHY: Show available surveys.

        Args:
            org_id: Organization ID
            user_id: User ID

        Returns:
            List of active surveys
        """
        return await self.survey_dao.get_active_surveys(org_id, user_id)

    async def start_response(
        self,
        survey_id: int,
        org_id: int,
        user_id: Optional[int] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> SurveyResponse:
        """
        Start a survey response.

        WHAT: Creates a new response record.

        WHY: Track response in progress.

        Args:
            survey_id: Survey ID
            org_id: Organization ID
            user_id: Optional user ID (for non-anonymous)
            user_agent: Browser user agent
            ip_address: Client IP

        Returns:
            Created SurveyResponse

        Raises:
            SurveyNotFoundError: If survey not found
            SurveyAlreadyRespondedError: If already responded
        """
        survey = await self.get_survey(survey_id, org_id)

        if not survey.is_active:
            raise SurveyError(
                message="Survey is not currently active",
                details={"survey_id": survey_id, "status": survey.status},
            )

        # Check for existing response (if not allowing multiple)
        if user_id and not survey.allow_multiple_responses:
            existing = await self.response_dao.get_user_response(survey_id, user_id)
            if existing and existing.is_complete:
                raise SurveyAlreadyRespondedError(
                    message="You have already completed this survey",
                    details={"survey_id": survey_id},
                )
            if existing:
                return existing

        response = await self.response_dao.create(
            org_id=org_id,
            survey_id=survey_id,
            respondent_id=user_id if not survey.is_anonymous else None,
            answers={},
            is_complete=False,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return response

    async def update_response(
        self,
        response_id: int,
        org_id: int,
        answers: Dict[str, Any],
    ) -> SurveyResponse:
        """
        Update response answers.

        WHAT: Saves partial answers.

        WHY: Allow saving progress.

        Args:
            response_id: Response ID
            org_id: Organization ID
            answers: Answer data

        Returns:
            Updated SurveyResponse
        """
        response = await self.response_dao.get_by_id(response_id)
        if not response or response.org_id != org_id:
            raise SurveyNotFoundError(
                message="Response not found",
                details={"response_id": response_id},
            )

        if response.is_complete:
            raise SurveyError(
                message="Cannot modify completed response",
                details={"response_id": response_id},
            )

        return await self.response_dao.update_answers(response_id, answers)

    async def submit_response(
        self,
        response_id: int,
        org_id: int,
        answers: Dict[str, Any],
        time_taken_seconds: Optional[int] = None,
    ) -> SurveyResponse:
        """
        Submit a completed response.

        WHAT: Finalizes a survey response.

        WHY: Mark response as complete.

        Args:
            response_id: Response ID
            org_id: Organization ID
            answers: Final answers
            time_taken_seconds: Time to complete

        Returns:
            Completed SurveyResponse

        Raises:
            ValidationError: If required questions not answered
        """
        response = await self.response_dao.get_by_id(response_id)
        if not response or response.org_id != org_id:
            raise SurveyNotFoundError(
                message="Response not found",
                details={"response_id": response_id},
            )

        # Get survey for validation
        survey = await self.survey_dao.get_by_id(response.survey_id)
        if not survey:
            raise SurveyNotFoundError(message="Survey not found")

        # Validate required questions
        questions = survey.questions if isinstance(survey.questions, list) else []
        for question in questions:
            if question.get("required", False):
                if question["id"] not in answers or answers[question["id"]] is None:
                    raise ValidationError(
                        message=f"Required question not answered: {question['text']}",
                        details={"question_id": question["id"]},
                    )

        # Update answers
        await self.response_dao.update_answers(response_id, answers)

        # Update time taken
        response = await self.response_dao.get_by_id(response_id)
        if time_taken_seconds:
            response.time_taken_seconds = time_taken_seconds

        # Mark complete
        return await self.response_dao.submit_response(response_id)

    async def list_responses(
        self,
        survey_id: int,
        org_id: int,
        is_complete: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[SurveyResponse], int]:
        """
        List responses for a survey.

        WHAT: Lists survey responses.

        WHY: View and analyze feedback.

        Args:
            survey_id: Survey ID
            org_id: Organization ID
            is_complete: Optional completion filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (responses list, total count)
        """
        # Verify survey exists
        await self.get_survey(survey_id, org_id)

        responses = await self.response_dao.get_survey_responses(
            survey_id=survey_id,
            org_id=org_id,
            is_complete=is_complete,
            skip=skip,
            limit=limit,
        )

        all_responses = await self.response_dao.get_survey_responses(
            survey_id=survey_id,
            org_id=org_id,
            is_complete=is_complete,
            skip=0,
            limit=10000,
        )

        return responses, len(all_responses)

    # =========================================================================
    # Invitations
    # =========================================================================

    async def create_invitations(
        self,
        survey_id: int,
        org_id: int,
        user_ids: List[int],
    ) -> List[SurveyInvitation]:
        """
        Create survey invitations.

        WHAT: Creates invitations for users.

        WHY: Distribute survey.

        Args:
            survey_id: Survey ID
            org_id: Organization ID
            user_ids: Users to invite

        Returns:
            List of created invitations
        """
        await self.get_survey(survey_id, org_id)

        invitations = []
        for user_id in user_ids:
            invitation = await self.invitation_dao.create_invitation(
                org_id=org_id,
                survey_id=survey_id,
                user_id=user_id,
            )
            invitations.append(invitation)

        return invitations

    async def get_invitation_by_token(
        self,
        token: str,
    ) -> Optional[SurveyInvitation]:
        """
        Get invitation by token.

        WHAT: Validates invitation token.

        WHY: Anonymous survey access.

        Args:
            token: Invitation token

        Returns:
            Invitation if valid
        """
        return await self.invitation_dao.get_by_token(token)

    # =========================================================================
    # Analytics
    # =========================================================================

    async def get_nps(
        self,
        survey_id: int,
        org_id: int,
    ) -> Dict[str, Any]:
        """
        Get NPS metrics for a survey.

        WHAT: Calculates Net Promoter Score.

        WHY: Standard satisfaction metric.

        Args:
            survey_id: Survey ID
            org_id: Organization ID

        Returns:
            NPS data
        """
        await self.get_survey(survey_id, org_id)
        return await self.response_dao.calculate_nps(survey_id, org_id)

    async def get_rating(
        self,
        survey_id: int,
        org_id: int,
        question_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get rating metrics for a survey.

        WHAT: Calculates average ratings.

        WHY: CSAT and other metrics.

        Args:
            survey_id: Survey ID
            org_id: Organization ID
            question_id: Optional specific question

        Returns:
            Rating data
        """
        await self.get_survey(survey_id, org_id)
        return await self.response_dao.calculate_average_rating(
            survey_id, org_id, question_id
        )

    async def get_score_history(
        self,
        org_id: int,
        score_type: str,
        project_id: Optional[int] = None,
        periods: int = 12,
    ) -> Dict[str, Any]:
        """
        Get historical feedback scores.

        WHAT: Retrieves score trend.

        WHY: Track improvement over time.

        Args:
            org_id: Organization ID
            score_type: Score type (nps, csat)
            project_id: Optional project filter
            periods: Number of periods

        Returns:
            Score history with trend
        """
        scores = await self.score_dao.get_score_history(
            org_id=org_id,
            score_type=score_type,
            project_id=project_id,
            periods=periods,
        )

        if not scores:
            return {
                "scores": [],
                "current_score": None,
                "trend": None,
            }

        # Calculate trend
        trend = None
        if len(scores) >= 2:
            latest = scores[0].score
            previous = scores[1].score
            if latest > previous:
                trend = "up"
            elif latest < previous:
                trend = "down"
            else:
                trend = "stable"

        return {
            "scores": scores,
            "current_score": scores[0].score if scores else None,
            "trend": trend,
        }

    async def get_survey_stats(
        self,
        org_id: int,
    ) -> Dict[str, Any]:
        """
        Get overall survey statistics.

        WHAT: Aggregates survey metrics.

        WHY: Dashboard overview.

        Args:
            org_id: Organization ID

        Returns:
            Stats dict
        """
        # Get survey counts
        all_surveys = await self.survey_dao.get_org_surveys(
            org_id=org_id,
            skip=0,
            limit=10000,
        )

        active_surveys = [
            s for s in all_surveys if s.status == SurveyStatus.ACTIVE.value
        ]

        # Count total responses
        total_responses = 0
        completed_responses = 0
        for survey in all_surveys:
            responses = await self.response_dao.get_survey_responses(
                survey_id=survey.id,
                org_id=org_id,
                skip=0,
                limit=10000,
            )
            total_responses += len(responses)
            completed_responses += sum(1 for r in responses if r.is_complete)

        completion_rate = (
            completed_responses / total_responses if total_responses > 0 else 0.0
        )

        # Get latest NPS and CSAT
        latest_nps = await self.score_dao.get_latest_score(org_id, "nps")
        latest_csat = await self.score_dao.get_latest_score(org_id, "csat")

        return {
            "total_surveys": len(all_surveys),
            "active_surveys": len(active_surveys),
            "total_responses": total_responses,
            "completion_rate": round(completion_rate, 2),
            "nps": {
                "score": latest_nps.score if latest_nps else None,
                "promoters": latest_nps.promoters if latest_nps else 0,
                "passives": latest_nps.passives if latest_nps else 0,
                "detractors": latest_nps.detractors if latest_nps else 0,
                "response_count": latest_nps.response_count if latest_nps else 0,
            } if latest_nps else None,
            "csat": {
                "average": latest_csat.score if latest_csat else None,
                "response_count": latest_csat.response_count if latest_csat else 0,
            } if latest_csat else None,
        }
