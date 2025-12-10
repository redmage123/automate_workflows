"""
Security headers middleware.

WHY: OWASP recommends adding security headers to protect against common
web vulnerabilities (A02: Cryptographic Failures, A05: Security Misconfiguration).
These headers provide defense in depth by instructing browsers to enforce
additional security policies.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses.

    WHY: Security headers provide multiple layers of protection:
    - Strict-Transport-Security: Forces HTTPS connections (prevents downgrade attacks)
    - X-Content-Type-Options: Prevents MIME-sniffing attacks
    - X-Frame-Options: Prevents clickjacking attacks
    - X-XSS-Protection: Enables browser XSS protection
    - Content-Security-Policy: Prevents XSS, data injection, and other attacks
    - Referrer-Policy: Controls referrer information sent to other sites
    - Permissions-Policy: Controls browser features that can be used

    Following OWASP ASVS V1 requirements and OWASP Top 10 2021 recommendations.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add security headers to response.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with security headers added
        """
        response = await call_next(request)

        # Strict-Transport-Security (HSTS)
        # WHY: Forces HTTPS for all connections for 1 year, preventing
        # SSL stripping attacks and ensuring encrypted communication.
        # includeSubDomains ensures all subdomains also use HTTPS.
        # preload allows inclusion in browser HSTS preload lists.
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # X-Content-Type-Options
        # WHY: Prevents browsers from MIME-sniffing responses away from
        # declared content-type, blocking certain XSS attacks.
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options
        # WHY: Prevents clickjacking attacks by not allowing the page
        # to be embedded in iframes from other domains.
        response.headers["X-Frame-Options"] = "DENY"

        # X-XSS-Protection
        # WHY: Enables browser's built-in XSS protection (legacy support).
        # Mode=block prevents page rendering if XSS is detected.
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content-Security-Policy (CSP)
        # WHY: Prevents XSS, clickjacking, and other code injection attacks
        # by controlling which resources can be loaded and executed.
        # - default-src 'self': Only allow resources from same origin
        # - script-src 'self': Only allow scripts from same origin
        # - style-src 'self': Only allow styles from same origin
        # - img-src 'self' data: https:": Allow images from same origin, data URIs, and HTTPS
        # - font-src 'self': Only allow fonts from same origin
        # - connect-src 'self': Only allow API calls to same origin
        # - frame-ancestors 'none': Don't allow embedding in iframes
        # - base-uri 'self': Restrict base tag to same origin
        # - form-action 'self': Only submit forms to same origin
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        # Referrer-Policy
        # WHY: Prevents leaking sensitive information in URLs to third parties.
        # strict-origin-when-cross-origin sends full URL for same-origin,
        # only origin for cross-origin, and nothing when downgrading from HTTPS to HTTP.
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy (formerly Feature-Policy)
        # WHY: Restricts which browser features can be used, reducing attack surface.
        # Disables geolocation, microphone, camera, payment, and USB by default.
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )

        # Cache-Control for sensitive endpoints
        # WHY: Prevents caching of sensitive data in browsers/proxies.
        # For API endpoints, we generally don't want caching.
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        return response
