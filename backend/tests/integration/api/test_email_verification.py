"""
Integration tests for email verification API endpoints.

WHAT: Tests the email verification flow end-to-end:
1. Send verification email
2. Verify email with token
3. Already verified user handling

WHY: Integration tests verify the complete flow works correctly:
- API endpoints
- Database operations
- Email service integration
- Token validation
- Error handling

HOW: Uses httpx AsyncClient with test database and mocked email service.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_token import TokenType
from app.services.email import MockEmailProvider
from tests.factories import UserFactory, OrganizationFactory


class TestSendVerificationEmail:
    """Tests for POST /api/auth/send-verification-email endpoint."""

    @pytest.mark.asyncio
    async def test_send_verification_email_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test sending verification email to unverified user.

        WHY: Verifies that verification email is sent and token is created.
        """
        # Clear any previous mock emails
        MockEmailProvider.clear_sent_emails()

        # Create unverified user
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="unverified@test.com",
            organization=org,
        )

        # Ensure user is not verified
        user.email_verified = False
        await db_session.commit()

        # Login to get token
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "unverified@test.com", "password": "TestPassword123!"},
        )
        token = login_response.json()["access_token"]

        # Send verification email
        response = await client.post(
            "/api/auth/send-verification-email",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "Verification email sent" in data["message"]

        # Verify mock email was sent
        assert len(MockEmailProvider.sent_emails) == 1
        sent = MockEmailProvider.sent_emails[0]
        assert sent.to_email == "unverified@test.com"
        assert "Verify" in sent.subject

    @pytest.mark.asyncio
    async def test_send_verification_email_already_verified(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that already verified users get appropriate message.

        WHY: Don't send unnecessary verification emails.
        """
        MockEmailProvider.clear_sent_emails()

        # Create verified user
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="verified@test.com",
            organization=org,
        )

        # Mark as verified
        user.email_verified = True
        await db_session.commit()

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "verified@test.com", "password": "TestPassword123!"},
        )
        token = login_response.json()["access_token"]

        # Try to send verification email
        response = await client.post(
            "/api/auth/send-verification-email",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "already verified" in data["message"].lower()

        # Verify no email was sent
        assert len(MockEmailProvider.sent_emails) == 0

    @pytest.mark.asyncio
    async def test_send_verification_email_unauthenticated(self, client: AsyncClient):
        """
        Test that unauthenticated requests are rejected.

        WHY: Only authenticated users should request verification emails.
        """
        response = await client.post("/api/auth/send-verification-email")
        assert response.status_code == 403


class TestVerifyEmail:
    """Tests for POST /api/auth/verify-email endpoint."""

    @pytest.mark.asyncio
    async def test_verify_email_with_valid_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test verifying email with valid token.

        WHY: Main verification flow - user clicks link in email.
        """
        from app.dao.verification_token import VerificationTokenDAO

        # Create unverified user
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="verify@test.com",
            organization=org,
        )
        user.email_verified = False
        await db_session.commit()

        # Create verification token directly (simulating what send-verification-email does)
        token_dao = VerificationTokenDAO(db_session)
        verification_token = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
            include_code=True,
        )
        await db_session.commit()

        # Verify email with token
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": verification_token.token},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email_verified"] is True
        assert "successfully" in data["message"].lower()

        # Verify user is now marked as verified
        await db_session.refresh(user)
        assert user.email_verified is True

    @pytest.mark.asyncio
    async def test_verify_email_with_invalid_token(self, client: AsyncClient):
        """
        Test verifying email with invalid token.

        WHY: Invalid tokens should be rejected gracefully.
        """
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": "invalid-token-that-does-not-exist"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_verify_email_with_expired_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test verifying email with expired token.

        WHY: Expired tokens should be rejected for security.
        """
        from datetime import datetime, timedelta
        from app.dao.verification_token import VerificationTokenDAO

        # Create user
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="expired@test.com",
            organization=org,
        )
        user.email_verified = False
        await db_session.commit()

        # Create verification token
        token_dao = VerificationTokenDAO(db_session)
        verification_token = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Manually expire the token
        verification_token.expires_at = datetime.utcnow() - timedelta(hours=1)
        await db_session.commit()

        # Try to verify
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": verification_token.token},
        )

        assert response.status_code == 400
        data = response.json()
        assert "expired" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_verify_email_with_already_used_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test verifying email with already used token.

        WHY: Tokens are single-use to prevent replay attacks.
        """
        from datetime import datetime
        from app.dao.verification_token import VerificationTokenDAO

        # Create user
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="used@test.com",
            organization=org,
        )
        user.email_verified = False
        await db_session.commit()

        # Create verification token
        token_dao = VerificationTokenDAO(db_session)
        verification_token = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Mark as used
        verification_token.used_at = datetime.utcnow()
        await db_session.commit()

        # Try to verify
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": verification_token.token},
        )

        assert response.status_code == 400
        data = response.json()
        assert "used" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_verify_email_missing_token_and_code(self, client: AsyncClient):
        """
        Test that verification requires token or code.

        WHY: Must provide one verification method.
        """
        response = await client.post(
            "/api/auth/verify-email",
            json={},  # No token or code
        )

        assert response.status_code == 400
        data = response.json()
        assert "token or code" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_verify_email_code_requires_auth(self, client: AsyncClient):
        """
        Test that code verification requires authentication.

        WHY: Codes are not globally unique, so need user context.
        """
        response = await client.post(
            "/api/auth/verify-email",
            json={"code": "123456"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "authentication" in data["message"].lower()


class TestVerificationEmailFlow:
    """End-to-end tests for the complete verification flow."""

    @pytest.mark.asyncio
    async def test_complete_verification_flow(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test complete flow: register -> send verification -> verify -> login.

        WHY: Verifies all components work together correctly.
        """
        MockEmailProvider.clear_sent_emails()

        # Step 1: Register new user
        register_response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "NewUserPassword123!",
                "password_confirm": "NewUserPassword123!",
                "name": "New User",
                "organization_name": "New Org",
            },
        )
        assert register_response.status_code == 201
        token = register_response.json()["access_token"]

        # Step 2: Send verification email
        send_response = await client.post(
            "/api/auth/send-verification-email",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert send_response.status_code == 200

        # Get the token from mock email
        assert len(MockEmailProvider.sent_emails) == 1

        # Step 3: Get the verification token from database
        from app.dao.verification_token import VerificationTokenDAO
        from app.dao.user import UserDAO
        from app.models.user import User

        user_dao = UserDAO(User, db_session)
        user = await user_dao.get_by_email("newuser@test.com")

        token_dao = VerificationTokenDAO(db_session)
        from sqlalchemy import select, and_
        from app.models.verification_token import VerificationToken

        stmt = select(VerificationToken).where(
            and_(
                VerificationToken.user_id == user.id,
                VerificationToken.token_type == TokenType.EMAIL_VERIFICATION,
                VerificationToken.used_at.is_(None),
            )
        )
        result = await db_session.execute(stmt)
        verification_token = result.scalar_one()

        # Step 4: Verify email
        verify_response = await client.post(
            "/api/auth/verify-email",
            json={"token": verification_token.token},
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["email_verified"] is True

        # Step 5: Verify user is marked as verified
        await db_session.refresh(user)
        assert user.email_verified is True

    @pytest.mark.asyncio
    async def test_new_token_invalidates_previous(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that requesting new verification invalidates previous tokens.

        WHY: Only one valid token should exist at a time for security.
        """
        from app.dao.verification_token import VerificationTokenDAO

        # Create user
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="multi@test.com",
            organization=org,
        )
        user.email_verified = False
        await db_session.commit()

        # Create first token
        token_dao = VerificationTokenDAO(db_session)
        token1 = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )
        token1_str = token1.token
        await db_session.commit()

        # Create second token (should invalidate first)
        token2 = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )
        await db_session.commit()

        # First token should now be invalid
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": token1_str},
        )
        assert response.status_code == 400  # Token was invalidated

        # Second token should work
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": token2.token},
        )
        assert response.status_code == 200
