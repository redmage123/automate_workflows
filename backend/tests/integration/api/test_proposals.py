"""
Integration tests for proposal management API.

WHAT: Tests for proposal CRUD and workflow operations via HTTP API.

WHY: Proposals are critical business documents. These tests ensure:
1. Only admins can create/modify proposals
2. Workflow transitions (send, view, approve, reject) work correctly
3. Org-scoping prevents cross-org access (OWASP A01)
4. Line item calculations are accurate
5. Revision handling works properly

HOW: Uses pytest-asyncio with AsyncClient for HTTP testing.
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import OrganizationFactory, UserFactory, ProjectFactory, ProposalFactory
from app.models.proposal import ProposalStatus


class TestProposalCreate:
    """Integration tests for proposal creation endpoint."""

    @pytest.mark.asyncio
    async def test_create_proposal_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test creating a proposal as ADMIN.

        WHY: Admins should be able to create proposals for projects.
        """
        # Create organization, admin, and project
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Create proposal
        response = await client.post(
            "/api/proposals",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "New Proposal",
                "description": "A test proposal",
                "project_id": project.id,
                "line_items": [
                    {"description": "Development", "quantity": 10, "unit_price": 100},
                    {"description": "Testing", "quantity": 5, "unit_price": 75},
                ],
                "discount_percent": 10,
                "tax_percent": 8,
                "valid_until": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Proposal"
        assert data["status"] == "draft"
        assert data["project_id"] == project.id
        assert data["version"] == 1
        assert len(data["line_items"]) == 2
        # Verify calculated totals
        assert data["subtotal"] == 1375  # 10*100 + 5*75
        assert data["discount_percent"] == 10
        assert data["tax_percent"] == 8
        assert "id" in data

    @pytest.mark.asyncio
    async def test_cannot_create_proposal_as_client(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that CLIENT users cannot create proposals.

        WHY: RBAC - only admins should create proposals.
        """
        # Create organization, client, and project
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to create proposal
        response = await client.post(
            "/api/proposals",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Unauthorized Proposal",
                "project_id": project.id,
                "line_items": [],
            },
        )

        # Should be forbidden
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_proposal_for_other_org_project_fails(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that admins cannot create proposals for other org's projects.

        WHY: Multi-tenancy security (OWASP A01).
        """
        # Create two organizations
        org1 = await OrganizationFactory.create(db_session, name="Company 1")
        org2 = await OrganizationFactory.create(db_session, name="Company 2")

        await UserFactory.create_admin(
            db_session,
            email="admin@org1.com",
            password="Password123!",
            organization=org1,
        )

        # Create project in org2
        project2 = await ProjectFactory.create(
            db_session, name="Org2 Project", organization=org2
        )

        # Login as admin from org1
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@org1.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to create proposal for org2's project
        response = await client.post(
            "/api/proposals",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Cross-org Proposal",
                "project_id": project2.id,
                "line_items": [],
            },
        )

        # Should fail - project not found in user's org
        assert response.status_code == 404


class TestProposalList:
    """Integration tests for proposal listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_proposals(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test listing proposals for current organization.

        WHY: Users need to browse proposals in their organization.
        """
        # Create organization, user, project, and proposals
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        await ProposalFactory.create(db_session, title="Proposal 1", project=project)
        await ProposalFactory.create(db_session, title="Proposal 2", project=project)

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # List proposals
        response = await client.get(
            "/api/proposals",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_proposals_filter_by_status(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test filtering proposals by status.

        WHY: Dashboard views need to filter proposals by status.
        """
        # Create organization, user, project, and proposals with different statuses
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        await ProposalFactory.create(
            db_session, title="Draft", status=ProposalStatus.DRAFT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Sent", status=ProposalStatus.SENT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Approved", status=ProposalStatus.APPROVED, project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Filter by sent status
        response = await client.get(
            "/api/proposals?status=sent",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Sent"

    @pytest.mark.asyncio
    async def test_list_proposals_filter_by_project(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test filtering proposals by project.

        WHY: Users need to see proposals for a specific project.
        """
        # Create organization, user, and projects
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project1 = await ProjectFactory.create(
            db_session, name="Project 1", organization=org
        )
        project2 = await ProjectFactory.create(
            db_session, name="Project 2", organization=org
        )
        await ProposalFactory.create(db_session, title="P1 Proposal", project=project1)
        await ProposalFactory.create(db_session, title="P2 Proposal", project=project2)

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Filter by project
        response = await client.get(
            f"/api/proposals?project_id={project1.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "P1 Proposal"


class TestProposalGet:
    """Integration tests for getting individual proposal."""

    @pytest.mark.asyncio
    async def test_get_proposal_by_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting a proposal by ID.

        WHY: Users need to view proposal details.
        """
        # Create organization, user, project, and proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Test Proposal", project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get proposal
        response = await client.get(
            f"/api/proposals/{proposal.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == proposal.id
        assert data["title"] == "Test Proposal"

    @pytest.mark.asyncio
    async def test_client_cannot_see_internal_notes(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that CLIENT users cannot see internal notes.

        WHY: Internal notes are for admin eyes only.
        """
        # Create organization, client, project, and proposal with notes
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session,
            title="Test Proposal",
            project=project,
            notes="SECRET INTERNAL NOTE",
            client_notes="Visible to client",
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get proposal
        response = await client.get(
            f"/api/proposals/{proposal.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify internal notes are hidden
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] is None  # Internal notes hidden for CLIENT
        assert data["client_notes"] == "Visible to client"


class TestProposalWorkflow:
    """Integration tests for proposal workflow operations."""

    @pytest.mark.asyncio
    async def test_send_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test sending a draft proposal.

        WHY: Proposals must be sent to clients for review.
        """
        # Create organization, admin, project, and draft proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Draft Proposal", status=ProposalStatus.DRAFT, project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Send proposal
        response = await client.post(
            f"/api/proposals/{proposal.id}/send",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        assert data["sent_at"] is not None

    @pytest.mark.asyncio
    async def test_view_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test marking a sent proposal as viewed.

        WHY: Track when clients view proposals.
        """
        # Create organization, user, project, and sent proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Sent Proposal", status=ProposalStatus.SENT, project=project
        )
        # Set sent_at
        proposal.sent_at = datetime.utcnow()
        await db_session.flush()

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # View proposal
        response = await client.post(
            f"/api/proposals/{proposal.id}/view",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "viewed"
        assert data["viewed_at"] is not None

    @pytest.mark.asyncio
    async def test_approve_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test approving a viewed proposal.

        WHY: Clients approve proposals to start work.
        """
        # Create organization, user, project, and viewed proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Viewed Proposal", status=ProposalStatus.VIEWED, project=project
        )
        # Set validity and timestamps
        proposal.valid_until = datetime.utcnow() + timedelta(days=30)
        proposal.sent_at = datetime.utcnow() - timedelta(hours=1)
        proposal.viewed_at = datetime.utcnow()
        await db_session.flush()

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Approve proposal
        response = await client.post(
            f"/api/proposals/{proposal.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["approved_at"] is not None

    @pytest.mark.asyncio
    async def test_cannot_approve_expired_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that expired proposals cannot be approved.

        WHY: Expired proposals may have outdated pricing.
        """
        # Create organization, user, project, and expired proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Expired Proposal", status=ProposalStatus.SENT, project=project
        )
        # Set valid_until in the past
        proposal.valid_until = datetime.utcnow() - timedelta(days=1)
        await db_session.flush()

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to approve
        response = await client.post(
            f"/api/proposals/{proposal.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should fail
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test rejecting a proposal.

        WHY: Clients may reject proposals.
        """
        # Create organization, user, project, and sent proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="To Reject", status=ProposalStatus.SENT, project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Reject proposal
        response = await client.post(
            f"/api/proposals/{proposal.id}/reject",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Price too high"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["rejected_at"] is not None
        assert data["rejection_reason"] == "Price too high"


class TestProposalRevision:
    """Integration tests for proposal revision endpoint."""

    @pytest.mark.asyncio
    async def test_create_revision(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test creating a revision of a proposal.

        WHY: Rejected proposals need revisions with updated terms.
        """
        # Create organization, admin, project, and rejected proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Original Proposal", status=ProposalStatus.REJECTED, project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Create revision
        response = await client.post(
            f"/api/proposals/{proposal.id}/revise",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Revised Proposal",
                "line_items": [
                    {"description": "Development", "quantity": 8, "unit_price": 100},
                ],
                "discount_percent": 15,
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Revised Proposal"
        assert data["version"] == 2
        assert data["status"] == "draft"
        assert data["previous_version_id"] == proposal.id


class TestProposalUpdate:
    """Integration tests for proposal update endpoint."""

    @pytest.mark.asyncio
    async def test_update_draft_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test updating a draft proposal.

        WHY: Admins need to modify proposals before sending.
        """
        # Create organization, admin, project, and draft proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Old Title", status=ProposalStatus.DRAFT, project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Update proposal
        response = await client.put(
            f"/api/proposals/{proposal.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "New Title",
                "description": "Updated description",
            },
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Title"
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_cannot_update_sent_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that sent proposals cannot be updated.

        WHY: Sent proposals are contractual documents.
        """
        # Create organization, admin, project, and sent proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Sent Proposal", status=ProposalStatus.SENT, project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to update sent proposal
        response = await client.put(
            f"/api/proposals/{proposal.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "Modified Title"},
        )

        # Should fail
        assert response.status_code == 400


class TestProposalDelete:
    """Integration tests for proposal deletion endpoint."""

    @pytest.mark.asyncio
    async def test_delete_draft_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test deleting a draft proposal.

        WHY: Admins can delete draft proposals.
        """
        # Create organization, admin, project, and draft proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="To Delete", status=ProposalStatus.DRAFT, project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Delete proposal
        response = await client.delete(
            f"/api/proposals/{proposal.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify deletion
        assert response.status_code == 204

        # Verify proposal is gone
        get_response = await client.get(
            f"/api/proposals/{proposal.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_delete_approved_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that approved proposals cannot be deleted.

        WHY: Approved proposals are legal documents for auditing.
        """
        # Create organization, admin, project, and approved proposal
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        proposal = await ProposalFactory.create(
            db_session, title="Approved", status=ProposalStatus.APPROVED, project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to delete approved proposal
        response = await client.delete(
            f"/api/proposals/{proposal.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should fail
        assert response.status_code == 400


class TestProposalStats:
    """Integration tests for proposal statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_proposal_stats(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting proposal statistics.

        WHY: Dashboard needs aggregated proposal metrics.
        """
        # Create organization, user, project, and proposals
        org = await OrganizationFactory.create(db_session, name="Test Company")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )
        project = await ProjectFactory.create(
            db_session, name="Test Project", organization=org
        )
        await ProposalFactory.create(
            db_session, title="Draft", status=ProposalStatus.DRAFT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Sent", status=ProposalStatus.SENT, project=project
        )
        await ProposalFactory.create(
            db_session, title="Approved", status=ProposalStatus.APPROVED, project=project
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get stats
        response = await client.get(
            "/api/proposals/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert "by_status" in data
        assert data["by_status"].get("draft") == 1
        assert data["by_status"].get("sent") == 1
        assert data["by_status"].get("approved") == 1


class TestProposalMultiTenancy:
    """Integration tests for multi-tenancy isolation."""

    @pytest.mark.asyncio
    async def test_cannot_access_other_org_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that users cannot access proposals from other organizations.

        WHY: Multi-tenancy security (OWASP A01).
        """
        # Create two organizations
        org1 = await OrganizationFactory.create(db_session, name="Company 1")
        org2 = await OrganizationFactory.create(db_session, name="Company 2")

        await UserFactory.create(
            db_session,
            email="user1@test.com",
            password="Password123!",
            organization=org1,
        )

        project2 = await ProjectFactory.create(
            db_session, name="Org2 Project", organization=org2
        )
        proposal2 = await ProposalFactory.create(
            db_session, title="Org2 Proposal", project=project2
        )

        # Login as user from org1
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user1@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to access org2's proposal
        response = await client.get(
            f"/api/proposals/{proposal2.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should be not found (hiding existence)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_approve_other_org_proposal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that users cannot approve proposals from other organizations.

        WHY: Workflow actions must respect org boundaries.
        """
        # Create two organizations
        org1 = await OrganizationFactory.create(db_session, name="Company 1")
        org2 = await OrganizationFactory.create(db_session, name="Company 2")

        await UserFactory.create(
            db_session,
            email="user1@test.com",
            password="Password123!",
            organization=org1,
        )

        project2 = await ProjectFactory.create(
            db_session, name="Org2 Project", organization=org2
        )
        proposal2 = await ProposalFactory.create(
            db_session, title="Org2 Proposal", status=ProposalStatus.SENT, project=project2
        )

        # Login as user from org1
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user1@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to approve org2's proposal
        response = await client.post(
            f"/api/proposals/{proposal2.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should be not found (hiding existence)
        assert response.status_code == 404
