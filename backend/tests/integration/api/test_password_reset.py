"""
Integration tests for password reset API endpoints.

WHAT: Tests the password reset flow end-to-end:
1. Request password reset (forgot-password)
2. Reset password with token
3. Login with new password

WHY: Integration tests verify the complete flow works correctly:
- API endpoints
- Database operations
- Email service integration
- Token validation
- Password hashing
- Error handling

HOW: Uses httpx AsyncClient with test database and mocked email service.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_token import TokenType
from app.services.email import MockEmailProvider
from tests.factories import UserFactory, OrganizationFactory


class TestForgotPassword:
    """Tests for POST /api/auth/forgot-password endpoint."""

    @pytest.mark.asyncio
    async def test_forgot_password_existing_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test password reset request for existing user.

        WHY: Verifies that reset email is sent to existing users.
        """
        MockEmailProvider.clear_sent_emails()

        # Create user
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create(
            db_session,
            email="forgot@test.com",
            password="OldPassword123!",
            organization=org,
        )

        # Request password reset
        response = await client.post(
            "/api/auth/forgot-password",
            json={"email": "forgot@test.com"},
        )

        assert response.status_code == 200
        data = response.json()
        # Response should be generic to prevent user enumeration
        assert "If an account exists" in data["message"]

        # Verify email was sent
        assert len(MockEmailProvider.sent_emails) == 1
        sent = MockEmailProvider.sent_emails[0]
        assert sent.to_email == "forgot@test.com"
        assert "Reset" in sent.subject or "reset" in sent.subject.lower()

    @pytest.mark.asyncio
    async def test_forgot_password_nonexistent_user(self, client: AsyncClient):
        """
        Test password reset for non-existent email.

        WHY: Should return same response to prevent user enumeration.
        """
        MockEmailProvider.clear_sent_emails()

        response = await client.post(
            "/api/auth/forgot-password",
            json={"email": "nonexistent@test.com"},
        )

        assert response.status_code == 200
        data = response.json()
        # Same response as existing user (no enumeration)
        assert "If an account exists" in data["message"]

        # No email should be sent
        assert len(MockEmailProvider.sent_emails) == 0

    @pytest.mark.asyncio
    async def test_forgot_password_inactive_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test password reset for inactive user.

        WHY: Inactive users shouldn't receive reset emails.
        """
        MockEmailProvider.clear_sent_emails()

        # Create inactive user
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create(
            db_session,
            email="inactive@test.com",
            organization=org,
            is_active=False,
        )

        # Request password reset
        response = await client.post(
            "/api/auth/forgot-password",
            json={"email": "inactive@test.com"},
        )

        assert response.status_code == 200
        # Same response (no enumeration)
        assert "If an account exists" in response.json()["message"]

        # No email should be sent
        assert len(MockEmailProvider.sent_emails) == 0

    @pytest.mark.asyncio
    async def test_forgot_password_invalid_email_format(self, client: AsyncClient):
        """
        Test password reset with invalid email format.

        WHY: Should validate email format before processing.
        """
        response = await client.post(
            "/api/auth/forgot-password",
            json={"email": "not-an-email"},
        )

        # Could be 400 (custom validation) or 422 (Pydantic validation)
        assert response.status_code in [400, 422]


class TestResetPassword:
    """Tests for POST /api/auth/reset-password endpoint."""

    @pytest.mark.asyncio
    async def test_reset_password_with_valid_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test resetting password with valid token.

        WHY: Main reset flow - user enters new password with token from email.
        """
        from app.dao.verification_token import VerificationTokenDAO

        MockEmailProvider.clear_sent_emails()

        # Create user
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="reset@test.com",
            password="OldPassword123!",
            organization=org,
        )

        # Create reset token directly
        token_dao = VerificationTokenDAO(db_session)
        reset_token = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.PASSWORD_RESET,
            include_code=True,
        )
        await db_session.commit()

        # Reset password
        response = await client.post(
            "/api/auth/reset-password",
            json={
                "token": reset_token.token,
                "password": "NewPassword456!",
                "password_confirm": "NewPassword456!",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "successfully" in data["message"].lower()

        # Verify password changed notification was sent
        assert len(MockEmailProvider.sent_emails) == 1
        sent = MockEmailProvider.sent_emails[0]
        assert "changed" in sent.subject.lower() or "reset" in sent.subject.lower()

        # Verify old password no longer works
        login_old = await client.post(
            "/api/auth/login",
            json={"email": "reset@test.com", "password": "OldPassword123!"},
        )
        assert login_old.status_code == 401

        # Verify new password works
        login_new = await client.post(
            "/api/auth/login",
            json={"email": "reset@test.com", "password": "NewPassword456!"},
        )
        assert login_new.status_code == 200

    @pytest.mark.asyncio
    async def test_reset_password_passwords_dont_match(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test reset with mismatched passwords.

        WHY: Password confirmation prevents typos.
        """
        from app.dao.verification_token import VerificationTokenDAO

        # Create user and token
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="mismatch@test.com",
            organization=org,
        )

        token_dao = VerificationTokenDAO(db_session)
        reset_token = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.PASSWORD_RESET,
        )
        await db_session.commit()

        # Try to reset with mismatched passwords
        response = await client.post(
            "/api/auth/reset-password",
            json={
                "token": reset_token.token,
                "password": "NewPassword123!",
                "password_confirm": "DifferentPassword123!",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert "do not match" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, client: AsyncClient):
        """
        Test reset with invalid token.

        WHY: Invalid tokens should be rejected.
        """
        response = await client.post(
            "/api/auth/reset-password",
            json={
                "token": "invalid-token-string",
                "password": "NewPassword123!",
                "password_confirm": "NewPassword123!",
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_reset_password_expired_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test reset with expired token.

        WHY: Expired tokens should be rejected for security.
        """
        from datetime import datetime, timedelta
        from app.dao.verification_token import VerificationTokenDAO

        # Create user and token
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="expired-reset@test.com",
            organization=org,
        )

        token_dao = VerificationTokenDAO(db_session)
        reset_token = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.PASSWORD_RESET,
        )

        # Expire the token
        reset_token.expires_at = datetime.utcnow() - timedelta(hours=2)
        await db_session.commit()

        # Try to reset
        response = await client.post(
            "/api/auth/reset-password",
            json={
                "token": reset_token.token,
                "password": "NewPassword123!",
                "password_confirm": "NewPassword123!",
            },
        )

        assert response.status_code == 400
        assert "expired" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_reset_password_already_used_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test reset with already used token.

        WHY: Tokens are single-use to prevent replay attacks.
        """
        from datetime import datetime
        from app.dao.verification_token import VerificationTokenDAO

        # Create user and token
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="used-reset@test.com",
            organization=org,
        )

        token_dao = VerificationTokenDAO(db_session)
        reset_token = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.PASSWORD_RESET,
        )

        # Mark as used
        reset_token.used_at = datetime.utcnow()
        await db_session.commit()

        # Try to reset
        response = await client.post(
            "/api/auth/reset-password",
            json={
                "token": reset_token.token,
                "password": "NewPassword123!",
                "password_confirm": "NewPassword123!",
            },
        )

        assert response.status_code == 400
        assert "used" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_reset_password_weak_password(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test reset with weak password.

        WHY: New passwords must meet security requirements.
        """
        from app.dao.verification_token import VerificationTokenDAO

        # Create user and token
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="weak@test.com",
            organization=org,
        )

        token_dao = VerificationTokenDAO(db_session)
        reset_token = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.PASSWORD_RESET,
        )
        await db_session.commit()

        # Try with too short password
        response = await client.post(
            "/api/auth/reset-password",
            json={
                "token": reset_token.token,
                "password": "short",
                "password_confirm": "short",
            },
        )

        # Could be 400 (custom validation) or 422 (Pydantic validation)
        assert response.status_code in [400, 422]


class TestPasswordResetFlow:
    """End-to-end tests for the complete password reset flow."""

    @pytest.mark.asyncio
    async def test_complete_password_reset_flow(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test complete flow: forgot-password -> reset -> login.

        WHY: Verifies all components work together correctly.
        """
        MockEmailProvider.clear_sent_emails()

        # Step 1: Create user
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create(
            db_session,
            email="complete-flow@test.com",
            password="OldPassword123!",
            organization=org,
        )

        # Step 2: Request password reset
        forgot_response = await client.post(
            "/api/auth/forgot-password",
            json={"email": "complete-flow@test.com"},
        )
        assert forgot_response.status_code == 200

        # Verify email was sent
        assert len(MockEmailProvider.sent_emails) == 1

        # Step 3: Get the reset token from database
        from app.dao.verification_token import VerificationTokenDAO
        from app.dao.user import UserDAO
        from app.models.user import User
        from sqlalchemy import select, and_
        from app.models.verification_token import VerificationToken

        user_dao = UserDAO(User, db_session)
        user = await user_dao.get_by_email("complete-flow@test.com")

        stmt = select(VerificationToken).where(
            and_(
                VerificationToken.user_id == user.id,
                VerificationToken.token_type == TokenType.PASSWORD_RESET,
                VerificationToken.used_at.is_(None),
            )
        )
        result = await db_session.execute(stmt)
        reset_token = result.scalar_one()

        # Step 4: Reset password
        MockEmailProvider.clear_sent_emails()
        reset_response = await client.post(
            "/api/auth/reset-password",
            json={
                "token": reset_token.token,
                "password": "NewSecurePassword789!",
                "password_confirm": "NewSecurePassword789!",
            },
        )
        assert reset_response.status_code == 200

        # Verify password changed notification was sent
        assert len(MockEmailProvider.sent_emails) == 1

        # Step 5: Login with new password
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "complete-flow@test.com",
                "password": "NewSecurePassword789!",
            },
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()

    @pytest.mark.asyncio
    async def test_multiple_reset_requests_invalidate_previous(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that new reset requests invalidate previous tokens.

        WHY: Only one valid reset token should exist at a time.
        """
        from app.dao.verification_token import VerificationTokenDAO
        from sqlalchemy import select, and_
        from app.models.verification_token import VerificationToken
        from app.dao.user import UserDAO
        from app.models.user import User

        MockEmailProvider.clear_sent_emails()

        # Create user
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create(
            db_session,
            email="multi-reset@test.com",
            organization=org,
        )

        # First reset request
        await client.post(
            "/api/auth/forgot-password",
            json={"email": "multi-reset@test.com"},
        )

        user_dao = UserDAO(User, db_session)
        user = await user_dao.get_by_email("multi-reset@test.com")

        # Get first token
        stmt = select(VerificationToken).where(
            and_(
                VerificationToken.user_id == user.id,
                VerificationToken.token_type == TokenType.PASSWORD_RESET,
            )
        )
        result = await db_session.execute(stmt)
        first_token = result.scalar_one()
        first_token_str = first_token.token

        # Second reset request
        MockEmailProvider.clear_sent_emails()
        await client.post(
            "/api/auth/forgot-password",
            json={"email": "multi-reset@test.com"},
        )

        # First token should now be invalid
        reset_response = await client.post(
            "/api/auth/reset-password",
            json={
                "token": first_token_str,
                "password": "NewPassword123!",
                "password_confirm": "NewPassword123!",
            },
        )
        assert reset_response.status_code == 400  # Token was invalidated

    @pytest.mark.asyncio
    async def test_reset_token_has_1_hour_expiry(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that password reset tokens expire after 1 hour.

        WHY: Short expiry for security-sensitive operations.
        """
        from datetime import datetime, timedelta
        from app.dao.verification_token import VerificationTokenDAO

        # Create user
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(
            db_session,
            email="expiry@test.com",
            organization=org,
        )

        # Create reset token
        token_dao = VerificationTokenDAO(db_session)
        reset_token = await token_dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.PASSWORD_RESET,
        )

        # Verify expiry is ~1 hour
        time_until_expiry = reset_token.expires_at - datetime.utcnow()
        assert time_until_expiry < timedelta(hours=1, minutes=5)
        assert time_until_expiry > timedelta(minutes=55)
