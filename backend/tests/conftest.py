"""
Pytest configuration and fixtures.

WHY: Fixtures provide reusable test setup/teardown logic, reducing
duplication and ensuring consistent test environments.
"""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient

from app.main import app
from app.models.base import Base
from app.db.session import get_db
from app.core import auth as auth_module
from app.middleware import rate_limiter as rate_limiter_module
from app.services import email as email_module


# Test database URL
# WHY: Using SQLite for tests eliminates external database dependencies
# and makes tests faster. For integration tests, use PostgreSQL.
TEST_ASYNC_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an event loop for the test session.

    WHY: pytest-asyncio requires an event loop fixture for async tests.
    Session scope ensures one loop for all tests, improving performance.
    """
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """
    Create a test database engine.

    WHY: Function scope ensures each test gets a fresh database state,
    preventing test pollution and ensuring test isolation.
    """
    engine = create_async_engine(
        TEST_ASYNC_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a test database session.

    WHY: Each test gets its own session that is rolled back after the test,
    ensuring test isolation without recreating tables for each test.

    Yields:
        AsyncSession: Database session for the test
    """
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a test HTTP client.

    WHY: AsyncClient allows testing FastAPI endpoints without running
    a real server, making tests faster and more reliable.

    Yields:
        AsyncClient: HTTP client for making test requests
    """
    from httpx import ASGITransport

    async def override_get_db():
        """Override database dependency with test session."""
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Use ASGI transport for httpx 0.26+
    # WHY: httpx 0.26+ uses ASGITransport instead of the app parameter
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data() -> dict:
    """
    Sample user data for tests.

    WHY: Centralizing test data ensures consistency across tests
    and makes it easy to update test data in one place.
    """
    return {
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "name": "Test User",
        "role": "CLIENT",
    }


@pytest.fixture
def sample_admin_data() -> dict:
    """Sample admin user data for tests."""
    return {
        "email": "admin@example.com",
        "password": "AdminPassword123!",
        "name": "Admin User",
        "role": "ADMIN",
    }


@pytest_asyncio.fixture
async def test_org(db_session: AsyncSession):
    """
    Create a test organization.

    WHY: Most tests need an organization for multi-tenant data isolation.
    This fixture creates a reusable test organization.
    """
    from app.models.organization import Organization

    org = Organization(
        name="Test Organization",
        description="Organization for testing",
        is_active=True,
    )
    db_session.add(org)
    await db_session.flush()
    await db_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_org):
    """
    Create a test user.

    WHY: Most tests need a user for authentication and action attribution.
    This fixture creates a reusable test user attached to test_org.
    """
    from app.models.user import User, UserRole
    from app.core.auth import hash_password

    user = User(
        name="Test User",
        email="testuser@example.com",
        hashed_password=hash_password("SecurePassword123!"),
        role=UserRole.CLIENT,
        org_id=test_org.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession, test_org):
    """
    Create a test admin user.

    WHY: Some tests require an admin user for testing admin-only operations.
    """
    from app.models.user import User, UserRole
    from app.core.auth import hash_password

    admin = User(
        name="Test Admin",
        email="testadmin@example.com",
        hashed_password=hash_password("AdminPassword123!"),
        role=UserRole.ADMIN,
        org_id=test_org.id,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.flush()
    await db_session.refresh(admin)
    return admin


@pytest.fixture(autouse=True)
def reset_redis_client():
    """
    Reset the global Redis client before each test.

    WHY: The auth module uses a global _redis_client singleton that can
    persist between tests, causing test isolation issues. This fixture
    ensures each test starts with a fresh Redis connection.
    """
    # Reset the cached Redis client before test
    auth_module._redis_client = None
    yield
    # Reset again after test to clean up
    auth_module._redis_client = None


@pytest.fixture(autouse=True)
def disable_rate_limiting(monkeypatch):
    """
    Disable rate limiting for all tests.

    WHY: Rate limiting uses Redis which persists state between tests.
    Since integration tests run many login attempts rapidly, they would
    hit rate limits and fail with 429 errors. Disabling rate limiting
    in tests ensures test isolation and reliable test execution.

    Rate limiting is tested separately in unit tests with mocked Redis.

    Note: This mocks the get_rate_limiter function to return a mock
    rate limiter that always allows requests.
    """
    from unittest.mock import AsyncMock, MagicMock

    # Create a mock rate limiter that always allows
    mock_result = MagicMock()
    mock_result.allowed = True
    mock_result.remaining = 100
    mock_result.reset_after = 60
    mock_result.limit = 100

    # Create mock rate limiter instance
    mock_limiter = MagicMock()
    mock_limiter.check_rate_limit = AsyncMock(return_value=mock_result)
    mock_limiter._config = rate_limiter_module.RateLimitConfig()

    async def mock_get_rate_limiter():
        return mock_limiter

    # Replace the get_rate_limiter function (used by middleware)
    monkeypatch.setattr(
        rate_limiter_module,
        "get_rate_limiter",
        mock_get_rate_limiter,
    )

    # Also reset the global rate limiter instance
    rate_limiter_module._rate_limiter = None

    yield

    # Cleanup
    rate_limiter_module._rate_limiter = None


@pytest.fixture(autouse=True)
def use_mock_email_provider(monkeypatch):
    """
    Use mock email provider for all tests.

    WHY: Tests should not send real emails. The mock provider:
    - Tracks sent emails for verification in tests
    - Is always "configured" so it gets used
    - Doesn't require API keys

    Note: Tests that check MockEmailProvider.sent_emails should
    call MockEmailProvider.clear_sent_emails() at the start.
    """
    # Clear any previous sent emails
    email_module.MockEmailProvider.clear_sent_emails()

    # Mock the settings to ensure mock provider is always used
    # by removing the RESEND_API_KEY
    from app.core import config
    original_resend_key = getattr(config.settings, 'RESEND_API_KEY', None)

    # Set RESEND_API_KEY to None to force mock provider
    monkeypatch.setattr(config.settings, 'RESEND_API_KEY', None)

    yield

    # Restore original setting
    if original_resend_key:
        monkeypatch.setattr(config.settings, 'RESEND_API_KEY', original_resend_key)

    # Cleanup
    email_module.MockEmailProvider.clear_sent_emails()
