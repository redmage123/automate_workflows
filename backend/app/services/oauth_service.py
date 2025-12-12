"""
OAuth Service for social authentication.

WHY: This service encapsulates all OAuth-related business logic:
1. Generating authorization URLs
2. Exchanging authorization codes for tokens
3. Fetching user info from OAuth providers
4. Creating/linking OAuth accounts
5. Managing OAuth state for CSRF protection

SECURITY (OWASP A07 - Identification and Authentication Failures):
- State parameter prevents CSRF attacks
- Tokens are encrypted before storage
- Provider user IDs (not emails) are used for account lookup
- All OAuth events are audit logged

ARCHITECTURE:
- Uses httpx for async HTTP requests
- Follows the OAuth 2.0 Authorization Code flow
- State is encrypted and stored in Redis with TTL
"""

import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import urlencode

import httpx
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.auth import create_access_token, get_redis
from app.core.exceptions import (
    OAuthError,
    OAuthProviderError,
    OAuthStateError,
    OAuthTokenError,
    OAuthAccountLinkError,
    OAuthAccountNotFoundError,
    ValidationError,
)
from app.dao.oauth_account import OAuthAccountDAO
from app.dao.user import UserDAO
from app.dao.base import BaseDAO
from app.models.oauth_account import OAuthAccount, OAuthProvider
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.schemas.oauth import OAuthStateData, LinkedOAuthAccount
from app.services.audit import AuditService
from app.services.encryption_service import EncryptionService

from sqlalchemy.ext.asyncio import AsyncSession


# OAuth state TTL (5 minutes)
# WHY: Short TTL prevents replay attacks while allowing enough time
# for user to complete the OAuth consent flow
OAUTH_STATE_TTL_SECONDS = 300

# Google OAuth endpoints
# WHY: Google's OAuth 2.0 endpoints for the authorization code flow
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Google OAuth scopes
# WHY: Request minimal scopes needed for authentication
# - openid: Required for OpenID Connect
# - email: Get user's email address
# - profile: Get user's name and profile picture
GOOGLE_SCOPES = ["openid", "email", "profile"]


class OAuthService:
    """
    Service for OAuth authentication flows.

    WHY: Centralizes OAuth logic for:
    1. Testability (can mock HTTP calls)
    2. Security (state management, token encryption)
    3. Maintainability (single place for OAuth changes)
    4. Extensibility (easy to add new providers)
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize OAuth service.

        WHY: Dependency injection allows easy testing and proper
        resource management.

        Args:
            session: Database session for OAuth account operations
        """
        self.session = session
        self.oauth_dao = OAuthAccountDAO(session)
        self.user_dao = UserDAO(User, session)
        self.org_dao = BaseDAO(Organization, session)
        self.audit = AuditService(session)
        self._encryption = EncryptionService()

    # ========================================================================
    # Google OAuth Flow
    # ========================================================================

    async def get_google_authorize_url(
        self,
        action: str = "login",
        user_id: Optional[int] = None,
        redirect_url: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Generate Google OAuth authorization URL.

        WHY: Initiates the OAuth 2.0 Authorization Code flow by:
        1. Generating a secure state parameter for CSRF protection
        2. Building the authorization URL with required parameters
        3. Storing the state in Redis for later verification

        Args:
            action: OAuth action ('login', 'register', or 'link')
            user_id: User ID if linking to existing account
            redirect_url: Frontend URL to redirect after completion

        Returns:
            Tuple of (authorization_url, state)

        Raises:
            OAuthError: If Google OAuth is not configured

        Example:
            >>> auth_url, state = await oauth_service.get_google_authorize_url()
            >>> # Redirect user to auth_url
        """
        if not settings.google_oauth_enabled:
            raise OAuthError(
                message="Google OAuth is not configured",
            )

        # Generate secure state
        # WHY: State parameter prevents CSRF attacks by ensuring the callback
        # is from a request we initiated
        state_data = OAuthStateData(
            nonce=secrets.token_urlsafe(32),
            action=action,
            user_id=user_id,
            redirect_url=redirect_url,
        )

        # Encrypt and store state
        # WHY: Encryption prevents tampering, Redis TTL prevents replay attacks
        state = await self._store_oauth_state(state_data)

        # Build authorization URL
        # WHY: Include all required OAuth 2.0 parameters
        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(GOOGLE_SCOPES),
            "state": state,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Always show consent to get refresh token
        }

        authorization_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

        return authorization_url, state

    async def handle_google_callback(
        self,
        code: str,
        state: str,
    ) -> Tuple[User, OAuthAccount, bool]:
        """
        Handle Google OAuth callback.

        WHY: Completes the OAuth flow by:
        1. Validating the state parameter (CSRF protection)
        2. Exchanging the authorization code for tokens
        3. Fetching user info from Google
        4. Creating or linking the OAuth account

        Args:
            code: Authorization code from Google
            state: State parameter to validate

        Returns:
            Tuple of (user, oauth_account, is_new_user)

        Raises:
            OAuthStateError: If state is invalid or expired
            OAuthTokenError: If code exchange fails
            OAuthProviderError: If user info fetch fails
            OAuthAccountLinkError: If linking fails

        Example:
            >>> user, account, is_new = await oauth_service.handle_google_callback(
            ...     code="auth-code",
            ...     state="encrypted-state",
            ... )
        """
        # Validate and retrieve state
        state_data = await self._validate_oauth_state(state)

        # Exchange code for tokens
        tokens = await self._exchange_google_code(code)

        # Fetch user info
        user_info = await self._fetch_google_user_info(tokens["access_token"])

        # Process based on action
        if state_data.action == "link":
            # Link to existing user
            return await self._link_google_account(
                user_id=state_data.user_id,
                user_info=user_info,
                tokens=tokens,
            )
        else:
            # Login or register
            return await self._login_or_register_google(
                user_info=user_info,
                tokens=tokens,
            )

    async def _exchange_google_code(self, code: str) -> dict:
        """
        Exchange authorization code for tokens.

        WHY: The authorization code is short-lived and must be exchanged
        for access and refresh tokens to access Google APIs.

        Args:
            code: Authorization code from callback

        Returns:
            Token response with access_token, refresh_token, etc.

        Raises:
            OAuthTokenError: If exchange fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                    },
                )

                if response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    raise OAuthTokenError(
                        message="Failed to exchange authorization code",
                        error=error_data.get("error_description", "Unknown error"),
                    )

                return response.json()

            except httpx.RequestError as e:
                raise OAuthTokenError(
                    message="Failed to connect to Google OAuth",
                    error=str(e),
                )

    async def _fetch_google_user_info(self, access_token: str) -> dict:
        """
        Fetch user info from Google using access token.

        WHY: Gets user's email, name, and profile picture for
        account creation/lookup.

        Args:
            access_token: Valid Google access token

        Returns:
            User info dict with sub, email, name, picture

        Raises:
            OAuthProviderError: If fetch fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if response.status_code != 200:
                    raise OAuthProviderError(
                        message="Failed to fetch user info from Google",
                    )

                return response.json()

            except httpx.RequestError as e:
                raise OAuthProviderError(
                    message="Failed to connect to Google",
                    error=str(e),
                )

    async def _login_or_register_google(
        self,
        user_info: dict,
        tokens: dict,
    ) -> Tuple[User, OAuthAccount, bool]:
        """
        Login existing user or register new user via Google OAuth.

        WHY: Handles both cases:
        1. Existing user with linked Google account -> login
        2. Existing user with same email -> link and login
        3. New user -> create account and login

        Args:
            user_info: User info from Google
            tokens: OAuth tokens from Google

        Returns:
            Tuple of (user, oauth_account, is_new_user)
        """
        provider_user_id = user_info["sub"]
        email = user_info.get("email")
        name = user_info.get("name", email.split("@")[0] if email else "User")

        # Check if OAuth account exists
        oauth_account = await self.oauth_dao.get_by_provider_user_id(
            provider=OAuthProvider.GOOGLE,
            provider_user_id=provider_user_id,
        )

        if oauth_account:
            # Existing OAuth account - login
            user = await self.user_dao.get_by_id(oauth_account.user_id)
            if not user:
                raise OAuthError(
                    message="User account not found",
                )

            # Update tokens
            await self._update_oauth_tokens(oauth_account, tokens)

            # Audit log
            await self.audit.log_oauth_login(
                user_id=user.id,
                org_id=user.org_id,
                provider="google",
            )

            return user, oauth_account, False

        # Check if user exists with same email
        existing_user = await self.user_dao.get_by_email(email) if email else None

        if existing_user:
            # Link Google to existing account
            oauth_account = await self._create_oauth_account(
                user_id=existing_user.id,
                provider=OAuthProvider.GOOGLE,
                user_info=user_info,
                tokens=tokens,
            )

            # Audit log
            await self.audit.log_oauth_account_linked(
                user_id=existing_user.id,
                org_id=existing_user.org_id,
                provider="google",
            )

            return existing_user, oauth_account, False

        # Create new user
        user, oauth_account = await self._create_oauth_user(
            provider=OAuthProvider.GOOGLE,
            user_info=user_info,
            tokens=tokens,
        )

        return user, oauth_account, True

    async def _link_google_account(
        self,
        user_id: int,
        user_info: dict,
        tokens: dict,
    ) -> Tuple[User, OAuthAccount, bool]:
        """
        Link Google account to existing user.

        WHY: Users with existing accounts can add Google login
        for convenience without creating a new account.

        Args:
            user_id: User ID to link to
            user_info: User info from Google
            tokens: OAuth tokens from Google

        Returns:
            Tuple of (user, oauth_account, False)

        Raises:
            OAuthAccountLinkError: If account is already linked
        """
        # Get user
        user = await self.user_dao.get_by_id(user_id)
        if not user:
            raise OAuthAccountLinkError(
                message="User not found",
            )

        # Check if already linked
        existing = await self.oauth_dao.get_by_user_and_provider(
            user_id=user_id,
            provider=OAuthProvider.GOOGLE,
        )
        if existing:
            raise OAuthAccountLinkError(
                message="Google account is already linked",
            )

        # Check if this Google account is linked to another user
        provider_user_id = user_info["sub"]
        other_account = await self.oauth_dao.get_by_provider_user_id(
            provider=OAuthProvider.GOOGLE,
            provider_user_id=provider_user_id,
        )
        if other_account:
            raise OAuthAccountLinkError(
                message="This Google account is already linked to another user",
            )

        # Create OAuth account
        oauth_account = await self._create_oauth_account(
            user_id=user_id,
            provider=OAuthProvider.GOOGLE,
            user_info=user_info,
            tokens=tokens,
        )

        # Audit log
        await self.audit.log_oauth_account_linked(
            user_id=user.id,
            org_id=user.org_id,
            provider="google",
        )

        return user, oauth_account, False

    # ========================================================================
    # Account Management
    # ========================================================================

    async def get_linked_accounts(self, user_id: int) -> list[LinkedOAuthAccount]:
        """
        Get all OAuth accounts linked to a user.

        WHY: Displays linked accounts in account settings.

        Args:
            user_id: User ID

        Returns:
            List of linked OAuth accounts
        """
        accounts = await self.oauth_dao.get_by_user_id(user_id)

        return [
            LinkedOAuthAccount(
                id=account.id,
                provider=account.provider.value,
                provider_name=self._get_provider_name(account.provider),
                email=account.email,
                name=account.name,
                picture_url=account.picture_url,
                linked_at=account.created_at,
            )
            for account in accounts
        ]

    async def can_unlink_account(self, user_id: int) -> bool:
        """
        Check if user can unlink OAuth accounts.

        WHY: User must have either:
        1. A password (can login without OAuth)
        2. Multiple OAuth providers (can login with remaining)

        Args:
            user_id: User ID

        Returns:
            True if user can unlink accounts
        """
        # Check if user has password
        has_password = await self.oauth_dao.user_has_password(user_id)
        if has_password:
            return True

        # Check if user has multiple OAuth accounts
        accounts = await self.oauth_dao.get_by_user_id(user_id)
        return len(accounts) > 1

    async def unlink_account(
        self,
        user_id: int,
        provider: str,
    ) -> None:
        """
        Unlink an OAuth account.

        WHY: Users may want to remove OAuth access if they prefer
        password login or want to disconnect the provider.

        Args:
            user_id: User ID
            provider: Provider to unlink (e.g., 'google')

        Raises:
            OAuthAccountNotFoundError: If account not linked
            OAuthAccountLinkError: If can't unlink (only auth method)
        """
        # Validate provider
        try:
            oauth_provider = OAuthProvider(provider)
        except ValueError:
            raise ValidationError(
                message=f"Unknown provider: {provider}",
            )

        # Check if account exists
        account = await self.oauth_dao.get_by_user_and_provider(
            user_id=user_id,
            provider=oauth_provider,
        )
        if not account:
            raise OAuthAccountNotFoundError(
                message=f"{provider.title()} account is not linked",
            )

        # Check if can unlink
        can_unlink = await self.can_unlink_account(user_id)
        if not can_unlink:
            # Get user to check if this is the only OAuth
            accounts = await self.oauth_dao.get_by_user_id(user_id)
            if len(accounts) == 1:
                raise OAuthAccountLinkError(
                    message="Cannot unlink - this is your only login method. "
                    "Please set a password first.",
                )

        # Delete account
        user = await self.user_dao.get_by_id(user_id)
        await self.oauth_dao.delete_by_user_and_provider(user_id, oauth_provider)

        # Audit log
        await self.audit.log_oauth_account_unlinked(
            user_id=user_id,
            org_id=user.org_id if user else None,
            provider=provider,
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _store_oauth_state(self, state_data: OAuthStateData) -> str:
        """
        Store OAuth state in Redis.

        WHY: State must be stored server-side to validate callbacks
        and prevent CSRF/replay attacks.

        Args:
            state_data: State data to store

        Returns:
            Encrypted state string
        """
        # Serialize and encrypt state
        state_json = state_data.model_dump_json()
        encrypted_state = self._encryption.encrypt(state_json)

        # Store in Redis with TTL
        redis = await get_redis()
        key = f"oauth:state:{encrypted_state}"
        await redis.setex(
            key,
            OAUTH_STATE_TTL_SECONDS,
            "1",  # Value doesn't matter, just checking existence
        )

        return encrypted_state

    async def _validate_oauth_state(self, state: str) -> OAuthStateData:
        """
        Validate and retrieve OAuth state.

        WHY: Ensures the callback is from a request we initiated
        and prevents replay attacks.

        Args:
            state: Encrypted state from callback

        Returns:
            Decrypted state data

        Raises:
            OAuthStateError: If state is invalid or expired
        """
        # Check if state exists in Redis
        redis = await get_redis()
        key = f"oauth:state:{state}"
        exists = await redis.exists(key)

        if not exists:
            raise OAuthStateError(
                message="Invalid or expired OAuth state. Please try again.",
            )

        # Delete state to prevent reuse
        await redis.delete(key)

        # Decrypt state
        try:
            state_json = self._encryption.decrypt(state)
            state_data = OAuthStateData.model_validate_json(state_json)
        except Exception:
            raise OAuthStateError(
                message="Invalid OAuth state. Please try again.",
            )

        # Check expiration (additional check beyond Redis TTL)
        age = datetime.utcnow() - state_data.created_at
        if age > timedelta(seconds=OAUTH_STATE_TTL_SECONDS):
            raise OAuthStateError(
                message="OAuth state has expired. Please try again.",
            )

        return state_data

    async def _create_oauth_account(
        self,
        user_id: int,
        provider: OAuthProvider,
        user_info: dict,
        tokens: dict,
    ) -> OAuthAccount:
        """
        Create a new OAuth account linked to a user.

        WHY: Stores the OAuth provider link with encrypted tokens.

        Args:
            user_id: User to link to
            provider: OAuth provider
            user_info: User info from provider
            tokens: OAuth tokens

        Returns:
            Created OAuthAccount
        """
        return await self.oauth_dao.create_oauth_account(
            user_id=user_id,
            provider=provider,
            provider_user_id=user_info["sub"],
            email=user_info.get("email"),
            name=user_info.get("name"),
            picture_url=user_info.get("picture"),
            access_token=tokens.get("access_token"),
            refresh_token=tokens.get("refresh_token"),
            token_expires_at=(
                datetime.utcnow() + timedelta(seconds=tokens["expires_in"])
                if "expires_in" in tokens
                else None
            ),
            scopes=" ".join(GOOGLE_SCOPES),
        )

    async def _create_oauth_user(
        self,
        provider: OAuthProvider,
        user_info: dict,
        tokens: dict,
    ) -> Tuple[User, OAuthAccount]:
        """
        Create a new user from OAuth sign-up.

        WHY: New users signing up via OAuth need:
        1. A new organization (auto-created)
        2. A user account (no password)
        3. An OAuth account link

        Args:
            provider: OAuth provider
            user_info: User info from provider
            tokens: OAuth tokens

        Returns:
            Tuple of (user, oauth_account)
        """
        email = user_info.get("email")
        name = user_info.get("name", email.split("@")[0] if email else "User")

        # Create organization
        # WHY: Every user needs an organization for multi-tenancy
        org = await self.org_dao.create(
            name=f"{name}'s Organization",
            description=f"Organization for {name}",
            is_active=True,
        )

        # Create user (no password - OAuth only)
        # WHY: First user in org is ADMIN
        user = await self.user_dao.create_user(
            email=email,
            hashed_password=None,  # OAuth-only user
            name=name,
            org_id=org.id,
            role="ADMIN",
        )

        # Create OAuth account
        oauth_account = await self._create_oauth_account(
            user_id=user.id,
            provider=provider,
            user_info=user_info,
            tokens=tokens,
        )

        # Audit logs
        await self.audit.log_org_created(
            org_id=org.id,
            created_by_user_id=user.id,
            org_name=org.name,
        )
        await self.audit.log_account_created(
            user_id=user.id,
            org_id=org.id,
            extra_data={
                "email": user.email,
                "role": "ADMIN",
                "registration_method": f"oauth_{provider.value}",
            },
        )

        return user, oauth_account

    async def _update_oauth_tokens(
        self,
        account: OAuthAccount,
        tokens: dict,
    ) -> None:
        """
        Update OAuth tokens after login.

        WHY: Google may return new tokens on each login.

        Args:
            account: OAuth account to update
            tokens: New tokens
        """
        await self.oauth_dao.update_tokens(
            account_id=account.id,
            access_token=tokens.get("access_token"),
            refresh_token=tokens.get("refresh_token"),
            token_expires_at=(
                datetime.utcnow() + timedelta(seconds=tokens["expires_in"])
                if "expires_in" in tokens
                else None
            ),
        )

    def _get_provider_name(self, provider: OAuthProvider) -> str:
        """Get human-readable provider name."""
        names = {
            OAuthProvider.GOOGLE: "Google",
        }
        return names.get(provider, provider.value.title())

    def generate_jwt_token(self, user: User) -> str:
        """
        Generate JWT token for authenticated user.

        WHY: After OAuth authentication, user needs a JWT token
        for API access (same as regular login).

        Args:
            user: Authenticated user

        Returns:
            JWT token string
        """
        token_data = {
            "user_id": user.id,
            "org_id": user.org_id,
            "role": user.role.value,
            "email": user.email,
        }
        return create_access_token(token_data)
