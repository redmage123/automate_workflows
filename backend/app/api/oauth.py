"""
OAuth API endpoints for social authentication.

WHY: These endpoints implement the OAuth 2.0 Authorization Code flow:
1. /oauth/{provider} - Initiates OAuth flow by returning authorization URL
2. /oauth/{provider}/callback - Handles OAuth callback, exchanges code for tokens
3. /oauth/accounts - Lists user's linked OAuth accounts
4. /oauth/accounts/{provider}/unlink - Unlinks an OAuth account

SECURITY (OWASP A07):
- State parameter prevents CSRF attacks
- Tokens are encrypted before storage
- All OAuth events are audit logged
- Rate limiting prevents abuse

ARCHITECTURE:
- Supports multiple OAuth providers (currently Google)
- Returns JWT tokens compatible with existing auth system
- Integrates with existing user/organization models
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.core.deps import get_current_user_optional, get_current_user
from app.core.exceptions import (
    OAuthError,
    OAuthProviderError,
    ValidationError,
)
from app.models.user import User
from app.schemas.oauth import (
    OAuthProviderInfo,
    OAuthProvidersResponse,
    OAuthAuthorizeResponse,
    OAuthTokenResponse,
    OAuthUserResponse,
    LinkedAccountsResponse,
    LinkedOAuthAccount,
    LinkAccountResponse,
    UnlinkAccountResponse,
)
from app.services.oauth_service import OAuthService


router = APIRouter(prefix="/oauth", tags=["OAuth"])


# ============================================================================
# Provider Information
# ============================================================================


@router.get(
    "/providers",
    response_model=OAuthProvidersResponse,
    summary="List available OAuth providers",
    description="Returns list of configured and available OAuth providers.",
)
async def list_providers():
    """
    List available OAuth providers.

    WHY: Frontend needs to know which OAuth buttons to display based on
    backend configuration. Only shows providers that are fully configured.

    Returns:
        List of available OAuth providers with authorize URLs
    """
    providers = []

    # Check Google OAuth
    if settings.google_oauth_enabled:
        providers.append(
            OAuthProviderInfo(
                provider="google",
                name="Google",
                authorize_url="/api/auth/oauth/google",
                icon_url=None,  # Frontend should use its own icon
            )
        )

    return OAuthProvidersResponse(providers=providers)


# ============================================================================
# Google OAuth Flow
# ============================================================================


@router.get(
    "/google",
    response_model=OAuthAuthorizeResponse,
    summary="Initiate Google OAuth",
    description="Returns the Google OAuth authorization URL to redirect the user to.",
)
async def google_authorize(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
    action: str = Query(
        default="login",
        description="OAuth action: 'login', 'register', or 'link'",
    ),
    redirect_url: Optional[str] = Query(
        default=None,
        description="Frontend URL to redirect after completion",
    ),
):
    """
    Initiate Google OAuth flow.

    WHY: This endpoint generates the Google authorization URL with:
    - Client ID and redirect URI from settings
    - Secure state parameter for CSRF protection
    - Requested scopes (openid, email, profile)

    Actions:
    - login: Sign in existing user or create new account
    - register: Same as login (Google doesn't distinguish)
    - link: Link Google account to existing user (requires auth)

    Args:
        action: OAuth action type
        redirect_url: Where to redirect after completion

    Returns:
        Authorization URL and state parameter

    Raises:
        OAuthError: If Google OAuth is not configured
        ValidationError: If action='link' but user not authenticated
    """
    # Validate link action requires authentication
    if action == "link" and not current_user:
        raise ValidationError(
            message="Authentication required to link OAuth account",
        )

    oauth_service = OAuthService(db)

    auth_url, state = await oauth_service.get_google_authorize_url(
        action=action,
        user_id=current_user.id if current_user and action == "link" else None,
        redirect_url=redirect_url,
    )

    return OAuthAuthorizeResponse(
        authorization_url=auth_url,
        state=state,
    )


@router.get(
    "/google/callback",
    summary="Google OAuth callback",
    description="Handles the OAuth callback from Google after user consent.",
)
async def google_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    code: Optional[str] = Query(default=None, description="Authorization code"),
    state: Optional[str] = Query(default=None, description="State parameter"),
    error: Optional[str] = Query(default=None, description="Error code if consent denied"),
    error_description: Optional[str] = Query(default=None, description="Error description"),
):
    """
    Handle Google OAuth callback.

    WHY: This endpoint completes the OAuth flow by:
    1. Validating the state parameter (CSRF protection)
    2. Exchanging the authorization code for tokens
    3. Fetching user info from Google
    4. Creating or linking the OAuth account
    5. Generating a JWT token for platform access

    Error Handling:
    - If user denies consent: Redirect with error
    - If state invalid: Redirect with error
    - If code exchange fails: Redirect with error

    Returns:
        Redirects to frontend with JWT token or error
    """
    # Get frontend URL for redirects
    frontend_url = settings.FRONTEND_URL or "http://localhost:3000"

    # Handle user denying consent
    if error:
        return RedirectResponse(
            url=f"{frontend_url}/auth/oauth/error?error={error}&error_description={error_description or 'User denied consent'}",
        )

    # Validate required parameters
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}/auth/oauth/error?error=invalid_request&error_description=Missing code or state parameter",
        )

    try:
        oauth_service = OAuthService(db)

        # Process callback
        user, oauth_account, is_new_user = await oauth_service.handle_google_callback(
            code=code,
            state=state,
        )

        # Generate JWT token
        token = oauth_service.generate_jwt_token(user)

        # Commit transaction
        await db.commit()

        # Redirect to frontend with token
        # WHY: Frontend will store the token and redirect to appropriate page
        return RedirectResponse(
            url=f"{frontend_url}/auth/oauth/success?token={token}&is_new_user={str(is_new_user).lower()}",
        )

    except OAuthError as e:
        await db.rollback()
        return RedirectResponse(
            url=f"{frontend_url}/auth/oauth/error?error={e.__class__.__name__}&error_description={e.message}",
        )
    except Exception as e:
        await db.rollback()
        return RedirectResponse(
            url=f"{frontend_url}/auth/oauth/error?error=server_error&error_description=An unexpected error occurred",
        )


# ============================================================================
# Linked Account Management
# ============================================================================


@router.get(
    "/accounts",
    response_model=LinkedAccountsResponse,
    summary="List linked OAuth accounts",
    description="Returns all OAuth accounts linked to the current user.",
)
async def list_linked_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List user's linked OAuth accounts.

    WHY: Users need to see which OAuth providers are linked to their account
    in the account settings page.

    Returns:
        List of linked OAuth accounts and whether unlinking is possible
    """
    oauth_service = OAuthService(db)

    accounts = await oauth_service.get_linked_accounts(current_user.id)
    can_unlink = await oauth_service.can_unlink_account(current_user.id)

    return LinkedAccountsResponse(
        accounts=accounts,
        can_unlink=can_unlink,
    )


@router.post(
    "/accounts/{provider}/unlink",
    response_model=UnlinkAccountResponse,
    summary="Unlink OAuth account",
    description="Removes an OAuth account link from the current user.",
)
async def unlink_account(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unlink an OAuth account.

    WHY: Users may want to remove OAuth access if they:
    - Prefer password-only login
    - Want to disconnect from the provider
    - Are removing access as a security measure

    Constraints:
    - Cannot unlink if it's the only authentication method
    - User must have password OR another OAuth provider

    Args:
        provider: Provider to unlink (e.g., 'google')

    Returns:
        Success message

    Raises:
        OAuthAccountNotFoundError: If provider not linked
        OAuthAccountLinkError: If cannot unlink (only auth method)
    """
    oauth_service = OAuthService(db)

    await oauth_service.unlink_account(
        user_id=current_user.id,
        provider=provider,
    )

    await db.commit()

    return UnlinkAccountResponse(
        message=f"{provider.title()} account unlinked successfully",
    )


# ============================================================================
# Token Exchange (for SPA/Mobile)
# ============================================================================


@router.post(
    "/google/token",
    response_model=OAuthTokenResponse,
    summary="Exchange Google auth code for JWT",
    description="Alternative to callback - exchanges code for JWT directly (for SPAs).",
)
async def google_token_exchange(
    db: AsyncSession = Depends(get_db),
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter"),
):
    """
    Exchange Google authorization code for JWT token.

    WHY: Alternative to redirect-based callback for single-page applications
    that want to handle the token exchange client-side.

    Returns:
        JWT token and user info

    Raises:
        OAuthStateError: If state is invalid
        OAuthTokenError: If code exchange fails
    """
    oauth_service = OAuthService(db)

    user, oauth_account, is_new_user = await oauth_service.handle_google_callback(
        code=code,
        state=state,
    )

    # Generate JWT token
    token = oauth_service.generate_jwt_token(user)

    # Commit transaction
    await db.commit()

    return OAuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
        user=OAuthUserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            org_id=user.org_id,
            is_active=user.is_active,
        ),
        is_new_user=is_new_user,
    )
