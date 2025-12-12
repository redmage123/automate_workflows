"""
Announcement Pydantic Schemas.

WHAT: Request/Response models for announcement API endpoints.

WHY: Pydantic schemas provide:
1. Request validation
2. Response serialization
3. OpenAPI documentation
4. Type safety

HOW: Defines schemas for:
- Announcements
- Read/acknowledgment tracking
- Analytics
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class AnnouncementType(str, Enum):
    """Announcement types."""

    INFO = "info"
    UPDATE = "update"
    ALERT = "alert"
    MAINTENANCE = "maintenance"
    PROMOTION = "promotion"


class AnnouncementPriority(str, Enum):
    """Priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AnnouncementStatus(str, Enum):
    """Announcement status."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    EXPIRED = "expired"
    ARCHIVED = "archived"


# ============================================================================
# Request Schemas
# ============================================================================


class AnnouncementCreateRequest(BaseModel):
    """
    Request schema for creating an announcement.

    WHAT: Fields needed to create announcement.

    WHY: Validates announcement creation data.
    """

    title: str = Field(..., min_length=1, max_length=255, description="Title")
    content: str = Field(..., min_length=1, max_length=10000, description="Content")
    content_html: Optional[str] = Field(None, description="HTML content")

    type: AnnouncementType = Field(
        default=AnnouncementType.INFO, description="Type"
    )
    priority: AnnouncementPriority = Field(
        default=AnnouncementPriority.NORMAL, description="Priority"
    )

    publish_at: Optional[datetime] = Field(None, description="Scheduled publish time")
    expire_at: Optional[datetime] = Field(None, description="Expiration time")

    target_all: bool = Field(default=True, description="Target all users")
    target_roles: Optional[List[str]] = Field(None, description="Target roles")
    target_user_ids: Optional[List[int]] = Field(None, description="Target user IDs")

    is_dismissible: bool = Field(default=True, description="Can be dismissed")
    require_acknowledgment: bool = Field(
        default=False, description="Requires acknowledgment"
    )
    show_banner: bool = Field(default=False, description="Show as banner")

    action_url: Optional[str] = Field(None, max_length=500, description="CTA URL")
    action_text: Optional[str] = Field(None, max_length=100, description="CTA text")

    metadata: Optional[Dict[str, Any]] = Field(None, description="Custom metadata")


class AnnouncementUpdateRequest(BaseModel):
    """
    Request schema for updating an announcement.

    WHAT: Fields that can be updated.

    WHY: Allows partial updates.
    """

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    content_html: Optional[str] = None

    type: Optional[AnnouncementType] = None
    priority: Optional[AnnouncementPriority] = None

    publish_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None

    target_all: Optional[bool] = None
    target_roles: Optional[List[str]] = None
    target_user_ids: Optional[List[int]] = None

    is_dismissible: Optional[bool] = None
    require_acknowledgment: Optional[bool] = None
    show_banner: Optional[bool] = None

    action_url: Optional[str] = None
    action_text: Optional[str] = None

    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# Response Schemas
# ============================================================================


class CreatorResponse(BaseModel):
    """
    Response schema for announcement creator.

    WHAT: User who created announcement.

    WHY: Display creator info.
    """

    id: int = Field(..., description="User ID")
    name: Optional[str] = Field(None, description="User name")
    email: Optional[str] = Field(None, description="User email")

    class Config:
        from_attributes = True


class AnnouncementResponse(BaseModel):
    """
    Response schema for announcement.

    WHAT: Announcement details for display.

    WHY: Provides all announcement information for UI.
    """

    id: int = Field(..., description="Announcement ID")
    org_id: int = Field(..., description="Organization ID")

    title: str = Field(..., description="Title")
    content: str = Field(..., description="Content")
    content_html: Optional[str] = Field(None, description="HTML content")

    type: AnnouncementType = Field(..., description="Type")
    priority: AnnouncementPriority = Field(..., description="Priority")
    status: AnnouncementStatus = Field(..., description="Status")

    publish_at: Optional[datetime] = Field(None, description="Scheduled publish time")
    expire_at: Optional[datetime] = Field(None, description="Expiration time")
    published_at: Optional[datetime] = Field(None, description="Actual publish time")

    target_all: bool = Field(..., description="Targets all users")
    target_roles: Optional[List[str]] = Field(None, description="Target roles")
    target_user_ids: Optional[List[int]] = Field(None, description="Target user IDs")

    is_dismissible: bool = Field(..., description="Can be dismissed")
    require_acknowledgment: bool = Field(..., description="Requires acknowledgment")
    show_banner: bool = Field(..., description="Shows as banner")

    action_url: Optional[str] = Field(None, description="CTA URL")
    action_text: Optional[str] = Field(None, description="CTA text")

    metadata: Optional[Dict[str, Any]] = Field(None, description="Custom metadata")

    created_by: int = Field(..., description="Creator user ID")
    creator: Optional[CreatorResponse] = Field(None, description="Creator details")

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    # User-specific fields (added when viewing)
    is_read: Optional[bool] = Field(None, description="Read by current user")
    is_acknowledged: Optional[bool] = Field(None, description="Acknowledged by current user")
    is_dismissed: Optional[bool] = Field(None, description="Dismissed by current user")

    class Config:
        from_attributes = True


class AnnouncementListResponse(BaseModel):
    """
    Response schema for announcement list.

    WHAT: Paginated list of announcements.

    WHY: Feed display.
    """

    items: List[AnnouncementResponse] = Field(..., description="Announcements")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")


class ReadStatsResponse(BaseModel):
    """
    Response schema for read statistics.

    WHAT: Engagement statistics.

    WHY: Analytics for announcements.
    """

    total_reads: int = Field(..., description="Total reads")
    acknowledged: int = Field(..., description="Acknowledged count")
    dismissed: int = Field(..., description="Dismissed count")


class BannerAnnouncementResponse(BaseModel):
    """
    Response schema for banner announcements.

    WHAT: Minimal announcement for banner display.

    WHY: Lightweight response for banners.
    """

    id: int = Field(..., description="Announcement ID")
    title: str = Field(..., description="Title")
    content: str = Field(..., description="Content")
    type: AnnouncementType = Field(..., description="Type")
    priority: AnnouncementPriority = Field(..., description="Priority")
    is_dismissible: bool = Field(..., description="Can be dismissed")
    require_acknowledgment: bool = Field(..., description="Requires acknowledgment")
    action_url: Optional[str] = Field(None, description="CTA URL")
    action_text: Optional[str] = Field(None, description="CTA text")

    class Config:
        from_attributes = True
