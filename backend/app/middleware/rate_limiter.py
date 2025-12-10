"""
Rate limiting middleware for authentication endpoints.

WHAT: This module provides rate limiting functionality to protect
authentication endpoints from brute-force and credential stuffing attacks.

WHY: Rate limiting is essential for:
1. OWASP A07 (Identification and Authentication Failures) - Prevent brute force
2. Protect against credential stuffing attacks
3. Reduce DDoS impact on auth endpoints
4. Fair usage enforcement

HOW: Uses Redis sliding window algorithm:
1. Each request increments a counter for IP+endpoint combination
2. Counter key expires after the window duration
3. If counter exceeds limit, return 429 Too Many Requests
4. Rate limit headers inform clients of their current status

Design decisions:
- Fail-open: If Redis is unavailable, allow requests (prevents self-DOS)
- Per-endpoint limits: Different endpoints can have different limits
- IP-based limiting: Uses client IP (supports X-Forwarded-For for proxies)
"""

from dataclasses import dataclass
from typing import Optional, Dict
import logging
import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import RateLimitExceeded


logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================


@dataclass
class RateLimitConfig:
    """
    Configuration for rate limiting.

    WHAT: Defines rate limit parameters for an endpoint or group of endpoints.

    WHY: Different endpoints need different limits:
    - Login: Strict (5/min) to prevent brute force
    - Register: Moderate (10/min) to prevent spam
    - Password reset: Very strict (3/min) to prevent harassment

    HOW: Uses token bucket / sliding window algorithm in Redis.
    """

    requests_per_window: int = 5
    """Maximum number of requests allowed in the window.

    WHY: 5 requests per minute is industry standard for login.
    Allows genuine users to recover from typos while blocking attacks.
    """

    window_seconds: int = 60
    """Duration of the rate limit window in seconds.

    WHY: 60 seconds provides good balance between security and usability.
    Users rarely need more than 5 login attempts per minute legitimately.
    """

    key_prefix: str = "ratelimit"
    """Redis key prefix for rate limit counters.

    WHY: Namespacing prevents key collisions with other Redis data
    and enables easy cleanup/monitoring of rate limit keys.
    """


# Endpoint-specific rate limit configurations
# WHY: Auth endpoints are primary targets for attacks and need stricter limits
AUTH_RATE_LIMITS: Dict[str, RateLimitConfig] = {
    "/api/auth/login": RateLimitConfig(
        requests_per_window=5,
        window_seconds=60,
        key_prefix="ratelimit:login",
    ),
    "/api/auth/register": RateLimitConfig(
        requests_per_window=10,
        window_seconds=60,
        key_prefix="ratelimit:register",
    ),
    "/api/auth/forgot-password": RateLimitConfig(
        requests_per_window=3,
        window_seconds=60,
        key_prefix="ratelimit:forgot-password",
    ),
    "/api/auth/reset-password": RateLimitConfig(
        requests_per_window=5,
        window_seconds=60,
        key_prefix="ratelimit:reset-password",
    ),
}


# ============================================================================
# Rate Limit Result
# ============================================================================


@dataclass
class RateLimitResult:
    """
    Result of a rate limit check.

    WHAT: Contains information about whether a request is allowed
    and the current rate limit status.

    WHY: Provides complete information for:
    - Deciding whether to allow the request
    - Setting rate limit headers in response
    - Logging and monitoring

    HOW: Returned by RateLimiter.check_rate_limit() after Redis check.
    """

    allowed: bool
    """Whether the request is allowed (under limit)."""

    remaining: int
    """Number of requests remaining in current window.

    WHY: Clients can use this to implement backoff strategies.
    """

    reset_after: int
    """Seconds until the rate limit window resets.

    WHY: Clients know when to retry (Retry-After header).
    """

    limit: int
    """Maximum requests allowed per window.

    WHY: Clients can understand the rate limit policy.
    """


# ============================================================================
# Rate Limiter Service
# ============================================================================


class RateLimiter:
    """
    Rate limiter service using Redis.

    WHAT: Implements sliding window rate limiting using Redis INCR and EXPIRE.

    WHY: Redis-based rate limiting provides:
    - Distributed rate limiting across multiple app instances
    - Fast O(1) operations (INCR, EXPIRE)
    - Automatic cleanup via key expiration
    - Atomic operations preventing race conditions

    HOW: Uses Redis pipeline for atomic increment + expire:
    1. INCR key (increments counter, creates with value 1 if new)
    2. EXPIRE key window_seconds (sets TTL only if key is new)
    3. Compare counter to limit
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        config: Optional[RateLimitConfig] = None,
    ):
        """
        Initialize rate limiter with Redis client.

        WHY: Dependency injection allows:
        - Testing with mock Redis
        - Sharing Redis connection across services
        - Configuring different limits for different contexts

        Args:
            redis_client: Async Redis client
            config: Rate limit configuration (uses defaults if not provided)
        """
        self._redis = redis_client
        self._config = config or RateLimitConfig()

    def _build_key(self, identifier: str, endpoint: str) -> str:
        """
        Build Redis key for rate limit counter.

        WHAT: Creates a unique key combining prefix, endpoint, and identifier.

        WHY: Separate keys for:
        - Different endpoints (login vs register)
        - Different clients (by IP)
        - Easy pattern matching for monitoring/cleanup

        HOW: Format: {prefix}:{endpoint_normalized}:{identifier}

        Args:
            identifier: Client identifier (usually IP address)
            endpoint: API endpoint path

        Returns:
            Redis key string
        """
        # Normalize endpoint path
        # WHY: Remove leading slashes and replace / with : for readability
        normalized_endpoint = endpoint.strip("/").replace("/", ":")

        return f"{self._config.key_prefix}:{normalized_endpoint}:{identifier}"

    async def check_rate_limit(
        self,
        identifier: str,
        endpoint: str,
    ) -> RateLimitResult:
        """
        Check if request is within rate limit.

        WHAT: Increments counter and checks against limit.

        WHY: This is the core rate limiting logic:
        - Atomic increment prevents race conditions
        - Separate expire ensures cleanup
        - Returns full status for headers/logging

        HOW: Uses Redis pipeline:
        1. INCR to increment (and create if new)
        2. EXPIRE to set TTL (only on first request)
        3. Compare result to limit

        Args:
            identifier: Client identifier (IP address)
            endpoint: API endpoint being accessed

        Returns:
            RateLimitResult with allowed status and metadata
        """
        key = self._build_key(identifier, endpoint)

        try:
            # Use pipeline for atomic operations
            # WHY: Ensures increment and expire happen together
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self._config.window_seconds)

            results = await pipe.execute()
            current_count = results[0]

            # Check if under limit
            allowed = current_count <= self._config.requests_per_window
            remaining = max(0, self._config.requests_per_window - current_count)

            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                reset_after=self._config.window_seconds,
                limit=self._config.requests_per_window,
            )

        except Exception as e:
            # Fail-open: allow request if Redis is unavailable
            # WHY: We prefer allowing potentially malicious requests
            # over blocking all legitimate users during Redis outage.
            # This is a security/availability trade-off.
            logger.error(
                f"Rate limit Redis error (allowing request): {e}",
                extra={
                    "identifier": identifier,
                    "endpoint": endpoint,
                    "error": str(e),
                },
            )
            return RateLimitResult(
                allowed=True,
                remaining=-1,  # Unknown
                reset_after=self._config.window_seconds,
                limit=self._config.requests_per_window,
            )


# ============================================================================
# Global Rate Limiter Instance
# ============================================================================


_rate_limiter: Optional[RateLimiter] = None


async def get_rate_limiter() -> RateLimiter:
    """
    Get or create global rate limiter instance.

    WHAT: Lazy initialization of rate limiter with Redis connection.

    WHY: Singleton pattern ensures:
    - Single Redis connection for rate limiting
    - Consistent configuration across requests
    - Easy testing through mock injection

    HOW: Creates on first call, reuses on subsequent calls.

    Returns:
        RateLimiter instance
    """
    global _rate_limiter

    if _rate_limiter is None:
        redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        _rate_limiter = RateLimiter(redis_client=redis_client)

    return _rate_limiter


async def check_rate_limit(
    identifier: str,
    endpoint: str,
    config: Optional[RateLimitConfig] = None,
) -> RateLimitResult:
    """
    Convenience function to check rate limit and raise if exceeded.

    WHAT: Wrapper that checks rate limit and raises RateLimitExceeded if over limit.

    WHY: Simplifies usage in endpoints:
    - Single function call
    - Automatic exception on limit exceeded
    - Consistent error responses

    HOW: Gets rate limiter, checks limit, raises if exceeded.

    Args:
        identifier: Client identifier (IP address)
        endpoint: API endpoint
        config: Optional custom configuration

    Returns:
        RateLimitResult if allowed

    Raises:
        RateLimitExceeded: If rate limit is exceeded (429)
    """
    limiter = await get_rate_limiter()

    # Apply endpoint-specific config if available
    if config is None and endpoint in AUTH_RATE_LIMITS:
        # Use endpoint-specific config
        limiter._config = AUTH_RATE_LIMITS[endpoint]

    result = await limiter.check_rate_limit(identifier, endpoint)

    if not result.allowed:
        raise RateLimitExceeded(
            message=f"Rate limit exceeded. Try again in {result.reset_after} seconds.",
            retry_after=result.reset_after,
            limit=result.limit,
            remaining=result.remaining,
        )

    return result


# ============================================================================
# Rate Limit Middleware
# ============================================================================


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting authentication endpoints.

    WHAT: Intercepts requests to auth endpoints and applies rate limiting.

    WHY: Middleware approach provides:
    - Automatic protection for all auth endpoints
    - No code changes needed in endpoint handlers
    - Consistent rate limit headers in responses
    - Early rejection before hitting database/business logic

    HOW: Checks request path, applies rate limit if auth endpoint,
    adds headers to response.

    Usage:
        app.add_middleware(RateLimitMiddleware)
    """

    # Endpoints to rate limit
    # WHY: Only auth endpoints need rate limiting in this middleware
    # Other endpoints may have different rate limiting needs
    RATE_LIMITED_PATHS = frozenset([
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
    ])

    async def dispatch(self, request: Request, call_next):
        """
        Process request through rate limiting.

        WHAT: Main middleware entry point for each request.

        WHY: Implements the rate limiting logic:
        1. Check if endpoint is rate limited
        2. Extract client IP (handling proxies)
        3. Check rate limit
        4. Block or allow request
        5. Add rate limit headers

        HOW: Uses RateLimiter service for Redis-based checking.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response (either from handler or 429 if rate limited)
        """
        path = request.url.path

        # Skip non-rate-limited paths
        if path not in self.RATE_LIMITED_PATHS:
            return await call_next(request)

        # Extract client IP
        # WHY: Need real client IP for rate limiting, not proxy IP
        identifier = self._get_client_ip(request)

        try:
            # Check rate limit
            limiter = await get_rate_limiter()

            # Use endpoint-specific config
            if path in AUTH_RATE_LIMITS:
                limiter._config = AUTH_RATE_LIMITS[path]

            result = await limiter.check_rate_limit(identifier, path)

            if not result.allowed:
                # Return 429 response with rate limit headers
                # WHY: Standard HTTP status for rate limiting
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "RateLimitExceeded",
                        "message": f"Rate limit exceeded. Try again in {result.reset_after} seconds.",
                        "retry_after": result.reset_after,
                    },
                    headers={
                        "X-RateLimit-Limit": str(result.limit),
                        "X-RateLimit-Remaining": str(result.remaining),
                        "X-RateLimit-Reset": str(result.reset_after),
                        "Retry-After": str(result.reset_after),
                    },
                )

            # Proceed with request
            response = await call_next(request)

            # Add rate limit headers to response
            # WHY: Inform clients of their rate limit status
            response.headers["X-RateLimit-Limit"] = str(result.limit)
            response.headers["X-RateLimit-Remaining"] = str(result.remaining)
            response.headers["X-RateLimit-Reset"] = str(result.reset_after)

            return response

        except Exception as e:
            # Log error but allow request (fail-open)
            logger.error(f"Rate limit middleware error: {e}")
            return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.

        WHAT: Gets the real client IP, handling proxy headers.

        WHY: When behind a reverse proxy (Traefik/nginx):
        - request.client.host is the proxy IP
        - Real client IP is in X-Forwarded-For or X-Real-IP headers

        HOW: Check headers in order:
        1. X-Real-IP (single IP from nginx)
        2. X-Forwarded-For (comma-separated list, first is client)
        3. Fall back to request.client.host

        Args:
            request: HTTP request

        Returns:
            Client IP address string
        """
        # Check X-Real-IP first (set by nginx)
        x_real_ip = request.headers.get("X-Real-IP")
        if x_real_ip:
            return x_real_ip.strip()

        # Check X-Forwarded-For (may have multiple IPs)
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            # First IP in the list is the original client
            return x_forwarded_for.split(",")[0].strip()

        # Fall back to direct client address
        if request.client:
            return request.client.host

        return "unknown"


# ============================================================================
# Dependency for Endpoint Rate Limiting
# ============================================================================


async def rate_limit_login(request: Request) -> None:
    """
    FastAPI dependency for rate limiting login endpoint.

    WHAT: Checks rate limit for login attempts.

    WHY: Can be used as a Depends() in endpoint for explicit rate limiting.

    HOW: Extracts IP, checks limit, raises if exceeded.

    Usage:
        @router.post("/login")
        async def login(
            request: Request,
            _: None = Depends(rate_limit_login),
        ):
            ...

    Args:
        request: HTTP request

    Raises:
        RateLimitExceeded: If rate limit is exceeded
    """
    # Extract client IP (handling proxies)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        identifier = x_forwarded_for.split(",")[0].strip()
    elif request.client:
        identifier = request.client.host
    else:
        identifier = "unknown"

    # Check rate limit
    await check_rate_limit(
        identifier=identifier,
        endpoint="/api/auth/login",
        config=AUTH_RATE_LIMITS.get("/api/auth/login"),
    )


async def rate_limit_register(request: Request) -> None:
    """
    FastAPI dependency for rate limiting register endpoint.

    WHAT: Checks rate limit for registration attempts.

    WHY: Prevents mass account creation and email enumeration.

    Args:
        request: HTTP request

    Raises:
        RateLimitExceeded: If rate limit is exceeded
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        identifier = x_forwarded_for.split(",")[0].strip()
    elif request.client:
        identifier = request.client.host
    else:
        identifier = "unknown"

    await check_rate_limit(
        identifier=identifier,
        endpoint="/api/auth/register",
        config=AUTH_RATE_LIMITS.get("/api/auth/register"),
    )
