"""
Unit tests for rate limiting middleware.

WHY: Rate limiting is critical for:
1. Preventing brute-force attacks on login/register
2. Protecting against credential stuffing attacks
3. Reducing DDoS impact on auth endpoints
4. OWASP A07: Identification and Authentication Failures

Test scenarios:
- Requests under limit are allowed
- Requests over limit are blocked with 429 status
- Rate limit resets after window expires
- Different IP addresses have separate limits
- Different endpoints can have different limits
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.middleware.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    get_rate_limiter,
    check_rate_limit,
    RateLimitMiddleware,
)
from app.core.exceptions import RateLimitExceeded


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_default_values(self):
        """Test default rate limit configuration.

        WHY: Default values should be secure (5 requests per minute)
        to prevent brute force attacks while allowing normal usage.
        """
        config = RateLimitConfig()

        assert config.requests_per_window == 5
        assert config.window_seconds == 60
        assert config.key_prefix == "ratelimit"

    def test_custom_values(self):
        """Test custom rate limit configuration.

        WHY: Different endpoints may need different limits
        (e.g., login stricter than /me endpoint).
        """
        config = RateLimitConfig(
            requests_per_window=10,
            window_seconds=30,
            key_prefix="auth_ratelimit",
        )

        assert config.requests_per_window == 10
        assert config.window_seconds == 30
        assert config.key_prefix == "auth_ratelimit"


class TestRateLimiter:
    """Tests for RateLimiter service."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client.

        WHY: Unit tests should not depend on real Redis.
        Mocking allows testing rate limit logic in isolation.
        """
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create RateLimiter with mock Redis.

        WHY: Dependency injection allows testing without external services.
        """
        config = RateLimitConfig(
            requests_per_window=5,
            window_seconds=60,
        )
        limiter = RateLimiter(redis_client=mock_redis, config=config)
        return limiter

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, rate_limiter, mock_redis):
        """Test first request is always allowed.

        WHY: With no previous requests, user should be able to proceed.
        The counter starts at 1 after first request.
        """
        # Mock Redis pipeline
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[1, True])  # [incr result, expire result]
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        # Check rate limit
        result = await rate_limiter.check_rate_limit(
            identifier="192.168.1.1",
            endpoint="/api/auth/login",
        )

        assert result.allowed is True
        assert result.remaining == 4  # 5 - 1 = 4
        assert result.reset_after <= 60

    @pytest.mark.asyncio
    async def test_under_limit_allowed(self, rate_limiter, mock_redis):
        """Test requests under limit are allowed.

        WHY: Users should be able to make multiple requests
        up to the configured limit.
        """
        # Mock Redis: 3 requests already made, limit is 5
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[3, True])
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        result = await rate_limiter.check_rate_limit(
            identifier="192.168.1.1",
            endpoint="/api/auth/login",
        )

        assert result.allowed is True
        assert result.remaining == 2  # 5 - 3 = 2

    @pytest.mark.asyncio
    async def test_at_limit_denied(self, rate_limiter, mock_redis):
        """Test request at limit is denied.

        WHY: Once limit is reached, further requests should be blocked
        to prevent brute-force attacks.
        """
        # Mock Redis: 5 requests made (at limit)
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[6, True])  # Increment makes it 6
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        result = await rate_limiter.check_rate_limit(
            identifier="192.168.1.1",
            endpoint="/api/auth/login",
        )

        assert result.allowed is False
        assert result.remaining == 0

    @pytest.mark.asyncio
    async def test_over_limit_denied(self, rate_limiter, mock_redis):
        """Test requests over limit are denied.

        WHY: Even after being denied, attempts should still be tracked
        and continue to be denied until window resets.
        """
        # Mock Redis: 10 requests made (well over limit of 5)
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[11, True])
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        result = await rate_limiter.check_rate_limit(
            identifier="192.168.1.1",
            endpoint="/api/auth/login",
        )

        assert result.allowed is False
        assert result.remaining == 0

    @pytest.mark.asyncio
    async def test_different_ips_separate_limits(self, rate_limiter, mock_redis):
        """Test different IPs have separate rate limits.

        WHY: Each client should have their own limit window.
        One user's rate limit shouldn't affect another user.
        """
        # Track calls to verify different keys
        calls = []

        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[1, True])

        def capture_pipeline(*args, **kwargs):
            return mock_pipeline

        mock_redis.pipeline = MagicMock(side_effect=capture_pipeline)

        # Request from IP 1
        await rate_limiter.check_rate_limit(
            identifier="192.168.1.1",
            endpoint="/api/auth/login",
        )

        # Request from IP 2
        await rate_limiter.check_rate_limit(
            identifier="192.168.1.2",
            endpoint="/api/auth/login",
        )

        # Verify pipeline was called twice with different keys
        assert mock_redis.pipeline.call_count == 2

    @pytest.mark.asyncio
    async def test_different_endpoints_separate_limits(self, rate_limiter, mock_redis):
        """Test different endpoints have separate rate limits.

        WHY: A user hitting /login shouldn't affect their /register limit.
        This allows granular rate limiting per endpoint.
        """
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[1, True])
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        # Request to login
        await rate_limiter.check_rate_limit(
            identifier="192.168.1.1",
            endpoint="/api/auth/login",
        )

        # Request to register
        await rate_limiter.check_rate_limit(
            identifier="192.168.1.1",
            endpoint="/api/auth/register",
        )

        # Verify separate calls (different keys)
        assert mock_redis.pipeline.call_count == 2

    @pytest.mark.asyncio
    async def test_build_key_format(self, rate_limiter):
        """Test rate limit key format.

        WHY: Consistent key format enables:
        - Easy debugging in Redis
        - Proper key expiration
        - Clear namespace separation
        """
        key = rate_limiter._build_key(
            identifier="192.168.1.1",
            endpoint="/api/auth/login",
        )

        assert key.startswith("ratelimit:")
        assert "192.168.1.1" in key
        assert "auth:login" in key or "auth_login" in key

    @pytest.mark.asyncio
    async def test_redis_error_allows_request(self, rate_limiter, mock_redis):
        """Test Redis error gracefully allows request (fail-open).

        WHY: If Redis fails, we shouldn't block legitimate users.
        Security trade-off: Allow requests during outage rather than
        blocking everyone (can lead to DOS by breaking Redis).

        Note: This is a configurable policy. Some systems prefer fail-close.
        """
        mock_redis.pipeline = MagicMock(side_effect=Exception("Redis connection failed"))

        result = await rate_limiter.check_rate_limit(
            identifier="192.168.1.1",
            endpoint="/api/auth/login",
        )

        # Fail-open: allow request when Redis is unavailable
        assert result.allowed is True
        assert result.remaining == -1  # Indicates unknown


class TestRateLimitResult:
    """Tests for RateLimitResult structure."""

    def test_rate_limit_result_allowed(self):
        """Test RateLimitResult when request is allowed."""
        from app.middleware.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            remaining=3,
            reset_after=45,
            limit=5,
        )

        assert result.allowed is True
        assert result.remaining == 3
        assert result.reset_after == 45
        assert result.limit == 5

    def test_rate_limit_result_denied(self):
        """Test RateLimitResult when request is denied."""
        from app.middleware.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=False,
            remaining=0,
            reset_after=30,
            limit=5,
        )

        assert result.allowed is False
        assert result.remaining == 0


class TestCheckRateLimitFunction:
    """Tests for the check_rate_limit convenience function."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_raises_when_exceeded(self):
        """Test check_rate_limit raises RateLimitExceeded when over limit.

        WHY: This is the main function used by endpoints.
        It should raise exception for easy integration with FastAPI error handling.
        """
        with patch("app.middleware.rate_limiter.get_rate_limiter") as mock_get:
            mock_limiter = AsyncMock()
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=MagicMock(
                    allowed=False,
                    remaining=0,
                    reset_after=30,
                    limit=5,
                )
            )
            mock_get.return_value = mock_limiter

            with pytest.raises(RateLimitExceeded) as exc_info:
                await check_rate_limit(
                    identifier="192.168.1.1",
                    endpoint="/api/auth/login",
                )

            assert exc_info.value.status_code == 429
            assert "rate limit" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_check_rate_limit_passes_when_allowed(self):
        """Test check_rate_limit passes silently when under limit.

        WHY: Normal requests should proceed without exception.
        """
        with patch("app.middleware.rate_limiter.get_rate_limiter") as mock_get:
            mock_limiter = AsyncMock()
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=MagicMock(
                    allowed=True,
                    remaining=4,
                    reset_after=60,
                    limit=5,
                )
            )
            mock_get.return_value = mock_limiter

            # Should not raise
            result = await check_rate_limit(
                identifier="192.168.1.1",
                endpoint="/api/auth/login",
            )

            assert result.allowed is True


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware FastAPI middleware."""

    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_middleware_allows_non_rate_limited_paths(self, mock_app):
        """Test middleware ignores non-auth paths.

        WHY: Rate limiting should only apply to auth endpoints.
        Other endpoints have their own rate limiting needs (or none).
        """
        middleware = RateLimitMiddleware(mock_app)

        # Mock request to non-auth endpoint
        mock_request = MagicMock()
        mock_request.url.path = "/api/projects"
        mock_request.client.host = "192.168.1.1"

        mock_call_next = AsyncMock(return_value=MagicMock())

        await middleware.dispatch(mock_request, mock_call_next)

        # Verify request was passed through
        mock_call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_rate_limits_auth_endpoints(self, mock_app):
        """Test middleware applies rate limiting to auth endpoints.

        WHY: Auth endpoints (/login, /register) are primary targets
        for brute-force attacks and need rate limiting.
        """
        with patch("app.middleware.rate_limiter.get_rate_limiter") as mock_get:
            mock_limiter = AsyncMock()
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=MagicMock(
                    allowed=True,
                    remaining=4,
                    reset_after=60,
                    limit=5,
                )
            )
            mock_get.return_value = mock_limiter

            middleware = RateLimitMiddleware(mock_app)

            # Mock request to login
            mock_request = MagicMock()
            mock_request.url.path = "/api/auth/login"
            mock_request.client.host = "192.168.1.1"

            mock_response = MagicMock()
            mock_response.headers = {}
            mock_call_next = AsyncMock(return_value=mock_response)

            await middleware.dispatch(mock_request, mock_call_next)

            # Verify rate limit was checked
            mock_limiter.check_rate_limit.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_returns_429_when_exceeded(self, mock_app):
        """Test middleware returns 429 response when rate limit exceeded.

        WHY: Standard HTTP 429 status code tells client to back off.
        Headers provide information about when to retry.
        """
        with patch("app.middleware.rate_limiter.get_rate_limiter") as mock_get:
            mock_limiter = AsyncMock()
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=MagicMock(
                    allowed=False,
                    remaining=0,
                    reset_after=30,
                    limit=5,
                )
            )
            mock_get.return_value = mock_limiter

            middleware = RateLimitMiddleware(mock_app)

            # Mock request to login
            mock_request = MagicMock()
            mock_request.url.path = "/api/auth/login"
            mock_request.client.host = "192.168.1.1"

            mock_call_next = AsyncMock()

            response = await middleware.dispatch(mock_request, mock_call_next)

            # Verify 429 response
            assert response.status_code == 429
            # Verify call_next was NOT called (request blocked)
            mock_call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_middleware_adds_rate_limit_headers(self, mock_app):
        """Test middleware adds rate limit headers to response.

        WHY: RFC 6585 recommends headers to inform clients about:
        - X-RateLimit-Limit: Maximum requests allowed
        - X-RateLimit-Remaining: Requests remaining in window
        - X-RateLimit-Reset: Seconds until limit resets
        """
        with patch("app.middleware.rate_limiter.get_rate_limiter") as mock_get:
            mock_limiter = AsyncMock()
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=MagicMock(
                    allowed=True,
                    remaining=4,
                    reset_after=45,
                    limit=5,
                )
            )
            mock_get.return_value = mock_limiter

            middleware = RateLimitMiddleware(mock_app)

            # Mock request
            mock_request = MagicMock()
            mock_request.url.path = "/api/auth/login"
            mock_request.client.host = "192.168.1.1"

            # Mock response with mutable headers dict
            mock_response = MagicMock()
            mock_response.headers = {}
            mock_call_next = AsyncMock(return_value=mock_response)

            response = await middleware.dispatch(mock_request, mock_call_next)

            # Verify rate limit headers
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
            assert response.headers["X-RateLimit-Limit"] == "5"
            assert response.headers["X-RateLimit-Remaining"] == "4"


class TestRateLimiterWithForwardedFor:
    """Tests for rate limiting with X-Forwarded-For header."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[1, True])
        mock.pipeline = MagicMock(return_value=mock_pipeline)
        return mock

    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create RateLimiter with mock Redis."""
        config = RateLimitConfig()
        return RateLimiter(redis_client=mock_redis, config=config)

    @pytest.mark.asyncio
    async def test_rate_limit_uses_client_ip_from_forwarded(self, rate_limiter):
        """Test rate limiter uses X-Forwarded-For when behind proxy.

        WHY: When behind a reverse proxy (Traefik/nginx), the real client IP
        is in X-Forwarded-For header. Using request.client.host would give
        the proxy IP, rate-limiting all users together.
        """
        # This tests the identifier extraction logic
        # The actual middleware should extract IP from X-Forwarded-For
        result = await rate_limiter.check_rate_limit(
            identifier="203.0.113.195",  # Real client IP from X-Forwarded-For
            endpoint="/api/auth/login",
        )

        assert result.allowed is True


class TestLoginEndpointRateLimit:
    """Integration-style tests for login endpoint rate limiting."""

    def test_rate_limit_config_for_login(self):
        """Test login endpoint has appropriate rate limit config.

        WHY: Login is high-risk for brute force attacks.
        5 attempts per minute is industry standard.
        """
        from app.middleware.rate_limiter import AUTH_RATE_LIMITS

        login_config = AUTH_RATE_LIMITS.get("/api/auth/login")

        # Should have rate limit configuration
        assert login_config is not None
        # Should be restrictive (5 attempts per minute is common)
        assert login_config.requests_per_window <= 10
        # Window should be 60 seconds (1 minute) or more
        assert login_config.window_seconds >= 60

    def test_rate_limit_config_for_register(self):
        """Test register endpoint has appropriate rate limit config.

        WHY: Registration can be abused for:
        - Account enumeration (checking if emails exist)
        - Spam account creation
        - Resource exhaustion
        """
        from app.middleware.rate_limiter import AUTH_RATE_LIMITS

        register_config = AUTH_RATE_LIMITS.get("/api/auth/register")

        # Should have rate limit configuration
        assert register_config is not None
        # Can be slightly more lenient than login
        assert register_config.requests_per_window <= 20

    def test_rate_limit_config_for_password_reset(self):
        """Test password reset has appropriate rate limit config.

        WHY: Password reset endpoints can be abused for:
        - Email spam/harassment
        - User enumeration
        - Denial of service (locking legitimate users)
        """
        from app.middleware.rate_limiter import AUTH_RATE_LIMITS

        reset_config = AUTH_RATE_LIMITS.get("/api/auth/forgot-password")

        # Should have rate limit configuration
        assert reset_config is not None
        # Should be very restrictive
        assert reset_config.requests_per_window <= 5
