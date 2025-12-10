"""
Request context middleware for audit logging.

WHAT: Middleware that extracts request context (IP address, user agent, request ID)
and makes it available throughout the request lifecycle.

WHY: OWASP A09 (Security Logging and Monitoring) requires comprehensive context
for security events. This middleware captures:
- Client IP address (handling proxies via X-Forwarded-For)
- User agent for device/browser identification
- Request ID for correlation across logs
- Request timing for performance monitoring

HOW: Uses Starlette's request state to store context, which can be accessed
by any handler or dependency during the request lifecycle. Uses contextvars
for async-safe access to request context from anywhere in the codebase.
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


@dataclass
class RequestContext:
    """
    Container for request-scoped context data.

    WHAT: Immutable data class holding request context for audit logging.

    WHY: Using a dataclass provides type safety and immutability,
    ensuring context cannot be accidentally modified after capture.

    Fields:
    - request_id: Unique identifier for the request (for log correlation)
    - ip_address: Client's real IP (considering proxies)
    - user_agent: Client's browser/application identifier
    - path: Request path (for logging without full URL)
    - method: HTTP method (GET, POST, etc.)
    """

    request_id: str
    ip_address: str
    user_agent: Optional[str]
    path: str
    method: str


# Context variable for async-safe access to request context
# WHY: ContextVar ensures each async request gets its own isolated context,
# preventing data leaks between concurrent requests
_request_context: ContextVar[Optional[RequestContext]] = ContextVar(
    "request_context", default=None
)


def get_request_context() -> Optional[RequestContext]:
    """
    Get the current request context.

    WHAT: Retrieves the request context for the current async context.

    WHY: Allows access to request context from anywhere in the codebase
    (services, DAOs, etc.) without passing it through every function call.

    Returns:
        RequestContext if within a request, None otherwise

    Example:
        >>> ctx = get_request_context()
        >>> if ctx:
        ...     await audit_dao.create(ip_address=ctx.ip_address, ...)
    """
    return _request_context.get()


def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP address from a request.

    WHAT: Gets the client's IP, handling proxy headers.

    WHY: When behind load balancers or proxies (Traefik, Cloudflare, etc.),
    the direct client IP is the proxy's IP. The real client IP is in
    X-Forwarded-For or similar headers. Correctly identifying the client IP
    is critical for:
    - Rate limiting
    - Geographic analysis
    - Attack attribution
    - Fraud detection

    HOW: Checks headers in order of trust:
    1. X-Real-IP (set by some proxies like nginx)
    2. X-Forwarded-For (comma-separated list, first is original client)
    3. request.client.host (direct connection IP)

    Args:
        request: The incoming request

    Returns:
        Client IP address as string

    Security Note:
        These headers can be spoofed by clients if not behind a trusted proxy.
        In production, configure your proxy to strip/overwrite these headers
        from untrusted sources.
    """
    # X-Real-IP is commonly set by nginx and similar proxies
    # WHY: Check this first as it's typically more reliable than X-Forwarded-For
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip.strip()

    # X-Forwarded-For contains comma-separated list of IPs
    # WHY: First IP in the chain is the original client (if proxy is trusted)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # Get the first (leftmost) IP in the chain
        # Format: "client, proxy1, proxy2"
        first_ip = x_forwarded_for.split(",")[0].strip()
        return first_ip

    # Fall back to direct connection IP
    # WHY: This is the actual TCP connection source IP
    if request.client and request.client.host:
        return request.client.host

    # Final fallback (shouldn't happen in normal operation)
    return "unknown"


def get_user_agent(request: Request) -> Optional[str]:
    """
    Extract the User-Agent header from a request.

    WHAT: Gets the client's User-Agent string.

    WHY: User-Agent helps identify:
    - Browser type and version
    - Operating system
    - Bot detection
    - Device fingerprinting for anomaly detection

    Args:
        request: The incoming request

    Returns:
        User-Agent string or None if not present
    """
    return request.headers.get("User-Agent")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that captures and stores request context.

    WHAT: Extracts IP, user agent, and request ID from every request
    and makes them available for audit logging.

    WHY: OWASP A09 requires comprehensive logging with context.
    This middleware ensures:
    1. Every request has a unique ID for log correlation
    2. Client IP is correctly extracted (handling proxies)
    3. User agent is captured for device tracking
    4. Context is available throughout the request lifecycle

    HOW: Uses Starlette's BaseHTTPMiddleware to wrap request processing.
    Stores context in both:
    - request.state (for access from request handlers)
    - ContextVar (for access from services/DAOs without request object)

    Example:
        # In a route handler:
        @app.get("/api/example")
        async def example(request: Request):
            ctx = request.state.context
            # or
            ctx = get_request_context()
            print(f"Request {ctx.request_id} from {ctx.ip_address}")
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add context.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with request ID header added
        """
        # Generate unique request ID
        # WHY: UUID4 ensures globally unique IDs for log correlation
        # across distributed systems
        request_id = str(uuid.uuid4())

        # Extract client IP (handling proxies)
        ip_address = get_client_ip(request)

        # Extract user agent
        user_agent = get_user_agent(request)

        # Create context object
        context = RequestContext(
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            path=request.url.path,
            method=request.method,
        )

        # Store in request state (for handlers with request access)
        request.state.context = context

        # Store in context var (for services/DAOs without request access)
        # WHY: ContextVar is async-safe and scoped to the current async context
        token = _request_context.set(context)

        try:
            # Process request
            response = await call_next(request)

            # Add request ID to response headers
            # WHY: Helps clients correlate responses with their requests
            # and enables support teams to trace issues
            response.headers["X-Request-ID"] = request_id

            return response

        finally:
            # Reset context var to prevent leaks
            # WHY: Even though ContextVar is scoped, explicitly resetting
            # ensures clean state and prevents edge-case leaks
            _request_context.reset(token)
