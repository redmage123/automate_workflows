"""
Announcements API Routes.

WHAT: REST API endpoints for announcement operations.

WHY: Announcements enable:
1. Broadcasting important updates to all users
2. Scheduled communication
3. Targeted messaging (by role, user group)
4. Acknowledgment tracking

HOW: Uses FastAPI with dependency injection for auth/db.
All routes require authentication and enforce org-scoping.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_admin
from app.models.user import User, UserRole
from app.services.announcement_service import AnnouncementService
from app.services.audit import AuditService
from app.schemas.announcement import (
    AnnouncementType,
    AnnouncementPriority,
    AnnouncementStatus,
    AnnouncementCreateRequest,
    AnnouncementUpdateRequest,
    CreatorResponse,
    AnnouncementResponse,
    AnnouncementListResponse,
    ReadStatsResponse,
    BannerAnnouncementResponse,
)


router = APIRouter(prefix="/announcements", tags=["announcements"])


def _announcement_to_response(
    announcement,
    include_read_status: bool = False,
) -> AnnouncementResponse:
    """
    Convert Announcement model to response schema.

    WHAT: Maps model fields to response.

    WHY: Consistent response formatting.
    """
    creator = None
    if announcement.creator:
        creator = CreatorResponse(
            id=announcement.creator.id,
            name=announcement.creator.name,
            email=announcement.creator.email,
        )

    response = AnnouncementResponse(
        id=announcement.id,
        org_id=announcement.org_id,
        title=announcement.title,
        content=announcement.content,
        content_html=announcement.content_html,
        type=AnnouncementType(announcement.type),
        priority=AnnouncementPriority(announcement.priority),
        status=AnnouncementStatus(announcement.status),
        publish_at=announcement.publish_at,
        expire_at=announcement.expire_at,
        published_at=announcement.published_at,
        target_all=announcement.target_all,
        target_roles=announcement.target_roles,
        target_user_ids=announcement.target_user_ids,
        is_dismissible=announcement.is_dismissible,
        require_acknowledgment=announcement.require_acknowledgment,
        show_banner=announcement.show_banner,
        action_url=announcement.action_url,
        action_text=announcement.action_text,
        metadata=announcement.metadata,
        created_by=announcement.created_by,
        creator=creator,
        created_at=announcement.created_at,
        updated_at=announcement.updated_at,
    )

    if include_read_status:
        response.is_read = getattr(announcement, "is_read", None)
        response.is_acknowledged = getattr(announcement, "is_acknowledged", None)
        response.is_dismissed = getattr(announcement, "is_dismissed", None)

    return response


# ============================================================================
# User-Facing Endpoints
# ============================================================================


@router.get("/active", response_model=AnnouncementListResponse)
async def get_active_announcements(
    include_read: bool = Query(False, description="Include already read"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get active announcements for current user.

    WHAT: Lists announcements relevant to the user.

    WHY: User's announcement feed.
    """
    service = AnnouncementService(session)

    result = await service.get_active_announcements(
        org_id=current_user.org_id,
        user_id=current_user.id,
        user_role=current_user.role,
        include_read=include_read,
        skip=skip,
        limit=limit,
    )

    return AnnouncementListResponse(
        items=[_announcement_to_response(a, include_read_status=True) for a in result["items"]],
        total=result["total"],
        skip=result["skip"],
        limit=result["limit"],
    )


@router.get("/banners", response_model=List[BannerAnnouncementResponse])
async def get_banner_announcements(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get announcements to show as banners.

    WHAT: Retrieves banner-eligible announcements.

    WHY: Show important banners in UI header.
    """
    service = AnnouncementService(session)

    banners = await service.get_banner_announcements(
        org_id=current_user.org_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return [
        BannerAnnouncementResponse(
            id=b.id,
            title=b.title,
            content=b.content,
            type=AnnouncementType(b.type),
            priority=AnnouncementPriority(b.priority),
            is_dismissible=b.is_dismissible,
            require_acknowledgment=b.require_acknowledgment,
            action_url=b.action_url,
            action_text=b.action_text,
        )
        for b in banners
    ]


@router.post("/{announcement_id}/read")
async def mark_announcement_read(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Mark announcement as read.

    WHAT: Records that user has seen announcement.

    WHY: Track engagement.
    """
    service = AnnouncementService(session)

    await service.mark_read(
        announcement_id, current_user.org_id, current_user.id
    )

    await session.commit()
    return {"message": "Marked as read"}


@router.post("/{announcement_id}/acknowledge")
async def acknowledge_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Acknowledge an announcement.

    WHAT: Marks announcement as acknowledged.

    WHY: Required for important announcements.
    """
    service = AnnouncementService(session)

    await service.acknowledge(
        announcement_id, current_user.org_id, current_user.id
    )

    await session.commit()
    return {"message": "Acknowledged"}


@router.post("/{announcement_id}/dismiss")
async def dismiss_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Dismiss an announcement.

    WHAT: Hides announcement from user's view.

    WHY: User chooses to hide.
    """
    service = AnnouncementService(session)

    await service.dismiss(
        announcement_id, current_user.org_id, current_user.id
    )

    await session.commit()
    return {"message": "Dismissed"}


# ============================================================================
# Admin Endpoints
# ============================================================================


@router.get("", response_model=AnnouncementListResponse)
async def list_announcements(
    status: Optional[AnnouncementStatus] = Query(None, description="Filter by status"),
    type: Optional[AnnouncementType] = Query(None, description="Filter by type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    List all announcements (admin).

    WHAT: Lists all announcements with filters.

    WHY: Admin management view.

    Requires: Admin role
    """
    service = AnnouncementService(session)

    result = await service.get_org_announcements(
        org_id=current_user.org_id,
        status=status.value if status else None,
        type=type.value if type else None,
        skip=skip,
        limit=limit,
    )

    return AnnouncementListResponse(
        items=[_announcement_to_response(a) for a in result["items"]],
        total=result["total"],
        skip=result["skip"],
        limit=result["limit"],
    )


@router.post("", response_model=AnnouncementResponse)
async def create_announcement(
    request: AnnouncementCreateRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new announcement.

    WHAT: Creates announcement in draft or scheduled status.

    WHY: Broadcast messages to users.

    Requires: Admin role
    """
    service = AnnouncementService(session)

    announcement = await service.create_announcement(
        org_id=current_user.org_id,
        created_by=current_user.id,
        title=request.title,
        content=request.content,
        type=request.type.value,
        priority=request.priority.value,
        content_html=request.content_html,
        publish_at=request.publish_at,
        expire_at=request.expire_at,
        target_all=request.target_all,
        target_roles=request.target_roles,
        target_user_ids=request.target_user_ids,
        is_dismissible=request.is_dismissible,
        require_acknowledgment=request.require_acknowledgment,
        show_banner=request.show_banner,
        action_url=request.action_url,
        action_text=request.action_text,
        metadata=request.metadata,
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="announcement_created",
        resource_type="announcement",
        resource_id=announcement.id,
        details={"title": announcement.title, "status": announcement.status},
    )

    await session.commit()
    return _announcement_to_response(announcement)


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Get announcement details.

    WHAT: Retrieves announcement details.

    WHY: View announcement information.

    Requires: Admin role
    """
    service = AnnouncementService(session)

    announcement = await service.get_announcement(
        announcement_id, current_user.org_id
    )

    return _announcement_to_response(announcement)


@router.patch("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: int,
    request: AnnouncementUpdateRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Update an announcement.

    WHAT: Updates announcement fields.

    WHY: Edit draft/scheduled announcements.

    Requires: Admin role

    Note: Cannot edit active/published announcements.
    """
    service = AnnouncementService(session)

    # Build update dict from non-None values
    updates = {}
    for key, value in request.model_dump().items():
        if value is not None:
            if key in ["type", "priority"]:
                updates[key] = value.value
            else:
                updates[key] = value

    announcement = await service.update_announcement(
        announcement_id, current_user.org_id, **updates
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="announcement_updated",
        resource_type="announcement",
        resource_id=announcement_id,
        details=updates,
    )

    await session.commit()
    return _announcement_to_response(announcement)


@router.delete("/{announcement_id}")
async def delete_announcement(
    announcement_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete an announcement.

    WHAT: Removes announcement.

    WHY: Clean up drafts or cancel scheduled.

    Requires: Admin role

    Note: Cannot delete active announcements - archive them instead.
    """
    service = AnnouncementService(session)

    await service.delete_announcement(announcement_id, current_user.org_id)

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="announcement_deleted",
        resource_type="announcement",
        resource_id=announcement_id,
    )

    await session.commit()
    return {"message": "Announcement deleted"}


@router.post("/{announcement_id}/publish", response_model=AnnouncementResponse)
async def publish_announcement(
    announcement_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Publish an announcement immediately.

    WHAT: Changes status to ACTIVE.

    WHY: Make announcement visible now.

    Requires: Admin role
    """
    service = AnnouncementService(session)

    announcement = await service.publish_announcement(
        announcement_id, current_user.org_id
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="announcement_published",
        resource_type="announcement",
        resource_id=announcement_id,
    )

    await session.commit()
    return _announcement_to_response(announcement)


@router.post("/{announcement_id}/archive", response_model=AnnouncementResponse)
async def archive_announcement(
    announcement_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Archive an announcement.

    WHAT: Changes status to ARCHIVED.

    WHY: Hide old announcements.

    Requires: Admin role
    """
    service = AnnouncementService(session)

    announcement = await service.archive_announcement(
        announcement_id, current_user.org_id
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="announcement_archived",
        resource_type="announcement",
        resource_id=announcement_id,
    )

    await session.commit()
    return _announcement_to_response(announcement)


@router.get("/{announcement_id}/stats", response_model=ReadStatsResponse)
async def get_announcement_stats(
    announcement_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Get read/acknowledgment statistics.

    WHAT: Engagement analytics.

    WHY: Track announcement reach.

    Requires: Admin role
    """
    service = AnnouncementService(session)

    stats = await service.get_read_stats(announcement_id, current_user.org_id)

    return ReadStatsResponse(
        total_reads=stats["total_reads"],
        acknowledged=stats["acknowledged"],
        dismissed=stats["dismissed"],
    )
