"""
Verification token DAO for managing verification tokens.

WHAT: Provides data access operations for verification tokens including
creation, validation, and consumption of tokens.

WHY: DAO pattern separates database operations from business logic:
1. Encapsulates all token-related queries
2. Provides type-safe token operations
3. Handles token lifecycle (creation, validation, consumption)
4. Supports audit trail for security analysis

HOW: Extends BaseDAO with token-specific methods:
- create_verification_token: Create new token for user
- get_by_token: Find token by token string
- get_by_code: Find token by 6-digit code
- mark_as_used: Mark token as consumed
- invalidate_previous_tokens: Revoke older tokens of same type
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.verification_token import VerificationToken, TokenType
from app.core.exceptions import ResourceNotFoundError, ValidationError


class VerificationTokenDAO(BaseDAO[VerificationToken]):
    """
    Data Access Object for verification tokens.

    WHAT: Provides database operations for verification token management.

    WHY: Token operations require specific logic:
    - Cryptographically secure token generation
    - Expiration and usage tracking
    - Invalidation of previous tokens
    - Security-focused query patterns
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize VerificationToken DAO.

        Args:
            session: AsyncSession for database operations
        """
        super().__init__(VerificationToken, session)

    async def create_verification_token(
        self,
        user_id: int,
        token_type: TokenType,
        include_code: bool = True,
        new_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        invalidate_previous: bool = True,
    ) -> VerificationToken:
        """
        Create a new verification token for a user.

        WHAT: Generates and stores a new verification token.

        WHY: Centralized token creation ensures:
        - Consistent token generation
        - Proper expiration setting
        - Optional code generation
        - Automatic invalidation of previous tokens

        HOW:
        1. Optionally invalidate previous tokens of same type
        2. Generate secure token and optional code
        3. Calculate expiration based on token type
        4. Store and return the new token

        Args:
            user_id: User to create token for
            token_type: Type of verification token
            include_code: Whether to generate a 6-digit code
            new_email: New email (for EMAIL_CHANGE tokens)
            ip_address: IP address of request
            invalidate_previous: Whether to invalidate previous tokens

        Returns:
            Created VerificationToken
        """
        if invalidate_previous:
            await self.invalidate_previous_tokens(user_id, token_type)

        token = VerificationToken(
            user_id=user_id,
            token=VerificationToken.generate_token(),
            code=VerificationToken.generate_code() if include_code else None,
            token_type=token_type,
            new_email=new_email,
            expires_at=VerificationToken.get_expiration(token_type),
            created_ip=ip_address,
        )

        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)

        return token

    async def get_by_token(
        self,
        token: str,
        token_type: Optional[TokenType] = None,
    ) -> Optional[VerificationToken]:
        """
        Get verification token by token string.

        WHAT: Finds a token by its secure token value.

        WHY: Primary lookup method for token verification:
        - Used when user clicks verification link
        - Must be fast (indexed query)

        Args:
            token: Token string to look up
            token_type: Optional type filter for added security

        Returns:
            VerificationToken if found, None otherwise
        """
        conditions = [VerificationToken.token == token]

        if token_type:
            conditions.append(VerificationToken.token_type == token_type)

        stmt = select(VerificationToken).where(and_(*conditions))
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        user_id: int,
        code: str,
        token_type: TokenType,
    ) -> Optional[VerificationToken]:
        """
        Get verification token by 6-digit code.

        WHAT: Finds a token by its numeric code for a specific user.

        WHY: Alternative lookup method for mobile/UX:
        - Easier to type than full token
        - Must be scoped to user (codes not globally unique)
        - Must check expiration and usage

        Args:
            user_id: User ID to scope the search
            code: 6-digit code string
            token_type: Type of token (required for security)

        Returns:
            VerificationToken if found and valid, None otherwise
        """
        stmt = select(VerificationToken).where(
            and_(
                VerificationToken.user_id == user_id,
                VerificationToken.code == code,
                VerificationToken.token_type == token_type,
                VerificationToken.expires_at > datetime.utcnow(),
                VerificationToken.used_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_valid_token(
        self,
        token: str,
        token_type: Optional[TokenType] = None,
    ) -> Optional[VerificationToken]:
        """
        Get a valid (unexpired and unused) token.

        WHAT: Finds a token and validates it in one query.

        WHY: Common pattern - need valid token, not just any token.
        Single query is more efficient than get + validate.

        Args:
            token: Token string to look up
            token_type: Optional type filter

        Returns:
            VerificationToken if valid, None if not found/invalid
        """
        conditions = [
            VerificationToken.token == token,
            VerificationToken.expires_at > datetime.utcnow(),
            VerificationToken.used_at.is_(None),
        ]

        if token_type:
            conditions.append(VerificationToken.token_type == token_type)

        stmt = select(VerificationToken).where(and_(*conditions))
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def mark_as_used(
        self,
        token_id: int,
        ip_address: Optional[str] = None,
    ) -> VerificationToken:
        """
        Mark a token as used.

        WHAT: Sets the used_at timestamp to mark token as consumed.

        WHY: Single-use tokens prevent:
        - Replay attacks (same token used multiple times)
        - Token sharing (forward email with link)
        - Delayed attacks (token used long after intended)

        Args:
            token_id: ID of token to mark as used
            ip_address: IP address that used the token

        Returns:
            Updated VerificationToken

        Raises:
            ResourceNotFoundError: If token not found
            ValidationError: If token already used
        """
        token = await self.get_by_id(token_id)

        if not token:
            raise ResourceNotFoundError(
                message="Verification token not found",
                resource_type="VerificationToken",
                resource_id=token_id,
            )

        if token.is_used:
            raise ValidationError(
                message="Token has already been used",
                token_id=token_id,
            )

        token.used_at = datetime.utcnow()
        token.used_ip = ip_address

        await self.session.flush()
        await self.session.refresh(token)

        return token

    async def invalidate_previous_tokens(
        self,
        user_id: int,
        token_type: TokenType,
    ) -> int:
        """
        Invalidate all previous tokens of a type for a user.

        WHAT: Marks all unused tokens as used (effectively invalidating them).

        WHY: Security best practice:
        - Only one active token per type per user
        - Prevents multiple valid reset links
        - Reduces attack surface

        Args:
            user_id: User to invalidate tokens for
            token_type: Type of tokens to invalidate

        Returns:
            Number of tokens invalidated
        """
        stmt = (
            update(VerificationToken)
            .where(
                and_(
                    VerificationToken.user_id == user_id,
                    VerificationToken.token_type == token_type,
                    VerificationToken.used_at.is_(None),
                )
            )
            .values(used_at=datetime.utcnow())
        )

        result = await self.session.execute(stmt)
        return result.rowcount

    async def validate_and_consume_token(
        self,
        token: str,
        expected_type: TokenType,
        ip_address: Optional[str] = None,
    ) -> VerificationToken:
        """
        Validate a token and mark it as used in one operation.

        WHAT: Combines validation and consumption for atomic operation.

        WHY: Common pattern that needs to be atomic:
        - Find valid token
        - Mark as used
        - Return for further processing

        Args:
            token: Token string to validate
            expected_type: Expected token type
            ip_address: IP address using the token

        Returns:
            Consumed VerificationToken

        Raises:
            ResourceNotFoundError: If token not found
            ValidationError: If token is expired, used, or wrong type
        """
        token_obj = await self.get_by_token(token, expected_type)

        if not token_obj:
            raise ResourceNotFoundError(
                message="Verification token not found or invalid type",
                resource_type="VerificationToken",
            )

        if token_obj.is_expired:
            raise ValidationError(
                message="Token has expired",
                expires_at=token_obj.expires_at.isoformat(),
            )

        if token_obj.is_used:
            raise ValidationError(
                message="Token has already been used",
            )

        return await self.mark_as_used(token_obj.id, ip_address)

    async def cleanup_expired_tokens(self, days_old: int = 7) -> int:
        """
        Delete expired tokens older than specified days.

        WHAT: Removes old expired tokens from database.

        WHY: Database hygiene:
        - Prevents unbounded table growth
        - Improves query performance
        - Removes old sensitive data

        Args:
            days_old: Delete tokens expired more than this many days ago

        Returns:
            Number of tokens deleted
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days_old)

        stmt = (
            VerificationToken.__table__.delete().where(
                VerificationToken.expires_at < cutoff
            )
        )

        result = await self.session.execute(stmt)
        return result.rowcount
