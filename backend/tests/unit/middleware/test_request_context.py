"""
Request Context Middleware Tests.

WHAT: Unit tests for the RequestContextMiddleware.

WHY: The request context middleware is critical for OWASP A09 compliance,
providing IP address, user agent, and request ID for all audit logs.
These tests ensure correct behavior for:
- Client IP extraction (direct and through proxies)
- User agent extraction
- Request ID generation
- Context availability throughout request lifecycle

HOW: Tests use mock requests to verify context extraction and propagation.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.request_context import (
    get_client_ip,
    get_user_agent,
    get_request_context,
    RequestContextMiddleware,
    RequestContext,
    _request_context,
)


class TestGetClientIp:
    """Tests for the get_client_ip function."""

    def _make_request(self, headers: dict = None, client_host: str = None) -> Request:
        """
        Create a mock request with specified headers and client.

        Args:
            headers: Dictionary of headers
            client_host: Client IP address

        Returns:
            Mock Request object
        """
        scope = {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        }

        if client_host:
            scope["client"] = (client_host, 12345)
        else:
            scope["client"] = None

        request = Request(scope)
        return request

    def test_get_client_ip_from_x_real_ip(self):
        """
        Test IP extraction from X-Real-IP header.

        WHY: Nginx and similar proxies often set X-Real-IP to the original
        client IP. This should take priority.
        """
        request = self._make_request(
            headers={"X-Real-IP": "192.168.1.100"},
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "192.168.1.100"

    def test_get_client_ip_from_x_forwarded_for(self):
        """
        Test IP extraction from X-Forwarded-For header.

        WHY: X-Forwarded-For is set by many proxies and load balancers.
        The first IP is the original client.
        """
        request = self._make_request(
            headers={"X-Forwarded-For": "203.0.113.50, 70.41.3.18, 150.172.238.178"},
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_get_client_ip_from_x_forwarded_for_single_ip(self):
        """
        Test IP extraction from X-Forwarded-For with single IP.

        WHY: Some configurations may only have one IP in the chain.
        """
        request = self._make_request(
            headers={"X-Forwarded-For": "203.0.113.50"},
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_get_client_ip_prefers_x_real_ip_over_x_forwarded_for(self):
        """
        Test that X-Real-IP takes priority over X-Forwarded-For.

        WHY: X-Real-IP is typically more reliable as it's usually set
        by a trusted reverse proxy closest to the server.
        """
        request = self._make_request(
            headers={
                "X-Real-IP": "192.168.1.100",
                "X-Forwarded-For": "203.0.113.50, 70.41.3.18",
            },
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "192.168.1.100"

    def test_get_client_ip_from_direct_connection(self):
        """
        Test IP extraction from direct connection.

        WHY: When no proxy headers are present, use the direct
        TCP connection source IP.
        """
        request = self._make_request(
            headers={},
            client_host="192.168.1.50",
        )
        assert get_client_ip(request) == "192.168.1.50"

    def test_get_client_ip_handles_ipv6(self):
        """
        Test IP extraction with IPv6 address.

        WHY: IPv6 addresses must be handled correctly for logging.
        """
        ipv6_addr = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        request = self._make_request(
            headers={"X-Real-IP": ipv6_addr},
        )
        assert get_client_ip(request) == ipv6_addr

    def test_get_client_ip_unknown_fallback(self):
        """
        Test IP extraction returns 'unknown' when no IP available.

        WHY: Edge case where no client info is available should
        return a safe default rather than crashing.
        """
        request = self._make_request(headers={}, client_host=None)
        assert get_client_ip(request) == "unknown"

    def test_get_client_ip_strips_whitespace(self):
        """
        Test that whitespace is stripped from IP addresses.

        WHY: Headers may contain leading/trailing whitespace.
        """
        request = self._make_request(
            headers={"X-Real-IP": "  192.168.1.100  "},
        )
        assert get_client_ip(request) == "192.168.1.100"


class TestGetUserAgent:
    """Tests for the get_user_agent function."""

    def _make_request(self, headers: dict = None) -> Request:
        """Create a mock request with specified headers."""
        scope = {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        }
        return Request(scope)

    def test_get_user_agent_present(self):
        """
        Test user agent extraction when header is present.

        WHY: User agent is essential for device identification
        and anomaly detection.
        """
        request = self._make_request(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        )
        assert "Mozilla/5.0" in get_user_agent(request)

    def test_get_user_agent_missing(self):
        """
        Test user agent extraction when header is missing.

        WHY: Some clients (bots, scripts) may not send user agent.
        """
        request = self._make_request(headers={})
        assert get_user_agent(request) is None


class TestRequestContext:
    """Tests for the RequestContext dataclass."""

    def test_request_context_creation(self):
        """Test creating a RequestContext object."""
        ctx = RequestContext(
            request_id="abc-123",
            ip_address="192.168.1.1",
            user_agent="TestBrowser/1.0",
            path="/api/test",
            method="POST",
        )

        assert ctx.request_id == "abc-123"
        assert ctx.ip_address == "192.168.1.1"
        assert ctx.user_agent == "TestBrowser/1.0"
        assert ctx.path == "/api/test"
        assert ctx.method == "POST"

    def test_request_context_allows_none_user_agent(self):
        """Test that user_agent can be None."""
        ctx = RequestContext(
            request_id="abc-123",
            ip_address="192.168.1.1",
            user_agent=None,
            path="/api/test",
            method="GET",
        )

        assert ctx.user_agent is None


class TestGetRequestContext:
    """Tests for the get_request_context function."""

    def test_get_request_context_returns_none_by_default(self):
        """
        Test that context returns None outside of request.

        WHY: When called outside a request context, the function
        should safely return None rather than raising an error.
        """
        # Reset context to ensure clean state
        _request_context.set(None)
        assert get_request_context() is None

    def test_get_request_context_returns_set_context(self):
        """
        Test that context returns the set value.

        WHY: Context set by middleware should be retrievable.
        """
        ctx = RequestContext(
            request_id="test-id",
            ip_address="1.2.3.4",
            user_agent="Test",
            path="/test",
            method="GET",
        )

        token = _request_context.set(ctx)
        try:
            retrieved = get_request_context()
            assert retrieved == ctx
            assert retrieved.request_id == "test-id"
        finally:
            _request_context.reset(token)


@pytest.mark.asyncio
class TestRequestContextMiddleware:
    """Tests for the RequestContextMiddleware class."""

    async def test_middleware_adds_request_id_header(self):
        """
        Test that middleware adds X-Request-ID to response.

        WHY: Request ID in response helps clients correlate
        requests with server-side logs.
        """
        # Create mock request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)
        request._url = type("URL", (), {"path": "/test"})()

        # Mock the call_next function
        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        # Create middleware and dispatch
        middleware = RequestContextMiddleware(app=MagicMock())
        response = await middleware.dispatch(request, mock_call_next)

        # Verify request ID header is set
        assert "X-Request-ID" in response.headers
        # UUID4 format check (36 chars with hyphens)
        assert len(response.headers["X-Request-ID"]) == 36

    async def test_middleware_sets_context_in_request_state(self):
        """
        Test that middleware sets context in request.state.

        WHY: Request handlers need access to context for audit logging.
        """
        # Create mock request with headers
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/login",
            "headers": [
                (b"x-real-ip", b"192.168.1.100"),
                (b"user-agent", b"TestBrowser/1.0"),
            ],
            "query_string": b"",
        }
        request = Request(scope)
        request._url = type("URL", (), {"path": "/api/login"})()

        captured_context = None

        async def mock_call_next(req):
            nonlocal captured_context
            captured_context = getattr(req.state, "context", None)
            return Response(content="OK", status_code=200)

        middleware = RequestContextMiddleware(app=MagicMock())
        await middleware.dispatch(request, mock_call_next)

        # Verify context was set
        assert captured_context is not None
        assert captured_context.ip_address == "192.168.1.100"
        assert captured_context.user_agent == "TestBrowser/1.0"
        assert captured_context.path == "/api/login"
        assert captured_context.method == "POST"

    async def test_middleware_sets_context_var(self):
        """
        Test that middleware sets the context variable.

        WHY: Services/DAOs need access to context without request object.
        """
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [(b"x-real-ip", b"10.0.0.1")],
            "query_string": b"",
        }
        request = Request(scope)
        request._url = type("URL", (), {"path": "/test"})()

        context_during_request = None

        async def mock_call_next(req):
            nonlocal context_during_request
            context_during_request = get_request_context()
            return Response(content="OK", status_code=200)

        middleware = RequestContextMiddleware(app=MagicMock())
        await middleware.dispatch(request, mock_call_next)

        # Verify context var was set during request
        assert context_during_request is not None
        assert context_during_request.ip_address == "10.0.0.1"

    async def test_middleware_clears_context_after_request(self):
        """
        Test that context is cleared after request completes.

        WHY: Context should not leak between requests.
        """
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)
        request._url = type("URL", (), {"path": "/test"})()

        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        middleware = RequestContextMiddleware(app=MagicMock())
        await middleware.dispatch(request, mock_call_next)

        # Context should be cleared after request
        assert get_request_context() is None

    async def test_middleware_clears_context_on_error(self):
        """
        Test that context is cleared even when handler raises.

        WHY: Errors in handlers should not prevent context cleanup.
        """
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)
        request._url = type("URL", (), {"path": "/test"})()

        async def mock_call_next(req):
            raise ValueError("Test error")

        middleware = RequestContextMiddleware(app=MagicMock())

        with pytest.raises(ValueError):
            await middleware.dispatch(request, mock_call_next)

        # Context should still be cleared
        assert get_request_context() is None
