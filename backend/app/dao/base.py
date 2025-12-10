"""
Base Data Access Object (DAO) class.

WHY: The DAO pattern separates database operations from business logic,
making the codebase more testable, maintainable, and allowing easier
database technology changes in the future.
"""

from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

# Type variable for model class
ModelType = TypeVar("ModelType", bound=Base)


class BaseDAO(Generic[ModelType]):
    """
    Base Data Access Object providing CRUD operations for all models.

    WHY: Centralizing database operations in DAOs separates data access
    concerns from business logic, making code more testable and maintainable.
    Using generics allows type-safe reuse across different models.

    Type Parameters:
        ModelType: The SQLAlchemy model class this DAO manages
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        Initialize DAO with model class and database session.

        WHY: Dependency injection of the session allows easier testing
        with mock sessions and ensures proper session lifecycle management.

        Args:
            model: The SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def create(self, **kwargs: Any) -> ModelType:
        """
        Create a new record.

        WHY: Centralizing creation logic ensures consistent handling of
        database constraints, validation, and error handling.

        Args:
            **kwargs: Field values for the new record

        Returns:
            The created model instance with database-generated fields populated

        Raises:
            IntegrityError: If unique constraints are violated
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()  # Flush to get auto-generated fields
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Retrieve a single record by primary key.

        WHY: Primary key lookups are the most common query pattern.
        Returning Optional signals that the record might not exist,
        allowing callers to handle the absence gracefully.

        Args:
            id: Primary key value

        Returns:
            The model instance if found, None otherwise
        """
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100, **filters: Any) -> List[ModelType]:
        """
        Retrieve multiple records with optional pagination and filtering.

        WHY: Pagination prevents memory issues with large datasets.
        Keyword filters provide flexible querying while maintaining type safety.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            **filters: Field name to value filters (e.g., org_id=1)

        Returns:
            List of model instances matching the filters
        """
        query = select(self.model)

        # Apply filters
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)

        # Apply pagination
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_field(self, field_name: str, value: Any) -> Optional[ModelType]:
        """
        Retrieve a single record by any field.

        WHY: Common pattern for lookups by unique fields (email, username, etc.)
        Returns single result or None for consistent error handling.

        Args:
            field_name: Name of the field to search
            value: Value to match

        Returns:
            The model instance if found, None otherwise

        Raises:
            AttributeError: If field_name doesn't exist on the model
        """
        if not hasattr(self.model, field_name):
            raise AttributeError(f"{self.model.__name__} has no field '{field_name}'")

        result = await self.session.execute(
            select(self.model).where(getattr(self.model, field_name) == value)
        )
        return result.scalar_one_or_none()

    async def update(self, id: int, **kwargs: Any) -> Optional[ModelType]:
        """
        Update an existing record.

        WHY: Centralized update logic ensures consistent handling of
        updated_at timestamps and validation across all models.

        Args:
            id: Primary key of the record to update
            **kwargs: Fields to update

        Returns:
            Updated model instance if found, None otherwise
        """
        result = await self.session.execute(
            update(self.model).where(self.model.id == id).values(**kwargs).returning(self.model)
        )
        instance = result.scalar_one_or_none()
        if instance:
            await self.session.refresh(instance)
        return instance

    async def delete(self, id: int) -> bool:
        """
        Delete a record by primary key.

        WHY: Soft deletes should be preferred in production (add is_deleted field),
        but hard deletes are useful for testing and data cleanup.

        Args:
            id: Primary key of the record to delete

        Returns:
            True if a record was deleted, False if not found
        """
        result = await self.session.execute(delete(self.model).where(self.model.id == id))
        return result.rowcount > 0

    async def count(self, **filters: Any) -> int:
        """
        Count records matching filters.

        WHY: Useful for pagination metadata and analytics without
        loading full records into memory.

        Args:
            **filters: Field name to value filters

        Returns:
            Number of records matching the filters
        """
        query = select(self.model)

        # Apply filters
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)

        result = await self.session.execute(query)
        return len(list(result.scalars().all()))

    async def exists(self, **filters: Any) -> bool:
        """
        Check if any records matching filters exist.

        WHY: More efficient than counting when you only need to know
        if records exist (stops at first match).

        Args:
            **filters: Field name to value filters

        Returns:
            True if at least one matching record exists
        """
        query = select(self.model)

        # Apply filters
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)

        query = query.limit(1)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_by_org(self, org_id: int, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Retrieve records for a specific organization (multi-tenant support).

        WHY: Organization-scoped queries are critical for multi-tenancy data isolation.
        This method enforces org-scoping at the DAO level (defense in depth).

        Args:
            org_id: Organization ID to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of model instances for the organization

        Raises:
            AttributeError: If the model doesn't have an org_id field
        """
        if not hasattr(self.model, "org_id"):
            raise AttributeError(
                f"{self.model.__name__} is not a multi-tenant model (no org_id field)"
            )

        return await self.get_all(skip=skip, limit=limit, org_id=org_id)

    async def get_by_id_and_org(self, id: int, org_id: int) -> Optional[ModelType]:
        """
        Retrieve a record by ID, ensuring it belongs to the specified organization.

        WHY: Critical for preventing cross-organization data access (A01: Broken Access Control).
        Always use this method instead of get_by_id for CLIENT role queries.

        Args:
            id: Primary key value
            org_id: Organization ID that must own the record

        Returns:
            The model instance if found and belongs to org, None otherwise

        Raises:
            AttributeError: If the model doesn't have an org_id field
        """
        if not hasattr(self.model, "org_id"):
            raise AttributeError(
                f"{self.model.__name__} is not a multi-tenant model (no org_id field)"
            )

        result = await self.session.execute(
            select(self.model).where(
                self.model.id == id,
                self.model.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()
