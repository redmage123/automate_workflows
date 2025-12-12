"""
OAuth account model for storing linked social authentication accounts.

WHY: OAuth accounts allow users to authenticate via external providers
(Google, GitHub, Microsoft) instead of email/password. This model stores
the provider-specific user ID and tokens to enable:
1. Social login without password
2. Multiple OAuth providers per user
3. Token refresh for continued API access
4. Account linking to existing email/password accounts

SECURITY (OWASP A07 - Identification and Authentication Failures):
- Access and refresh tokens are encrypted at rest using Fernet
- Provider user IDs are used for lookup, not email (emails can change)
- Unique constraint on (provider, provider_user_id) prevents duplicate accounts
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    ForeignKey,
    DateTime,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, PrimaryKeyMixin


class OAuthProvider(str, enum.Enum):
    """
    Supported OAuth providers.

    WHY: Enum ensures only supported providers can be stored, preventing
    typos and making it easy to add new providers in the future.

    Currently supported:
    - GOOGLE: Google OAuth 2.0 (most common, supports OpenID Connect)

    Future providers (can be added as needed):
    - GITHUB: Popular for developer-focused apps
    - MICROSOFT: Enterprise SSO via Azure AD
    - APPLE: Required for iOS apps with social login
    """

    GOOGLE = "google"
    # GITHUB = "github"  # Future: Add when needed
    # MICROSOFT = "microsoft"  # Future: Add when needed
    # APPLE = "apple"  # Future: Add when needed


class OAuthAccount(Base, PrimaryKeyMixin, TimestampMixin):
    """
    OAuth account linking model.

    WHY: This model enables social authentication by:
    1. Storing provider-specific user IDs for authentication lookup
    2. Storing encrypted tokens for API access (calendar, contacts, etc.)
    3. Supporting multiple providers per user (Google AND GitHub)
    4. Tracking token expiration for refresh flows

    RELATIONS:
    - Many-to-one with User: A user can have multiple OAuth accounts
    - Unique constraint on (provider, provider_user_id): One account per provider user

    SECURITY CONSIDERATIONS:
    - access_token and refresh_token are encrypted using Fernet (AES-128-CBC)
    - Tokens should be decrypted only when needed and never logged
    - provider_user_id is the primary identifier (emails can change)
    """

    __tablename__ = "oauth_accounts"

    # Foreign key to user
    # WHY: Links OAuth account to our platform user. A user can have
    # multiple OAuth accounts (Google + GitHub) but each OAuth account
    # belongs to exactly one user.
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # OAuth provider identification
    # WHY: provider + provider_user_id uniquely identifies an OAuth account
    # across the platform. The provider_user_id is Google's/GitHub's user ID.
    provider = Column(
        Enum(OAuthProvider),
        nullable=False,
        doc="OAuth provider (google, github, etc.)",
    )
    provider_user_id = Column(
        String(255),
        nullable=False,
        doc="User ID from the OAuth provider (e.g., Google's sub claim)",
    )

    # User info from provider
    # WHY: Store email from provider for display/reference. Note that we
    # should NOT rely on this for user lookup because:
    # 1. Users can change their email in the provider
    # 2. Provider email might differ from platform email
    # 3. provider_user_id is the stable identifier
    email = Column(
        String(255),
        nullable=True,
        doc="Email from OAuth provider (for display, not lookup)",
    )
    name = Column(
        String(255),
        nullable=True,
        doc="Display name from OAuth provider",
    )
    picture_url = Column(
        String(2048),
        nullable=True,
        doc="Profile picture URL from OAuth provider",
    )

    # OAuth tokens (encrypted at rest)
    # WHY: Tokens enable API access to provider services (calendar, contacts).
    # They are encrypted using Fernet to protect against database breaches.
    # If you don't need API access, these can be null.
    access_token_encrypted = Column(
        Text,
        nullable=True,
        doc="Encrypted OAuth access token for API calls",
    )
    refresh_token_encrypted = Column(
        Text,
        nullable=True,
        doc="Encrypted OAuth refresh token for token renewal",
    )
    token_expires_at = Column(
        DateTime,
        nullable=True,
        doc="When the access token expires (UTC)",
    )

    # Scopes granted by user
    # WHY: Track which permissions the user granted. Needed to know if
    # re-authorization is required for additional scopes.
    scopes = Column(
        String(1024),
        nullable=True,
        doc="Space-separated list of granted OAuth scopes",
    )

    # Relationship to User
    user = relationship("User", back_populates="oauth_accounts")

    # Unique constraint: one account per provider per provider_user_id
    # WHY: Prevents duplicate OAuth accounts. A Google user can only be
    # linked to one platform account.
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_oauth_provider_user",
        ),
        # Index for common query: find OAuth account by provider + provider_user_id
        Index(
            "ix_oauth_provider_lookup",
            "provider",
            "provider_user_id",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<OAuthAccount(id={self.id}, user_id={self.user_id}, "
            f"provider={self.provider.value}, email={self.email})>"
        )

    @property
    def is_token_expired(self) -> bool:
        """
        Check if the access token has expired.

        WHY: Before using the access token for API calls, we need to check
        if it's still valid. If expired, we should use the refresh token
        to get a new access token.

        Returns:
            True if token is expired or expiration is unknown, False otherwise
        """
        if self.token_expires_at is None:
            # WHY: If we don't know when it expires, assume it's expired
            # to force a refresh (safer approach)
            return True
        return datetime.utcnow() >= self.token_expires_at

    @property
    def needs_refresh(self) -> bool:
        """
        Check if the access token should be refreshed (expires within 5 min).

        WHY: Proactively refresh tokens before they expire to prevent
        failed API calls. 5-minute buffer accounts for clock skew and
        request processing time.

        Returns:
            True if token expires within 5 minutes, False otherwise
        """
        if self.token_expires_at is None:
            return True
        from datetime import timedelta

        buffer = timedelta(minutes=5)
        return datetime.utcnow() >= (self.token_expires_at - buffer)
