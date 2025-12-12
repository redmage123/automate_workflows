"""
Pydantic schemas for OAuth authentication endpoints.

WHY: Schemas define request/response contracts for OAuth flows, providing:
1. Automatic validation of request data
2. API documentation (OpenAPI/Swagger)
3. Type safety throughout the OAuth flow
4. Clear separation between API and database models

SECURITY (OWASP A07):
- Sensitive fields (tokens) are never exposed in responses
- State parameter validates OAuth callback authenticity
- Provider user info is sanitized before storage
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, HttpUrl


# ============================================================================
# OAuth Provider Info
# ============================================================================


class OAuthProviderInfo(BaseModel):
    """
    Information about a supported OAuth provider.

    WHY: Provides frontend with details about available OAuth providers
    for rendering login buttons and configuring OAuth flows.
    """

    provider: str = Field(
        ...,
        description="Provider identifier (e.g., 'google')",
        examples=["google"],
    )
    name: str = Field(
        ...,
        description="Human-readable provider name",
        examples=["Google"],
    )
    authorize_url: str = Field(
        ...,
        description="URL to redirect users for OAuth authorization",
    )
    icon_url: Optional[str] = Field(
        default=None,
        description="URL to provider's logo/icon",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "google",
                "name": "Google",
                "authorize_url": "/api/auth/oauth/google",
                "icon_url": "https://www.google.com/favicon.ico",
            }
        }


class OAuthProvidersResponse(BaseModel):
    """Response listing available OAuth providers."""

    providers: List[OAuthProviderInfo] = Field(
        ...,
        description="List of available OAuth providers",
    )


# ============================================================================
# OAuth Authorization Flow
# ============================================================================


class OAuthAuthorizeResponse(BaseModel):
    """
    Response from OAuth authorize endpoint.

    WHY: Returns the authorization URL that frontend should redirect to.
    The state parameter is included for the frontend to verify later.
    """

    authorization_url: str = Field(
        ...,
        description="Full URL to redirect user to for OAuth consent",
    )
    state: str = Field(
        ...,
        description="State parameter for CSRF protection (store securely)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...",
                "state": "random-state-string",
            }
        }


class OAuthCallbackRequest(BaseModel):
    """
    Request data from OAuth callback (query parameters).

    WHY: Captures the authorization code and state from the OAuth callback.
    Used to exchange the code for tokens.
    """

    code: str = Field(
        ...,
        description="Authorization code from OAuth provider",
    )
    state: str = Field(
        ...,
        description="State parameter to validate against stored value",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error code if user denied consent or error occurred",
    )
    error_description: Optional[str] = Field(
        default=None,
        description="Human-readable error description",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "code": "4/0AX4XfWi...",
                "state": "random-state-string",
            }
        }


# ============================================================================
# OAuth Token Response
# ============================================================================


class OAuthTokenResponse(BaseModel):
    """
    Response after successful OAuth authentication.

    WHY: Returns JWT token for platform authentication plus user info.
    This is the same format as regular login for frontend consistency.
    """

    access_token: str = Field(
        ...,
        description="JWT access token for platform API",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Token expiration time in seconds",
    )
    user: "OAuthUserResponse" = Field(
        ...,
        description="User data",
    )
    is_new_user: bool = Field(
        default=False,
        description="True if this is a newly created account",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400,
                "user": {
                    "id": 1,
                    "email": "user@gmail.com",
                    "name": "John Doe",
                    "role": "CLIENT",
                    "org_id": 1,
                    "is_active": True,
                },
                "is_new_user": False,
            }
        }


class OAuthUserResponse(BaseModel):
    """
    User data in OAuth response.

    WHY: Matches the standard UserResponse format for frontend consistency.
    """

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User's email address")
    name: str = Field(..., description="User's full name")
    role: str = Field(..., description="User role (ADMIN or CLIENT)")
    org_id: int = Field(..., description="Organization ID")
    is_active: bool = Field(..., description="Whether user account is active")

    class Config:
        from_attributes = True


# ============================================================================
# Linked OAuth Account Management
# ============================================================================


class LinkedOAuthAccount(BaseModel):
    """
    Information about a linked OAuth account.

    WHY: Shows users which OAuth providers are linked to their account
    without exposing sensitive data like tokens.
    """

    id: int = Field(..., description="OAuth account ID")
    provider: str = Field(
        ...,
        description="Provider identifier",
        examples=["google"],
    )
    provider_name: str = Field(
        ...,
        description="Human-readable provider name",
        examples=["Google"],
    )
    email: Optional[str] = Field(
        default=None,
        description="Email associated with this OAuth account",
    )
    name: Optional[str] = Field(
        default=None,
        description="Name from OAuth provider",
    )
    picture_url: Optional[str] = Field(
        default=None,
        description="Profile picture URL",
    )
    linked_at: datetime = Field(
        ...,
        description="When the account was linked",
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "provider": "google",
                "provider_name": "Google",
                "email": "user@gmail.com",
                "name": "John Doe",
                "picture_url": "https://lh3.googleusercontent.com/...",
                "linked_at": "2025-12-11T10:30:00",
            }
        }


class LinkedAccountsResponse(BaseModel):
    """Response listing user's linked OAuth accounts."""

    accounts: List[LinkedOAuthAccount] = Field(
        ...,
        description="List of linked OAuth accounts",
    )
    can_unlink: bool = Field(
        ...,
        description="Whether user can unlink accounts (has password or multiple providers)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "accounts": [
                    {
                        "id": 1,
                        "provider": "google",
                        "provider_name": "Google",
                        "email": "user@gmail.com",
                        "linked_at": "2025-12-11T10:30:00",
                    }
                ],
                "can_unlink": True,
            }
        }


# ============================================================================
# Link/Unlink OAuth Account
# ============================================================================


class LinkAccountRequest(BaseModel):
    """
    Request to link an OAuth account to existing user.

    WHY: Users with existing accounts may want to add OAuth login.
    This initiates the OAuth flow for linking, not creating a new account.
    """

    provider: str = Field(
        ...,
        description="Provider to link (e.g., 'google')",
        examples=["google"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "google",
            }
        }


class LinkAccountResponse(BaseModel):
    """Response after successfully linking an OAuth account."""

    message: str = Field(
        default="OAuth account linked successfully",
        description="Success message",
    )
    account: LinkedOAuthAccount = Field(
        ...,
        description="The newly linked account",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "OAuth account linked successfully",
                "account": {
                    "id": 1,
                    "provider": "google",
                    "provider_name": "Google",
                    "email": "user@gmail.com",
                    "linked_at": "2025-12-11T10:30:00",
                },
            }
        }


class UnlinkAccountRequest(BaseModel):
    """
    Request to unlink an OAuth account.

    WHY: Users may want to remove OAuth access, especially if they
    set a password and prefer email/password login.
    """

    provider: str = Field(
        ...,
        description="Provider to unlink (e.g., 'google')",
        examples=["google"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "google",
            }
        }


class UnlinkAccountResponse(BaseModel):
    """Response after successfully unlinking an OAuth account."""

    message: str = Field(
        default="OAuth account unlinked successfully",
        description="Success message",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "OAuth account unlinked successfully",
            }
        }


# ============================================================================
# OAuth State Management (Internal)
# ============================================================================


class OAuthStateData(BaseModel):
    """
    Data stored in OAuth state parameter.

    WHY: State parameter carries data needed after OAuth callback:
    - CSRF nonce for validation
    - User ID if linking to existing account
    - Redirect URL for frontend routing

    This is encrypted before being sent to the OAuth provider.
    """

    nonce: str = Field(
        ...,
        description="Random nonce for CSRF protection",
    )
    action: str = Field(
        default="login",
        description="Action: 'login', 'register', or 'link'",
    )
    user_id: Optional[int] = Field(
        default=None,
        description="User ID if linking (None for login/register)",
    )
    redirect_url: Optional[str] = Field(
        default=None,
        description="URL to redirect after completion",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the state was created (for expiration)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "nonce": "abc123xyz",
                "action": "login",
                "user_id": None,
                "redirect_url": "/dashboard",
                "created_at": "2025-12-11T10:30:00",
            }
        }


# Forward reference resolution
OAuthTokenResponse.model_rebuild()
