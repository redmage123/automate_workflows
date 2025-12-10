"""
User Data Access Object.

WHY: UserDAO provides database operations for User model, following
the DAO pattern for separation of concerns and testability.
"""

from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.user import User
from app.core.exceptions import ResourceAlreadyExistsError


class UserDAO(BaseDAO[User]):
    """
    Data Access Object for User model.

    WHY: Separating user database operations from business logic makes
    the code more maintainable and testable. All user queries go through
    this DAO, ensuring consistent error handling and org-scoping.
    """

    def __init__(self, model: type[User], session: AsyncSession):
        """Initialize UserDAO with model and session."""
        super().__init__(model, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Retrieve user by email address.

        WHY: Email is the unique identifier for authentication.
        Case-insensitive comparison prevents duplicate accounts with
        different casing (user@example.com vs USER@EXAMPLE.COM).

        Args:
            email: User's email address

        Returns:
            User instance if found, None otherwise

        Example:
            >>> user = await user_dao.get_by_email("admin@example.com")
            >>> user.email
            'admin@example.com'
        """
        result = await self.session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """
        Check if email already exists in database.

        WHY: More efficient than get_by_email when you only need to know
        if the email exists (e.g., during registration validation).

        Args:
            email: Email address to check

        Returns:
            True if email exists, False otherwise

        Example:
            >>> await user_dao.email_exists("admin@example.com")
            True
        """
        result = await self.session.execute(
            select(User.id).where(func.lower(User.email) == email.lower()).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def create_user(
        self,
        email: str,
        hashed_password: str,
        name: str,
        org_id: int,
        role: str = "CLIENT",
    ) -> User:
        """
        Create a new user.

        WHY: This method ensures email uniqueness and provides a clean
        interface for user creation with all required fields.

        Args:
            email: User's email address
            hashed_password: Already hashed password (use hash_password())
            name: User's full name
            org_id: Organization ID
            role: User role (ADMIN or CLIENT)

        Returns:
            Created User instance

        Raises:
            ResourceAlreadyExistsError: If email already exists

        Example:
            >>> from app.core.auth import hash_password
            >>> hashed = hash_password("SecurePassword123!")
            >>> user = await user_dao.create_user(
            ...     email="user@example.com",
            ...     hashed_password=hashed,
            ...     name="John Doe",
            ...     org_id=1,
            ...     role="CLIENT"
            ... )
        """
        # Check if email already exists
        # WHY: Prevent duplicate accounts before attempting insert
        if await self.email_exists(email):
            raise ResourceAlreadyExistsError(
                message="User with this email already exists",
                resource_type="User",
                email=email,
            )

        # Create user
        user = await self.create(
            email=email,
            hashed_password=hashed_password,
            name=name,
            org_id=org_id,
            role=role,
            is_active=True,
        )

        return user

    async def get_by_email_and_org(self, email: str, org_id: int) -> Optional[User]:
        """
        Retrieve user by email within specific organization.

        WHY: For multi-tenant systems, ensures we're fetching the correct
        user within the right organization context.

        Args:
            email: User's email address
            org_id: Organization ID

        Returns:
            User instance if found in org, None otherwise
        """
        result = await self.session.execute(
            select(User).where(
                func.lower(User.email) == email.lower(),
                User.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def deactivate_user(self, user_id: int) -> Optional[User]:
        """
        Deactivate a user (soft delete).

        WHY: Soft deletion preserves audit trails and allows reactivation
        if needed. Better than hard deletion for compliance and debugging.

        Args:
            user_id: User ID to deactivate

        Returns:
            Updated User instance if found, None otherwise

        Example:
            >>> user = await user_dao.deactivate_user(123)
            >>> user.is_active
            False
        """
        return await self.update(user_id, is_active=False)

    async def activate_user(self, user_id: int) -> Optional[User]:
        """
        Activate a user.

        WHY: Allows reactivating previously deactivated accounts.

        Args:
            user_id: User ID to activate

        Returns:
            Updated User instance if found, None otherwise
        """
        return await self.update(user_id, is_active=True)

    async def update_password(self, user_id: int, new_hashed_password: str) -> Optional[User]:
        """
        Update user's password.

        WHY: Password changes are sensitive operations that should be
        tracked separately. This method makes the intent clear.

        Args:
            user_id: User ID
            new_hashed_password: New hashed password (use hash_password())

        Returns:
            Updated User instance if found, None otherwise

        Security Note:
            After password change, consider invalidating all existing tokens
            by calling blacklist_user_tokens() from auth module.

        Example:
            >>> from app.core.auth import hash_password
            >>> new_hashed = hash_password("NewSecurePassword123!")
            >>> user = await user_dao.update_password(123, new_hashed)
        """
        return await self.update(user_id, hashed_password=new_hashed_password)

    async def get_users_by_org(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> list[User]:
        """
        Get all users for an organization.

        WHY: Admin endpoints need to list users within an organization,
        with optional filtering by active status.

        Args:
            org_id: Organization ID
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return
            include_inactive: Whether to include inactive users

        Returns:
            List of User instances

        Example:
            >>> users = await user_dao.get_users_by_org(org_id=1)
            >>> len(users)
            10
        """
        query = select(User).where(User.org_id == org_id)

        if not include_inactive:
            query = query.where(User.is_active)

        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_users_by_org(self, org_id: int, include_inactive: bool = False) -> int:
        """
        Count users in an organization.

        WHY: Useful for pagination and analytics without loading all records.

        Args:
            org_id: Organization ID
            include_inactive: Whether to include inactive users

        Returns:
            Number of users
        """
        query = select(func.count(User.id)).where(User.org_id == org_id)

        if not include_inactive:
            query = query.where(User.is_active)

        result = await self.session.execute(query)
        return result.scalar_one()
