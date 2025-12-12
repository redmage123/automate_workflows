"""
Announcement Data Access Object (DAO).

WHAT: Database operations for announcement models.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for announcement operations
3. Enforces org-scoping for multi-tenancy
4. Handles complex queries for targeting and status

HOW: Extends BaseDAO with announcement-specific queries:
- CRUD operations
- Status management
- Read/acknowledgment tracking
- Targeting queries
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.announcement import (
    Announcement,
    AnnouncementStatus,
    AnnouncementType,
    AnnouncementPriority,
    AnnouncementRead,
)


class AnnouncementDAO(BaseDAO[Announcement]):
    """
    Data Access Object for Announcement model.

    WHAT: Provides operations for announcements.

    WHY: Centralizes announcement management.

    HOW: Extends BaseDAO with announcement-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize AnnouncementDAO."""
        super().__init__(Announcement, session)

    async def create_announcement(
        self,
        org_id: int,
        created_by: int,
        title: str,
        content: str,
        type: str = AnnouncementType.INFO.value,
        priority: str = AnnouncementPriority.NORMAL.value,
        content_html: Optional[str] = None,
        publish_at: Optional[datetime] = None,
        expire_at: Optional[datetime] = None,
        target_all: bool = True,
        target_roles: Optional[List[str]] = None,
        target_user_ids: Optional[List[int]] = None,
        is_dismissible: bool = True,
        require_acknowledgment: bool = False,
        show_banner: bool = False,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Announcement:
        """
        Create a new announcement.

        WHAT: Creates announcement in draft status.

        WHY: Announcements start as drafts for review.

        Args:
            org_id: Organization ID
            created_by: Creator user ID
            title: Announcement title
            content: Announcement content
            type: Announcement type
            priority: Priority level
            content_html: Optional HTML content
            publish_at: Optional scheduled publish time
            expire_at: Optional expiration time
            target_all: Target all users
            target_roles: Target specific roles
            target_user_ids: Target specific users
            is_dismissible: Can be dismissed
            require_acknowledgment: Requires acknowledgment
            show_banner: Show as banner
            action_url: Optional CTA URL
            action_text: Optional CTA text
            metadata: Optional metadata

        Returns:
            Created Announcement
        """
        status = AnnouncementStatus.DRAFT.value
        if publish_at and publish_at > datetime.utcnow():
            status = AnnouncementStatus.SCHEDULED.value

        return await self.create(
            org_id=org_id,
            created_by=created_by,
            title=title,
            content=content,
            content_html=content_html,
            type=type,
            priority=priority,
            status=status,
            publish_at=publish_at,
            expire_at=expire_at,
            target_all=target_all,
            target_roles=target_roles,
            target_user_ids=target_user_ids,
            is_dismissible=is_dismissible,
            require_acknowledgment=require_acknowledgment,
            show_banner=show_banner,
            action_url=action_url,
            action_text=action_text,
            metadata=metadata,
        )

    async def get_active_announcements(
        self,
        org_id: int,
        user_id: int,
        user_role: str,
        include_read: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Announcement]:
        """
        Get active announcements for a user.

        WHAT: Retrieves announcements matching user's targeting.

        WHY: Show relevant announcements to users.

        Args:
            org_id: Organization ID
            user_id: User ID
            user_role: User's role
            include_read: Include already read announcements
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of announcements
        """
        now = datetime.utcnow()

        # Base conditions
        conditions = [
            Announcement.org_id == org_id,
            Announcement.status == AnnouncementStatus.ACTIVE.value,
            or_(
                Announcement.publish_at.is_(None),
                Announcement.publish_at <= now,
            ),
            or_(
                Announcement.expire_at.is_(None),
                Announcement.expire_at > now,
            ),
        ]

        # Targeting conditions
        targeting = or_(
            Announcement.target_all == True,
            Announcement.target_user_ids.contains([user_id]),
            Announcement.target_roles.contains([user_role]),
        )
        conditions.append(targeting)

        query = (
            select(Announcement)
            .where(*conditions)
            .order_by(
                # Critical first, then by priority, then by date
                Announcement.priority.desc(),
                Announcement.publish_at.desc().nullslast(),
            )
        )

        if not include_read:
            # Exclude already read announcements
            read_subq = (
                select(AnnouncementRead.announcement_id)
                .where(
                    AnnouncementRead.user_id == user_id,
                    AnnouncementRead.is_dismissed == True,
                )
            )
            query = query.where(Announcement.id.notin_(read_subq))

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_org_announcements(
        self,
        org_id: int,
        status: Optional[str] = None,
        type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Announcement]:
        """
        Get all announcements for an organization.

        WHAT: Lists announcements with optional filters.

        WHY: Admin management view.

        Args:
            org_id: Organization ID
            status: Optional status filter
            type: Optional type filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of announcements
        """
        query = (
            select(Announcement)
            .where(Announcement.org_id == org_id)
            .options(selectinload(Announcement.creator))
        )

        if status:
            query = query.where(Announcement.status == status)

        if type:
            query = query.where(Announcement.type == type)

        query = query.order_by(Announcement.created_at.desc())

        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def publish_announcement(
        self,
        announcement_id: int,
        org_id: int,
    ) -> Optional[Announcement]:
        """
        Publish an announcement.

        WHAT: Changes status to ACTIVE.

        WHY: Make announcement visible.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID

        Returns:
            Updated announcement
        """
        announcement = await self.get_by_id_and_org(announcement_id, org_id)
        if not announcement:
            return None

        announcement.status = AnnouncementStatus.ACTIVE.value
        announcement.published_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(announcement)
        return announcement

    async def archive_announcement(
        self,
        announcement_id: int,
        org_id: int,
    ) -> Optional[Announcement]:
        """
        Archive an announcement.

        WHAT: Changes status to ARCHIVED.

        WHY: Hide old announcements.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID

        Returns:
            Updated announcement
        """
        announcement = await self.get_by_id_and_org(announcement_id, org_id)
        if not announcement:
            return None

        announcement.status = AnnouncementStatus.ARCHIVED.value

        await self.session.flush()
        await self.session.refresh(announcement)
        return announcement

    async def update_scheduled_announcements(self) -> int:
        """
        Activate scheduled announcements that are due.

        WHAT: Background job to activate scheduled announcements.

        WHY: Automatic publishing at scheduled time.

        Returns:
            Number of announcements activated
        """
        now = datetime.utcnow()

        result = await self.session.execute(
            update(Announcement)
            .where(
                Announcement.status == AnnouncementStatus.SCHEDULED.value,
                Announcement.publish_at <= now,
            )
            .values(
                status=AnnouncementStatus.ACTIVE.value,
                published_at=now,
            )
        )
        await self.session.flush()
        return result.rowcount

    async def expire_old_announcements(self) -> int:
        """
        Expire announcements past their expire_at time.

        WHAT: Background job to expire old announcements.

        WHY: Automatic cleanup.

        Returns:
            Number of announcements expired
        """
        now = datetime.utcnow()

        result = await self.session.execute(
            update(Announcement)
            .where(
                Announcement.status == AnnouncementStatus.ACTIVE.value,
                Announcement.expire_at.isnot(None),
                Announcement.expire_at < now,
            )
            .values(status=AnnouncementStatus.EXPIRED.value)
        )
        await self.session.flush()
        return result.rowcount

    async def get_banner_announcements(
        self,
        org_id: int,
        user_id: int,
        user_role: str,
    ) -> List[Announcement]:
        """
        Get announcements to show as banners.

        WHAT: Retrieves banner-eligible announcements.

        WHY: Show important banners in UI.

        Args:
            org_id: Organization ID
            user_id: User ID
            user_role: User's role

        Returns:
            List of banner announcements
        """
        now = datetime.utcnow()

        conditions = [
            Announcement.org_id == org_id,
            Announcement.status == AnnouncementStatus.ACTIVE.value,
            Announcement.show_banner == True,
            or_(
                Announcement.publish_at.is_(None),
                Announcement.publish_at <= now,
            ),
            or_(
                Announcement.expire_at.is_(None),
                Announcement.expire_at > now,
            ),
            or_(
                Announcement.target_all == True,
                Announcement.target_user_ids.contains([user_id]),
                Announcement.target_roles.contains([user_role]),
            ),
        ]

        # Exclude dismissed banners
        read_subq = (
            select(AnnouncementRead.announcement_id)
            .where(
                AnnouncementRead.user_id == user_id,
                AnnouncementRead.is_dismissed == True,
            )
        )

        query = (
            select(Announcement)
            .where(*conditions)
            .where(Announcement.id.notin_(read_subq))
            .order_by(Announcement.priority.desc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())


class AnnouncementReadDAO(BaseDAO[AnnouncementRead]):
    """
    Data Access Object for AnnouncementRead.

    WHAT: Tracks announcement read/acknowledgment status.

    WHY: Know who has seen announcements.
    """

    def __init__(self, session: AsyncSession):
        """Initialize AnnouncementReadDAO."""
        super().__init__(AnnouncementRead, session)

    async def mark_read(
        self,
        announcement_id: int,
        user_id: int,
    ) -> AnnouncementRead:
        """
        Mark announcement as read.

        WHAT: Creates or updates read status.

        WHY: Track who has seen announcement.

        Args:
            announcement_id: Announcement ID
            user_id: User ID

        Returns:
            Read record
        """
        result = await self.session.execute(
            select(AnnouncementRead).where(
                AnnouncementRead.announcement_id == announcement_id,
                AnnouncementRead.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        return await self.create(
            announcement_id=announcement_id,
            user_id=user_id,
            is_read=True,
        )

    async def acknowledge(
        self,
        announcement_id: int,
        user_id: int,
    ) -> AnnouncementRead:
        """
        Acknowledge an announcement.

        WHAT: Marks announcement as acknowledged.

        WHY: Required acknowledgment tracking.

        Args:
            announcement_id: Announcement ID
            user_id: User ID

        Returns:
            Updated read record
        """
        result = await self.session.execute(
            select(AnnouncementRead).where(
                AnnouncementRead.announcement_id == announcement_id,
                AnnouncementRead.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.is_acknowledged = True
            existing.acknowledged_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        return await self.create(
            announcement_id=announcement_id,
            user_id=user_id,
            is_read=True,
            is_acknowledged=True,
            acknowledged_at=datetime.utcnow(),
        )

    async def dismiss(
        self,
        announcement_id: int,
        user_id: int,
    ) -> AnnouncementRead:
        """
        Dismiss an announcement.

        WHAT: Marks announcement as dismissed.

        WHY: Hide from user's view.

        Args:
            announcement_id: Announcement ID
            user_id: User ID

        Returns:
            Updated read record
        """
        result = await self.session.execute(
            select(AnnouncementRead).where(
                AnnouncementRead.announcement_id == announcement_id,
                AnnouncementRead.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.is_dismissed = True
            existing.dismissed_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        return await self.create(
            announcement_id=announcement_id,
            user_id=user_id,
            is_read=True,
            is_dismissed=True,
            dismissed_at=datetime.utcnow(),
        )

    async def get_read_stats(
        self,
        announcement_id: int,
    ) -> Dict[str, int]:
        """
        Get read/acknowledge/dismiss statistics.

        WHAT: Aggregated engagement stats.

        WHY: Analytics for announcements.

        Args:
            announcement_id: Announcement ID

        Returns:
            Stats dict
        """
        result = await self.session.execute(
            select(
                func.count(AnnouncementRead.id).label("total_reads"),
                func.count(AnnouncementRead.id).filter(
                    AnnouncementRead.is_acknowledged == True
                ).label("acknowledged"),
                func.count(AnnouncementRead.id).filter(
                    AnnouncementRead.is_dismissed == True
                ).label("dismissed"),
            ).where(AnnouncementRead.announcement_id == announcement_id)
        )
        row = result.one()
        return {
            "total_reads": row.total_reads,
            "acknowledged": row.acknowledged,
            "dismissed": row.dismissed,
        }

    async def has_read(
        self,
        announcement_id: int,
        user_id: int,
    ) -> bool:
        """
        Check if user has read announcement.

        WHAT: Validates read status.

        WHY: UI state.

        Args:
            announcement_id: Announcement ID
            user_id: User ID

        Returns:
            True if read
        """
        result = await self.session.execute(
            select(AnnouncementRead).where(
                AnnouncementRead.announcement_id == announcement_id,
                AnnouncementRead.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None
