"""
Alembic environment configuration.

WHY: This file configures Alembic to work with our async SQLAlchemy setup
and automatically detect model changes for migration generation.
"""

from logging.config import fileConfig
import asyncio

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import app settings
from app.core.config import settings

# Import Base to enable autogenerate
# WHY: Alembic needs access to all models to detect schema changes
from app.models.base import Base

# Import all models so they're registered with Base
# WHY: This ensures all model tables are included in migrations
from app.models import user  # noqa: F401
# TODO: Import additional models as they are created
# from app.models import organization, project, proposal, etc.


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set sqlalchemy.url from settings
# WHY: Using environment variables prevents hardcoding database credentials
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# add your model's MetaData object here
# for 'autogenerate' support
# WHY: Base.metadata contains all table definitions from our models
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    WHY: Offline mode generates SQL scripts without connecting to the database,
    useful for manual review or running migrations on production databases
    where direct access may be restricted.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Run migrations with database connection.

    WHY: Separated into its own function to be called by both
    sync and async migration runners.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.

    WHY: Our application uses async SQLAlchemy, so migrations
    need to run in an async context to match the application's
    database usage pattern.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Get async database URL
    # WHY: asyncpg driver is required for async PostgreSQL connections
    url = settings.async_database_url

    # Create async engine
    # WHY: Configuration from alembic.ini merged with async URL
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # WHY: Migrations don't need connection pooling
    )

    async with connectable.connect() as connection:
        # WHY: run_sync allows running synchronous migration code
        # in an async context
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    WHY: Entry point for online migrations, delegates to async runner
    since our app uses async SQLAlchemy.
    """
    asyncio.run(run_async_migrations())


# Determine which mode to run in
# WHY: Alembic determines offline vs online mode based on context
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
