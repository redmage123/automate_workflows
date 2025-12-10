"""
Pydantic schemas for authentication endpoints.

WHY: Schemas define request/response contracts, providing:
1. Automatic validation of request data
2. API documentation (OpenAPI/Swagger)
3. Type safety
4. Clear separation between API and database models
"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """
    Login request schema.

    WHY: Validates login credentials with email format checking
    and password length requirements.
    """

    email: EmailStr = Field(
        ...,
        description="User's email address",
        example="admin@example.com",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="User's password",
        example="SecurePassword123!",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@example.com",
                "password": "SecurePassword123!",
            }
        }


class TokenResponse(BaseModel):
    """
    JWT token response schema.

    WHY: Returns access token with additional metadata for client-side
    token management (expiration time, token type).
    """

    access_token: str = Field(
        ...,
        description="JWT access token",
        example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer' for JWT)",
        example="bearer",
    )
    expires_in: int = Field(
        ...,
        description="Token expiration time in seconds",
        example=86400,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxfQ...",
                "token_type": "bearer",
                "expires_in": 86400,
            }
        }


class UserResponse(BaseModel):
    """
    User response schema.

    WHY: Returns user data without sensitive information (no password hash).
    Includes fields needed by frontend for user profile and authorization.
    """

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User's email address")
    name: str = Field(..., description="User's full name")
    role: str = Field(..., description="User role (ADMIN or CLIENT)")
    org_id: int = Field(..., description="Organization ID")
    is_active: bool = Field(..., description="Whether user account is active")
    created_at: str = Field(..., description="Account creation timestamp")

    class Config:
        from_attributes = True  # Enable ORM mode for SQLAlchemy models
        json_schema_extra = {
            "example": {
                "id": 1,
                "email": "admin@example.com",
                "name": "Admin User",
                "role": "ADMIN",
                "org_id": 1,
                "is_active": True,
                "created_at": "2025-10-12T10:30:00",
            }
        }


class LogoutResponse(BaseModel):
    """Logout response schema."""

    message: str = Field(
        default="Successfully logged out",
        description="Logout confirmation message",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Successfully logged out",
            }
        }


class RegisterRequest(BaseModel):
    """
    User registration request schema.

    WHY: Validates registration data with comprehensive checks:
    1. Email format validation
    2. Password strength requirements (min 8 chars)
    3. Password confirmation matching
    4. Organization creation or joining
    """

    email: EmailStr = Field(
        ...,
        description="User's email address (must be unique)",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Password (min 8 characters, should include uppercase, lowercase, numbers)",
    )
    password_confirm: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Password confirmation (must match password)",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's full name",
    )
    organization_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Organization name (for creating new organization)",
    )
    org_id: int | None = Field(
        default=None,
        description="Organization ID (for joining existing organization)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
                "name": "John Doe",
                "organization_name": "Acme Corp",
            }
        }


class OrganizationResponse(BaseModel):
    """Organization response schema."""

    id: int = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    description: str | None = Field(None, description="Organization description")
    is_active: bool = Field(..., description="Whether organization is active")
    created_at: str = Field(..., description="Organization creation timestamp")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Acme Corp",
                "description": "Leading automation services provider",
                "is_active": True,
                "created_at": "2025-10-12T10:30:00",
            }
        }


class RegisterResponse(BaseModel):
    """
    User registration response schema.

    WHY: Returns JWT token, user data, and organization data
    after successful registration.
    """

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserResponse = Field(..., description="Registered user data")
    organization: OrganizationResponse = Field(..., description="Organization data")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400,
                "user": {
                    "id": 1,
                    "email": "user@example.com",
                    "name": "John Doe",
                    "role": "ADMIN",
                    "org_id": 1,
                    "is_active": True,
                    "created_at": "2025-10-12T10:30:00",
                },
                "organization": {
                    "id": 1,
                    "name": "Acme Corp",
                    "description": "Leading automation services provider",
                    "is_active": True,
                    "created_at": "2025-10-12T10:30:00",
                },
            }
        }


# ============================================================================
# Email Verification Schemas
# ============================================================================


class SendVerificationEmailRequest(BaseModel):
    """
    Request to send verification email.

    WHY: Allows authenticated users to request a new verification email
    if they didn't receive the first one or it expired.
    """

    pass  # No fields needed - uses authenticated user's email

    class Config:
        json_schema_extra = {"example": {}}


class SendVerificationEmailResponse(BaseModel):
    """Response for sending verification email."""

    message: str = Field(
        ...,
        description="Status message",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Verification email sent. Please check your inbox.",
            }
        }


class VerifyEmailRequest(BaseModel):
    """
    Request to verify email with token or code.

    WHY: Supports two verification methods:
    1. Token from email link (more secure, harder to type)
    2. 6-digit code (easier on mobile, requires login)
    """

    token: str | None = Field(
        default=None,
        description="Verification token from email link",
    )
    code: str | None = Field(
        default=None,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit verification code",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "token": "abc123xyz...",
            }
        }


class VerifyEmailResponse(BaseModel):
    """Response for email verification."""

    message: str = Field(
        ...,
        description="Status message",
    )
    email_verified: bool = Field(
        ...,
        description="Whether email is now verified",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Email verified successfully.",
                "email_verified": True,
            }
        }


# ============================================================================
# Password Reset Schemas
# ============================================================================


class ForgotPasswordRequest(BaseModel):
    """
    Request to initiate password reset.

    WHY: Email is the only required field - we send reset link to this address.
    Generic response prevents user enumeration (don't reveal if email exists).
    """

    email: EmailStr = Field(
        ...,
        description="Email address to send reset link to",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
            }
        }


class ForgotPasswordResponse(BaseModel):
    """Response for password reset request."""

    message: str = Field(
        ...,
        description="Status message (always generic to prevent enumeration)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "If an account exists with this email, you will receive a password reset link.",
            }
        }


class ResetPasswordRequest(BaseModel):
    """
    Request to reset password with token.

    WHY: Token verifies user identity, new passwords must match
    and meet security requirements.
    """

    token: str = Field(
        ...,
        description="Password reset token from email",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="New password",
    )
    password_confirm: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="New password confirmation",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "token": "abc123xyz...",
                "password": "NewSecurePassword123!",
                "password_confirm": "NewSecurePassword123!",
            }
        }


class ResetPasswordResponse(BaseModel):
    """Response for password reset."""

    message: str = Field(
        ...,
        description="Status message",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Password reset successfully. You can now log in with your new password.",
            }
        }
