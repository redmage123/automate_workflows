"""
OAuth Account Data Access Object.

WHY: The DAO pattern encapsulates all database operations for OAuth accounts,
providing a clean interface for the OAuth service to interact with the database.
This separation allows:
1. Easy testing with mock DAOs
2. Consistent database access patterns
3. Centralized query optimization
4. Type-safe operations

SECURITY (OWASP A07 - Identification and Authentication Failures):
- All OAuth accounts are looked up by provider + provider_user_id (stable identifiers)
- User linkage is enforced via foreign keys
- Queries are properly parameterized to prevent SQL injection
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.oauth_account import OAuthAccount, OAuthProvider
from app.services.encryption_service import EncryptionService


class OAuthAccountDAO(BaseDAO[OAuthAccount]):
    """
    Data Access Object for OAuth account operations.

    WHY: Encapsulates all database operations for OAuth accounts with
    specialized methods for OAuth-specific queries like provider lookup
    and token management.

    Inherits from BaseDAO[OAuthAccount] for standard CRUD operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize OAuth Account DAO.

        WHY: Uses dependency injection for both session and encryption service,
        allowing easy mocking in tests and proper resource management.

        Args:
            session: Async database session for executing queries
        """
        super().__init__(OAuthAccount, session)
        self._encryption = EncryptionService()

    async def get_by_provider_user_id(
        self,
        provider: OAuthProvider,
        provider_user_id: str,
    ) -> Optional[OAuthAccount]:
        """
        Find an OAuth account by provider and provider's user ID.

        WHY: This is the primary lookup for OAuth authentication. When a user
        signs in via Google/GitHub, we receive their provider_user_id and need
        to find the corresponding platform account.

        SECURITY: Uses provider_user_id (stable) instead of email (can change)
        for reliable account lookup.

        Args:
            provider: OAuth provider (e.g., OAuthProvider.GOOGLE)
            provider_user_id: User ID from the OAuth provider

        Returns:
            OAuthAccount if found, None otherwise

        Example:
            >>> account = await oauth_dao.get_by_provider_user_id(
            ...     OAuthProvider.GOOGLE,
            ...     "google-user-123"
            ... )
        """
        result = await self.session.execute(
            select(OAuthAccount).where(
                and_(
                    OAuthAccount.provider == provider,
                    OAuthAccount.provider_user_id == provider_user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(
        self,
        user_id: int,
    ) -> List[OAuthAccount]:
        """
        Get all OAuth accounts linked to a user.

        WHY: Users may have multiple OAuth accounts (Google + GitHub).
        This retrieves all linked accounts for display in account settings.

        Args:
            user_id: Platform user ID

        Returns:
            List of linked OAuth accounts (may be empty)

        Example:
            >>> accounts = await oauth_dao.get_by_user_id(user_id=1)
            >>> [a.provider.value for a in accounts]
            ['google', 'github']
        """
        result = await self.session.execute(
            select(OAuthAccount).where(OAuthAccount.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_by_user_and_provider(
        self,
        user_id: int,
        provider: OAuthProvider,
    ) -> Optional[OAuthAccount]:
        """
        Get a specific OAuth account for a user and provider.

        WHY: Check if a user already has a specific provider linked,
        used before linking to prevent duplicates and when unlinking.

        Args:
            user_id: Platform user ID
            provider: OAuth provider to look up

        Returns:
            OAuthAccount if found, None otherwise

        Example:
            >>> google_account = await oauth_dao.get_by_user_and_provider(
            ...     user_id=1,
            ...     provider=OAuthProvider.GOOGLE
            ... )
        """
        result = await self.session.execute(
            select(OAuthAccount).where(
                and_(
                    OAuthAccount.user_id == user_id,
                    OAuthAccount.provider == provider,
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_oauth_account(
        self,
        user_id: int,
        provider: OAuthProvider,
        provider_user_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        picture_url: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        scopes: Optional[str] = None,
    ) -> OAuthAccount:
        """
        Create a new OAuth account with encrypted tokens.

        WHY: This method handles:
        1. Token encryption before storage (OWASP A02)
        2. All required fields for OAuth account creation
        3. Proper database insertion with flush/refresh

        SECURITY: Tokens are encrypted using Fernet (AES-128-CBC) before
        storage to protect against database breaches.

        Args:
            user_id: Platform user ID to link to
            provider: OAuth provider (e.g., OAuthProvider.GOOGLE)
            provider_user_id: User ID from the OAuth provider
            email: Email from provider (optional, for display)
            name: Display name from provider (optional)
            picture_url: Profile picture URL (optional)
            access_token: OAuth access token (will be encrypted)
            refresh_token: OAuth refresh token (will be encrypted)
            token_expires_at: When the access token expires
            scopes: Space-separated list of granted scopes

        Returns:
            Created OAuthAccount instance

        Raises:
            IntegrityError: If provider_user_id already exists for provider

        Example:
            >>> account = await oauth_dao.create_oauth_account(
            ...     user_id=1,
            ...     provider=OAuthProvider.GOOGLE,
            ...     provider_user_id="google-user-123",
            ...     email="user@gmail.com",
            ...     access_token="ya29.xxx",
            ... )
        """
        # Encrypt tokens before storage
        # WHY: Tokens grant access to external services and must be protected
        encrypted_access_token = None
        encrypted_refresh_token = None

        if access_token:
            encrypted_access_token = self._encryption.encrypt(access_token)
        if refresh_token:
            encrypted_refresh_token = self._encryption.encrypt(refresh_token)

        # Create OAuth account
        account = OAuthAccount(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            name=name,
            picture_url=picture_url,
            access_token_encrypted=encrypted_access_token,
            refresh_token_encrypted=encrypted_refresh_token,
            token_expires_at=token_expires_at,
            scopes=scopes,
        )

        self.session.add(account)
        await self.session.flush()
        await self.session.refresh(account)

        return account

    async def update_tokens(
        self,
        account_id: int,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
    ) -> Optional[OAuthAccount]:
        """
        Update OAuth tokens after refresh.

        WHY: OAuth access tokens expire and need periodic refresh. This method
        updates the stored tokens after a successful refresh operation.

        SECURITY: New tokens are encrypted before storage.

        Args:
            account_id: OAuth account ID to update
            access_token: New access token (will be encrypted)
            refresh_token: New refresh token if provided (will be encrypted)
            token_expires_at: When the new access token expires

        Returns:
            Updated OAuthAccount if found, None otherwise

        Example:
            >>> updated = await oauth_dao.update_tokens(
            ...     account_id=1,
            ...     access_token="ya29.new-token",
            ...     token_expires_at=datetime.utcnow() + timedelta(hours=1),
            ... )
        """
        account = await self.get_by_id(account_id)
        if not account:
            return None

        # Encrypt new tokens
        account.access_token_encrypted = self._encryption.encrypt(access_token)
        if refresh_token:
            account.refresh_token_encrypted = self._encryption.encrypt(refresh_token)
        if token_expires_at:
            account.token_expires_at = token_expires_at

        await self.session.flush()
        await self.session.refresh(account)

        return account

    async def delete_by_user_and_provider(
        self,
        user_id: int,
        provider: OAuthProvider,
    ) -> bool:
        """
        Delete (unlink) an OAuth account.

        WHY: Users should be able to unlink OAuth providers from their account.
        This removes the OAuth account record, requiring re-linking if they
        want to use that provider again.

        Args:
            user_id: Platform user ID
            provider: OAuth provider to unlink

        Returns:
            True if account was deleted, False if not found

        Example:
            >>> deleted = await oauth_dao.delete_by_user_and_provider(
            ...     user_id=1,
            ...     provider=OAuthProvider.GOOGLE,
            ... )
        """
        account = await self.get_by_user_and_provider(user_id, provider)
        if not account:
            return False

        await self.session.delete(account)
        await self.session.flush()
        return True

    def get_decrypted_access_token(self, account: OAuthAccount) -> Optional[str]:
        """
        Decrypt and return the access token.

        WHY: Access tokens are stored encrypted. This method decrypts them
        when needed for API calls to the OAuth provider.

        SECURITY: Call this method only when the token is needed, and don't
        log or store the decrypted value.

        Args:
            account: OAuth account with encrypted token

        Returns:
            Decrypted access token, or None if not set

        Example:
            >>> account = await oauth_dao.get_by_id(1)
            >>> token = oauth_dao.get_decrypted_access_token(account)
            >>> # Use token for Google API call
        """
        if not account.access_token_encrypted:
            return None
        return self._encryption.decrypt(account.access_token_encrypted)

    def get_decrypted_refresh_token(self, account: OAuthAccount) -> Optional[str]:
        """
        Decrypt and return the refresh token.

        WHY: Refresh tokens are stored encrypted. This method decrypts them
        when needed to refresh expired access tokens.

        SECURITY: Call this method only when the token is needed, and don't
        log or store the decrypted value.

        Args:
            account: OAuth account with encrypted token

        Returns:
            Decrypted refresh token, or None if not set

        Example:
            >>> account = await oauth_dao.get_by_id(1)
            >>> refresh_token = oauth_dao.get_decrypted_refresh_token(account)
            >>> # Use refresh_token to get new access token
        """
        if not account.refresh_token_encrypted:
            return None
        return self._encryption.decrypt(account.refresh_token_encrypted)

    async def user_has_password(self, user_id: int) -> bool:
        """
        Check if user has a password set (not OAuth-only).

        WHY: Before unlinking the last OAuth provider, we need to verify
        the user has an alternative login method (password). OAuth-only
        users without a password cannot unlink their last provider.

        Args:
            user_id: Platform user ID

        Returns:
            True if user has a password, False if OAuth-only

        Example:
            >>> has_password = await oauth_dao.user_has_password(user_id=1)
            >>> if not has_password:
            ...     raise OAuthAccountLinkError("Cannot unlink last provider")
        """
        from app.models.user import User

        result = await self.session.execute(
            select(User.hashed_password).where(User.id == user_id)
        )
        hashed_password = result.scalar_one_or_none()

        return hashed_password is not None and len(hashed_password) > 0
