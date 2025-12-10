"""
Integration tests for organization management API.

WHY: Organizations are the core multi-tenancy unit. These tests ensure:
1. Only admins can create/update organizations
2. Users can view their own organization
3. Org-scoping prevents cross-org access
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import OrganizationFactory, UserFactory


class TestOrganizationEndpoints:
    """Integration tests for organization management endpoints."""

    @pytest.mark.asyncio
    async def test_get_current_organization(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting current user's organization.

        WHY: Users need to view their organization details.
        """
        # Create organization and user
        org = await OrganizationFactory.create(
            db_session, name="Test Company", description="A test organization"
        )
        user = await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get organization
        response = await client.get(
            "/api/organizations/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == org.id
        assert data["name"] == "Test Company"
        assert data["description"] == "A test organization"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_organization_by_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting organization by ID (same org as user).

        WHY: Users should be able to fetch their organization by ID.
        """
        # Create organization and user
        org = await OrganizationFactory.create(
            db_session, name="Test Company"
        )
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get organization by ID
        response = await client.get(
            f"/api/organizations/{org.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == org.id
        assert data["name"] == "Test Company"

    @pytest.mark.asyncio
    async def test_cannot_get_other_organization(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that users cannot access other organizations.

        WHY: Org-scoping prevents cross-organization data leaks (OWASP A01).
        """
        # Create two organizations with users
        org1 = await OrganizationFactory.create(db_session, name="Company 1")
        org2 = await OrganizationFactory.create(db_session, name="Company 2")

        await UserFactory.create(
            db_session,
            email="user1@test.com",
            password="Password123!",
            organization=org1,
        )

        # Login as user from org1
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user1@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to access org2
        response = await client.get(
            f"/api/organizations/{org2.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should be forbidden or not found
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_update_organization_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test updating organization as ADMIN.

        WHY: Admins should be able to update organization settings.
        """
        # Create organization and admin user
        org = await OrganizationFactory.create(
            db_session, name="Old Name", description="Old description"
        )
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Update organization
        response = await client.put(
            f"/api/organizations/{org.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "New Name",
                "description": "New description",
            },
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "New description"

    @pytest.mark.asyncio
    async def test_cannot_update_organization_as_client(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that CLIENT users cannot update organization.

        WHY: RBAC - only admins should modify organization settings.
        """
        # Create organization and client user
        org = await OrganizationFactory.create(db_session, name="Company")
        await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to update organization
        response = await client.put(
            f"/api/organizations/{org.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Hacked Name",
            },
        )

        # Should be forbidden
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_organization_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test creating new organization as ADMIN.

        WHY: Admins should be able to create organizations.
        (This would typically be a platform admin feature)
        """
        # Create existing org and admin user
        org = await OrganizationFactory.create(db_session, name="Existing Org")
        await UserFactory.create_admin(
            db_session,
            email="admin@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Create new organization
        response = await client.post(
            "/api/organizations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "New Organization",
                "description": "A brand new org",
            },
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Organization"
        assert data["description"] == "A brand new org"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_cannot_create_organization_as_client(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that CLIENT users cannot create organizations.

        WHY: RBAC - only admins should create organizations.
        """
        # Create organization and client user
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_client(
            db_session,
            email="client@test.com",
            password="Password123!",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "client@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to create organization
        response = await client.post(
            "/api/organizations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "New Organization",
            },
        )

        # Should be forbidden
        assert response.status_code == 403
