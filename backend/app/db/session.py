"""
Database session management.

WHY: Async database sessions are required for FastAPI's async/await pattern.
Using a context manager ensures proper connection cleanup and transaction management.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings


# Create async engine
# WHY: pool_pre_ping ensures stale connections are recycled, preventing
# "server has gone away" errors in long-running applications.
# pool_size and max_overflow control connection pooling for optimal performance.
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create session factory
# WHY: async_sessionmaker provides async-compatible session creation.
# expire_on_commit=False prevents lazy-loading issues after commit.
# autocommit=False and autoflush=False give explicit control over transactions.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.

    WHY: FastAPI dependency injection ensures each request gets its own
    database session, with automatic cleanup via context manager.
    The try/except/finally ensures proper transaction handling even on errors.

    Yields:
        AsyncSession: Database session for the request
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
