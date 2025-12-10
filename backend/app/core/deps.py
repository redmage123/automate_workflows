"""
FastAPI dependencies for authentication and authorization.

WHY: Dependencies provide reusable authentication and authorization logic
that can be injected into route handlers, following the DRY principle
and ensuring consistent security across the API.
"""

from typing import Optional
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_token, is_token_blacklisted
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    TokenExpiredError,
    TokenInvalidError,
)
from app.db.session import get_db
from app.models.user import User, UserRole
from app.dao.user import UserDAO


# HTTP Bearer token security scheme
# WHY: HTTPBearer extracts the token from Authorization header automatically
# Format: "Authorization: Bearer <token>"
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT token.

    WHY: This dependency:
    1. Extracts token from Authorization header
    2. Verifies token signature and expiration
    3. Checks if token is blacklisted (logged out)
    4. Fetches user from database
    5. Ensures user still exists and is active

    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id}

    Args:
        credentials: JWT token from Authorization header
        db: Database session

    Returns:
        Authenticated User instance

    Raises:
        AuthenticationError: If token is invalid, expired, or user not found
    """
    token = credentials.credentials

    # Verify token signature and expiration
    try:
        payload = verify_token(token)
    except (TokenExpiredError, TokenInvalidError) as e:
        # WHY: Re-raise as AuthenticationError for consistent API responses
        raise AuthenticationError(
            message=str(e),
            status_code=e.status_code,
        )

    # Check if token is blacklisted (user logged out)
    # WHY: Even valid tokens should be rejected if user logged out
    if await is_token_blacklisted(token):
        raise AuthenticationError(
            message="Token has been revoked",
            reason="logged_out",
        )

    # Extract user_id from token
    user_id: int = payload.get("user_id")
    if not user_id:
        raise AuthenticationError(
            message="Invalid token: missing user_id",
        )

    # Fetch user from database
    # WHY: User data in token might be stale; always fetch current data
    user_dao = UserDAO(User, db)
    user = await user_dao.get_by_id(user_id)

    if not user:
        # WHY: User might have been deleted after token was issued
        raise AuthenticationError(
            message="User not found",
            user_id=user_id,
        )

    if not user.is_active:
        # WHY: Inactive users (banned, suspended) should not access the system
        raise AuthenticationError(
            message="User account is inactive",
            user_id=user_id,
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user.

    WHY: Alias for get_current_user for better semantic clarity.
    Some routes might want to explicitly check for active users.

    Args:
        current_user: User from get_current_user dependency

    Returns:
        Active User instance
    """
    # Note: is_active check is already done in get_current_user
    return current_user


def require_role(required_role: str):
    """
    Factory function to create a role requirement dependency.

    WHY: Provides a flexible way to require specific roles without
    creating separate functions for each role.

    Usage:
        @app.get("/admin/users")
        async def admin_only_route(admin: User = Depends(require_role("ADMIN"))):
            return {"message": "Admin access granted"}

    Args:
        required_role: Role name (e.g., "ADMIN", "CLIENT")

    Returns:
        Dependency function that checks for the required role
    """

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        """
        Check if user has required role.

        Args:
            current_user: User from get_current_user dependency

        Returns:
            User instance (guaranteed to have required role)

        Raises:
            AuthorizationError: If user doesn't have required role
        """
        if current_user.role.value != required_role:
            raise AuthorizationError(
                message=f"{required_role} access required",
                user_id=current_user.id,
                user_role=current_user.role.value,
                required_role=required_role,
            )
        return current_user

    return role_checker


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Require user to have ADMIN role.

    WHY: RBAC (Role-Based Access Control) ensures only authorized users
    can access admin endpoints. This prevents privilege escalation attacks
    (OWASP A01: Broken Access Control).

    Usage:
        @app.get("/admin/users")
        async def admin_only_route(admin: User = Depends(require_admin)):
            return {"message": "Admin access granted"}

    Args:
        current_user: User from get_current_user dependency

    Returns:
        User instance (guaranteed to be ADMIN)

    Raises:
        AuthorizationError: If user is not ADMIN
    """
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError(
            message="Admin access required",
            user_id=current_user.id,
            user_role=current_user.role.value,
            required_role=UserRole.ADMIN.value,
        )

    return current_user


async def require_client(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Require user to have CLIENT role.

    WHY: Some endpoints might be client-only (e.g., client portal features
    that admins shouldn't access directly).

    Args:
        current_user: User from get_current_user dependency

    Returns:
        User instance (guaranteed to be CLIENT)

    Raises:
        AuthorizationError: If user is not CLIENT
    """
    if current_user.role != UserRole.CLIENT:
        raise AuthorizationError(
            message="Client access required",
            user_id=current_user.id,
            user_role=current_user.role.value,
        )

    return current_user


def get_current_org_id(
    current_user: User = Depends(get_current_user),
) -> int:
    """
    Get current user's organization ID.

    WHY: Many routes need org_id for org-scoped queries. This dependency
    provides it directly, making route handlers cleaner.

    Usage:
        @app.get("/projects")
        async def list_projects(org_id: int = Depends(get_current_org_id)):
            # Query projects for org_id

    Args:
        current_user: User from get_current_user dependency

    Returns:
        Organization ID
    """
    return current_user.org_id


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.

    WHY: Some endpoints might be accessible to both authenticated and
    anonymous users, but show different data based on auth status.

    Usage:
        @app.get("/public")
        async def public_route(user: Optional[User] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user.name}"}
            return {"message": "Hello guest"}

    Args:
        credentials: Optional JWT token from Authorization header
        db: Database session

    Returns:
        User instance if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = verify_token(token)

        # Check blacklist
        if await is_token_blacklisted(token):
            return None

        # Get user
        user_id = payload.get("user_id")
        if not user_id:
            return None

        user_dao = UserDAO(User, db)
        user = await user_dao.get_by_id(user_id)

        if user and user.is_active:
            return user

    except (TokenExpiredError, TokenInvalidError, AuthenticationError):
        # WHY: Silently fail for optional auth
        pass

    return None
