"""
JWT authentication and password hashing utilities.

WHY: This module provides secure authentication functionality:
1. Password hashing with bcrypt (OWASP A07: Authentication Failures)
2. JWT token generation and verification
3. Token blacklist for logout functionality
4. Protection against common auth vulnerabilities
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.exceptions import (
    TokenExpiredError,
    TokenInvalidError,
)


# Password hashing context
# WHY: bcrypt with default cost factor (12 rounds) provides strong protection
# against brute-force attacks while maintaining acceptable performance.
# The cost factor can be increased over time as hardware improves.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Redis connection for token blacklist
# WHY: Redis provides fast in-memory storage for blacklisted tokens,
# allowing sub-millisecond lookups on every request without database load.
_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """
    Get Redis client for token blacklist.

    WHY: Lazy initialization ensures Redis is only connected when needed,
    and connection is reused across requests for performance.

    Returns:
        Redis client instance
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


# ============================================================================
# Password Hashing
# ============================================================================


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    WHY: bcrypt is specifically designed for password hashing with:
    - Adaptive cost factor (currently 12 rounds = ~300ms)
    - Automatic salt generation (unique hash for same password)
    - Resistance to rainbow table and brute-force attacks
    - OWASP recommendation for password storage

    Args:
        password: Plain text password

    Returns:
        Hashed password (60 characters, includes salt and cost factor)

    Example:
        >>> hashed = hash_password("MyPassword123!")
        >>> len(hashed)
        60
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    WHY: Constant-time comparison (built into passlib) prevents timing
    attacks that could leak information about the password.

    Args:
        plain_password: Password provided by user
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("MyPassword123!")
        >>> verify_password("MyPassword123!", hashed)
        True
        >>> verify_password("WrongPassword", hashed)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# JWT Token Management
# ============================================================================


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    WHY: JWT tokens are stateless, allowing horizontal scaling without
    shared session storage. They include all necessary user information
    (user_id, org_id, role) for authorization decisions.

    Token includes:
    - User data (user_id, org_id, role, etc.)
    - exp: Expiration time (default: 24 hours)
    - iat: Issued at time (for audit)
    - nbf: Not before time (prevents premature use)

    Args:
        data: User data to encode in token (user_id, org_id, role, etc.)
        expires_delta: Optional custom expiration time

    Returns:
        JWT token string

    Security Notes:
        - NEVER include passwords or sensitive data in tokens
        - Tokens are signed but not encrypted (base64 encoded)
        - Keep JWT_SECRET secure and rotate periodically

    Example:
        >>> token = create_access_token({"user_id": 1, "role": "ADMIN"})
        >>> len(token) > 100
        True
    """
    to_encode = data.copy()

    # Set expiration time
    # WHY: Short expiration (24h default) limits damage if token is stolen
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)

    # Add standard JWT claims
    # WHY: Standard claims enable proper token lifecycle management
    to_encode.update(
        {
            "exp": expire,  # Expiration time
            "iat": datetime.utcnow(),  # Issued at
            "nbf": datetime.utcnow(),  # Not before (immediately valid)
        }
    )

    # Encode token
    # WHY: HS256 (HMAC with SHA-256) provides strong security with symmetric keys
    # For higher security, consider RS256 (RSA) with public/private key pairs
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.

    WHY: Token verification ensures:
    1. Signature is valid (token not tampered with)
    2. Token hasn't expired
    3. Token is from a trusted issuer (our JWT_SECRET)

    Args:
        token: JWT token string

    Returns:
        Decoded token payload with user data

    Raises:
        TokenExpiredError: If token has expired
        TokenInvalidError: If token is malformed or signature invalid

    Example:
        >>> token = create_access_token({"user_id": 1})
        >>> payload = verify_token(token)
        >>> payload["user_id"]
        1
    """
    try:
        # Decode and verify token
        # WHY: Verification checks signature and expiration automatically
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload

    except jwt.ExpiredSignatureError:
        # WHY: Separate exception for expired tokens allows frontend
        # to trigger token refresh without full re-authentication
        raise TokenExpiredError(
            message="Token has expired",
            token_exp=None,  # Could extract from token if needed
        )

    except JWTError as e:
        # WHY: Any other JWT error (invalid signature, malformed token, etc.)
        # should be treated as invalid credentials
        raise TokenInvalidError(
            message="Invalid token",
            error=str(e),
        )


# ============================================================================
# Token Blacklist (Logout)
# ============================================================================


async def blacklist_token(
    token: str,
    user_id: int,
    ttl_seconds: Optional[int] = None,
) -> None:
    """
    Add a token to the blacklist (for logout).

    WHY: JWT tokens are stateless and can't be "deleted". Blacklisting
    prevents a token from being used even if it hasn't expired yet.
    This is essential for logout and account security (forced logout).

    Args:
        token: JWT token to blacklist
        user_id: User ID for logging/analytics
        ttl_seconds: Optional TTL (defaults to token expiration time)

    Example:
        >>> token = create_access_token({"user_id": 1})
        >>> await blacklist_token(token, user_id=1)
        >>> await is_token_blacklisted(token)
        True
    """
    redis = await get_redis()

    # Calculate TTL based on token expiration
    # WHY: No need to keep blacklist entries longer than token lifetime
    if ttl_seconds is None:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_signature": False, "verify_exp": False},
            )
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                ttl_seconds = max(
                    int(exp_timestamp - datetime.utcnow().timestamp()),
                    0,
                )
            else:
                # Fallback to default expiration
                ttl_seconds = settings.JWT_EXPIRATION_MINUTES * 60
        except JWTError:
            # If token is malformed, use default TTL
            ttl_seconds = settings.JWT_EXPIRATION_MINUTES * 60

    # Store in Redis with TTL
    # WHY: Redis automatically removes expired entries, preventing
    # unbounded memory growth
    blacklist_key = f"blacklist:token:{token}"
    await redis.setex(
        blacklist_key,
        ttl_seconds,
        str(user_id),  # Store user_id for audit/analytics
    )


async def is_token_blacklisted(token: str) -> bool:
    """
    Check if a token is blacklisted.

    WHY: Fast Redis lookup (sub-millisecond) checks token validity
    on every request without impacting performance.

    Args:
        token: JWT token to check

    Returns:
        True if token is blacklisted, False otherwise

    Example:
        >>> token = create_access_token({"user_id": 1})
        >>> await is_token_blacklisted(token)
        False
        >>> await blacklist_token(token, user_id=1)
        >>> await is_token_blacklisted(token)
        True
    """
    redis = await get_redis()
    blacklist_key = f"blacklist:token:{token}"

    # Check if key exists
    # WHY: EXISTS is O(1) operation in Redis, extremely fast
    exists = await redis.exists(blacklist_key)
    return exists > 0


async def blacklist_user_tokens(user_id: int) -> None:
    """
    Blacklist all tokens for a user (force logout all sessions).

    WHY: When an account is compromised or user changes password,
    all existing sessions should be invalidated immediately.

    Note: This is a placeholder. Full implementation would require
    tracking all user tokens, which adds complexity. Consider:
    1. Adding token_id to JWT and tracking in database
    2. Using refresh tokens with database storage
    3. Implementing "issued_before" timestamp in user record

    Args:
        user_id: User ID to force logout

    TODO: Implement proper multi-session invalidation
    """
    # TODO: Implement token tracking for multi-session logout
    # For now, this is a placeholder
    pass


# ============================================================================
# Token Refresh (Future Enhancement)
# ============================================================================


def create_refresh_token(user_id: int) -> str:
    """
    Create a long-lived refresh token.

    WHY: Refresh tokens allow generating new access tokens without
    re-authentication. They should be:
    - Long-lived (30 days)
    - Stored in database (can be revoked)
    - Used only to obtain new access tokens

    TODO: Implement refresh token flow for better UX

    Args:
        user_id: User ID

    Returns:
        Refresh token string
    """
    # TODO: Implement refresh token with database storage
    raise NotImplementedError("Refresh tokens not yet implemented")
