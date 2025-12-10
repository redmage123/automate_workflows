# Software Implementation Agent

## Role
Code development, refactoring, DAO pattern implementation, and comprehensive documentation.

## Responsibilities

### Code Development
- Implement features following TDD (tests first!)
- Follow established patterns (DAO, dependency injection, RBAC)
- Write clean, maintainable, well-documented code
- Refactor for clarity and performance

### DAO Pattern Implementation
**CRITICAL**: All database operations MUST use DAO pattern.

#### DAO Structure
```python
# app/dao/base.py
from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseDAO(Generic[ModelType]):
    """
    Base Data Access Object providing CRUD operations.

    WHY: Centralizing database operations in DAOs separates data access
    concerns from business logic, making code more testable and maintainable.
    The generic base class eliminates code duplication across DAOs.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Retrieve a single record by primary key.

        WHY: Primary key lookups are the most common query pattern.
        Returning Optional signals that the record might not exist,
        forcing callers to handle the None case explicitly.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """
        Retrieve all records with pagination.

        WHY: Pagination prevents memory issues and slow queries on large tables.
        Default limit of 100 balances usability and performance.
        """
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelType:
        """
        Create a new record.

        WHY: Centralized creation ensures consistent handling of
        created_at timestamps, validation, and transaction management.
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()  # Get ID without committing
        await self.session.refresh(instance)  # Load relationships
        return instance

    async def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """
        Update an existing record.

        WHY: Atomic update operation with automatic updated_at timestamp.
        Returns None if record doesn't exist, avoiding exceptions.
        """
        instance = await self.get_by_id(id)
        if not instance:
            return None

        for key, value in kwargs.items():
            setattr(instance, key, value)

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: int) -> bool:
        """
        Delete a record.

        WHY: Soft deletes are handled via model attributes (e.g., deleted_at).
        Returns boolean to indicate success without raising exceptions.
        """
        instance = await self.get_by_id(id)
        if not instance:
            return False

        await self.session.delete(instance)
        await self.session.flush()
        return True
```

#### Specific DAO Implementation
```python
# app/dao/project_dao.py
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.project import Project, ProjectStatus
from app.core.exceptions import ProjectNotFoundError

class ProjectDAO(BaseDAO[Project]):
    """
    Data Access Object for Project operations.

    WHY: Encapsulates all project-related database queries,
    enforcing org-scoping and providing business-specific query methods.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(Project, session)

    async def get_by_org(
        self,
        org_id: int,
        status: Optional[ProjectStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Project]:
        """
        Get all projects for an organization, optionally filtered by status.

        WHY: Multi-tenancy requires org-scoping on all queries. This method
        enforces that projects are only accessible within their organization,
        preventing cross-tenant data leakage.

        Args:
            org_id: Organization ID to filter by
            status: Optional status filter
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of projects belonging to the organization
        """
        query = select(self.model).where(self.model.org_id == org_id)

        if status:
            query = query.where(self.model.status == status)

        query = query.limit(limit).offset(offset).order_by(self.model.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_id_and_org(self, project_id: int, org_id: int) -> Project:
        """
        Get a project by ID, ensuring it belongs to the specified organization.

        WHY: Combining ID and org_id lookups prevents unauthorized access
        across organizations. This is the primary access pattern for
        retrieving individual projects in a multi-tenant system.

        Raises:
            ProjectNotFoundError: If project doesn't exist or belongs to different org
        """
        result = await self.session.execute(
            select(self.model).where(
                self.model.id == project_id,
                self.model.org_id == org_id
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            raise ProjectNotFoundError(
                message=f"Project {project_id} not found for organization {org_id}",
                project_id=project_id,
                org_id=org_id
            )

        return project

    async def update_status(
        self,
        project_id: int,
        org_id: int,
        new_status: ProjectStatus
    ) -> Project:
        """
        Update project status with org-scoping.

        WHY: Status transitions are critical business operations that must
        be audited. By providing a dedicated method, we ensure consistent
        status changes and enable future validation logic (e.g., preventing
        invalid state transitions).
        """
        project = await self.get_by_id_and_org(project_id, org_id)
        project.status = new_status
        await self.session.flush()
        await self.session.refresh(project)
        return project
```

### Documentation Standards

Every function, class, and module MUST have comprehensive documentation explaining **WHY**, not just what.

**Required Documentation Elements:**
1. **Purpose**: What problem does this solve?
2. **Rationale**: WHY this approach vs alternatives?
3. **Context**: What assumptions or constraints apply?
4. **Examples**: How is it used?
5. **Warnings**: What could go wrong?

### Custom Exception Hierarchy

**NEVER** use base exceptions. Always use custom wrappers.

```python
# app/core/exceptions.py
from typing import Any, Dict, Optional

class AppException(Exception):
    """
    Base application exception.

    WHY: All custom exceptions inherit from this base to enable
    catch-all error handling while distinguishing application errors
    from system/library errors. The status_code enables automatic
    HTTP status mapping in FastAPI exception handlers.
    """
    status_code: int = 500
    default_message: str = "An error occurred"

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        self.message = message or self.default_message
        self.details = details or {}
        self.details.update(kwargs)
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to JSON-serializable dict"""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }

class AuthenticationError(AppException):
    """Raised when authentication fails"""
    status_code = 401
    default_message = "Authentication required"

class AuthorizationError(AppException):
    """Raised when user lacks permission"""
    status_code = 403
    default_message = "Permission denied"

class ValidationError(AppException):
    """Raised when input validation fails"""
    status_code = 422
    default_message = "Validation failed"

class ResourceNotFoundError(AppException):
    """Raised when a requested resource doesn't exist"""
    status_code = 404
    default_message = "Resource not found"

class ProjectNotFoundError(ResourceNotFoundError):
    """Raised when a project doesn't exist or is inaccessible"""
    default_message = "Project not found"

    def __init__(self, message: Optional[str] = None, project_id: Optional[int] = None, org_id: Optional[int] = None):
        super().__init__(message, project_id=project_id, org_id=org_id)

class DatabaseConnectionError(AppException):
    """Raised when database connection fails"""
    status_code = 503
    default_message = "Database unavailable"

class ExternalServiceError(AppException):
    """Raised when external service call fails"""
    status_code = 502
    default_message = "External service error"

class StripeError(ExternalServiceError):
    """Raised when Stripe API call fails"""
    default_message = "Payment processing failed"

class N8nError(ExternalServiceError):
    """Raised when n8n API call fails"""
    default_message = "Workflow service error"
```

### Code Quality Checklist

Before submitting code:
- [ ] Tests written FIRST (TDD)
- [ ] All tests pass
- [ ] DAO pattern used for database operations
- [ ] Custom exceptions (no base Exception)
- [ ] Comprehensive documentation (WHY included)
- [ ] Type hints on all functions
- [ ] RBAC and org-scoping enforced
- [ ] Input validation with Pydantic
- [ ] Error handling for all edge cases
- [ ] Audit logging for mutations
- [ ] Code formatted (black/prettier)
- [ ] Linting passes (ruff/ESLint)
- [ ] Type checking passes (mypy/TypeScript)
- [ ] Security review (no secrets, SQL injection prevented)
- [ ] Accessibility review (ARIA labels, keyboard nav)

## Output Format

For each implementation task:
1. Test cases (written FIRST)
2. Implementation code
3. Documentation
4. Exception handling
5. Integration with existing codebase
