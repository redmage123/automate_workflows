"""
Tests for organization-scoping enforcement.

WHY: Org-scoping is CRITICAL for multi-tenant security (OWASP A01: Broken Access Control).
These tests ensure that users can only access data from their own organization,
preventing cross-organization data leaks.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User
from app.dao.base import BaseDAO
from app.dao.user import UserDAO
from app.core.auth import hash_password


class TestOrgScopingEnforcement:
    """Test multi-tenancy org-scoping enforcement."""

    @pytest.fixture
    async def orgs(self, db_session: AsyncSession):
        """Create test organizations."""
        org_dao = BaseDAO(Organization, db_session)

        org1 = await org_dao.create(name="Organization 1", description="First org")
        org2 = await org_dao.create(name="Organization 2", description="Second org")

        return org1, org2

    @pytest.fixture
    async def users(self, db_session: AsyncSession, orgs):
        """Create test users in different organizations."""
        org1, org2 = orgs
        user_dao = UserDAO(User, db_session)

        # Users in Organization 1
        user1_org1 = await user_dao.create_user(
            email="user1@org1.com",
            hashed_password=hash_password("password123"),
            name="User 1 Org 1",
            org_id=org1.id,
            role="CLIENT",
        )
        user2_org1 = await user_dao.create_user(
            email="user2@org1.com",
            hashed_password=hash_password("password123"),
            name="User 2 Org 1",
            org_id=org1.id,
            role="ADMIN",
        )

        # Users in Organization 2
        user1_org2 = await user_dao.create_user(
            email="user1@org2.com",
            hashed_password=hash_password("password123"),
            name="User 1 Org 2",
            org_id=org2.id,
            role="CLIENT",
        )

        return {
            "org1_user1": user1_org1,
            "org1_user2": user2_org1,
            "org2_user1": user1_org2,
        }

    @pytest.mark.asyncio
    async def test_get_by_org_returns_only_org_users(self, db_session: AsyncSession, users, orgs):
        """Test that get_by_org returns only users from specified organization."""
        org1, org2 = orgs
        user_dao = UserDAO(User, db_session)

        # Get users for org 1
        org1_users = await user_dao.get_by_org(org1.id)

        # Should return 2 users from org 1
        assert len(org1_users) == 2
        assert all(user.org_id == org1.id for user in org1_users)
        assert users["org1_user1"].id in [u.id for u in org1_users]
        assert users["org1_user2"].id in [u.id for u in org1_users]

        # User from org 2 should NOT be included
        assert users["org2_user1"].id not in [u.id for u in org1_users]

    @pytest.mark.asyncio
    async def test_get_by_org_different_org(self, db_session: AsyncSession, users, orgs):
        """Test that different org returns different users."""
        org1, org2 = orgs
        user_dao = UserDAO(User, db_session)

        # Get users for org 2
        org2_users = await user_dao.get_by_org(org2.id)

        # Should return 1 user from org 2
        assert len(org2_users) == 1
        assert org2_users[0].org_id == org2.id
        assert org2_users[0].id == users["org2_user1"].id

        # Users from org 1 should NOT be included
        assert users["org1_user1"].id not in [u.id for u in org2_users]
        assert users["org1_user2"].id not in [u.id for u in org2_users]

    @pytest.mark.asyncio
    async def test_get_by_id_and_org_success(self, db_session: AsyncSession, users, orgs):
        """Test that get_by_id_and_org returns user when org matches."""
        org1, org2 = orgs
        user_dao = UserDAO(User, db_session)

        # Get user with correct org_id
        user = await user_dao.get_by_id_and_org(users["org1_user1"].id, org1.id)

        assert user is not None
        assert user.id == users["org1_user1"].id
        assert user.org_id == org1.id

    @pytest.mark.asyncio
    async def test_get_by_id_and_org_wrong_org_returns_none(
        self, db_session: AsyncSession, users, orgs
    ):
        """
        Test that get_by_id_and_org returns None when org doesn't match.

        WHY: This is CRITICAL for security. Attempting to access a resource
        from another organization should fail, preventing cross-org data leaks.
        """
        org1, org2 = orgs
        user_dao = UserDAO(User, db_session)

        # Try to get org1 user with org2's org_id
        # WHY: This simulates a CLIENT user from org2 trying to access
        # a user from org1 by guessing/knowing their ID
        user = await user_dao.get_by_id_and_org(
            users["org1_user1"].id, org2.id  # User from org 1  # But querying with org 2's ID
        )

        # Should return None (user "doesn't exist" for org 2)
        # WHY: Returning None instead of raising an error prevents
        # information disclosure about whether the user exists
        assert user is None

    @pytest.mark.asyncio
    async def test_count_users_by_org(self, db_session: AsyncSession, users, orgs):
        """Test that count_users_by_org counts only org's users."""
        org1, org2 = orgs
        user_dao = UserDAO(User, db_session)

        # Count users in org 1
        org1_count = await user_dao.count_users_by_org(org1.id)
        assert org1_count == 2

        # Count users in org 2
        org2_count = await user_dao.count_users_by_org(org2.id)
        assert org2_count == 1

    @pytest.mark.asyncio
    async def test_get_by_email_and_org_correct_org(self, db_session: AsyncSession, users, orgs):
        """Test get_by_email_and_org with correct organization."""
        org1, org2 = orgs
        user_dao = UserDAO(User, db_session)

        # Get user with correct org
        user = await user_dao.get_by_email_and_org("user1@org1.com", org1.id)

        assert user is not None
        assert user.email == "user1@org1.com"
        assert user.org_id == org1.id

    @pytest.mark.asyncio
    async def test_get_by_email_and_org_wrong_org(self, db_session: AsyncSession, users, orgs):
        """
        Test get_by_email_and_org with wrong organization returns None.

        WHY: Even if the email exists, if it's in a different organization,
        it should not be accessible. This prevents cross-org user enumeration.
        """
        org1, org2 = orgs
        user_dao = UserDAO(User, db_session)

        # Try to get org1 user's email with org2's org_id
        user = await user_dao.get_by_email_and_org("user1@org1.com", org2.id)

        # Should return None
        assert user is None

    @pytest.mark.asyncio
    async def test_base_dao_get_by_org_method(self, db_session: AsyncSession, users, orgs):
        """Test BaseDAO's get_by_org method works correctly."""
        org1, org2 = orgs
        user_dao = BaseDAO(User, db_session)

        # Get users by org using base DAO method
        org1_users = await user_dao.get_by_org(org1.id)

        assert len(org1_users) == 2
        assert all(user.org_id == org1.id for user in org1_users)

    @pytest.mark.asyncio
    async def test_base_dao_get_by_id_and_org_method(self, db_session: AsyncSession, users, orgs):
        """Test BaseDAO's get_by_id_and_org method works correctly."""
        org1, org2 = orgs
        user_dao = BaseDAO(User, db_session)

        # Correct org
        user = await user_dao.get_by_id_and_org(users["org1_user1"].id, org1.id)
        assert user is not None

        # Wrong org
        user = await user_dao.get_by_id_and_org(users["org1_user1"].id, org2.id)
        assert user is None


class TestSecurityScenarios:
    """Test real-world security scenarios for org-scoping."""

    @pytest.fixture
    async def setup(self, db_session: AsyncSession):
        """Set up test scenario with organizations and users."""
        org_dao = BaseDAO(Organization, db_session)
        user_dao = UserDAO(User, db_session)

        # Create organizations
        acme_corp = await org_dao.create(name="Acme Corp")
        rival_corp = await org_dao.create(name="Rival Corp")

        # Create users
        acme_admin = await user_dao.create_user(
            email="admin@acme.com",
            hashed_password=hash_password("password123"),
            name="Acme Admin",
            org_id=acme_corp.id,
            role="ADMIN",
        )
        acme_client = await user_dao.create_user(
            email="client@acme.com",
            hashed_password=hash_password("password123"),
            name="Acme Client",
            org_id=acme_corp.id,
            role="CLIENT",
        )
        rival_client = await user_dao.create_user(
            email="client@rival.com",
            hashed_password=hash_password("password123"),
            name="Rival Client",
            org_id=rival_corp.id,
            role="CLIENT",
        )

        return {
            "acme_corp": acme_corp,
            "rival_corp": rival_corp,
            "acme_admin": acme_admin,
            "acme_client": acme_client,
            "rival_client": rival_client,
        }

    @pytest.mark.asyncio
    async def test_client_cannot_access_other_org_users(self, db_session: AsyncSession, setup):
        """
        Test that a client user cannot access users from another organization.

        WHY: This is a common attack vector - malicious user tries to access
        another organization's data by guessing IDs or manipulating requests.
        """
        user_dao = UserDAO(User, db_session)

        # Rival client tries to access Acme client by ID
        # Simulates: GET /api/users/{id} with rival_client's org_id
        stolen_user = await user_dao.get_by_id_and_org(
            setup["acme_client"].id,  # Try to access Acme's user
            setup["rival_corp"].id,  # But with Rival's org_id
        )

        # Should fail (return None)
        assert stolen_user is None

    @pytest.mark.asyncio
    async def test_client_can_only_list_own_org_users(self, db_session: AsyncSession, setup):
        """
        Test that listing users only returns users from the same organization.

        WHY: API endpoints that list resources must be org-scoped to prevent
        information disclosure about other organizations.
        """
        user_dao = UserDAO(User, db_session)

        # Acme client lists users
        acme_users = await user_dao.get_users_by_org(setup["acme_corp"].id)

        # Should see 2 users (admin and client from Acme)
        assert len(acme_users) == 2
        user_ids = [u.id for u in acme_users]
        assert setup["acme_admin"].id in user_ids
        assert setup["acme_client"].id in user_ids

        # Should NOT see Rival's client
        assert setup["rival_client"].id not in user_ids

    @pytest.mark.asyncio
    async def test_email_enumeration_prevention(self, db_session: AsyncSession, setup):
        """
        Test that email lookup is org-scoped to prevent enumeration attacks.

        WHY: Without org-scoping, an attacker could enumerate email addresses
        across all organizations by trying different emails.
        """
        user_dao = UserDAO(User, db_session)

        # Rival tries to check if admin@acme.com exists
        # by using get_by_email_and_org with their org_id
        user = await user_dao.get_by_email_and_org(
            "admin@acme.com",  # Acme's admin email
            setup["rival_corp"].id,  # But Rival's org_id
        )

        # Should return None (email "doesn't exist" for Rival Corp)
        assert user is None

        # But Acme can find their own admin
        user = await user_dao.get_by_email_and_org(
            "admin@acme.com",
            setup["acme_corp"].id,
        )
        assert user is not None
        assert user.id == setup["acme_admin"].id
