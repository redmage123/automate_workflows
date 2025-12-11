"""
Project Data Access Object (DAO).

WHAT: Database operations for the Project model.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides a consistent API for project operations
3. Enforces org-scoping for multi-tenancy
4. Makes testing easier with mockable interfaces

HOW: Extends BaseDAO with project-specific queries:
- Status filtering
- Priority filtering
- Overdue project queries
- Active project counts
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.project import Project, ProjectStatus, ProjectPriority


class ProjectDAO(BaseDAO[Project]):
    """
    Data Access Object for Project model.

    WHAT: Provides CRUD and query operations for projects.

    WHY: Centralizes all project database operations:
    - Enforces org_id scoping for security
    - Provides specialized project queries
    - Enables consistent error handling

    HOW: Extends BaseDAO with project-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize ProjectDAO.

        Args:
            session: Async database session
        """
        super().__init__(Project, session)

    async def get_by_status(
        self,
        org_id: int,
        status: ProjectStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Project]:
        """
        Get projects by status for an organization.

        WHAT: Filter projects by their status.

        WHY: Common use case for dashboards and lists:
        - "Show me all in-progress projects"
        - "What projects are on hold?"

        Args:
            org_id: Organization ID
            status: Project status to filter by
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of projects matching the status
        """
        result = await self.session.execute(
            select(Project)
            .where(
                Project.org_id == org_id,
                Project.status == status,
            )
            .order_by(Project.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_priority(
        self,
        org_id: int,
        priority: ProjectPriority,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Project]:
        """
        Get projects by priority for an organization.

        WHAT: Filter projects by their priority level.

        WHY: Enables priority-based project views:
        - "Show me all urgent projects"
        - Resource allocation decisions

        Args:
            org_id: Organization ID
            priority: Project priority to filter by
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of projects matching the priority
        """
        result = await self.session.execute(
            select(Project)
            .where(
                Project.org_id == org_id,
                Project.priority == priority,
            )
            .order_by(Project.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_projects(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Project]:
        """
        Get all active (not completed/cancelled) projects.

        WHAT: Filter out completed and cancelled projects.

        WHY: Common dashboard view - show work in progress.

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of active projects
        """
        result = await self.session.execute(
            select(Project)
            .where(
                Project.org_id == org_id,
                Project.status.notin_([ProjectStatus.COMPLETED, ProjectStatus.CANCELLED]),
            )
            .order_by(Project.priority.desc(), Project.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_overdue_projects(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Project]:
        """
        Get projects that are past their due date.

        WHAT: Find projects where due_date < now and not completed.

        WHY: Critical for project management - identify delayed work.

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of overdue projects
        """
        now = datetime.utcnow()
        result = await self.session.execute(
            select(Project)
            .where(
                Project.org_id == org_id,
                Project.due_date < now,
                Project.status.notin_([ProjectStatus.COMPLETED, ProjectStatus.CANCELLED]),
            )
            .order_by(Project.due_date.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_projects_starting_soon(
        self,
        org_id: int,
        days: int = 7,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Project]:
        """
        Get projects with start_date in the next N days.

        WHAT: Find upcoming projects.

        WHY: Resource planning - know what's coming up.

        Args:
            org_id: Organization ID
            days: Number of days to look ahead
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of projects starting soon
        """
        now = datetime.utcnow()
        future = datetime(
            now.year, now.month, now.day,
        )
        from datetime import timedelta
        future = future + timedelta(days=days)

        result = await self.session.execute(
            select(Project)
            .where(
                Project.org_id == org_id,
                Project.start_date >= now,
                Project.start_date <= future,
                Project.status == ProjectStatus.APPROVED,
            )
            .order_by(Project.start_date.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_with_proposals(
        self,
        project_id: int,
        org_id: int,
    ) -> Optional[Project]:
        """
        Get a project with its proposals eagerly loaded.

        WHAT: Fetch project with related proposals in one query.

        WHY: Avoid N+1 queries when accessing proposals.

        Args:
            project_id: Project ID
            org_id: Organization ID for security

        Returns:
            Project with proposals loaded, or None if not found
        """
        result = await self.session.execute(
            select(Project)
            .options(selectinload(Project.proposals))
            .where(
                Project.id == project_id,
                Project.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        project_id: int,
        org_id: int,
        new_status: ProjectStatus,
    ) -> Optional[Project]:
        """
        Update a project's status.

        WHAT: Change project status with validation.

        WHY: Status changes need special handling:
        - Set completed_at when completing
        - Clear completed_at when reopening
        - Validate status transitions (future)

        Args:
            project_id: Project ID
            org_id: Organization ID for security
            new_status: New status to set

        Returns:
            Updated project or None if not found
        """
        project = await self.get_by_id_and_org(project_id, org_id)
        if not project:
            return None

        project.status = new_status

        # Handle completion timestamp
        if new_status == ProjectStatus.COMPLETED:
            project.completed_at = datetime.utcnow()
        elif project.completed_at and new_status != ProjectStatus.COMPLETED:
            # Reopening a completed project
            project.completed_at = None

        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def count_by_status(self, org_id: int) -> dict:
        """
        Get count of projects by status for an organization.

        WHAT: Aggregate project counts by status.

        WHY: Dashboard statistics - "How many projects in each state?"

        Args:
            org_id: Organization ID

        Returns:
            Dict mapping status to count
        """
        result = await self.session.execute(
            select(Project.status, func.count(Project.id))
            .where(Project.org_id == org_id)
            .group_by(Project.status)
        )

        return {row[0].value: row[1] for row in result.all()}

    async def count_active(self, org_id: int) -> int:
        """
        Count active projects for an organization.

        WHAT: Count projects not completed/cancelled.

        WHY: Quick metric for dashboard widgets.

        Args:
            org_id: Organization ID

        Returns:
            Number of active projects
        """
        result = await self.session.execute(
            select(func.count(Project.id))
            .where(
                Project.org_id == org_id,
                Project.status.notin_([ProjectStatus.COMPLETED, ProjectStatus.CANCELLED]),
            )
        )
        return result.scalar_one()

    async def search_projects(
        self,
        org_id: int,
        query: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Project]:
        """
        Search projects by name or description.

        WHAT: Full-text search on project name and description.

        WHY: Enable users to find projects quickly.

        Args:
            org_id: Organization ID
            query: Search query string
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of matching projects
        """
        search_pattern = f"%{query}%"
        result = await self.session.execute(
            select(Project)
            .where(
                Project.org_id == org_id,
                or_(
                    Project.name.ilike(search_pattern),
                    Project.description.ilike(search_pattern),
                ),
            )
            .order_by(Project.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_hours(
        self,
        project_id: int,
        org_id: int,
        hours: float,
    ) -> Optional[Project]:
        """
        Add hours to a project's actual_hours.

        WHAT: Increment the actual_hours field.

        WHY: Time tracking - log work performed on project.

        Args:
            project_id: Project ID
            org_id: Organization ID for security
            hours: Hours to add

        Returns:
            Updated project or None if not found
        """
        project = await self.get_by_id_and_org(project_id, org_id)
        if not project:
            return None

        current_hours = project.actual_hours or 0
        project.actual_hours = current_hours + hours

        await self.session.flush()
        await self.session.refresh(project)
        return project
