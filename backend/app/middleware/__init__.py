"""
Middleware package.

WHY: Middleware provides cross-cutting concerns like security headers,
authentication, and logging that apply to all requests.
"""

from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.request_context import (
    RequestContextMiddleware,
    get_request_context,
    get_client_ip,
    get_user_agent,
    RequestContext,
)

__all__ = [
    "SecurityHeadersMiddleware",
    "RequestContextMiddleware",
    "get_request_context",
    "get_client_ip",
    "get_user_agent",
    "RequestContext",
]
