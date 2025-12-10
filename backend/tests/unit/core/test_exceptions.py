"""
Tests for custom exception hierarchy.

WHY: Comprehensive exception testing ensures:
1. Exceptions serialize correctly without leaking sensitive data
2. HTTP status codes map correctly
3. Context data is properly filtered
4. Exception handlers work as expected
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    TokenExpiredError,
    TokenInvalidError,
    ValidationError,
    InputError,
    ResourceNotFoundError,
    ResourceAlreadyExistsError,
    BusinessRuleViolation,
    StripeError,
    N8nError,
    S3Error,
    RateLimitExceeded,
    OrganizationAccessDenied,
)
from app.core.exception_handlers import app_exception_handler


class TestAppException:
    """Test base AppException class."""

    def test_default_message(self):
        """Verify default message is used when none provided."""
        exc = AppException()
        assert exc.message == "An unexpected error occurred"
        assert exc.status_code == 500

    def test_custom_message(self):
        """Verify custom message overrides default."""
        exc = AppException(message="Custom error message")
        assert exc.message == "Custom error message"

    def test_custom_status_code(self):
        """Verify custom status code overrides class default."""
        exc = AppException(status_code=418)
        assert exc.status_code == 418

    def test_context_data(self):
        """Verify context data is stored."""
        exc = AppException(user_id=123, org_id=456, action="delete")
        assert exc.context == {"user_id": 123, "org_id": 456, "action": "delete"}

    def test_to_dict_basic(self):
        """Verify exception serializes to dict correctly."""
        exc = AppException(message="Test error", user_id=123)
        result = exc.to_dict()

        assert result["error"] == "AppException"
        assert result["message"] == "Test error"
        assert result["status_code"] == 500
        assert result["details"] == {"user_id": 123}

    def test_to_dict_filters_sensitive_data(self):
        """Verify sensitive fields are filtered from dict."""
        exc = AppException(
            message="Test error",
            user_id=123,
            password="secret123",
            token="abc123",
            api_key="key123",
            secret="mysecret",
            regular_field="visible",
        )
        result = exc.to_dict()

        # Sensitive fields should be filtered
        assert "password" not in result["details"]
        assert "token" not in result["details"]
        assert "api_key" not in result["details"]
        assert "secret" not in result["details"]

        # Non-sensitive fields should be included
        assert result["details"]["user_id"] == 123
        assert result["details"]["regular_field"] == "visible"

    def test_to_dict_no_context(self):
        """Verify to_dict works with no context data."""
        exc = AppException(message="Test error")
        result = exc.to_dict()

        assert result["details"] is None


class TestAuthenticationExceptions:
    """Test authentication-related exceptions."""

    def test_authentication_error_status_code(self):
        """Verify AuthenticationError returns 401."""
        exc = AuthenticationError()
        assert exc.status_code == 401
        assert exc.message == "Authentication failed"

    def test_authorization_error_status_code(self):
        """Verify AuthorizationError returns 403."""
        exc = AuthorizationError()
        assert exc.status_code == 403

    def test_token_expired_error(self):
        """Verify TokenExpiredError has appropriate message."""
        exc = TokenExpiredError()
        assert exc.status_code == 401
        assert "expired" in exc.message.lower()

    def test_token_invalid_error(self):
        """Verify TokenInvalidError has appropriate message."""
        exc = TokenInvalidError()
        assert exc.status_code == 401
        assert "invalid" in exc.message.lower()


class TestValidationExceptions:
    """Test validation-related exceptions."""

    def test_validation_error_status_code(self):
        """Verify ValidationError returns 400."""
        exc = ValidationError()
        assert exc.status_code == 400

    def test_input_error_status_code(self):
        """Verify InputError returns 400."""
        exc = InputError()
        assert exc.status_code == 400

    def test_validation_error_with_field_context(self):
        """Verify validation errors can include field information."""
        exc = ValidationError(
            message="Email is invalid",
            field="email",
            value="not-an-email",
        )
        result = exc.to_dict()

        assert result["details"]["field"] == "email"
        assert result["details"]["value"] == "not-an-email"


class TestResourceExceptions:
    """Test resource-related exceptions."""

    def test_resource_not_found_status_code(self):
        """Verify ResourceNotFoundError returns 404."""
        exc = ResourceNotFoundError()
        assert exc.status_code == 404

    def test_resource_already_exists_status_code(self):
        """Verify ResourceAlreadyExistsError returns 409."""
        exc = ResourceAlreadyExistsError()
        assert exc.status_code == 409

    def test_resource_not_found_with_context(self):
        """Verify resource exceptions can include resource details."""
        exc = ResourceNotFoundError(
            message="Project not found",
            resource_type="Project",
            resource_id=123,
        )
        result = exc.to_dict()

        assert result["details"]["resource_type"] == "Project"
        assert result["details"]["resource_id"] == 123


class TestExternalServiceExceptions:
    """Test external service exceptions."""

    def test_stripe_error_status_code(self):
        """Verify StripeError returns 502."""
        exc = StripeError()
        assert exc.status_code == 502

    def test_n8n_error_status_code(self):
        """Verify N8nError returns 502."""
        exc = N8nError()
        assert exc.status_code == 502

    def test_s3_error_status_code(self):
        """Verify S3Error returns 502."""
        exc = S3Error()
        assert exc.status_code == 502


class TestBusinessLogicExceptions:
    """Test business logic exceptions."""

    def test_business_rule_violation_status_code(self):
        """Verify BusinessRuleViolation returns 422."""
        exc = BusinessRuleViolation()
        assert exc.status_code == 422

    def test_rate_limit_exceeded_status_code(self):
        """Verify RateLimitExceeded returns 429."""
        exc = RateLimitExceeded()
        assert exc.status_code == 429


class TestMultiTenancyExceptions:
    """Test multi-tenancy related exceptions."""

    def test_organization_access_denied_status_code(self):
        """Verify OrganizationAccessDenied returns 404 (not 403)."""
        # WHY: Return 404 instead of 403 to prevent information disclosure
        # about whether the resource exists in another organization
        exc = OrganizationAccessDenied()
        assert exc.status_code == 404


class TestExceptionHandlerIntegration:
    """Test exception handler integration with FastAPI."""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app with exception handlers."""
        app = FastAPI()
        app.add_exception_handler(AppException, app_exception_handler)

        @app.get("/test-auth-error")
        async def test_auth_error():
            raise AuthenticationError(message="Invalid credentials", user_id=123)

        @app.get("/test-sensitive-data")
        async def test_sensitive_data():
            raise AppException(
                message="Error with sensitive data",
                user_id=123,
                password="should-be-filtered",
            )

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_exception_handler_returns_json(self, client):
        """Verify exception handler returns JSON response."""
        response = client.get("/test-auth-error")

        assert response.status_code == 401
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert data["error"] == "AuthenticationError"
        assert data["message"] == "Invalid credentials"
        assert data["status_code"] == 401
        assert data["details"]["user_id"] == 123

    def test_exception_handler_filters_sensitive_data(self, client):
        """Verify exception handler filters sensitive data from response."""
        response = client.get("/test-sensitive-data")

        data = response.json()
        assert "password" not in data.get("details", {})
        assert data["details"]["user_id"] == 123
