"""
Integration tests for user registration API.

WHY: Registration is a critical security feature that requires thorough testing:
1. Valid registration flow
2. Email uniqueness validation
3. Password strength requirements
4. Organization creation
5. Input validation
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import OrganizationFactory, UserFactory


class TestUserRegistration:
    """Integration tests for user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_new_user_with_new_organization(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test successful user registration with new organization.

        WHY: Most common registration flow - new user creates their own organization.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
                "name": "New User",
                "organization_name": "New Company LLC",
            },
        )

        # Verify successful registration
        assert response.status_code == 201
        data = response.json()

        # Should return JWT token
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

        # Should return user data
        assert "user" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["name"] == "New User"
        assert data["user"]["role"] == "ADMIN"  # First user in org is ADMIN
        assert data["user"]["is_active"] is True

        # Should have created organization
        assert "organization" in data
        assert data["organization"]["name"] == "New Company LLC"

    @pytest.mark.asyncio
    async def test_register_user_with_existing_organization(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test user registration joining existing organization.

        WHY: Team members should be able to join existing organizations.
        """
        # Create organization first
        org = await OrganizationFactory.create(
            db_session, name="Existing Company", description="Test org"
        )

        response = await client.post(
            "/api/auth/register",
            json={
                "email": "teammate@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
                "name": "Team Member",
                "org_id": org.id,
            },
        )

        # Verify successful registration
        assert response.status_code == 201
        data = response.json()

        # Should return token and user data
        assert "access_token" in data
        assert data["user"]["email"] == "teammate@example.com"
        assert data["user"]["role"] == "CLIENT"  # Non-first users are CLIENT
        assert data["user"]["org_id"] == org.id

    @pytest.mark.asyncio
    async def test_register_with_duplicate_email(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test registration with email that already exists.

        WHY: Email uniqueness is critical for authentication and security.
        """
        # Create existing user
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create(
            db_session,
            email="existing@example.com",
            password="Password123!",
            organization=org,
        )

        # Attempt registration with same email
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "existing@example.com",
                "password": "NewPassword123!",
                "password_confirm": "NewPassword123!",
                "name": "Another User",
                "organization_name": "Another Company",
            },
        )

        # Should fail with 409 Conflict
        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_register_with_weak_password(self, client: AsyncClient):
        """
        Test registration with password that doesn't meet requirements.

        WHY: Enforce strong passwords to protect user accounts (OWASP A07).
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "short",  # Only 5 chars - less than min 8
                "password_confirm": "short",
                "name": "New User",
                "organization_name": "New Company",
            },
        )

        # Should fail with 422 Validation Error from Pydantic
        assert response.status_code in [400, 422]  # Accept both for now
        data = response.json()
        # Check that error mentions password or validation
        assert any(
            keyword in str(data).lower()
            for keyword in ["password", "validation", "string", "length"]
        )

    @pytest.mark.asyncio
    async def test_register_with_mismatched_passwords(self, client: AsyncClient):
        """
        Test registration with passwords that don't match.

        WHY: Password confirmation prevents typos during registration.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "DifferentPassword123!",
                "name": "New User",
                "organization_name": "New Company",
            },
        )

        # Should fail with 400 Bad Request
        assert response.status_code == 400
        data = response.json()
        assert "passwords do not match" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_register_with_invalid_email(self, client: AsyncClient):
        """
        Test registration with invalid email format.

        WHY: Email validation prevents invalid data and improves deliverability.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "not-an-email",  # Invalid email format
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
                "name": "New User",
                "organization_name": "New Company",
            },
        )

        # Should fail with 422 Validation Error from Pydantic EmailStr
        assert response.status_code in [400, 422]  # Accept both for now
        data = response.json()
        assert any(keyword in str(data).lower() for keyword in ["email", "validation", "invalid"])

    @pytest.mark.asyncio
    async def test_register_without_organization_data(self, client: AsyncClient):
        """
        Test registration without organization_name or org_id.

        WHY: Users must either create new org or join existing one.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
                "name": "New User",
                # Missing both organization_name and org_id
            },
        )

        # Should fail with 400 Bad Request
        assert response.status_code == 400
        data = response.json()
        assert "organization" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_register_with_both_org_name_and_org_id(self, client: AsyncClient):
        """
        Test registration with both organization_name and org_id.

        WHY: User should specify either new org OR existing org, not both.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
                "name": "New User",
                "organization_name": "New Company",
                "org_id": 1,  # Can't specify both
            },
        )

        # Should fail with 400 Bad Request
        assert response.status_code == 400
        data = response.json()
        assert "either" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_register_with_nonexistent_org_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test registration with org_id that doesn't exist.

        WHY: Prevent users from joining non-existent organizations.
        """
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
                "name": "New User",
                "org_id": 99999,  # Non-existent
            },
        )

        # Should fail with 404 Not Found
        assert response.status_code == 404
        data = response.json()
        assert "organization" in data["message"].lower()
        assert "not found" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_can_login_after_registration(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that user can login immediately after registration.

        WHY: Verifies complete registration flow including password hashing.
        """
        # Register new user
        register_response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
                "name": "New User",
                "organization_name": "New Company",
            },
        )
        assert register_response.status_code == 201

        # Login with same credentials
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
            },
        )

        # Should succeed
        assert login_response.status_code == 200
        data = login_response.json()
        assert "access_token" in data
