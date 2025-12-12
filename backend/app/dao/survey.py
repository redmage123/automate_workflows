"""
Survey Data Access Object (DAO).

WHAT: Database operations for survey models.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for survey operations
3. Enforces org-scoping for multi-tenancy
4. Handles response aggregation queries

HOW: Extends BaseDAO with survey-specific queries:
- Survey management
- Response collection
- Score aggregation
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import secrets

from sqlalchemy import select, func, and_, or_, update, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.survey import (
    Survey,
    SurveyResponse,
    SurveyInvitation,
    FeedbackScore,
    SurveyStatus,
    SurveyType,
    QuestionType,
)


class SurveyDAO(BaseDAO[Survey]):
    """
    Data Access Object for Survey model.

    WHAT: Provides operations for surveys.

    WHY: Centralizes survey management.

    HOW: Extends BaseDAO with survey-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize SurveyDAO."""
        super().__init__(Survey, session)

    async def get_org_surveys(
        self,
        org_id: int,
        status: Optional[str] = None,
        survey_type: Optional[str] = None,
        project_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Survey]:
        """
        Get surveys for an organization.

        WHAT: Lists surveys with optional filters.

        WHY: Admin management view.

        Args:
            org_id: Organization ID
            status: Optional status filter
            survey_type: Optional type filter
            project_id: Optional project filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of surveys
        """
        query = (
            select(Survey)
            .where(Survey.org_id == org_id)
            .options(selectinload(Survey.created_by))
        )

        if status:
            query = query.where(Survey.status == status)

        if survey_type:
            query = query.where(Survey.survey_type == survey_type)

        if project_id:
            query = query.where(Survey.project_id == project_id)

        query = query.order_by(Survey.created_at.desc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_active_surveys(
        self,
        org_id: int,
        user_id: Optional[int] = None,
    ) -> List[Survey]:
        """
        Get active surveys available to a user.

        WHAT: Finds surveys user can respond to.

        WHY: Show available surveys to users.

        Args:
            org_id: Organization ID
            user_id: Optional user ID for filtering

        Returns:
            List of active surveys
        """
        now = datetime.utcnow()

        query = (
            select(Survey)
            .where(
                Survey.org_id == org_id,
                Survey.status == SurveyStatus.ACTIVE.value,
                or_(Survey.starts_at.is_(None), Survey.starts_at <= now),
                or_(Survey.ends_at.is_(None), Survey.ends_at >= now),
            )
        )

        result = await self.session.execute(query.order_by(Survey.created_at.desc()))
        surveys = list(result.scalars().all())

        # Filter out surveys user has already responded to (if not allowing multiple)
        if user_id:
            filtered = []
            for survey in surveys:
                if survey.allow_multiple_responses:
                    filtered.append(survey)
                else:
                    response = await self.session.execute(
                        select(SurveyResponse).where(
                            SurveyResponse.survey_id == survey.id,
                            SurveyResponse.respondent_id == user_id,
                            SurveyResponse.is_complete == True,
                        )
                    )
                    if not response.scalar_one_or_none():
                        filtered.append(survey)
            return filtered

        return surveys

    async def publish_survey(
        self,
        survey_id: int,
        org_id: int,
    ) -> Optional[Survey]:
        """
        Publish a survey.

        WHAT: Changes status to active.

        WHY: Start accepting responses.

        Args:
            survey_id: Survey ID
            org_id: Organization ID

        Returns:
            Updated survey
        """
        survey = await self.get_by_id_and_org(survey_id, org_id)
        if not survey:
            return None

        survey.status = SurveyStatus.ACTIVE.value

        await self.session.flush()
        await self.session.refresh(survey)
        return survey

    async def close_survey(
        self,
        survey_id: int,
        org_id: int,
    ) -> Optional[Survey]:
        """
        Close a survey.

        WHAT: Changes status to closed.

        WHY: Stop accepting responses.

        Args:
            survey_id: Survey ID
            org_id: Organization ID

        Returns:
            Updated survey
        """
        survey = await self.get_by_id_and_org(survey_id, org_id)
        if not survey:
            return None

        survey.status = SurveyStatus.CLOSED.value

        await self.session.flush()
        await self.session.refresh(survey)
        return survey

    async def get_response_count(
        self,
        survey_id: int,
    ) -> int:
        """
        Get number of responses for a survey.

        WHAT: Counts completed responses.

        WHY: Display response metrics.

        Args:
            survey_id: Survey ID

        Returns:
            Response count
        """
        result = await self.session.execute(
            select(func.count(SurveyResponse.id)).where(
                SurveyResponse.survey_id == survey_id,
                SurveyResponse.is_complete == True,
            )
        )
        return result.scalar() or 0


class SurveyResponseDAO(BaseDAO[SurveyResponse]):
    """
    Data Access Object for SurveyResponse model.

    WHAT: Provides operations for survey responses.

    WHY: Centralizes response collection and analysis.

    HOW: Extends BaseDAO with response-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize SurveyResponseDAO."""
        super().__init__(SurveyResponse, session)

    async def get_survey_responses(
        self,
        survey_id: int,
        org_id: int,
        is_complete: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[SurveyResponse]:
        """
        Get responses for a survey.

        WHAT: Lists survey responses.

        WHY: View and analyze feedback.

        Args:
            survey_id: Survey ID
            org_id: Organization ID
            is_complete: Optional completion filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of responses
        """
        query = (
            select(SurveyResponse)
            .where(
                SurveyResponse.survey_id == survey_id,
                SurveyResponse.org_id == org_id,
            )
            .options(selectinload(SurveyResponse.respondent))
        )

        if is_complete is not None:
            query = query.where(SurveyResponse.is_complete == is_complete)

        query = query.order_by(SurveyResponse.created_at.desc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_user_response(
        self,
        survey_id: int,
        user_id: int,
    ) -> Optional[SurveyResponse]:
        """
        Get user's response to a survey.

        WHAT: Finds existing response.

        WHY: Check if user has responded.

        Args:
            survey_id: Survey ID
            user_id: User ID

        Returns:
            Response if exists
        """
        result = await self.session.execute(
            select(SurveyResponse).where(
                SurveyResponse.survey_id == survey_id,
                SurveyResponse.respondent_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def submit_response(
        self,
        response_id: int,
    ) -> Optional[SurveyResponse]:
        """
        Mark response as complete.

        WHAT: Finalizes a response.

        WHY: Track completion.

        Args:
            response_id: Response ID

        Returns:
            Updated response
        """
        response = await self.get_by_id(response_id)
        if not response:
            return None

        response.is_complete = True
        response.completed_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(response)
        return response

    async def update_answers(
        self,
        response_id: int,
        answers: Dict[str, Any],
    ) -> Optional[SurveyResponse]:
        """
        Update response answers.

        WHAT: Saves answer data.

        WHY: Allow partial saves.

        Args:
            response_id: Response ID
            answers: Answer data

        Returns:
            Updated response
        """
        response = await self.get_by_id(response_id)
        if not response:
            return None

        # Merge with existing answers
        current = response.answers or {}
        current.update(answers)
        response.answers = current

        await self.session.flush()
        await self.session.refresh(response)
        return response

    async def calculate_nps(
        self,
        survey_id: int,
        org_id: int,
    ) -> Dict[str, Any]:
        """
        Calculate NPS for a survey.

        WHAT: Computes Net Promoter Score.

        WHY: Standard satisfaction metric.

        Args:
            survey_id: Survey ID
            org_id: Organization ID

        Returns:
            NPS data including score and distribution
        """
        # Get all complete responses
        responses = await self.get_survey_responses(
            survey_id=survey_id,
            org_id=org_id,
            is_complete=True,
            skip=0,
            limit=10000,
        )

        if not responses:
            return {
                "score": None,
                "promoters": 0,
                "passives": 0,
                "detractors": 0,
                "response_count": 0,
            }

        promoters = 0
        passives = 0
        detractors = 0

        for response in responses:
            answers = response.answers or {}
            # Find NPS question answer
            for key, value in answers.items():
                if isinstance(value, (int, float)) and 0 <= value <= 10:
                    if value >= 9:
                        promoters += 1
                    elif value >= 7:
                        passives += 1
                    else:
                        detractors += 1
                    break

        total = promoters + passives + detractors
        if total == 0:
            return {
                "score": None,
                "promoters": 0,
                "passives": 0,
                "detractors": 0,
                "response_count": 0,
            }

        nps_score = ((promoters - detractors) / total) * 100

        return {
            "score": round(nps_score, 1),
            "promoters": promoters,
            "passives": passives,
            "detractors": detractors,
            "response_count": total,
        }

    async def calculate_average_rating(
        self,
        survey_id: int,
        org_id: int,
        question_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate average rating for a survey or question.

        WHAT: Computes mean rating score.

        WHY: CSAT and other rating metrics.

        Args:
            survey_id: Survey ID
            org_id: Organization ID
            question_id: Optional specific question

        Returns:
            Average and distribution data
        """
        responses = await self.get_survey_responses(
            survey_id=survey_id,
            org_id=org_id,
            is_complete=True,
            skip=0,
            limit=10000,
        )

        if not responses:
            return {
                "average": None,
                "min": None,
                "max": None,
                "response_count": 0,
                "distribution": {},
            }

        ratings = []
        distribution: Dict[int, int] = {}

        for response in responses:
            answers = response.answers or {}
            if question_id:
                value = answers.get(question_id)
                if isinstance(value, (int, float)):
                    ratings.append(value)
                    distribution[int(value)] = distribution.get(int(value), 0) + 1
            else:
                # Find first rating question
                for value in answers.values():
                    if isinstance(value, (int, float)) and 1 <= value <= 10:
                        ratings.append(value)
                        distribution[int(value)] = distribution.get(int(value), 0) + 1
                        break

        if not ratings:
            return {
                "average": None,
                "min": None,
                "max": None,
                "response_count": 0,
                "distribution": {},
            }

        return {
            "average": round(sum(ratings) / len(ratings), 2),
            "min": min(ratings),
            "max": max(ratings),
            "response_count": len(ratings),
            "distribution": distribution,
        }


class SurveyInvitationDAO(BaseDAO[SurveyInvitation]):
    """
    Data Access Object for SurveyInvitation model.

    WHAT: Provides operations for survey invitations.

    WHY: Track survey distribution.

    HOW: Extends BaseDAO with invitation-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize SurveyInvitationDAO."""
        super().__init__(SurveyInvitation, session)

    async def create_invitation(
        self,
        org_id: int,
        survey_id: int,
        user_id: int,
    ) -> SurveyInvitation:
        """
        Create a survey invitation.

        WHAT: Creates invitation with unique token.

        WHY: Allow anonymous survey access.

        Args:
            org_id: Organization ID
            survey_id: Survey ID
            user_id: User ID

        Returns:
            Created invitation
        """
        token = secrets.token_urlsafe(32)

        invitation = SurveyInvitation(
            org_id=org_id,
            survey_id=survey_id,
            user_id=user_id,
            token=token,
        )

        self.session.add(invitation)
        await self.session.flush()
        await self.session.refresh(invitation)
        return invitation

    async def get_by_token(
        self,
        token: str,
    ) -> Optional[SurveyInvitation]:
        """
        Get invitation by token.

        WHAT: Finds invitation for anonymous access.

        WHY: Validate survey access.

        Args:
            token: Invitation token

        Returns:
            Invitation if exists
        """
        result = await self.session.execute(
            select(SurveyInvitation)
            .where(SurveyInvitation.token == token)
            .options(
                selectinload(SurveyInvitation.survey),
                selectinload(SurveyInvitation.user),
            )
        )
        return result.scalar_one_or_none()

    async def mark_sent(
        self,
        invitation_id: int,
    ) -> Optional[SurveyInvitation]:
        """
        Mark invitation as sent.

        WHAT: Records email sent time.

        WHY: Track distribution.

        Args:
            invitation_id: Invitation ID

        Returns:
            Updated invitation
        """
        invitation = await self.get_by_id(invitation_id)
        if not invitation:
            return None

        invitation.sent_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(invitation)
        return invitation

    async def mark_opened(
        self,
        invitation_id: int,
    ) -> Optional[SurveyInvitation]:
        """
        Mark invitation as opened.

        WHAT: Records first open time.

        WHY: Track engagement.

        Args:
            invitation_id: Invitation ID

        Returns:
            Updated invitation
        """
        invitation = await self.get_by_id(invitation_id)
        if not invitation:
            return None

        if not invitation.opened_at:
            invitation.opened_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(invitation)
        return invitation

    async def link_response(
        self,
        invitation_id: int,
        response_id: int,
    ) -> Optional[SurveyInvitation]:
        """
        Link invitation to response.

        WHAT: Associates response with invitation.

        WHY: Track response rates.

        Args:
            invitation_id: Invitation ID
            response_id: Response ID

        Returns:
            Updated invitation
        """
        invitation = await self.get_by_id(invitation_id)
        if not invitation:
            return None

        invitation.response_id = response_id
        invitation.responded_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(invitation)
        return invitation

    async def get_survey_invitations(
        self,
        survey_id: int,
        org_id: int,
        responded_only: bool = False,
    ) -> List[SurveyInvitation]:
        """
        Get invitations for a survey.

        WHAT: Lists all invitations.

        WHY: Track response rates.

        Args:
            survey_id: Survey ID
            org_id: Organization ID
            responded_only: Filter to responded only

        Returns:
            List of invitations
        """
        query = (
            select(SurveyInvitation)
            .where(
                SurveyInvitation.survey_id == survey_id,
                SurveyInvitation.org_id == org_id,
            )
            .options(selectinload(SurveyInvitation.user))
        )

        if responded_only:
            query = query.where(SurveyInvitation.responded_at.isnot(None))

        result = await self.session.execute(query.order_by(SurveyInvitation.created_at.desc()))
        return list(result.scalars().all())


class FeedbackScoreDAO(BaseDAO[FeedbackScore]):
    """
    Data Access Object for FeedbackScore model.

    WHAT: Provides operations for aggregated scores.

    WHY: Efficient analytics queries.

    HOW: Stores pre-computed period scores.
    """

    def __init__(self, session: AsyncSession):
        """Initialize FeedbackScoreDAO."""
        super().__init__(FeedbackScore, session)

    async def get_latest_score(
        self,
        org_id: int,
        score_type: str,
        project_id: Optional[int] = None,
    ) -> Optional[FeedbackScore]:
        """
        Get most recent score.

        WHAT: Finds latest aggregated score.

        WHY: Display current metrics.

        Args:
            org_id: Organization ID
            score_type: Score type (nps, csat, ces)
            project_id: Optional project filter

        Returns:
            Latest score if exists
        """
        query = (
            select(FeedbackScore)
            .where(
                FeedbackScore.org_id == org_id,
                FeedbackScore.score_type == score_type,
            )
        )

        if project_id:
            query = query.where(FeedbackScore.project_id == project_id)

        query = query.order_by(FeedbackScore.period_end.desc())

        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_score_history(
        self,
        org_id: int,
        score_type: str,
        project_id: Optional[int] = None,
        periods: int = 12,
    ) -> List[FeedbackScore]:
        """
        Get score history.

        WHAT: Lists historical scores.

        WHY: Trend analysis.

        Args:
            org_id: Organization ID
            score_type: Score type
            project_id: Optional project filter
            periods: Number of periods

        Returns:
            List of scores
        """
        query = (
            select(FeedbackScore)
            .where(
                FeedbackScore.org_id == org_id,
                FeedbackScore.score_type == score_type,
            )
        )

        if project_id:
            query = query.where(FeedbackScore.project_id == project_id)

        query = query.order_by(FeedbackScore.period_end.desc()).limit(periods)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def upsert_score(
        self,
        org_id: int,
        score_type: str,
        period_start: datetime,
        period_end: datetime,
        score: float,
        response_count: int,
        project_id: Optional[int] = None,
        promoters: Optional[int] = None,
        passives: Optional[int] = None,
        detractors: Optional[int] = None,
    ) -> FeedbackScore:
        """
        Create or update a score.

        WHAT: Saves aggregated score.

        WHY: Store pre-computed metrics.

        Args:
            org_id: Organization ID
            score_type: Score type
            period_start: Period start
            period_end: Period end
            score: Computed score
            response_count: Number of responses
            project_id: Optional project ID
            promoters: NPS promoters count
            passives: NPS passives count
            detractors: NPS detractors count

        Returns:
            Created or updated score
        """
        # Check for existing
        query = (
            select(FeedbackScore)
            .where(
                FeedbackScore.org_id == org_id,
                FeedbackScore.score_type == score_type,
                FeedbackScore.period_start == period_start,
                FeedbackScore.period_end == period_end,
            )
        )

        if project_id:
            query = query.where(FeedbackScore.project_id == project_id)

        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.score = score
            existing.response_count = response_count
            existing.promoters = promoters
            existing.passives = passives
            existing.detractors = detractors
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        # Create new
        feedback_score = FeedbackScore(
            org_id=org_id,
            score_type=score_type,
            period_start=period_start,
            period_end=period_end,
            score=score,
            response_count=response_count,
            project_id=project_id,
            promoters=promoters,
            passives=passives,
            detractors=detractors,
        )

        self.session.add(feedback_score)
        await self.session.flush()
        await self.session.refresh(feedback_score)
        return feedback_score
