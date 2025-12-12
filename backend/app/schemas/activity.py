"""
Activity Feed Pydantic Schemas.

WHAT: Request/Response models for activity feed API endpoints.

WHY: Pydantic schemas provide:
1. Request validation
2. Response serialization
3. OpenAPI documentation
4. Type safety

HOW: Defines schemas for:
- Activity events
- Subscriptions
- Feed responses
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class ActivityType(str, Enum):
    """Activity event types."""

    # Project activities
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    PROJECT_STATUS_CHANGED = "project.status_changed"
    PROJECT_ASSIGNED = "project.assigned"

    # Proposal activities
    PROPOSAL_CREATED = "proposal.created"
    PROPOSAL_SENT = "proposal.sent"
    PROPOSAL_APPROVED = "proposal.approved"
    PROPOSAL_REJECTED = "proposal.rejected"

    # Invoice activities
    INVOICE_CREATED = "invoice.created"
    INVOICE_SENT = "invoice.sent"
    INVOICE_PAID = "invoice.paid"
    INVOICE_OVERDUE = "invoice.overdue"

    # Ticket activities
    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_STATUS_CHANGED = "ticket.status_changed"
    TICKET_ASSIGNED = "ticket.assigned"
    TICKET_COMMENTED = "ticket.commented"

    # Workflow activities
    WORKFLOW_CREATED = "workflow.created"
    WORKFLOW_EXECUTED = "workflow.executed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_COMPLETED = "workflow.completed"

    # Document activities
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_SHARED = "document.shared"
    DOCUMENT_DOWNLOADED = "document.downloaded"
    DOCUMENT_DELETED = "document.deleted"

    # Time tracking activities
    TIME_ENTRY_SUBMITTED = "time_entry.submitted"
    TIME_ENTRY_APPROVED = "time_entry.approved"
    TIME_ENTRY_REJECTED = "time_entry.rejected"

    # User activities
    USER_JOINED = "user.joined"
    USER_INVITED = "user.invited"

    # Message activities
    CONVERSATION_CREATED = "conversation.created"
    MESSAGE_SENT = "message.sent"

    # General
    COMMENT_ADDED = "comment.added"
    NOTE_ADDED = "note.added"


# ============================================================================
# Request Schemas
# ============================================================================


class ActivityFilterRequest(BaseModel):
    """
    Request schema for filtering activities.

    WHAT: Filter parameters for activity feed.

    WHY: Flexible querying.
    """

    event_types: Optional[List[ActivityType]] = Field(
        None, description="Filter by event types"
    )
    entity_type: Optional[str] = Field(
        None, max_length=50, description="Filter by entity type"
    )
    entity_id: Optional[int] = Field(None, description="Filter by entity ID")
    actor_id: Optional[int] = Field(None, description="Filter by actor")
    since: Optional[datetime] = Field(None, description="Start time")
    until: Optional[datetime] = Field(None, description="End time")


class SubscribeRequest(BaseModel):
    """
    Request schema for subscribing to an entity.

    WHAT: Subscription parameters.

    WHY: Follow entities for updates.
    """

    entity_type: str = Field(..., max_length=50, description="Entity type")
    entity_id: int = Field(..., description="Entity ID")
    notify_in_app: bool = Field(default=True, description="In-app notifications")
    notify_email: bool = Field(default=False, description="Email notifications")


class UpdateSubscriptionRequest(BaseModel):
    """
    Request schema for updating subscription preferences.

    WHAT: Update notification preferences.

    WHY: Control how to receive updates.
    """

    notify_in_app: Optional[bool] = Field(None, description="In-app notifications")
    notify_email: Optional[bool] = Field(None, description="Email notifications")


# ============================================================================
# Response Schemas
# ============================================================================


class ActorResponse(BaseModel):
    """
    Response schema for activity actor.

    WHAT: User who performed action.

    WHY: Display actor info in feed.
    """

    id: int = Field(..., description="User ID")
    name: Optional[str] = Field(None, description="User name")
    email: Optional[str] = Field(None, description="User email")

    class Config:
        from_attributes = True


class ActivityEventResponse(BaseModel):
    """
    Response schema for a single activity event.

    WHAT: Activity event details for display.

    WHY: Provides all event information for UI.
    """

    id: int = Field(..., description="Event ID")
    org_id: int = Field(..., description="Organization ID")

    event_type: ActivityType = Field(..., description="Event type")

    # Actor
    actor_id: int = Field(..., description="Actor user ID")
    actor: Optional[ActorResponse] = Field(None, description="Actor details")

    # Entity
    entity_type: str = Field(..., description="Entity type")
    entity_id: int = Field(..., description="Entity ID")
    entity_name: Optional[str] = Field(None, description="Entity name")

    # Parent entity
    parent_entity_type: Optional[str] = Field(None, description="Parent entity type")
    parent_entity_id: Optional[int] = Field(None, description="Parent entity ID")

    # Description
    description: str = Field(..., description="Human-readable description")
    description_html: Optional[str] = Field(None, description="HTML description")

    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Event metadata")

    # Visibility
    is_public: bool = Field(..., description="Is publicly visible")

    created_at: datetime = Field(..., description="Event timestamp")

    class Config:
        from_attributes = True


class ActivityFeedResponse(BaseModel):
    """
    Response schema for activity feed.

    WHAT: Paginated list of activities.

    WHY: Feed display.
    """

    items: List[ActivityEventResponse] = Field(..., description="Activities")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")
    has_more: bool = Field(..., description="More items available")


class SubscriptionResponse(BaseModel):
    """
    Response schema for a subscription.

    WHAT: Subscription details.

    WHY: Show followed entities.
    """

    id: int = Field(..., description="Subscription ID")
    user_id: int = Field(..., description="User ID")
    entity_type: str = Field(..., description="Entity type")
    entity_id: int = Field(..., description="Entity ID")
    notify_in_app: bool = Field(..., description="In-app notifications enabled")
    notify_email: bool = Field(..., description="Email notifications enabled")
    created_at: datetime = Field(..., description="Subscription timestamp")

    class Config:
        from_attributes = True


class SubscriptionListResponse(BaseModel):
    """
    Response schema for subscription list.

    WHAT: List of user's subscriptions.

    WHY: Manage followed entities.
    """

    items: List[SubscriptionResponse] = Field(..., description="Subscriptions")
    total: int = Field(..., description="Total count")


class ActivitySummaryResponse(BaseModel):
    """
    Response schema for activity summary.

    WHAT: Aggregated activity statistics.

    WHY: Dashboard widgets.
    """

    counts_by_type: Dict[str, int] = Field(..., description="Count per event type")
    total_events: int = Field(..., description="Total events")
    period_start: Optional[datetime] = Field(None, description="Summary period start")
    period_end: Optional[datetime] = Field(None, description="Summary period end")


class ActiveUserResponse(BaseModel):
    """
    Response schema for active user summary.

    WHAT: User activity statistics.

    WHY: Team activity insights.
    """

    actor_id: int = Field(..., description="User ID")
    actor_name: Optional[str] = Field(None, description="User name")
    activity_count: int = Field(..., description="Number of activities")
    last_activity: datetime = Field(..., description="Last activity timestamp")


class ActiveUsersResponse(BaseModel):
    """
    Response schema for active users list.

    WHAT: Most active users.

    WHY: Team engagement tracking.
    """

    items: List[ActiveUserResponse] = Field(..., description="Active users")
    period_days: int = Field(..., description="Period in days")
