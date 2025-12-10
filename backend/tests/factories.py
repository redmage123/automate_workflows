"""
Test factories for creating test data.

WHY: Factories provide a consistent, reusable way to create test objects,
reducing duplication and making tests more maintainable. Using factories
instead of manual object creation ensures tests stay consistent when models change.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.organization import Organization
from app.dao.user import UserDAO
from app.core.auth import hash_password


class OrganizationFactory:
    """
    Factory for creating Organization test instances.

    WHY: Centralizes organization creation logic for tests,
    ensuring consistent test data across all test suites.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        name: str = "Test Organization",
        description: Optional[str] = None,
        settings: Optional[dict] = None,
        is_active: bool = True,
    ) -> Organization:
        """
        Create an organization for testing.

        Args:
            session: Database session
            name: Organization name
            description: Organization description
            settings: JSONB settings
            is_active: Whether organization is active

        Returns:
            Created Organization instance
        """
        org = Organization(
            name=name,
            description=description or f"Description for {name}",
            settings=settings or {},
            is_active=is_active,
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)
        return org


class UserFactory:
    """
    Factory for creating User test instances.

    WHY: Provides consistent user creation with proper password hashing
    and organization relationships for testing authentication and authorization.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        email: str = "test@example.com",
        password: str = "TestPassword123!",
        name: str = "Test User",
        role: UserRole = UserRole.CLIENT,
        org_id: Optional[int] = None,
        is_active: bool = True,
        organization: Optional[Organization] = None,
    ) -> User:
        """
        Create a user for testing.

        WHY: Tests need users with different roles and organizations
        to verify RBAC and multi-tenancy features.

        Args:
            session: Database session
            email: User email (must be unique)
            password: Plain text password (will be hashed)
            name: User's full name
            role: User role (ADMIN or CLIENT)
            org_id: Organization ID
            is_active: Whether user is active
            organization: Organization instance (will create one if not provided)

        Returns:
            Created User instance
        """
        # Create organization if not provided
        if organization is None and org_id is None:
            organization = await OrganizationFactory.create(session, name=f"Org for {email}")
            org_id = organization.id
        elif organization is not None:
            org_id = organization.id

        user_dao = UserDAO(User, session)
        hashed_password = hash_password(password)

        user = await user_dao.create_user(
            email=email,
            hashed_password=hashed_password,
            name=name,
            org_id=org_id,
            role=role.value,
        )

        # Set is_active if different from default
        if not is_active:
            user.is_active = is_active
            await session.commit()
            await session.refresh(user)

        return user

    @staticmethod
    async def create_admin(
        session: AsyncSession,
        email: str = "admin@example.com",
        password: str = "AdminPassword123!",
        name: str = "Admin User",
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
    ) -> User:
        """
        Create an admin user for testing.

        WHY: Many tests require admin users to test privileged operations.
        """
        return await UserFactory.create(
            session=session,
            email=email,
            password=password,
            name=name,
            role=UserRole.ADMIN,
            org_id=org_id,
            organization=organization,
        )

    @staticmethod
    async def create_client(
        session: AsyncSession,
        email: str = "client@example.com",
        password: str = "ClientPassword123!",
        name: str = "Client User",
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
    ) -> User:
        """
        Create a client user for testing.

        WHY: Most users are clients, so this is a common test scenario.
        """
        return await UserFactory.create(
            session=session,
            email=email,
            password=password,
            name=name,
            role=UserRole.CLIENT,
            org_id=org_id,
            organization=organization,
        )


class TestDataBuilder:
    """
    Builder for creating complex test scenarios.

    WHY: Some tests require multiple related objects. This builder
    provides a fluent API for creating complex test data scenarios.
    """

    def __init__(self, session: AsyncSession):
        """Initialize builder with database session."""
        self.session = session
        self.organizations: list[Organization] = []
        self.users: list[User] = []

    async def with_organization(
        self,
        name: str = "Test Organization",
        **kwargs,
    ) -> "TestDataBuilder":
        """Add an organization to the test data."""
        org = await OrganizationFactory.create(self.session, name=name, **kwargs)
        self.organizations.append(org)
        return self

    async def with_admin(
        self,
        email: str = "admin@example.com",
        org_index: int = -1,
        **kwargs,
    ) -> "TestDataBuilder":
        """
        Add an admin user to the test data.

        Args:
            email: User email
            org_index: Index of organization in self.organizations (-1 for last)
            **kwargs: Additional user creation arguments
        """
        org = self.organizations[org_index] if self.organizations else None
        user = await UserFactory.create_admin(self.session, email=email, organization=org, **kwargs)
        self.users.append(user)
        return self

    async def with_client(
        self,
        email: str = "client@example.com",
        org_index: int = -1,
        **kwargs,
    ) -> "TestDataBuilder":
        """
        Add a client user to the test data.

        Args:
            email: User email
            org_index: Index of organization in self.organizations (-1 for last)
            **kwargs: Additional user creation arguments
        """
        org = self.organizations[org_index] if self.organizations else None
        user = await UserFactory.create_client(
            self.session, email=email, organization=org, **kwargs
        )
        self.users.append(user)
        return self

    async def with_multi_tenant_setup(self) -> "TestDataBuilder":
        """
        Create a complete multi-tenant test scenario.

        WHY: Tests org-scoping by creating two organizations,
        each with an admin and a client user.

        Returns:
            Builder with:
            - 2 organizations
            - 4 users (1 admin + 1 client per org)
        """
        # Organization 1
        await self.with_organization(name="Acme Corp")
        await self.with_admin(email="admin1@acme.com")
        await self.with_client(email="client1@acme.com")

        # Organization 2
        await self.with_organization(name="Wayne Enterprises")
        await self.with_admin(email="admin2@wayne.com")
        await self.with_client(email="client2@wayne.com")

        return self

    def get_organization(self, index: int = 0) -> Organization:
        """Get organization by index."""
        return self.organizations[index]

    def get_user(self, index: int = 0) -> User:
        """Get user by index."""
        return self.users[index]
