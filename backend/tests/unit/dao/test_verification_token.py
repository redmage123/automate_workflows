"""
Unit tests for VerificationTokenDAO.

WHAT: Tests the VerificationTokenDAO for managing email verification
and password reset tokens.

WHY: DAO tests ensure data access operations work correctly:
1. Token creation with proper expiration
2. Token lookup by token string and code
3. Token consumption (marking as used)
4. Token invalidation
5. Expired token handling

HOW: Uses pytest with async SQLite database for isolated testing.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.verification_token import VerificationTokenDAO
from app.models.verification_token import VerificationToken, TokenType
from app.core.exceptions import ResourceNotFoundError, ValidationError
from tests.factories import UserFactory, OrganizationFactory


class TestVerificationTokenDAO:
    """Unit tests for VerificationTokenDAO."""

    @pytest.mark.asyncio
    async def test_create_verification_token(self, db_session: AsyncSession):
        """
        Test creating a verification token.

        WHY: Verifies that tokens are created with:
        - Cryptographically secure token string
        - Optional 6-digit code
        - Correct expiration time
        - User association
        """
        # Create user
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        # Create token
        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
            include_code=True,
        )

        # Verify token was created correctly
        assert token.id is not None
        assert token.user_id == user.id
        assert token.token_type == TokenType.EMAIL_VERIFICATION
        assert len(token.token) == 43  # URL-safe base64 of 32 bytes
        assert token.code is not None
        assert len(token.code) == 6
        assert token.code.isdigit()
        assert token.is_valid  # Not expired and not used
        assert token.expires_at > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_create_password_reset_token_has_shorter_expiry(
        self, db_session: AsyncSession
    ):
        """
        Test that password reset tokens have 1 hour expiry.

        WHY: Password reset is security-sensitive and should have
        shorter expiration than email verification (1h vs 24h).
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.PASSWORD_RESET,
        )

        # Password reset should expire in ~1 hour
        time_until_expiry = token.expires_at - datetime.utcnow()
        assert time_until_expiry < timedelta(hours=1, minutes=5)
        assert time_until_expiry > timedelta(minutes=55)

    @pytest.mark.asyncio
    async def test_create_email_verification_token_has_24h_expiry(
        self, db_session: AsyncSession
    ):
        """
        Test that email verification tokens have 24 hour expiry.

        WHY: Email verification can be done later, so longer expiry is OK.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Email verification should expire in ~24 hours
        time_until_expiry = token.expires_at - datetime.utcnow()
        assert time_until_expiry < timedelta(hours=24, minutes=5)
        assert time_until_expiry > timedelta(hours=23, minutes=55)

    @pytest.mark.asyncio
    async def test_create_token_without_code(self, db_session: AsyncSession):
        """
        Test creating a token without a 6-digit code.

        WHY: Some flows only need the full token (e.g., email links only).
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
            include_code=False,
        )

        assert token.token is not None
        assert token.code is None

    @pytest.mark.asyncio
    async def test_create_token_with_ip_address(self, db_session: AsyncSession):
        """
        Test that IP address is stored for security audit.

        WHY: IP tracking helps detect suspicious patterns like
        multiple reset requests from different locations.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.PASSWORD_RESET,
            ip_address="192.168.1.100",
        )

        assert token.created_ip == "192.168.1.100"
        assert token.used_ip is None  # Not used yet

    @pytest.mark.asyncio
    async def test_get_by_token(self, db_session: AsyncSession):
        """
        Test finding a token by its token string.

        WHY: Primary lookup method when user clicks verification link.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        created_token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Find by token
        found_token = await dao.get_by_token(created_token.token)

        assert found_token is not None
        assert found_token.id == created_token.id
        assert found_token.user_id == user.id

    @pytest.mark.asyncio
    async def test_get_by_token_with_type_filter(self, db_session: AsyncSession):
        """
        Test finding a token with type filter for added security.

        WHY: Prevents using an email verification token as a password reset.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Should find with correct type
        found = await dao.get_by_token(token.token, TokenType.EMAIL_VERIFICATION)
        assert found is not None

        # Should NOT find with wrong type
        not_found = await dao.get_by_token(token.token, TokenType.PASSWORD_RESET)
        assert not_found is None

    @pytest.mark.asyncio
    async def test_get_by_token_not_found(self, db_session: AsyncSession):
        """
        Test that non-existent tokens return None.

        WHY: Must handle invalid tokens gracefully without errors.
        """
        dao = VerificationTokenDAO(db_session)
        found = await dao.get_by_token("nonexistent-token-string")
        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_code(self, db_session: AsyncSession):
        """
        Test finding a token by 6-digit code.

        WHY: Alternative lookup for mobile users who enter code manually.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
            include_code=True,
        )

        # Find by code (requires user_id and type)
        found = await dao.get_by_code(
            user_id=user.id,
            code=token.code,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        assert found is not None
        assert found.id == token.id

    @pytest.mark.asyncio
    async def test_get_by_code_wrong_user(self, db_session: AsyncSession):
        """
        Test that codes are scoped to user.

        WHY: Codes are not globally unique, so must be scoped to user.
        """
        org = await OrganizationFactory.create(db_session)
        user1 = await UserFactory.create(db_session, email="user1@test.com", organization=org)
        user2 = await UserFactory.create(db_session, email="user2@test.com", organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user1.id,
            token_type=TokenType.EMAIL_VERIFICATION,
            include_code=True,
        )

        # Should not find with wrong user_id
        not_found = await dao.get_by_code(
            user_id=user2.id,
            code=token.code,
            token_type=TokenType.EMAIL_VERIFICATION,
        )
        assert not_found is None

    @pytest.mark.asyncio
    async def test_get_valid_token(self, db_session: AsyncSession):
        """
        Test getting a valid (unexpired and unused) token.

        WHY: Common pattern - need valid token, not just any token.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Should find valid token
        found = await dao.get_valid_token(token.token)
        assert found is not None
        assert found.id == token.id

    @pytest.mark.asyncio
    async def test_get_valid_token_excludes_used(self, db_session: AsyncSession):
        """
        Test that used tokens are not returned as valid.

        WHY: Single-use tokens prevent replay attacks.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Mark as used
        await dao.mark_as_used(token.id)

        # Should not find as valid
        found = await dao.get_valid_token(token.token)
        assert found is None

    @pytest.mark.asyncio
    async def test_mark_as_used(self, db_session: AsyncSession):
        """
        Test marking a token as used.

        WHY: Single-use tokens prevent replay attacks.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Mark as used with IP
        updated = await dao.mark_as_used(token.id, ip_address="10.0.0.1")

        assert updated.used_at is not None
        assert updated.used_ip == "10.0.0.1"
        assert updated.is_used
        assert not updated.is_valid  # Used tokens are not valid

    @pytest.mark.asyncio
    async def test_mark_as_used_already_used_raises_error(
        self, db_session: AsyncSession
    ):
        """
        Test that marking an already-used token raises error.

        WHY: Prevents double-use of tokens.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # First use succeeds
        await dao.mark_as_used(token.id)

        # Second use should fail
        with pytest.raises(ValidationError) as exc_info:
            await dao.mark_as_used(token.id)

        assert "already been used" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mark_as_used_not_found_raises_error(
        self, db_session: AsyncSession
    ):
        """
        Test that marking a non-existent token raises error.
        """
        dao = VerificationTokenDAO(db_session)

        with pytest.raises(ResourceNotFoundError):
            await dao.mark_as_used(99999)

    @pytest.mark.asyncio
    async def test_invalidate_previous_tokens(self, db_session: AsyncSession):
        """
        Test invalidating previous tokens of the same type.

        WHY: Only one active token per type per user for security.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)

        # Create first token (don't auto-invalidate)
        token1 = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
            invalidate_previous=False,
        )

        # Create second token (don't auto-invalidate)
        token2 = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
            invalidate_previous=False,
        )

        # Both should be valid
        assert await dao.get_valid_token(token1.token) is not None
        assert await dao.get_valid_token(token2.token) is not None

        # Invalidate previous
        count = await dao.invalidate_previous_tokens(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )
        assert count == 2

        # Both should now be invalid
        assert await dao.get_valid_token(token1.token) is None
        assert await dao.get_valid_token(token2.token) is None

    @pytest.mark.asyncio
    async def test_create_token_auto_invalidates_previous(
        self, db_session: AsyncSession
    ):
        """
        Test that creating a token auto-invalidates previous tokens.

        WHY: Default behavior ensures only one valid token per type.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)

        # Create first token
        token1 = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Create second token (auto-invalidates first)
        token2 = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # First should be invalid, second should be valid
        assert await dao.get_valid_token(token1.token) is None
        assert await dao.get_valid_token(token2.token) is not None

    @pytest.mark.asyncio
    async def test_validate_and_consume_token(self, db_session: AsyncSession):
        """
        Test validating and consuming a token in one operation.

        WHY: Atomic validation + consumption prevents race conditions.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Validate and consume
        consumed = await dao.validate_and_consume_token(
            token=token.token,
            expected_type=TokenType.EMAIL_VERIFICATION,
            ip_address="172.16.0.1",
        )

        assert consumed.id == token.id
        assert consumed.is_used
        assert consumed.used_ip == "172.16.0.1"

    @pytest.mark.asyncio
    async def test_validate_and_consume_wrong_type_raises_error(
        self, db_session: AsyncSession
    ):
        """
        Test that wrong token type raises error.

        WHY: Prevents using verification token for password reset.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Try to consume as password reset
        with pytest.raises(ResourceNotFoundError):
            await dao.validate_and_consume_token(
                token=token.token,
                expected_type=TokenType.PASSWORD_RESET,
            )

    @pytest.mark.asyncio
    async def test_validate_and_consume_expired_token_raises_error(
        self, db_session: AsyncSession
    ):
        """
        Test that expired tokens raise error.

        WHY: Time-limited tokens prevent stale token attacks.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # Manually expire the token
        token.expires_at = datetime.utcnow() - timedelta(hours=1)
        await db_session.flush()

        # Try to consume expired token
        with pytest.raises(ValidationError) as exc_info:
            await dao.validate_and_consume_token(
                token=token.token,
                expected_type=TokenType.EMAIL_VERIFICATION,
            )

        assert "expired" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_and_consume_used_token_raises_error(
        self, db_session: AsyncSession
    ):
        """
        Test that already-used tokens raise error.

        WHY: Single-use tokens prevent replay attacks.
        """
        org = await OrganizationFactory.create(db_session)
        user = await UserFactory.create(db_session, organization=org)

        dao = VerificationTokenDAO(db_session)
        token = await dao.create_verification_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
        )

        # First consumption succeeds
        await dao.validate_and_consume_token(
            token=token.token,
            expected_type=TokenType.EMAIL_VERIFICATION,
        )

        # Second consumption should fail
        with pytest.raises(ValidationError) as exc_info:
            await dao.validate_and_consume_token(
                token=token.token,
                expected_type=TokenType.EMAIL_VERIFICATION,
            )

        assert "already been used" in str(exc_info.value).lower()


class TestVerificationTokenModel:
    """Unit tests for VerificationToken model helper methods."""

    def test_generate_token_is_url_safe(self):
        """
        Test that generated tokens are URL-safe.

        WHY: Tokens are used in email links, so must be URL-safe.
        """
        token = VerificationToken.generate_token()

        # URL-safe base64 uses only alphanumeric, -, and _
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', token)
        assert len(token) == 43  # 32 bytes -> 43 chars in base64

    def test_generate_token_is_unique(self):
        """
        Test that generated tokens are unique.

        WHY: Token collisions would be a security vulnerability.
        """
        tokens = [VerificationToken.generate_token() for _ in range(100)]
        assert len(set(tokens)) == 100  # All unique

    def test_generate_code_is_6_digits(self):
        """
        Test that generated codes are exactly 6 digits.

        WHY: Consistent format for UX.
        """
        for _ in range(100):
            code = VerificationToken.generate_code()
            assert len(code) == 6
            assert code.isdigit()

    def test_get_expiration_email_verification(self):
        """
        Test email verification expiration is 24 hours.
        """
        expiry = VerificationToken.get_expiration(TokenType.EMAIL_VERIFICATION)
        time_diff = expiry - datetime.utcnow()
        assert timedelta(hours=23, minutes=55) < time_diff < timedelta(hours=24, minutes=5)

    def test_get_expiration_password_reset(self):
        """
        Test password reset expiration is 1 hour.
        """
        expiry = VerificationToken.get_expiration(TokenType.PASSWORD_RESET)
        time_diff = expiry - datetime.utcnow()
        assert timedelta(minutes=55) < time_diff < timedelta(hours=1, minutes=5)

    def test_is_expired_property(self):
        """
        Test is_expired property.
        """
        token = VerificationToken(
            token="test",
            token_type=TokenType.EMAIL_VERIFICATION,
            user_id=1,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        assert token.is_expired

        token.expires_at = datetime.utcnow() + timedelta(hours=1)
        assert not token.is_expired

    def test_is_used_property(self):
        """
        Test is_used property.
        """
        token = VerificationToken(
            token="test",
            token_type=TokenType.EMAIL_VERIFICATION,
            user_id=1,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        assert not token.is_used

        token.used_at = datetime.utcnow()
        assert token.is_used

    def test_is_valid_property(self):
        """
        Test is_valid property (not expired AND not used).
        """
        # Valid: not expired, not used
        token = VerificationToken(
            token="test",
            token_type=TokenType.EMAIL_VERIFICATION,
            user_id=1,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=None,
        )
        assert token.is_valid

        # Invalid: expired
        token.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert not token.is_valid

        # Invalid: used
        token.expires_at = datetime.utcnow() + timedelta(hours=1)
        token.used_at = datetime.utcnow()
        assert not token.is_valid
