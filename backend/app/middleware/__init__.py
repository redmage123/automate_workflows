"""
Middleware package.

WHY: Middleware provides cross-cutting concerns like security headers,
authentication, rate limiting, and logging that apply to all requests.
"""

from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.request_context import (
    RequestContextMiddleware,
    get_request_context,
    get_client_ip,
    get_user_agent,
    RequestContext,
)
from app.middleware.rate_limiter import (
    RateLimitMiddleware,
    RateLimiter,
    RateLimitConfig,
    RateLimitResult,
    check_rate_limit,
    get_rate_limiter,
    rate_limit_login,
    rate_limit_register,
    AUTH_RATE_LIMITS,
)

__all__ = [
    # Security
    "SecurityHeadersMiddleware",
    # Request context
    "RequestContextMiddleware",
    "get_request_context",
    "get_client_ip",
    "get_user_agent",
    "RequestContext",
    # Rate limiting
    "RateLimitMiddleware",
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitResult",
    "check_rate_limit",
    "get_rate_limiter",
    "rate_limit_login",
    "rate_limit_register",
    "AUTH_RATE_LIMITS",
]
