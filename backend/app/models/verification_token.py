"""
Verification token model for email verification and password reset.

WHAT: Stores temporary tokens for user verification and password reset operations.

WHY: Secure token-based verification requires:
1. Time-limited tokens to prevent stale token attacks
2. One-time use to prevent token reuse attacks
3. Cryptographically secure token generation
4. Audit trail for security analysis

HOW: Tokens are generated with secrets.token_urlsafe() and stored with:
- Expiration time (24h for email verification, 1h for password reset)
- Usage tracking (used_at timestamp marks token as consumed)
- Token type to distinguish between verification and reset
"""

import enum
import secrets
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Enum, ForeignKey, DateTime, Boolean, Index
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, PrimaryKeyMixin


class TokenType(str, enum.Enum):
    """
    Types of verification tokens.

    WHY: Different token types have different:
    - Expiration times (verification: 24h, reset: 1h)
    - Security requirements
    - Usage patterns
    """

    EMAIL_VERIFICATION = "email_verification"
    """Token for verifying email ownership after registration."""

    PASSWORD_RESET = "password_reset"
    """Token for password reset request."""

    EMAIL_CHANGE = "email_change"
    """Token for confirming email address change."""


class VerificationToken(Base, PrimaryKeyMixin, TimestampMixin):
    """
    Verification token for email verification and password reset.

    WHAT: Stores temporary, single-use tokens for verification operations.

    WHY: Token-based verification is more secure than:
    - Magic links alone (tokens can be revoked, tracked, rate-limited)
    - Simple confirmation codes (tokens are cryptographically secure)

    HOW: Tokens are:
    1. Generated with 32-byte random data (URL-safe base64)
    2. Stored with expiration time
    3. Marked as used after consumption (single-use)
    4. Linked to user for audit trail
    """

    __tablename__ = "verification_tokens"

    # Token data
    token = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    """Cryptographically secure token string.

    WHY: 32-byte random data provides 256 bits of entropy,
    making brute-force attacks computationally infeasible.
    """

    token_type = Column(
        Enum(TokenType),
        nullable=False,
    )
    """Type of verification this token is for."""

    # Optional 6-digit code for mobile/UX convenience
    code = Column(
        String(6),
        nullable=True,
    )
    """6-digit numeric code for easier entry.

    WHY: While less secure than full token, 6-digit codes are:
    - Easier to enter on mobile devices
    - Usable for in-app verification
    - Protected by rate limiting and short expiration
    """

    # User association
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    """User this token was issued for."""

    # For email change tokens, store the new email
    new_email = Column(
        String(255),
        nullable=True,
    )
    """New email address (only for EMAIL_CHANGE tokens)."""

    # Expiration and usage
    expires_at = Column(
        DateTime,
        nullable=False,
    )
    """When this token expires.

    WHY: Time-limited tokens prevent:
    - Stale tokens being used long after issuance
    - Tokens in old emails being exploited
    """

    used_at = Column(
        DateTime,
        nullable=True,
    )
    """When this token was used (None if unused).

    WHY: Marking tokens as used instead of deleting them:
    - Maintains audit trail
    - Prevents reuse (even with replay attacks)
    - Allows analysis of verification patterns
    """

    # IP address for security audit
    created_ip = Column(
        String(45),
        nullable=True,
    )
    """IP address that requested this token.

    WHY: Helps detect suspicious patterns:
    - Multiple reset requests from different IPs
    - Tokens requested from unusual locations
    """

    used_ip = Column(
        String(45),
        nullable=True,
    )
    """IP address that used this token.

    WHY: Verifying reset was completed from expected location.
    """

    # Relationships
    user = relationship("User", backref="verification_tokens")

    # Indexes for efficient queries
    __table_args__ = (
        # For finding unexpired tokens by user and type
        Index(
            "ix_verification_tokens_user_type_expires",
            "user_id",
            "token_type",
            "expires_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<VerificationToken(id={self.id}, type={self.token_type}, "
            f"user_id={self.user_id}, expires_at={self.expires_at})>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if token has been used."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not used)."""
        return not self.is_expired and not self.is_used

    @classmethod
    def generate_token(cls) -> str:
        """
        Generate a cryptographically secure token.

        WHY: secrets.token_urlsafe provides:
        - 32 bytes of random data
        - URL-safe encoding (no special chars)
        - OS-level entropy source

        Returns:
            URL-safe token string (43 characters)
        """
        return secrets.token_urlsafe(32)

    @classmethod
    def generate_code(cls) -> str:
        """
        Generate a 6-digit numeric code.

        WHY: Numeric codes are easier to type on mobile devices
        and can be spoken over phone for support scenarios.

        Returns:
            6-digit string code (e.g., "123456")
        """
        return str(secrets.randbelow(1000000)).zfill(6)

    @classmethod
    def get_expiration(cls, token_type: TokenType) -> datetime:
        """
        Get expiration datetime for a token type.

        WHY: Different token types have different security requirements:
        - Email verification: 24 hours (user might check email later)
        - Password reset: 1 hour (security-sensitive, should be done quickly)

        Args:
            token_type: Type of token

        Returns:
            Expiration datetime
        """
        if token_type == TokenType.PASSWORD_RESET:
            # Password reset tokens expire in 1 hour
            return datetime.utcnow() + timedelta(hours=1)
        else:
            # Other tokens expire in 24 hours
            return datetime.utcnow() + timedelta(hours=24)
