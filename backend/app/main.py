"""
Main FastAPI application.

WHY: This is the entry point for the application. It configures middleware,
routes, exception handlers, and other application-level concerns.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.exception_handlers import (
    app_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    generic_exception_handler,
)
from app.middleware import SecurityHeadersMiddleware, RequestContextMiddleware, RateLimitMiddleware
from app.api import auth, organizations, projects, proposals, invoices, workflows, tickets, admin, analytics, notification_preferences, oauth, subscriptions, workflow_ai, documents, time_entries, messages, activity, announcements, reports, onboarding, surveys, email_templates, push, integrations
from app.services.scheduler import start_scheduler, shutdown_scheduler, get_scheduler_status


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    WHY: Factory pattern allows easier testing with different configurations
    and makes it possible to create multiple app instances if needed.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Automation Services Platform API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Register exception handlers
    # WHY: Exception handlers ensure consistent error responses across the API
    # and prevent sensitive data leaks in error messages (OWASP A04)
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Configure Request Context Middleware
    # WHY: Captures client IP, user agent, and request ID for audit logging.
    # Must be added early to ensure context is available for all handlers.
    # OWASP A09 (Security Logging) requires comprehensive request context.
    app.add_middleware(RequestContextMiddleware)

    # Configure Rate Limit Middleware
    # WHY: Protects authentication endpoints from brute-force and credential
    # stuffing attacks (OWASP A07). Limits login attempts to prevent password
    # guessing and registration abuse. Applied after request context to have
    # access to client IP information for per-client rate limiting.
    app.add_middleware(RateLimitMiddleware)

    # Configure Security Headers
    # WHY: Security headers provide defense in depth by instructing browsers
    # to enforce additional security policies (OWASP Top 10 A02, A05).
    # Must be added before CORS to ensure headers are applied to all responses.
    app.add_middleware(SecurityHeadersMiddleware)

    # Configure CORS
    # WHY: CORS middleware allows the Next.js frontend (running on a different port/domain)
    # to make API requests. In production, restrict allowed_origins to specific domains.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    # WHY: Load balancers and monitoring tools need a simple endpoint
    # to verify the service is running.
    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        """
        Health check endpoint.

        WHY: Allows load balancers and monitoring to verify service health
        without checking authentication or database connectivity.
        """
        scheduler_status = get_scheduler_status()
        return {
            "status": "healthy",
            "version": "0.1.0",
            "scheduler": scheduler_status,
        }

    # Startup/shutdown events for background job scheduler
    @app.on_event("startup")
    async def startup_event():
        """
        Application startup event handler.

        WHY: Starts background job scheduler for:
        - SLA breach monitoring
        - Future scheduled tasks
        """
        await start_scheduler()

    @app.on_event("shutdown")
    async def shutdown_event():
        """
        Application shutdown event handler.

        WHY: Gracefully stops background jobs to prevent data loss.
        """
        await shutdown_scheduler()

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root() -> dict:
        """Root endpoint with API information."""
        return {
            "name": settings.PROJECT_NAME,
            "version": "0.1.0",
            "docs": "/api/docs",
        }

    # Register API routers
    # WHY: Organizing routes in separate modules improves maintainability
    app.include_router(auth.router, prefix="/api")
    app.include_router(organizations.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(proposals.router, prefix="/api")
    app.include_router(invoices.router, prefix="/api")
    app.include_router(invoices.payments_router, prefix="/api")
    app.include_router(invoices.webhooks_router, prefix="/api")
    app.include_router(workflows.router, prefix="/api")
    app.include_router(tickets.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(notification_preferences.router, prefix="/api")
    app.include_router(oauth.router, prefix="/api/auth")
    app.include_router(subscriptions.router, prefix="/api")
    app.include_router(subscriptions.webhooks_router, prefix="/api")
    app.include_router(workflow_ai.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(time_entries.router, prefix="/api")
    app.include_router(messages.router, prefix="/api")
    app.include_router(activity.router, prefix="/api")
    app.include_router(announcements.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(onboarding.router, prefix="/api")
    app.include_router(surveys.router, prefix="/api")
    app.include_router(email_templates.router, prefix="/api")
    app.include_router(push.router, prefix="/api")
    app.include_router(integrations.router, prefix="/api")

    return app


# Create app instance
# WHY: Creating the app instance here allows it to be imported by uvicorn
# and other modules that need access to the FastAPI app.
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # WHY: This allows running the app directly with `python -m app.main`
    # for development. In production, use `uvicorn app.main:app` directly.
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning",
    )
