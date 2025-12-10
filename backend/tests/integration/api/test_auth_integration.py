"""
Integration tests for authentication API.

WHY: Integration tests verify that multiple components work together correctly,
testing the full request-response cycle including database operations.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import UserFactory, OrganizationFactory


class TestAuthenticationIntegration:
    """Integration tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_login_flow_success(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test complete login flow with valid credentials.

        WHY: Verifies that login works end-to-end with database,
        password hashing, JWT generation, and HTTP response.
        """
        # Create organization and user
        org = await OrganizationFactory.create(db_session, name="Test Corp")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="SecurePassword123!",
            organization=org,
        )

        # Attempt login
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "user@test.com",
                "password": "SecurePassword123!",
            },
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 86400  # 24 hours in seconds

    @pytest.mark.asyncio
    async def test_login_with_invalid_password(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test login with incorrect password.

        WHY: Verifies that invalid passwords are rejected properly
        without leaking information about whether the user exists.
        """
        # Create user
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="CorrectPassword123!",
            organization=org,
        )

        # Attempt login with wrong password
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "user@test.com",
                "password": "WrongPassword123!",
            },
        )

        # Verify rejection
        assert response.status_code == 401
        data = response.json()
        assert data["message"] == "Invalid email or password"

    @pytest.mark.asyncio
    async def test_login_with_nonexistent_user(self, client: AsyncClient):
        """
        Test login with non-existent email.

        WHY: Verifies that the error message is the same as invalid password
        to prevent email enumeration attacks (OWASP A04).
        """
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": "Password123!",
            },
        )

        # Should return same error as invalid password
        assert response.status_code == 401
        data = response.json()
        assert data["message"] == "Invalid email or password"

    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting current user with valid JWT token.

        WHY: Verifies that JWT authentication works and returns correct user data.
        """
        # Create user and login
        org = await OrganizationFactory.create(db_session, name="Test Corp")
        await UserFactory.create(
            db_session,
            email="user@test.com",
            password="Password123!",
            name="Test User",
            organization=org,
        )

        # Login to get token
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "user@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get current user
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify user data
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@test.com"
        assert data["name"] == "Test User"
        assert data["role"] == "CLIENT"
        assert "id" in data
        assert "hashed_password" not in data  # Should not leak password hash

    @pytest.mark.asyncio
    async def test_get_current_user_without_token(self, client: AsyncClient):
        """
        Test accessing protected endpoint without authentication.

        WHY: Verifies that authentication is enforced on protected endpoints.
        """
        response = await client.get("/api/auth/me")

        assert response.status_code == 403
        data = response.json()
        # WHY: Check 'message' key (from custom exception handler) or 'detail' (from FastAPI)
        error_msg = data.get("message", data.get("detail", "")).lower()
        assert "not authenticated" in error_msg

    @pytest.mark.asyncio
    async def test_logout_invalidates_token(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test that logout invalidates the JWT token.

        WHY: Verifies that logged-out tokens cannot be reused,
        preventing session hijacking after logout.
        """
        # Create user and login
        org = await OrganizationFactory.create(db_session)
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

        # Verify token works
        me_response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_response.status_code == 200

        # Logout
        logout_response = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout_response.status_code == 200

        # Try to use token again - should fail
        me_response_after = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_response_after.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_login(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test that inactive users cannot log in.

        WHY: Allows admins to disable accounts without deleting data.

        NOTE: For security best practices (user enumeration prevention), the
        API could return a generic "Invalid email or password" message instead
        of "Account is inactive". The current implementation chooses to inform
        the user their account is inactive so they can contact support.
        """
        # Create inactive user
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create(
            db_session,
            email="inactive@test.com",
            password="Password123!",
            organization=org,
            is_active=False,
        )

        # Attempt login
        response = await client.post(
            "/api/auth/login",
            json={"email": "inactive@test.com", "password": "Password123!"},
        )

        assert response.status_code == 401
        data = response.json()
        # API returns specific message for inactive accounts to help users contact support
        assert data["message"] == "Account is inactive"
