"""
FastAPI exception handlers for custom exceptions.

WHY: Exception handlers convert our custom exceptions into properly
formatted JSON responses with correct HTTP status codes, ensuring
consistent error handling across the entire API.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handle custom AppException and its subclasses.

    WHY: This handler catches all custom exceptions and converts them to
    JSON responses with proper HTTP status codes and structured error data.

    Args:
        request: The FastAPI request object
        exc: The custom exception instance

    Returns:
        JSONResponse with error details
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    WHY: Pydantic validation errors from request bodies need to be converted
    to a consistent format matching our custom exceptions. This provides
    detailed field-level error messages to help users correct their input.

    Args:
        request: The FastAPI request object
        exc: The Pydantic validation error

    Returns:
        JSONResponse with validation error details
    """
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    return JSONResponse(
        status_code=400,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "status_code": 400,
            "details": {"errors": errors},
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handle Starlette HTTP exceptions.

    WHY: Some HTTP exceptions (404, 405) are raised by Starlette/FastAPI
    before reaching our routes. This handler ensures they match our error format.

    Args:
        request: The FastAPI request object
        exc: The HTTP exception

    Returns:
        JSONResponse with error details
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail,
            "status_code": exc.status_code,
            "details": None,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions.

    WHY: This is a safety net for any exceptions that slip through.
    In production, log the full traceback but return a generic error
    to avoid leaking implementation details (OWASP A04: Insecure Design).

    Args:
        request: The FastAPI request object
        exc: The unexpected exception

    Returns:
        JSONResponse with generic error message
    """
    # TODO: Log full exception to Sentry in production
    # import sentry_sdk
    # sentry_sdk.capture_exception(exc)

    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "status_code": 500,
            "details": None,
        },
    )
