"""
Announcement Service.

WHAT: Business logic for announcement operations.

WHY: The service layer:
1. Encapsulates announcement business logic
2. Coordinates between DAOs
3. Enforces business rules
4. Handles scheduling and targeting

HOW: Orchestrates AnnouncementDAO and AnnouncementReadDAO
while validating operations against business rules.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.announcement import AnnouncementDAO, AnnouncementReadDAO
from app.dao.user import UserDAO
from app.models.announcement import (
    Announcement,
    AnnouncementStatus,
    AnnouncementType,
    AnnouncementPriority,
    AnnouncementRead,
)
from app.core.exceptions import (
    AnnouncementNotFoundError,
    AnnouncementError,
    AuthorizationError,
    ValidationError,
)


class AnnouncementService:
    """
    Service for announcement operations.

    WHAT: Provides business logic for announcements.

    WHY: Announcements enable:
    - Broadcasting important updates to all users
    - Scheduled communication
    - Targeted messaging (by role, user group)
    - Acknowledgment tracking

    HOW: Coordinates DAOs and enforces business rules.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize AnnouncementService.

        Args:
            session: Async database session
        """
        self.session = session
        self.announcement_dao = AnnouncementDAO(session)
        self.read_dao = AnnouncementReadDAO(session)
        self.user_dao = UserDAO(session)

    # =========================================================================
    # Announcement Management
    # =========================================================================

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

        WHAT: Creates announcement (starts as draft or scheduled).

        WHY: Broadcasts messages to users.

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

        Raises:
            ValidationError: If validation fails
        """
        # Validate dates
        if publish_at and expire_at and publish_at >= expire_at:
            raise ValidationError(
                message="Publish time must be before expiration time",
            )

        # Validate targeting
        if not target_all and not target_roles and not target_user_ids:
            raise ValidationError(
                message="Must target all users or specify roles/users",
            )

        # Validate target user IDs exist
        if target_user_ids:
            for uid in target_user_ids:
                user = await self.user_dao.get_by_id_and_org(uid, org_id)
                if not user:
                    raise ValidationError(
                        message=f"User {uid} not found in organization",
                        details={"user_id": uid},
                    )

        return await self.announcement_dao.create_announcement(
            org_id=org_id,
            created_by=created_by,
            title=title,
            content=content,
            type=type,
            priority=priority,
            content_html=content_html,
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

    async def get_announcement(
        self,
        announcement_id: int,
        org_id: int,
    ) -> Announcement:
        """
        Get an announcement by ID.

        WHAT: Retrieves announcement details.

        WHY: View announcement information.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID

        Returns:
            Announcement

        Raises:
            AnnouncementNotFoundError: If not found
        """
        announcement = await self.announcement_dao.get_by_id_and_org(
            announcement_id, org_id
        )
        if not announcement:
            raise AnnouncementNotFoundError(
                message="Announcement not found",
                announcement_id=announcement_id,
            )
        return announcement

    async def update_announcement(
        self,
        announcement_id: int,
        org_id: int,
        **kwargs,
    ) -> Announcement:
        """
        Update an announcement.

        WHAT: Updates announcement fields.

        WHY: Edit announcements.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID
            **kwargs: Fields to update

        Returns:
            Updated Announcement

        Raises:
            AnnouncementNotFoundError: If not found
            AnnouncementError: If cannot be edited
        """
        announcement = await self.get_announcement(announcement_id, org_id)

        # Can only edit draft or scheduled announcements
        if announcement.status not in [
            AnnouncementStatus.DRAFT.value,
            AnnouncementStatus.SCHEDULED.value,
        ]:
            raise AnnouncementError(
                message="Cannot edit published announcements",
                announcement_id=announcement_id,
            )

        # Update fields
        for key, value in kwargs.items():
            if value is not None and hasattr(announcement, key):
                setattr(announcement, key, value)

        await self.session.flush()
        await self.session.refresh(announcement)
        return announcement

    async def delete_announcement(
        self,
        announcement_id: int,
        org_id: int,
    ) -> None:
        """
        Delete an announcement.

        WHAT: Removes announcement.

        WHY: Clean up drafts or cancel scheduled.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID

        Raises:
            AnnouncementNotFoundError: If not found
            AnnouncementError: If cannot delete active
        """
        announcement = await self.get_announcement(announcement_id, org_id)

        # Can only delete draft, scheduled, or expired
        if announcement.status == AnnouncementStatus.ACTIVE.value:
            raise AnnouncementError(
                message="Archive active announcements instead of deleting",
                announcement_id=announcement_id,
            )

        await self.announcement_dao.delete(announcement_id)

    async def publish_announcement(
        self,
        announcement_id: int,
        org_id: int,
    ) -> Announcement:
        """
        Publish an announcement immediately.

        WHAT: Changes status to ACTIVE.

        WHY: Make announcement visible now.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID

        Returns:
            Updated Announcement

        Raises:
            AnnouncementNotFoundError: If not found
            AnnouncementError: If not in publishable state
        """
        announcement = await self.get_announcement(announcement_id, org_id)

        if announcement.status not in [
            AnnouncementStatus.DRAFT.value,
            AnnouncementStatus.SCHEDULED.value,
        ]:
            raise AnnouncementError(
                message="Announcement is not in a publishable state",
                announcement_id=announcement_id,
                status=announcement.status,
            )

        return await self.announcement_dao.publish_announcement(
            announcement_id, org_id
        )

    async def archive_announcement(
        self,
        announcement_id: int,
        org_id: int,
    ) -> Announcement:
        """
        Archive an announcement.

        WHAT: Changes status to ARCHIVED.

        WHY: Hide old announcements.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID

        Returns:
            Updated Announcement
        """
        await self.get_announcement(announcement_id, org_id)

        return await self.announcement_dao.archive_announcement(
            announcement_id, org_id
        )

    # =========================================================================
    # User-Facing Operations
    # =========================================================================

    async def get_active_announcements(
        self,
        org_id: int,
        user_id: int,
        user_role: str,
        include_read: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get active announcements for a user.

        WHAT: Lists announcements relevant to user.

        WHY: User's announcement feed.

        Args:
            org_id: Organization ID
            user_id: User ID
            user_role: User's role
            include_read: Include already read
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dict with announcements
        """
        announcements = await self.announcement_dao.get_active_announcements(
            org_id=org_id,
            user_id=user_id,
            user_role=user_role,
            include_read=include_read,
            skip=skip,
            limit=limit + 1,
        )

        has_more = len(announcements) > limit
        if has_more:
            announcements = announcements[:limit]

        # Add read status to each announcement
        for announcement in announcements:
            read_status = await self.get_read_status(announcement.id, user_id)
            announcement.is_read = read_status["is_read"]
            announcement.is_acknowledged = read_status["is_acknowledged"]
            announcement.is_dismissed = read_status["is_dismissed"]

        return {
            "items": announcements,
            "total": len(announcements),
            "skip": skip,
            "limit": limit,
        }

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
        return await self.announcement_dao.get_banner_announcements(
            org_id, user_id, user_role
        )

    async def mark_read(
        self,
        announcement_id: int,
        org_id: int,
        user_id: int,
    ) -> AnnouncementRead:
        """
        Mark announcement as read.

        WHAT: Records that user has seen announcement.

        WHY: Track engagement.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID
            user_id: User ID

        Returns:
            Read record
        """
        await self.get_announcement(announcement_id, org_id)
        return await self.read_dao.mark_read(announcement_id, user_id)

    async def acknowledge(
        self,
        announcement_id: int,
        org_id: int,
        user_id: int,
    ) -> AnnouncementRead:
        """
        Acknowledge an announcement.

        WHAT: Marks announcement as acknowledged.

        WHY: Required for important announcements.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID
            user_id: User ID

        Returns:
            Updated read record
        """
        announcement = await self.get_announcement(announcement_id, org_id)

        if not announcement.require_acknowledgment:
            raise ValidationError(
                message="This announcement does not require acknowledgment",
            )

        return await self.read_dao.acknowledge(announcement_id, user_id)

    async def dismiss(
        self,
        announcement_id: int,
        org_id: int,
        user_id: int,
    ) -> AnnouncementRead:
        """
        Dismiss an announcement.

        WHAT: Hides announcement from user's view.

        WHY: User chooses to hide.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID
            user_id: User ID

        Returns:
            Updated read record
        """
        announcement = await self.get_announcement(announcement_id, org_id)

        if not announcement.is_dismissible:
            raise ValidationError(
                message="This announcement cannot be dismissed",
            )

        return await self.read_dao.dismiss(announcement_id, user_id)

    async def get_read_status(
        self,
        announcement_id: int,
        user_id: int,
    ) -> Dict[str, bool]:
        """
        Get user's read status for an announcement.

        WHAT: Checks read/acknowledged/dismissed status.

        WHY: UI state.

        Args:
            announcement_id: Announcement ID
            user_id: User ID

        Returns:
            Status dict
        """
        result = await self.session.execute(
            self.read_dao.session.query(AnnouncementRead).filter(
                AnnouncementRead.announcement_id == announcement_id,
                AnnouncementRead.user_id == user_id,
            )
        )

        # Fix: Use the DAO's get method instead
        from sqlalchemy import select
        result = await self.session.execute(
            select(AnnouncementRead).where(
                AnnouncementRead.announcement_id == announcement_id,
                AnnouncementRead.user_id == user_id,
            )
        )
        read_record = result.scalar_one_or_none()

        if not read_record:
            return {
                "is_read": False,
                "is_acknowledged": False,
                "is_dismissed": False,
            }

        return {
            "is_read": read_record.is_read,
            "is_acknowledged": read_record.is_acknowledged,
            "is_dismissed": read_record.is_dismissed,
        }

    # =========================================================================
    # Admin Operations
    # =========================================================================

    async def get_org_announcements(
        self,
        org_id: int,
        status: Optional[str] = None,
        type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get all announcements for admin view.

        WHAT: Lists all announcements.

        WHY: Admin management.

        Args:
            org_id: Organization ID
            status: Optional status filter
            type: Optional type filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dict with announcements
        """
        announcements = await self.announcement_dao.get_org_announcements(
            org_id=org_id,
            status=status,
            type=type,
            skip=skip,
            limit=limit + 1,
        )

        has_more = len(announcements) > limit
        if has_more:
            announcements = announcements[:limit]

        return {
            "items": announcements,
            "total": len(announcements),
            "skip": skip,
            "limit": limit,
        }

    async def get_read_stats(
        self,
        announcement_id: int,
        org_id: int,
    ) -> Dict[str, int]:
        """
        Get read/acknowledgment statistics.

        WHAT: Engagement analytics.

        WHY: Track announcement reach.

        Args:
            announcement_id: Announcement ID
            org_id: Organization ID

        Returns:
            Stats dict
        """
        await self.get_announcement(announcement_id, org_id)
        return await self.read_dao.get_read_stats(announcement_id)

    # =========================================================================
    # Background Jobs
    # =========================================================================

    async def process_scheduled_announcements(self) -> int:
        """
        Activate scheduled announcements that are due.

        WHAT: Background job to publish scheduled announcements.

        WHY: Automatic scheduling.

        Returns:
            Number of announcements published
        """
        return await self.announcement_dao.update_scheduled_announcements()

    async def expire_old_announcements(self) -> int:
        """
        Expire announcements past their expire_at time.

        WHAT: Background job to expire old announcements.

        WHY: Automatic cleanup.

        Returns:
            Number of announcements expired
        """
        return await self.announcement_dao.expire_old_announcements()
