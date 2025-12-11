"""
Integration tests for Admin API.

WHAT: Tests for admin portal endpoints.

WHY: Admin endpoints provide critical platform management:
1. User CRUD across all organizations
2. Organization management
3. Audit log viewing
4. Security compliance requires comprehensive testing

HOW: Uses pytest-asyncio with AsyncClient for HTTP testing.
"""

import pytest
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    OrganizationFactory,
    UserFactory,
    ProjectFactory,
    InvoiceFactory,
    TicketFactory,
)
from app.models.user import UserRole


class TestAdminUserManagement:
    """Integration tests for admin user management endpoints."""

    @pytest.mark.asyncio
    async def test_list_users_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test listing all users as ADMIN.

        WHY: Admins need to view all platform users.
        """
        # Create organizations and users
        org1 = await OrganizationFactory.create(db_session, name="Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Org 2")

        admin = await UserFactory.create_admin(
            db_session, email="admin@test.com", password="Password123!", organization=org1
        )
        await UserFactory.create_client(
            db_session, email="user1@test.com", password="Password123!", organization=org1
        )
        await UserFactory.create_client(
            db_session, email="user2@test.com", password="Password123!", organization=org2
        )

        # Login as admin
        login_response = await client.post(
            "/api/auth/login", json={"email": "admin@test.com", "password": "Password123!"}
        )
        token = login_response.json()["access_token"]

        # List users
        response = await client.get(
            "/api/admin/users", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3  # At least our 3 users

    @pytest.mark.asyncio
    async def test_list_users_forbidden_for_client(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that CLIENT users cannot list all users.

        WHY: RBAC - only admins should access admin endpoints.
        """
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_client(
            db_session, email="client@test.com", password="Password123!", organization=org
        )

        # Login as client
        login_response = await client.post(
            "/api/auth/login", json={"email": "client@test.com", "password": "Password123!"}
        )
        token = login_response.json()["access_token"]

        # Try to list users
        response = await client.get(
            "/api/admin/users", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_users_with_filters(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test filtering users by organization, role, and status.

        WHY: Admin needs to find specific users quickly.
        """
        org1 = await OrganizationFactory.create(db_session, name="Filter Org")
        admin = await UserFactory.create_admin(
            db_session, email="filter-admin@test.com", password="Password123!", organization=org1
        )
        await UserFactory.create_client(
            db_session, email="filter-client@test.com", password="Password123!", organization=org1
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "filter-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Filter by organization
        response = await client.get(
            f"/api/admin/users?org_id={org1.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        # Filter by role
        response = await client.get(
            f"/api/admin/users?role=ADMIN",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["role"] == "ADMIN"

    @pytest.mark.asyncio
    async def test_get_user_details(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting user details by ID.

        WHY: Admins need to view individual user information.
        """
        org = await OrganizationFactory.create(db_session, name="Details Org")
        admin = await UserFactory.create_admin(
            db_session, email="details-admin@test.com", password="Password123!", organization=org
        )
        target_user = await UserFactory.create_client(
            db_session,
            email="details-target@test.com",
            password="Password123!",
            name="Target User",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "details-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get user details
        response = await client.get(
            f"/api/admin/users/{target_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == target_user.id
        assert data["email"] == "details-target@test.com"
        assert data["name"] == "Target User"
        assert data["org_name"] == "Details Org"

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting a non-existent user.

        WHY: Should return 404 for invalid user ID.
        """
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_admin(
            db_session, email="notfound-admin@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "notfound-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get non-existent user
        response = await client.get(
            "/api/admin/users/99999", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_user_as_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test creating a user as admin.

        WHY: Admins can create users directly without registration.
        """
        org = await OrganizationFactory.create(db_session, name="Create User Org")
        await UserFactory.create_admin(
            db_session, email="create-admin@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "create-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Create user
        response = await client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "newuser@test.com",
                "password": "NewPassword123!",
                "name": "New User",
                "org_id": org.id,
                "role": "CLIENT",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert data["name"] == "New User"
        assert data["role"] == "CLIENT"
        assert data["email_verified"] == True  # Admin-created users are auto-verified

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test creating a user with duplicate email fails.

        WHY: Email uniqueness constraint.
        """
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_admin(
            db_session, email="dup-admin@test.com", password="Password123!", organization=org
        )
        await UserFactory.create_client(
            db_session, email="existing@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "dup-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to create user with existing email
        response = await client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "existing@test.com",
                "password": "Password123!",
                "name": "Duplicate",
                "org_id": org.id,
            },
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_update_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test updating user details.

        WHY: Admins need to modify user accounts.
        """
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_admin(
            db_session, email="update-admin@test.com", password="Password123!", organization=org
        )
        target_user = await UserFactory.create_client(
            db_session,
            email="update-target@test.com",
            password="Password123!",
            name="Original Name",
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "update-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Update user
        response = await client.put(
            f"/api/admin/users/{target_user.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Updated Name", "role": "ADMIN"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["role"] == "ADMIN"

    @pytest.mark.asyncio
    async def test_deactivate_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test deactivating a user (soft delete).

        WHY: Soft deletion preserves data while blocking access.
        """
        org = await OrganizationFactory.create(db_session)
        admin = await UserFactory.create_admin(
            db_session, email="deact-admin@test.com", password="Password123!", organization=org
        )
        target_user = await UserFactory.create_client(
            db_session, email="deact-target@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "deact-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Deactivate user
        response = await client.delete(
            f"/api/admin/users/{target_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 204

        # Verify user is deactivated
        get_response = await client.get(
            f"/api/admin/users/{target_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_response.json()["is_active"] == False

    @pytest.mark.asyncio
    async def test_cannot_deactivate_self(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that admin cannot deactivate their own account.

        WHY: Prevents admin from locking themselves out.
        """
        org = await OrganizationFactory.create(db_session)
        admin = await UserFactory.create_admin(
            db_session, email="self-deact@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "self-deact@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to deactivate self
        response = await client.delete(
            f"/api/admin/users/{admin.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_force_password_reset(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test initiating password reset for a user.

        WHY: Admins need to help locked-out users.
        """
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_admin(
            db_session, email="reset-admin@test.com", password="Password123!", organization=org
        )
        target_user = await UserFactory.create_client(
            db_session, email="reset-target@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "reset-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Force password reset
        response = await client.post(
            f"/api/admin/users/{target_user.id}/reset-password",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert "message" in response.json()


class TestAdminOrganizationManagement:
    """Integration tests for admin organization management endpoints."""

    @pytest.mark.asyncio
    async def test_list_organizations(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test listing all organizations.

        WHY: Admins need to view all platform organizations.
        """
        org1 = await OrganizationFactory.create(db_session, name="List Org 1")
        await OrganizationFactory.create(db_session, name="List Org 2")
        await UserFactory.create_admin(
            db_session, email="listorg-admin@test.com", password="Password123!", organization=org1
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "listorg-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # List organizations
        response = await client.get(
            "/api/admin/organizations", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2

    @pytest.mark.asyncio
    async def test_get_organization_details(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting organization details with metrics.

        WHY: Admins need to view organization health.
        """
        org = await OrganizationFactory.create(db_session, name="Detail Org")
        admin = await UserFactory.create_admin(
            db_session, email="orgdetail-admin@test.com", password="Password123!", organization=org
        )
        # Create some users
        await UserFactory.create_client(
            db_session, email="orgdetail-user1@test.com", password="Password123!", organization=org
        )
        await UserFactory.create_client(
            db_session, email="orgdetail-user2@test.com", password="Password123!", organization=org
        )
        # Create a project
        await ProjectFactory.create(db_session, name="Test Project", organization=org)

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "orgdetail-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get organization details
        response = await client.get(
            f"/api/admin/organizations/{org.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == org.id
        assert data["name"] == "Detail Org"
        assert data["user_count"] == 3  # admin + 2 clients
        assert data["project_count"] == 1
        assert "total_revenue" in data

    @pytest.mark.asyncio
    async def test_update_organization(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test updating organization details.

        WHY: Admins need to modify organization settings.
        """
        org = await OrganizationFactory.create(db_session, name="Original Org Name")
        await UserFactory.create_admin(
            db_session, email="orgupdate-admin@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "orgupdate-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Update organization
        response = await client.put(
            f"/api/admin/organizations/{org.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Updated Org Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Org Name"

    @pytest.mark.asyncio
    async def test_suspend_organization(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test suspending an organization.

        WHY: Admins need to suspend problematic organizations.
        """
        admin_org = await OrganizationFactory.create(db_session, name="Admin Org")
        target_org = await OrganizationFactory.create(db_session, name="Target Org")
        await UserFactory.create_admin(
            db_session,
            email="suspend-admin@test.com",
            password="Password123!",
            organization=admin_org,
        )
        await UserFactory.create_client(
            db_session,
            email="suspend-user1@test.com",
            password="Password123!",
            organization=target_org,
        )
        await UserFactory.create_client(
            db_session,
            email="suspend-user2@test.com",
            password="Password123!",
            organization=target_org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "suspend-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Suspend organization
        response = await client.post(
            f"/api/admin/organizations/{target_org.id}/suspend",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Organization suspended"
        assert data["users_affected"] == 2

    @pytest.mark.asyncio
    async def test_activate_organization(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test reactivating a suspended organization.

        WHY: Admins need to restore suspended organizations.
        """
        admin_org = await OrganizationFactory.create(db_session, name="Admin Org")
        target_org = await OrganizationFactory.create(
            db_session, name="Suspended Org", is_active=False
        )
        await UserFactory.create_admin(
            db_session,
            email="activate-admin@test.com",
            password="Password123!",
            organization=admin_org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "activate-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Activate organization
        response = await client.post(
            f"/api/admin/organizations/{target_org.id}/activate",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Organization activated"


class TestAdminAuditLogs:
    """Integration tests for audit log viewer endpoints."""

    @pytest.mark.asyncio
    async def test_list_audit_logs(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test listing audit logs.

        WHY: Admins need security audit trail access.
        """
        org = await OrganizationFactory.create(db_session, name="Audit Org")
        await UserFactory.create_admin(
            db_session, email="audit-admin@test.com", password="Password123!", organization=org
        )

        # Login (this creates an audit log entry)
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "audit-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # List audit logs
        response = await client.get(
            "/api/admin/audit-logs", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_filter_audit_logs_by_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test filtering audit logs by user.

        WHY: Investigate specific user activity.
        """
        org = await OrganizationFactory.create(db_session, name="Audit Filter Org")
        admin = await UserFactory.create_admin(
            db_session, email="auditfilter-admin@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "auditfilter-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Filter by user
        response = await client.get(
            f"/api/admin/audit-logs?user_id={admin.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # All returned logs should be for this user
        for item in data["items"]:
            assert item["actor_user_id"] == admin.id

    @pytest.mark.asyncio
    async def test_filter_audit_logs_by_resource_type(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test filtering audit logs by resource type.

        WHY: Investigate specific types of actions.
        """
        org = await OrganizationFactory.create(db_session, name="Resource Filter Org")
        await UserFactory.create_admin(
            db_session, email="resourcefilter-admin@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "resourcefilter-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Filter by resource type
        response = await client.get(
            "/api/admin/audit-logs?resource_type=user",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["resource_type"] == "user"

    @pytest.mark.asyncio
    async def test_audit_logs_pagination(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test audit log pagination.

        WHY: Large audit logs need pagination.
        """
        org = await OrganizationFactory.create(db_session, name="Pagination Org")
        await UserFactory.create_admin(
            db_session, email="pagination-admin@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "pagination-admin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Test pagination
        response = await client.get(
            "/api/admin/audit-logs?skip=0&limit=5",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 0
        assert data["limit"] == 5
        assert len(data["items"]) <= 5
