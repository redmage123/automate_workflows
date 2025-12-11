"""
Workflow Template Data Access Object (DAO).

WHAT: Database operations for the WorkflowTemplate model.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for template operations
3. Handles visibility rules (public vs org-specific)
4. Enables template library management

HOW: Extends BaseDAO with template-specific queries:
- Public template listing
- Category-based filtering
- Org-specific template management
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.workflow import WorkflowTemplate


class WorkflowTemplateDAO(BaseDAO[WorkflowTemplate]):
    """
    Data Access Object for WorkflowTemplate model.

    WHAT: Provides CRUD and query operations for workflow templates.

    WHY: Centralizes all template database operations:
    - Handles public/private visibility logic
    - Enables category-based organization
    - Supports template library features

    HOW: Extends BaseDAO with template-specific methods.
    Templates can be public (visible to all) or org-specific.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize WorkflowTemplateDAO.

        Args:
            session: Async database session
        """
        super().__init__(WorkflowTemplate, session)

    async def create_template(
        self,
        name: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        n8n_template_id: Optional[str] = None,
        default_parameters: Optional[dict] = None,
        is_public: bool = True,
        created_by_org_id: Optional[int] = None,
    ) -> WorkflowTemplate:
        """
        Create a new workflow template.

        WHAT: Creates a reusable workflow template.

        WHY: Templates provide starting points for workflow creation:
        - Pre-built automations for common tasks
        - Consistent configuration across orgs
        - Reduced setup time for users

        Args:
            name: Template name
            description: Template description
            category: Template category (e.g., "notifications", "data-sync")
            n8n_template_id: ID of template workflow in n8n (optional)
            default_parameters: Default parameter values (JSON)
            is_public: Whether template is visible to all orgs
            created_by_org_id: Org that created this template (for private templates)

        Returns:
            Created WorkflowTemplate instance
        """
        return await self.create(
            name=name,
            description=description,
            category=category,
            n8n_template_id=n8n_template_id,
            default_parameters=default_parameters,
            is_public=is_public,
            created_by_org_id=created_by_org_id,
        )

    async def get_public_templates(
        self,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowTemplate]:
        """
        Get all public workflow templates.

        WHAT: Retrieves templates visible to all organizations.

        WHY: Public templates form the core template library
        available to all users.

        Args:
            category: Optional category filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of public templates
        """
        query = (
            select(WorkflowTemplate)
            .where(WorkflowTemplate.is_public == True)
        )

        if category:
            query = query.where(WorkflowTemplate.category == category)

        query = query.order_by(WorkflowTemplate.category, WorkflowTemplate.name)
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_available_templates(
        self,
        org_id: int,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowTemplate]:
        """
        Get all templates available to an organization.

        WHAT: Retrieves public templates plus org's private templates.

        WHY: Users see both global templates and their custom templates.

        Args:
            org_id: Organization ID
            category: Optional category filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of available templates
        """
        query = (
            select(WorkflowTemplate)
            .where(
                or_(
                    WorkflowTemplate.is_public == True,
                    WorkflowTemplate.created_by_org_id == org_id,
                )
            )
        )

        if category:
            query = query.where(WorkflowTemplate.category == category)

        query = query.order_by(WorkflowTemplate.category, WorkflowTemplate.name)
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_org_templates(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowTemplate]:
        """
        Get templates created by a specific organization.

        WHAT: Retrieves only templates owned by the org.

        WHY: For managing org's custom templates.

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of org's templates
        """
        result = await self.session.execute(
            select(WorkflowTemplate)
            .where(WorkflowTemplate.created_by_org_id == org_id)
            .order_by(WorkflowTemplate.name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_category(
        self,
        category: str,
        include_private_for_org: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowTemplate]:
        """
        Get templates by category.

        WHAT: Filters templates by category.

        WHY: Enables category-based browsing of template library.

        Args:
            category: Category to filter by
            include_private_for_org: Org ID to include private templates for
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of templates in category
        """
        if include_private_for_org:
            query = (
                select(WorkflowTemplate)
                .where(
                    WorkflowTemplate.category == category,
                    or_(
                        WorkflowTemplate.is_public == True,
                        WorkflowTemplate.created_by_org_id == include_private_for_org,
                    ),
                )
            )
        else:
            query = (
                select(WorkflowTemplate)
                .where(
                    WorkflowTemplate.category == category,
                    WorkflowTemplate.is_public == True,
                )
            )

        query = query.order_by(WorkflowTemplate.name)
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_categories(
        self,
        include_private_for_org: Optional[int] = None,
    ) -> List[str]:
        """
        Get list of unique template categories.

        WHAT: Returns distinct category values.

        WHY: For populating category filter dropdowns.

        Args:
            include_private_for_org: Org ID to include private templates

        Returns:
            List of unique category names
        """
        if include_private_for_org:
            query = (
                select(WorkflowTemplate.category)
                .where(
                    WorkflowTemplate.category.isnot(None),
                    or_(
                        WorkflowTemplate.is_public == True,
                        WorkflowTemplate.created_by_org_id == include_private_for_org,
                    ),
                )
                .distinct()
            )
        else:
            query = (
                select(WorkflowTemplate.category)
                .where(
                    WorkflowTemplate.category.isnot(None),
                    WorkflowTemplate.is_public == True,
                )
                .distinct()
            )

        result = await self.session.execute(query)
        return [row[0] for row in result.all() if row[0]]

    async def update_template(
        self,
        template_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        n8n_template_id: Optional[str] = None,
        default_parameters: Optional[dict] = None,
        is_public: Optional[bool] = None,
    ) -> Optional[WorkflowTemplate]:
        """
        Update a workflow template.

        WHAT: Updates template configuration.

        WHY: Enables template maintenance and updates.

        Args:
            template_id: Template ID to update
            name: New name (if changing)
            description: New description (if changing)
            category: New category (if changing)
            n8n_template_id: New n8n template ID (if changing)
            default_parameters: New default parameters (if changing)
            is_public: New visibility (if changing)

        Returns:
            Updated template or None if not found
        """
        template = await self.get_by_id(template_id)
        if not template:
            return None

        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if category is not None:
            template.category = category
        if n8n_template_id is not None:
            template.n8n_template_id = n8n_template_id
        if default_parameters is not None:
            template.default_parameters = default_parameters
        if is_public is not None:
            template.is_public = is_public

        template.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(template)
        return template

    async def search_templates(
        self,
        query: str,
        include_private_for_org: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowTemplate]:
        """
        Search templates by name or description.

        WHAT: Full-text search on templates.

        WHY: Enable users to find templates quickly.

        Args:
            query: Search query string
            include_private_for_org: Org ID to include private templates
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of matching templates
        """
        search_pattern = f"%{query}%"

        if include_private_for_org:
            base_query = (
                select(WorkflowTemplate)
                .where(
                    or_(
                        WorkflowTemplate.is_public == True,
                        WorkflowTemplate.created_by_org_id == include_private_for_org,
                    ),
                    or_(
                        WorkflowTemplate.name.ilike(search_pattern),
                        WorkflowTemplate.description.ilike(search_pattern),
                    ),
                )
            )
        else:
            base_query = (
                select(WorkflowTemplate)
                .where(
                    WorkflowTemplate.is_public == True,
                    or_(
                        WorkflowTemplate.name.ilike(search_pattern),
                        WorkflowTemplate.description.ilike(search_pattern),
                    ),
                )
            )

        base_query = base_query.order_by(WorkflowTemplate.name)
        base_query = base_query.offset(skip).limit(limit)

        result = await self.session.execute(base_query)
        return list(result.scalars().all())

    async def can_org_modify(
        self,
        template_id: int,
        org_id: int,
    ) -> bool:
        """
        Check if an organization can modify a template.

        WHAT: Validates modification permissions.

        WHY: Only the creating org can modify a template.
        Public templates created by system have no org owner.

        Args:
            template_id: Template ID
            org_id: Organization ID attempting modification

        Returns:
            True if org can modify, False otherwise
        """
        template = await self.get_by_id(template_id)
        if not template:
            return False

        # Template must be owned by the org to modify
        return template.created_by_org_id == org_id
