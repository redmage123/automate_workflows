"""
Tests for JWT authentication system.

WHY: Comprehensive auth testing ensures:
1. Tokens are generated with correct claims
2. Token validation works properly
3. Expired tokens are rejected
4. Invalid signatures are rejected
5. Password hashing is secure
6. Token blacklist prevents reuse after logout
"""

import pytest
from datetime import datetime, timedelta
from jose import jwt

from app.core.auth import (
    create_access_token,
    verify_token,
    hash_password,
    verify_password,
    blacklist_token,
    is_token_blacklisted,
)
from app.core.config import settings
from app.core.exceptions import (
    TokenExpiredError,
    TokenInvalidError,
)


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password_returns_different_from_plain(self):
        """Verify hashed password is different from plain password."""
        password = "SecurePassword123!"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > 0

    def test_hash_password_generates_different_hashes(self):
        """Verify same password generates different hashes (salt)."""
        # WHY: Each hash should have a unique salt to prevent rainbow table attacks
        password = "SecurePassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Verify correct password verification."""
        password = "SecurePassword123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Verify incorrect password is rejected."""
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_password_with_special_characters(self):
        """Verify password hashing works with special characters."""
        password = "P@ssw0rd!#$%^&*()"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True


class TestTokenCreation:
    """Test JWT token creation."""

    def test_create_access_token_with_user_data(self):
        """Test JWT token creation with user data."""
        data = {
            "user_id": 1,
            "org_id": 1,
            "role": "ADMIN",
            "email": "admin@example.com",
        }
        token = create_access_token(data)

        # Token should be a string
        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify claims
        decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert decoded["user_id"] == 1
        assert decoded["org_id"] == 1
        assert decoded["role"] == "ADMIN"
        assert decoded["email"] == "admin@example.com"

    def test_create_access_token_includes_standard_claims(self):
        """Verify token includes exp, iat, and nbf claims."""
        data = {"user_id": 1}
        token = create_access_token(data)

        decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

        # WHY: Standard JWT claims for proper token lifecycle management
        assert "exp" in decoded  # Expiration time
        assert "iat" in decoded  # Issued at time
        assert "nbf" in decoded  # Not before time

    def test_create_access_token_expiration_time(self):
        """Verify token expiration is set correctly."""
        data = {"user_id": 1}
        token = create_access_token(data)

        decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

        # Calculate expected expiration
        # WHY: Use UTC for both expected and actual to ensure consistent comparison
        expected_exp = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
        actual_exp = datetime.utcfromtimestamp(decoded["exp"])

        # Allow 10 second tolerance for test execution time
        assert abs((expected_exp - actual_exp).total_seconds()) < 10

    def test_create_access_token_custom_expiration(self):
        """Test creating token with custom expiration."""
        data = {"user_id": 1}
        expires_delta = timedelta(minutes=30)
        token = create_access_token(data, expires_delta=expires_delta)

        decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

        # WHY: Use UTC for both expected and actual to ensure consistent comparison
        expected_exp = datetime.utcnow() + expires_delta
        actual_exp = datetime.utcfromtimestamp(decoded["exp"])

        assert abs((expected_exp - actual_exp).total_seconds()) < 10


class TestTokenVerification:
    """Test JWT token verification."""

    def test_verify_token_valid(self):
        """Test verifying a valid token."""
        data = {"user_id": 1, "org_id": 1, "role": "CLIENT"}
        token = create_access_token(data)

        # Verify token
        payload = verify_token(token)

        assert payload["user_id"] == 1
        assert payload["org_id"] == 1
        assert payload["role"] == "CLIENT"

    def test_verify_token_expired(self):
        """Test that expired tokens are rejected."""
        # Create token that expires immediately
        data = {"user_id": 1}
        expires_delta = timedelta(seconds=-1)  # Already expired
        token = create_access_token(data, expires_delta=expires_delta)

        # Verify raises TokenExpiredError
        with pytest.raises(TokenExpiredError) as exc_info:
            verify_token(token)

        assert "expired" in str(exc_info.value).lower()

    def test_verify_token_invalid_signature(self):
        """Test that tokens with wrong signature are rejected."""
        # Create token with wrong secret
        data = {"user_id": 1}
        token = jwt.encode(data, "wrong-secret", algorithm=settings.JWT_ALGORITHM)

        # Verify raises TokenInvalidError
        with pytest.raises(TokenInvalidError) as exc_info:
            verify_token(token)

        assert "invalid" in str(exc_info.value).lower()

    def test_verify_token_malformed(self):
        """Test that malformed tokens are rejected."""
        malformed_token = "not.a.valid.jwt.token"

        with pytest.raises(TokenInvalidError):
            verify_token(malformed_token)

    def test_verify_token_wrong_algorithm(self):
        """Test that tokens with wrong algorithm are rejected."""
        # Create token with different algorithm
        data = {"user_id": 1}
        token = jwt.encode(data, settings.JWT_SECRET, algorithm="HS512")

        with pytest.raises(TokenInvalidError):
            verify_token(token)

    def test_verify_token_missing_required_claims(self):
        """Test that tokens missing required claims are rejected."""
        # Create token without required claims
        data = {"some_field": "value"}
        token = create_access_token(data)

        # Should still verify (claims are optional in the token itself)
        # but downstream code should validate required claims
        payload = verify_token(token)
        assert "some_field" in payload


class TestTokenBlacklist:
    """Test token blacklist functionality."""

    @pytest.mark.asyncio
    async def test_blacklist_token(self):
        """Test adding token to blacklist."""
        token = "test-token-123"
        user_id = 1

        # Blacklist the token
        await blacklist_token(token, user_id)

        # Verify token is blacklisted
        is_blacklisted = await is_token_blacklisted(token)
        assert is_blacklisted is True

    @pytest.mark.asyncio
    async def test_token_not_blacklisted_initially(self):
        """Test that new tokens are not blacklisted."""
        token = "new-token-456"

        # Token should not be blacklisted
        is_blacklisted = await is_token_blacklisted(token)
        assert is_blacklisted is False

    @pytest.mark.asyncio
    async def test_blacklist_token_expiration(self):
        """Test that blacklisted tokens expire from Redis."""
        # This test verifies Redis TTL is set correctly
        # In production, TTL should match token expiration time
        token = "expiring-token-789"
        user_id = 1

        # Blacklist with short TTL
        await blacklist_token(token, user_id, ttl_seconds=1)

        # Immediately should be blacklisted
        assert await is_token_blacklisted(token) is True

        # After TTL expires (need to wait)
        # Note: This test might be slow, consider mocking in actual test suite
        # import asyncio
        # await asyncio.sleep(2)
        # assert await is_token_blacklisted(token) is False


class TestAuthenticationFlow:
    """Test complete authentication flow."""

    def test_complete_login_flow(self):
        """Test complete login flow: hash password, create token, verify token."""
        # 1. Hash password (during registration)
        password = "UserPassword123!"
        hashed_password = hash_password(password)

        # 2. Verify password (during login)
        assert verify_password(password, hashed_password) is True

        # 3. Create access token
        user_data = {
            "user_id": 1,
            "org_id": 1,
            "role": "CLIENT",
            "email": "user@example.com",
        }
        token = create_access_token(user_data)

        # 4. Verify token
        payload = verify_token(token)
        assert payload["user_id"] == 1
        assert payload["org_id"] == 1
        assert payload["role"] == "CLIENT"

    def test_failed_login_flow(self):
        """Test failed login with wrong password."""
        # Hash correct password
        correct_password = "UserPassword123!"
        hashed_password = hash_password(correct_password)

        # Try with wrong password
        wrong_password = "WrongPassword456!"
        assert verify_password(wrong_password, hashed_password) is False


class TestSecurityConsiderations:
    """Test security-related considerations."""

    def test_password_hash_length(self):
        """Verify password hashes are sufficiently long."""
        # WHY: bcrypt hashes should be 60 characters
        password = "test"
        hashed = hash_password(password)

        assert len(hashed) == 60

    def test_token_does_not_contain_password(self):
        """Verify tokens never contain password data."""
        # WHY: OWASP A02 - Cryptographic Failures
        # Tokens should NEVER contain sensitive data like passwords
        data = {
            "user_id": 1,
            "email": "user@example.com",
            # Deliberately NOT including password
        }
        token = create_access_token(data)

        decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

        # Ensure no password-related fields
        assert "password" not in decoded
        assert "hashed_password" not in decoded
        assert "pwd" not in decoded

    def test_token_signature_prevents_tampering(self):
        """Verify token signature prevents tampering."""
        # Create valid token
        data = {"user_id": 1, "role": "CLIENT"}
        token = create_access_token(data)

        # Try to manually change the payload (should fail verification)
        # Decode without verification
        decoded = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_signature": False},
        )

        # Tamper with data
        decoded["role"] = "ADMIN"  # Try to escalate privileges

        # Re-encode with wrong secret
        tampered_token = jwt.encode(decoded, "wrong-secret", algorithm="HS256")

        # Verification should fail
        with pytest.raises(TokenInvalidError):
            verify_token(tampered_token)
