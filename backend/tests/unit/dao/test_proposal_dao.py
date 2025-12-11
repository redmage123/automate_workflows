"""
Unit tests for Proposal DAO.

WHAT: Tests for ProposalDAO database operations.

WHY: Verifies that:
1. Proposal CRUD operations work correctly
2. Org-scoping is enforced (multi-tenancy security)
3. Workflow operations (send, view, approve, reject) work properly
4. Status transitions handle timestamps correctly
5. Version management works for revisions
6. Query methods filter and paginate correctly

HOW: Uses pytest-asyncio with in-memory SQLite database for isolation.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from app.dao.proposal import ProposalDAO
from app.models.proposal import Proposal, ProposalStatus
from tests.factories import (
    OrganizationFactory,
    ProjectFactory,
    ProposalFactory,
)


class TestProposalDAOCreate:
    """Tests for proposal creation."""

    @pytest.mark.asyncio
    async def test_create_proposal_success(self, db_session, test_org):
        """Test creating a proposal with all required fields."""
        # Create a project first
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        proposal_dao = ProposalDAO(db_session)

        proposal = await proposal_dao.create(
            title="Test Proposal",
            description="Test description",
            project_id=project.id,
            org_id=test_org.id,
            line_items=[
                {"description": "Item 1", "quantity": 1, "unit_price": 100, "amount": 100}
            ],
            subtotal=100,
            total=100,
        )

        assert proposal.id is not None
        assert proposal.title == "Test Proposal"
        assert proposal.description == "Test description"
        assert proposal.status == ProposalStatus.DRAFT
        assert proposal.project_id == project.id
        assert proposal.org_id == test_org.id
        assert proposal.version == 1
        assert proposal.created_at is not None

    @pytest.mark.asyncio
    async def test_create_proposal_with_pricing(self, db_session, test_org):
        """Test creating a proposal with discount and tax."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        proposal_dao = ProposalDAO(db_session)

        proposal = await proposal_dao.create(
            title="Priced Proposal",
            project_id=project.id,
            org_id=test_org.id,
            line_items=[
                {"description": "Dev", "quantity": 10, "unit_price": 100, "amount": 1000}
            ],
            subtotal=1000,
            discount_percent=10,
            discount_amount=100,
            tax_percent=8,
            tax_amount=72,
            total=972,
        )

        assert proposal.subtotal == Decimal("1000")
        assert proposal.discount_percent == Decimal("10")
        assert proposal.discount_amount == Decimal("100")
        assert proposal.tax_percent == Decimal("8")
        assert proposal.tax_amount == Decimal("72")
        assert proposal.total == Decimal("972")

    @pytest.mark.asyncio
    async def test_create_proposal_with_validity(self, db_session, test_org):
        """Test creating a proposal with expiration date."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        proposal_dao = ProposalDAO(db_session)
        valid_until = datetime.utcnow() + timedelta(days=30)

        proposal = await proposal_dao.create(
            title="Time-Limited Proposal",
            project_id=project.id,
            org_id=test_org.id,
            valid_until=valid_until,
            subtotal=0,
            total=0,
        )

        assert proposal.valid_until is not None


class TestProposalDAORead:
    """Tests for proposal read operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_and_org_success(self, db_session, test_org):
        """Test retrieving a proposal by ID with org-scoping."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Findable Proposal", project=project
        )

        proposal_dao = ProposalDAO(db_session)
        found = await proposal_dao.get_by_id_and_org(proposal.id, test_org.id)

        assert found is not None
        assert found.id == proposal.id
        assert found.title == "Findable Proposal"

    @pytest.mark.asyncio
    async def test_get_by_id_and_org_wrong_org(self, db_session):
        """Test that org-scoping prevents cross-org access."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        project = await ProjectFactory.create(
            db_session, name="Org1 Project", organization=org1
        )
        proposal = await ProposalFactory.create(
            db_session, title="Org1 Proposal", project=project
        )

        proposal_dao = ProposalDAO(db_session)
        # Try to access from wrong org
        found = await proposal_dao.get_by_id_and_org(proposal.id, org2.id)

        assert found is None  # Should not find proposal from other org

    @pytest.mark.asyncio
    async def test_get_by_project(self, db_session, test_org):
        """Test listing proposals by project."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        # Create multiple proposals for same project
        await ProposalFactory.create(db_session, title="Proposal 1", project=project)
        await ProposalFactory.create(db_session, title="Proposal 2", project=project)
        await ProposalFactory.create(db_session, title="Proposal 3", project=project)

        proposal_dao = ProposalDAO(db_session)
        proposals = await proposal_dao.get_by_project(project.id, test_org.id)

        assert len(proposals) == 3

    @pytest.mark.asyncio
    async def test_get_by_project_pagination(self, db_session, test_org):
        """Test pagination for proposal listing."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        # Create 5 proposals
        for i in range(5):
            await ProposalFactory.create(
                db_session, title=f"Proposal {i}", project=project
            )

        proposal_dao = ProposalDAO(db_session)

        # Get first page
        page1 = await proposal_dao.get_by_project(project.id, test_org.id, skip=0, limit=2)
        assert len(page1) == 2

        # Get second page
        page2 = await proposal_dao.get_by_project(project.id, test_org.id, skip=2, limit=2)
        assert len(page2) == 2

        # Get remaining
        page3 = await proposal_dao.get_by_project(project.id, test_org.id, skip=4, limit=2)
        assert len(page3) == 1


class TestProposalDAOStatusFilters:
    """Tests for status-based filtering."""

    @pytest.mark.asyncio
    async def test_get_by_status(self, db_session, test_org):
        """Test filtering proposals by status."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        # Create proposals with different statuses
        await ProposalFactory.create(
            db_session, title="Draft", status=ProposalStatus.DRAFT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Sent", status=ProposalStatus.SENT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Approved", status=ProposalStatus.APPROVED, project=project
        )

        proposal_dao = ProposalDAO(db_session)

        # Get only sent proposals
        sent = await proposal_dao.get_by_status(test_org.id, ProposalStatus.SENT)

        assert len(sent) == 1
        assert sent[0].title == "Sent"

    @pytest.mark.asyncio
    async def test_get_pending_proposals(self, db_session, test_org):
        """Test getting proposals awaiting client action."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        await ProposalFactory.create(
            db_session, title="Draft", status=ProposalStatus.DRAFT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Sent", status=ProposalStatus.SENT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Viewed", status=ProposalStatus.VIEWED, project=project
        )
        await ProposalFactory.create(
            db_session, title="Approved", status=ProposalStatus.APPROVED, project=project
        )

        proposal_dao = ProposalDAO(db_session)
        pending = await proposal_dao.get_pending_proposals(test_org.id)

        assert len(pending) == 2  # Sent + Viewed
        titles = {p.title for p in pending}
        assert titles == {"Sent", "Viewed"}

    @pytest.mark.asyncio
    async def test_get_latest_for_project(self, db_session, test_org):
        """Test getting the latest version of a proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        proposal_dao = ProposalDAO(db_session)

        # Create v1
        await proposal_dao.create(
            title="Proposal v1",
            project_id=project.id,
            org_id=test_org.id,
            version=1,
            subtotal=0,
            total=0,
        )

        # Create v2
        await proposal_dao.create(
            title="Proposal v2",
            project_id=project.id,
            org_id=test_org.id,
            version=2,
            subtotal=0,
            total=0,
        )

        # Create v3
        await proposal_dao.create(
            title="Proposal v3",
            project_id=project.id,
            org_id=test_org.id,
            version=3,
            subtotal=0,
            total=0,
        )

        latest = await proposal_dao.get_latest_for_project(project.id, test_org.id)

        assert latest is not None
        assert latest.version == 3
        assert latest.title == "Proposal v3"

    @pytest.mark.asyncio
    async def test_get_approved_for_project(self, db_session, test_org):
        """Test getting approved proposal for a project."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        # Create draft and approved proposals
        await ProposalFactory.create(
            db_session, title="Draft", status=ProposalStatus.DRAFT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Approved", status=ProposalStatus.APPROVED, project=project
        )

        proposal_dao = ProposalDAO(db_session)
        approved = await proposal_dao.get_approved_for_project(project.id, test_org.id)

        assert approved is not None
        assert approved.title == "Approved"
        assert approved.status == ProposalStatus.APPROVED


class TestProposalDAOWorkflow:
    """Tests for proposal workflow operations."""

    @pytest.mark.asyncio
    async def test_send_proposal_success(self, db_session, test_org):
        """Test sending a draft proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session, title="To Send", status=ProposalStatus.DRAFT, project=project
        )
        assert proposal.sent_at is None

        proposal_dao = ProposalDAO(db_session)
        sent = await proposal_dao.send_proposal(proposal.id, test_org.id)

        assert sent is not None
        assert sent.status == ProposalStatus.SENT
        assert sent.sent_at is not None

    @pytest.mark.asyncio
    async def test_send_proposal_invalid_status(self, db_session, test_org):
        """Test that only draft proposals can be sent."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Already Sent", status=ProposalStatus.SENT, project=project
        )

        proposal_dao = ProposalDAO(db_session)
        result = await proposal_dao.send_proposal(proposal.id, test_org.id)

        assert result is None  # Should fail - already sent

    @pytest.mark.asyncio
    async def test_mark_viewed_success(self, db_session, test_org):
        """Test marking a sent proposal as viewed."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session, title="To View", status=ProposalStatus.SENT, project=project
        )
        # Manually set sent_at
        proposal.sent_at = datetime.utcnow()
        await db_session.flush()

        proposal_dao = ProposalDAO(db_session)
        viewed = await proposal_dao.mark_viewed(proposal.id, test_org.id)

        assert viewed is not None
        assert viewed.status == ProposalStatus.VIEWED
        assert viewed.viewed_at is not None

    @pytest.mark.asyncio
    async def test_mark_viewed_invalid_status(self, db_session, test_org):
        """Test that only sent proposals can be marked as viewed."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Draft", status=ProposalStatus.DRAFT, project=project
        )

        proposal_dao = ProposalDAO(db_session)
        result = await proposal_dao.mark_viewed(proposal.id, test_org.id)

        assert result is None  # Should fail - not sent yet

    @pytest.mark.asyncio
    async def test_approve_proposal_from_sent(self, db_session, test_org):
        """Test approving a sent proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session,
            title="To Approve",
            status=ProposalStatus.SENT,
            project=project,
        )
        # Set valid_until to future
        proposal.valid_until = datetime.utcnow() + timedelta(days=30)
        await db_session.flush()

        proposal_dao = ProposalDAO(db_session)
        approved = await proposal_dao.approve_proposal(proposal.id, test_org.id)

        assert approved is not None
        assert approved.status == ProposalStatus.APPROVED
        assert approved.approved_at is not None

    @pytest.mark.asyncio
    async def test_approve_proposal_from_viewed(self, db_session, test_org):
        """Test approving a viewed proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session,
            title="To Approve",
            status=ProposalStatus.VIEWED,
            project=project,
        )
        # Set valid_until to future
        proposal.valid_until = datetime.utcnow() + timedelta(days=30)
        await db_session.flush()

        proposal_dao = ProposalDAO(db_session)
        approved = await proposal_dao.approve_proposal(proposal.id, test_org.id)

        assert approved is not None
        assert approved.status == ProposalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_approve_expired_proposal_fails(self, db_session, test_org):
        """Test that expired proposals cannot be approved."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session,
            title="Expired",
            status=ProposalStatus.SENT,
            project=project,
        )
        # Set valid_until to past
        proposal.valid_until = datetime.utcnow() - timedelta(days=1)
        await db_session.flush()

        proposal_dao = ProposalDAO(db_session)
        result = await proposal_dao.approve_proposal(proposal.id, test_org.id)

        assert result is None  # Should fail - expired

    @pytest.mark.asyncio
    async def test_approve_draft_proposal_fails(self, db_session, test_org):
        """Test that draft proposals cannot be approved."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session,
            title="Draft",
            status=ProposalStatus.DRAFT,
            project=project,
        )

        proposal_dao = ProposalDAO(db_session)
        result = await proposal_dao.approve_proposal(proposal.id, test_org.id)

        assert result is None  # Should fail - not sent yet

    @pytest.mark.asyncio
    async def test_reject_proposal_success(self, db_session, test_org):
        """Test rejecting a proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session,
            title="To Reject",
            status=ProposalStatus.VIEWED,
            project=project,
        )

        proposal_dao = ProposalDAO(db_session)
        rejected = await proposal_dao.reject_proposal(
            proposal.id, test_org.id, reason="Too expensive"
        )

        assert rejected is not None
        assert rejected.status == ProposalStatus.REJECTED
        assert rejected.rejected_at is not None
        assert rejected.rejection_reason == "Too expensive"

    @pytest.mark.asyncio
    async def test_reject_proposal_from_sent(self, db_session, test_org):
        """Test rejecting a sent proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session,
            title="To Reject",
            status=ProposalStatus.SENT,
            project=project,
        )

        proposal_dao = ProposalDAO(db_session)
        rejected = await proposal_dao.reject_proposal(proposal.id, test_org.id)

        assert rejected is not None
        assert rejected.status == ProposalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_reject_draft_proposal_fails(self, db_session, test_org):
        """Test that draft proposals cannot be rejected."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session,
            title="Draft",
            status=ProposalStatus.DRAFT,
            project=project,
        )

        proposal_dao = ProposalDAO(db_session)
        result = await proposal_dao.reject_proposal(proposal.id, test_org.id)

        assert result is None  # Should fail - not sent yet


class TestProposalDAORevisions:
    """Tests for proposal revision operations."""

    @pytest.mark.asyncio
    async def test_create_revision_success(self, db_session, test_org):
        """Test creating a new revision of a proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        original = await ProposalFactory.create(
            db_session,
            title="Original Proposal",
            status=ProposalStatus.REJECTED,
            project=project,
        )
        assert original.version == 1

        proposal_dao = ProposalDAO(db_session)
        revision = await proposal_dao.create_revision(
            original.id,
            test_org.id,
            updates={
                "title": "Revised Proposal",
                "description": "Updated scope",
            },
        )

        assert revision is not None
        assert revision.title == "Revised Proposal"
        assert revision.description == "Updated scope"
        assert revision.version == 2
        assert revision.previous_version_id == original.id
        assert revision.status == ProposalStatus.DRAFT

        # Original should be marked as revised
        await db_session.refresh(original)
        assert original.status == ProposalStatus.REVISED

    @pytest.mark.asyncio
    async def test_create_revision_inherits_values(self, db_session, test_org):
        """Test that revision inherits values from original."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        original = await ProposalFactory.create(
            db_session,
            title="Original",
            project=project,
        )

        proposal_dao = ProposalDAO(db_session)
        revision = await proposal_dao.create_revision(
            original.id,
            test_org.id,
            updates={},  # No updates - inherit everything
        )

        assert revision is not None
        assert revision.title == original.title
        assert revision.line_items == original.line_items
        assert revision.project_id == original.project_id

    @pytest.mark.asyncio
    async def test_create_revision_wrong_org(self, db_session):
        """Test that revision fails for wrong org."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        project = await ProjectFactory.create(
            db_session, name="Org1 Project", organization=org1
        )
        proposal = await ProposalFactory.create(
            db_session, title="Org1 Proposal", project=project
        )

        proposal_dao = ProposalDAO(db_session)
        result = await proposal_dao.create_revision(
            proposal.id,
            org2.id,  # Wrong org
            updates={"title": "Hacked"},
        )

        assert result is None  # Should fail


class TestProposalDAOExpiration:
    """Tests for expiration-related queries."""

    @pytest.mark.asyncio
    async def test_get_expiring_soon(self, db_session, test_org):
        """Test getting proposals expiring within N days."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        proposal_dao = ProposalDAO(db_session)

        # Create proposal expiring in 3 days (should be found with days=7)
        expiring_soon = await proposal_dao.create(
            title="Expiring Soon",
            project_id=project.id,
            org_id=test_org.id,
            status=ProposalStatus.SENT,
            valid_until=datetime.utcnow() + timedelta(days=3),
            subtotal=0,
            total=0,
        )

        # Create proposal expiring in 10 days (should NOT be found with days=7)
        await proposal_dao.create(
            title="Expiring Later",
            project_id=project.id,
            org_id=test_org.id,
            status=ProposalStatus.SENT,
            valid_until=datetime.utcnow() + timedelta(days=10),
            subtotal=0,
            total=0,
        )

        # Create already expired proposal (should NOT be found)
        await proposal_dao.create(
            title="Already Expired",
            project_id=project.id,
            org_id=test_org.id,
            status=ProposalStatus.SENT,
            valid_until=datetime.utcnow() - timedelta(days=1),
            subtotal=0,
            total=0,
        )

        # Create draft proposal (should NOT be found - wrong status)
        await proposal_dao.create(
            title="Draft",
            project_id=project.id,
            org_id=test_org.id,
            status=ProposalStatus.DRAFT,
            valid_until=datetime.utcnow() + timedelta(days=3),
            subtotal=0,
            total=0,
        )

        expiring = await proposal_dao.get_expiring_soon(test_org.id, days=7)

        assert len(expiring) == 1
        assert expiring[0].title == "Expiring Soon"


class TestProposalDAOTotals:
    """Tests for total value calculations."""

    @pytest.mark.asyncio
    async def test_calculate_total_value_all(self, db_session, test_org):
        """Test calculating total value of all proposals."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        proposal_dao = ProposalDAO(db_session)

        await proposal_dao.create(
            title="Proposal 1",
            project_id=project.id,
            org_id=test_org.id,
            subtotal=1000,
            total=1000,
        )
        await proposal_dao.create(
            title="Proposal 2",
            project_id=project.id,
            org_id=test_org.id,
            subtotal=2000,
            total=2000,
        )

        total = await proposal_dao.calculate_total_value(test_org.id)

        assert total == Decimal("3000")

    @pytest.mark.asyncio
    async def test_calculate_total_value_by_status(self, db_session, test_org):
        """Test calculating total value filtered by status."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        proposal_dao = ProposalDAO(db_session)

        await proposal_dao.create(
            title="Draft",
            project_id=project.id,
            org_id=test_org.id,
            status=ProposalStatus.DRAFT,
            subtotal=1000,
            total=1000,
        )
        await proposal_dao.create(
            title="Approved",
            project_id=project.id,
            org_id=test_org.id,
            status=ProposalStatus.APPROVED,
            subtotal=5000,
            total=5000,
        )

        # Only approved
        approved_total = await proposal_dao.calculate_total_value(
            test_org.id, status=ProposalStatus.APPROVED
        )

        assert approved_total == Decimal("5000")


class TestProposalDAOCounts:
    """Tests for count operations."""

    @pytest.mark.asyncio
    async def test_count_by_status(self, db_session, test_org):
        """Test counting proposals by status."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )

        await ProposalFactory.create(
            db_session, title="Draft 1", status=ProposalStatus.DRAFT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Draft 2", status=ProposalStatus.DRAFT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Sent", status=ProposalStatus.SENT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Approved", status=ProposalStatus.APPROVED, project=project
        )

        proposal_dao = ProposalDAO(db_session)
        counts = await proposal_dao.count_by_status(test_org.id)

        assert counts.get("draft") == 2
        assert counts.get("sent") == 1
        assert counts.get("approved") == 1


class TestProposalDAOLineItems:
    """Tests for line item operations."""

    @pytest.mark.asyncio
    async def test_update_line_items_success(self, db_session, test_org):
        """Test updating line items and recalculating totals."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session, title="To Update", status=ProposalStatus.DRAFT, project=project
        )

        new_line_items = [
            {"description": "New Item 1", "quantity": 2, "unit_price": 500, "amount": 1000},
            {"description": "New Item 2", "quantity": 1, "unit_price": 250, "amount": 250},
        ]

        proposal_dao = ProposalDAO(db_session)
        updated = await proposal_dao.update_line_items(
            proposal.id, test_org.id, new_line_items
        )

        assert updated is not None
        assert len(updated.line_items) == 2
        assert updated.subtotal == Decimal("1250")

    @pytest.mark.asyncio
    async def test_update_line_items_non_draft_fails(self, db_session, test_org):
        """Test that line items can only be updated on draft proposals."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Sent", status=ProposalStatus.SENT, project=project
        )

        proposal_dao = ProposalDAO(db_session)
        result = await proposal_dao.update_line_items(
            proposal.id, test_org.id, [{"description": "Test", "amount": 100}]
        )

        assert result is None  # Should fail - not editable


class TestProposalDAODelete:
    """Tests for proposal deletion."""

    @pytest.mark.asyncio
    async def test_delete_proposal(self, db_session, test_org):
        """Test deleting a proposal."""
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=test_org
        )
        proposal = await ProposalFactory.create(
            db_session, title="To Delete", project=project
        )

        proposal_dao = ProposalDAO(db_session)
        result = await proposal_dao.delete(proposal.id)

        assert result is True

        # Verify deleted
        found = await proposal_dao.get_by_id(proposal.id)
        assert found is None


class TestProposalDAOMultiTenancy:
    """Tests for multi-tenancy isolation."""

    @pytest.mark.asyncio
    async def test_proposals_isolated_by_org(self, db_session):
        """Test that proposals from different orgs are isolated."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        project1 = await ProjectFactory.create(
            db_session, name="Org1 Project", organization=org1
        )
        project2 = await ProjectFactory.create(
            db_session, name="Org2 Project", organization=org2
        )

        # Create proposals in each org
        await ProposalFactory.create(
            db_session, title="Org1 Proposal 1", project=project1
        )
        await ProposalFactory.create(
            db_session, title="Org1 Proposal 2", project=project1
        )
        await ProposalFactory.create(
            db_session, title="Org2 Proposal", project=project2
        )

        proposal_dao = ProposalDAO(db_session)

        # Verify isolation
        org1_proposals = await proposal_dao.get_by_project(project1.id, org1.id)
        org2_proposals = await proposal_dao.get_by_project(project2.id, org2.id)

        assert len(org1_proposals) == 2
        assert len(org2_proposals) == 1
        assert all(p.org_id == org1.id for p in org1_proposals)
        assert all(p.org_id == org2.id for p in org2_proposals)

    @pytest.mark.asyncio
    async def test_workflow_operations_respect_org(self, db_session):
        """Test that workflow operations respect org-scoping."""
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        project = await ProjectFactory.create(
            db_session, name="Org1 Project", organization=org1
        )
        proposal = await ProposalFactory.create(
            db_session, title="Org1 Proposal", status=ProposalStatus.DRAFT, project=project
        )

        proposal_dao = ProposalDAO(db_session)

        # Try to send from wrong org
        result = await proposal_dao.send_proposal(proposal.id, org2.id)
        assert result is None  # Should fail

        # Try to approve from wrong org
        result = await proposal_dao.approve_proposal(proposal.id, org2.id)
        assert result is None  # Should fail

        # Try to reject from wrong org
        result = await proposal_dao.reject_proposal(proposal.id, org2.id)
        assert result is None  # Should fail
