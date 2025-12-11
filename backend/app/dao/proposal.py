"""
Proposal Data Access Object (DAO).

WHAT: Database operations for the Proposal model.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides a consistent API for proposal operations
3. Enforces org-scoping for multi-tenancy
4. Encapsulates complex queries for proposal management

HOW: Extends BaseDAO with proposal-specific queries:
- Status-based filtering
- Project-based queries
- Approval workflow operations
- Version management
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.proposal import Proposal, ProposalStatus


class ProposalDAO(BaseDAO[Proposal]):
    """
    Data Access Object for Proposal model.

    WHAT: Provides CRUD and query operations for proposals.

    WHY: Centralizes all proposal database operations:
    - Enforces org_id scoping for security
    - Provides specialized proposal queries
    - Manages approval workflow

    HOW: Extends BaseDAO with proposal-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize ProposalDAO.

        Args:
            session: Async database session
        """
        super().__init__(Proposal, session)

    async def get_by_project(
        self,
        project_id: int,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Proposal]:
        """
        Get all proposals for a project.

        WHAT: Filter proposals by project.

        WHY: View all proposals for a specific project:
        - Compare versions
        - Track approval history

        Args:
            project_id: Project ID
            org_id: Organization ID for security
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of proposals for the project
        """
        result = await self.session.execute(
            select(Proposal)
            .where(
                Proposal.project_id == project_id,
                Proposal.org_id == org_id,
            )
            .order_by(Proposal.version.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_status(
        self,
        org_id: int,
        status: ProposalStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Proposal]:
        """
        Get proposals by status for an organization.

        WHAT: Filter proposals by their status.

        WHY: Common use case for dashboards:
        - "Show me pending proposals"
        - "What proposals need attention?"

        Args:
            org_id: Organization ID
            status: Proposal status to filter by
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of proposals matching the status
        """
        result = await self.session.execute(
            select(Proposal)
            .where(
                Proposal.org_id == org_id,
                Proposal.status == status,
            )
            .order_by(Proposal.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_proposals(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Proposal]:
        """
        Get proposals awaiting client action (sent or viewed).

        WHAT: Filter proposals in sent/viewed status.

        WHY: Track proposals waiting for client response.

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of pending proposals
        """
        result = await self.session.execute(
            select(Proposal)
            .where(
                Proposal.org_id == org_id,
                Proposal.status.in_([ProposalStatus.SENT, ProposalStatus.VIEWED]),
            )
            .order_by(Proposal.sent_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_for_project(
        self,
        project_id: int,
        org_id: int,
    ) -> Optional[Proposal]:
        """
        Get the latest version of a proposal for a project.

        WHAT: Find highest version number proposal.

        WHY: Often need to work with the current version:
        - Display latest quote to client
        - Create new revision from latest

        Args:
            project_id: Project ID
            org_id: Organization ID for security

        Returns:
            Latest proposal version or None
        """
        result = await self.session.execute(
            select(Proposal)
            .where(
                Proposal.project_id == project_id,
                Proposal.org_id == org_id,
            )
            .order_by(Proposal.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_approved_for_project(
        self,
        project_id: int,
        org_id: int,
    ) -> Optional[Proposal]:
        """
        Get the approved proposal for a project.

        WHAT: Find proposal in APPROVED status.

        WHY: Used for:
        - Invoice generation
        - Scope reference
        - Contract basis

        Args:
            project_id: Project ID
            org_id: Organization ID for security

        Returns:
            Approved proposal or None
        """
        result = await self.session.execute(
            select(Proposal)
            .where(
                Proposal.project_id == project_id,
                Proposal.org_id == org_id,
                Proposal.status == ProposalStatus.APPROVED,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def send_proposal(
        self,
        proposal_id: int,
        org_id: int,
    ) -> Optional[Proposal]:
        """
        Mark a proposal as sent to the client.

        WHAT: Transition status from DRAFT to SENT.

        WHY: Track when proposals are sent:
        - Audit trail
        - Trigger notifications
        - Calculate response time

        Args:
            proposal_id: Proposal ID
            org_id: Organization ID for security

        Returns:
            Updated proposal or None if not found/invalid state
        """
        proposal = await self.get_by_id_and_org(proposal_id, org_id)
        if not proposal:
            return None

        if proposal.status != ProposalStatus.DRAFT:
            return None  # Can only send draft proposals

        proposal.status = ProposalStatus.SENT
        proposal.sent_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(proposal)
        return proposal

    async def mark_viewed(
        self,
        proposal_id: int,
        org_id: int,
    ) -> Optional[Proposal]:
        """
        Mark a proposal as viewed by the client.

        WHAT: Transition status from SENT to VIEWED.

        WHY: Track client engagement:
        - Know client has seen the proposal
        - Time between view and decision

        Args:
            proposal_id: Proposal ID
            org_id: Organization ID for security

        Returns:
            Updated proposal or None if not found/invalid state
        """
        proposal = await self.get_by_id_and_org(proposal_id, org_id)
        if not proposal:
            return None

        if proposal.status != ProposalStatus.SENT:
            return None  # Can only mark sent proposals as viewed

        proposal.status = ProposalStatus.VIEWED
        proposal.viewed_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(proposal)
        return proposal

    async def approve_proposal(
        self,
        proposal_id: int,
        org_id: int,
    ) -> Optional[Proposal]:
        """
        Mark a proposal as approved by the client.

        WHAT: Transition status to APPROVED.

        WHY: Critical business event:
        - Triggers project status update
        - Enables invoice generation
        - Records agreement timestamp

        Args:
            proposal_id: Proposal ID
            org_id: Organization ID for security

        Returns:
            Updated proposal or None if not found/invalid state
        """
        proposal = await self.get_by_id_and_org(proposal_id, org_id)
        if not proposal:
            return None

        # Can only approve sent or viewed proposals
        if proposal.status not in [ProposalStatus.SENT, ProposalStatus.VIEWED]:
            return None

        # Check if not expired
        if proposal.valid_until and datetime.utcnow() > proposal.valid_until:
            return None  # Expired proposals cannot be approved

        proposal.status = ProposalStatus.APPROVED
        proposal.approved_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(proposal)
        return proposal

    async def reject_proposal(
        self,
        proposal_id: int,
        org_id: int,
        reason: Optional[str] = None,
    ) -> Optional[Proposal]:
        """
        Mark a proposal as rejected by the client.

        WHAT: Transition status to REJECTED.

        WHY: Track rejections for:
        - Understanding why proposals fail
        - Follow-up opportunities
        - Pricing adjustments

        Args:
            proposal_id: Proposal ID
            org_id: Organization ID for security
            reason: Optional rejection reason

        Returns:
            Updated proposal or None if not found/invalid state
        """
        proposal = await self.get_by_id_and_org(proposal_id, org_id)
        if not proposal:
            return None

        # Can only reject sent or viewed proposals
        if proposal.status not in [ProposalStatus.SENT, ProposalStatus.VIEWED]:
            return None

        proposal.status = ProposalStatus.REJECTED
        proposal.rejected_at = datetime.utcnow()
        proposal.rejection_reason = reason

        await self.session.flush()
        await self.session.refresh(proposal)
        return proposal

    async def create_revision(
        self,
        proposal_id: int,
        org_id: int,
        updates: Dict[str, Any],
    ) -> Optional[Proposal]:
        """
        Create a new revision of an existing proposal.

        WHAT: Copy proposal with incremented version.

        WHY: Track proposal changes:
        - Price adjustments
        - Scope changes
        - Client feedback incorporation

        Args:
            proposal_id: ID of proposal to revise
            org_id: Organization ID for security
            updates: Fields to update in the new version

        Returns:
            New proposal version or None if original not found
        """
        original = await self.get_by_id_and_org(proposal_id, org_id)
        if not original:
            return None

        # Mark original as revised
        original.status = ProposalStatus.REVISED

        # Create new version
        new_proposal = Proposal(
            title=updates.get('title', original.title),
            description=updates.get('description', original.description),
            status=ProposalStatus.DRAFT,
            project_id=original.project_id,
            org_id=org_id,
            version=original.version + 1,
            previous_version_id=original.id,
            line_items=updates.get('line_items', original.line_items),
            subtotal=updates.get('subtotal', original.subtotal),
            discount_percent=updates.get('discount_percent', original.discount_percent),
            discount_amount=updates.get('discount_amount', original.discount_amount),
            tax_percent=updates.get('tax_percent', original.tax_percent),
            tax_amount=updates.get('tax_amount', original.tax_amount),
            total=updates.get('total', original.total),
            valid_until=updates.get('valid_until', original.valid_until),
            notes=updates.get('notes', original.notes),
            client_notes=updates.get('client_notes', original.client_notes),
            terms=updates.get('terms', original.terms),
        )

        self.session.add(new_proposal)
        await self.session.flush()
        await self.session.refresh(new_proposal)
        return new_proposal

    async def count_by_status(self, org_id: int) -> dict:
        """
        Get count of proposals by status for an organization.

        WHAT: Aggregate proposal counts by status.

        WHY: Dashboard statistics.

        Args:
            org_id: Organization ID

        Returns:
            Dict mapping status to count
        """
        result = await self.session.execute(
            select(Proposal.status, func.count(Proposal.id))
            .where(Proposal.org_id == org_id)
            .group_by(Proposal.status)
        )

        return {row[0].value: row[1] for row in result.all()}

    async def get_expiring_soon(
        self,
        org_id: int,
        days: int = 7,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Proposal]:
        """
        Get proposals expiring within N days.

        WHAT: Find proposals with valid_until approaching.

        WHY: Proactive follow-up with clients.

        Args:
            org_id: Organization ID
            days: Days until expiration
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of expiring proposals
        """
        now = datetime.utcnow()
        from datetime import timedelta
        future = now + timedelta(days=days)

        result = await self.session.execute(
            select(Proposal)
            .where(
                Proposal.org_id == org_id,
                Proposal.valid_until >= now,
                Proposal.valid_until <= future,
                Proposal.status.in_([ProposalStatus.SENT, ProposalStatus.VIEWED]),
            )
            .order_by(Proposal.valid_until.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def calculate_total_value(
        self,
        org_id: int,
        status: Optional[ProposalStatus] = None,
    ) -> Decimal:
        """
        Calculate total value of proposals.

        WHAT: Sum of proposal totals.

        WHY: Business metrics:
        - Total pipeline value
        - Approved contract value

        Args:
            org_id: Organization ID
            status: Optional status filter

        Returns:
            Total value
        """
        query = select(func.coalesce(func.sum(Proposal.total), 0)).where(
            Proposal.org_id == org_id
        )

        if status:
            query = query.where(Proposal.status == status)

        result = await self.session.execute(query)
        return Decimal(str(result.scalar_one()))

    async def update_line_items(
        self,
        proposal_id: int,
        org_id: int,
        line_items: List[Dict[str, Any]],
    ) -> Optional[Proposal]:
        """
        Update a proposal's line items and recalculate totals.

        WHAT: Replace line items and recalculate pricing.

        WHY: Line item changes require total recalculation.

        Args:
            proposal_id: Proposal ID
            org_id: Organization ID for security
            line_items: New line items

        Returns:
            Updated proposal or None if not found/not editable
        """
        proposal = await self.get_by_id_and_org(proposal_id, org_id)
        if not proposal:
            return None

        if not proposal.is_editable:
            return None  # Can only edit draft proposals

        proposal.line_items = line_items
        proposal.calculate_totals()

        await self.session.flush()
        await self.session.refresh(proposal)
        return proposal
