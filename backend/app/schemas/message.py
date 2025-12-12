"""
Message Pydantic Schemas.

WHAT: Request/Response models for messaging API endpoints.

WHY: Pydantic schemas provide:
1. Request validation
2. Response serialization
3. OpenAPI documentation
4. Type safety

HOW: Defines schemas for:
- Conversations
- Messages
- Participants
- Read receipts
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class ConversationType(str, Enum):
    """Conversation type values."""

    DIRECT = "direct"
    GROUP = "group"
    PROJECT = "project"
    TICKET = "ticket"
    SUPPORT = "support"


# ============================================================================
# Request Schemas
# ============================================================================


class ConversationCreateRequest(BaseModel):
    """
    Request schema for creating a conversation.

    WHAT: Fields needed to create a conversation.

    WHY: Validates conversation creation data.
    """

    type: ConversationType = Field(
        default=ConversationType.DIRECT,
        description="Conversation type",
    )
    title: Optional[str] = Field(
        None, max_length=255, description="Conversation title"
    )
    participant_ids: List[int] = Field(
        default=[], description="Initial participant IDs"
    )
    entity_type: Optional[str] = Field(
        None, max_length=50, description="Linked entity type"
    )
    entity_id: Optional[int] = Field(
        None, description="Linked entity ID"
    )


class DirectMessageRequest(BaseModel):
    """
    Request schema for starting a direct message.

    WHAT: Creates or retrieves direct conversation.

    WHY: Simplified direct messaging.
    """

    recipient_id: int = Field(..., description="Recipient user ID")
    initial_message: Optional[str] = Field(
        None, max_length=5000, description="Optional first message"
    )


class MessageCreateRequest(BaseModel):
    """
    Request schema for sending a message.

    WHAT: Message content and optional reply.

    WHY: Validates message data.
    """

    content: str = Field(
        ..., min_length=1, max_length=5000, description="Message content"
    )
    reply_to_id: Optional[int] = Field(
        None, description="Message ID to reply to"
    )
    attachment_ids: Optional[List[int]] = Field(
        None, max_items=10, description="Document IDs to attach"
    )


class MessageUpdateRequest(BaseModel):
    """
    Request schema for editing a message.

    WHAT: New content for message.

    WHY: Allows editing messages.
    """

    content: str = Field(
        ..., min_length=1, max_length=5000, description="New message content"
    )


class AddParticipantsRequest(BaseModel):
    """
    Request schema for adding participants.

    WHAT: User IDs to add.

    WHY: Expand group conversations.
    """

    user_ids: List[int] = Field(
        ..., min_items=1, max_items=50, description="User IDs to add"
    )


# ============================================================================
# Response Schemas
# ============================================================================


class ParticipantResponse(BaseModel):
    """
    Response schema for a conversation participant.

    WHAT: Participant details.

    WHY: Shows who's in conversation.
    """

    id: int = Field(..., description="Participant record ID")
    user_id: int = Field(..., description="User ID")
    user_name: Optional[str] = Field(None, description="User name")
    user_email: Optional[str] = Field(None, description="User email")
    joined_at: datetime = Field(..., description="Join timestamp")
    left_at: Optional[datetime] = Field(None, description="Leave timestamp")
    is_active: bool = Field(..., description="Is still in conversation")
    is_admin: bool = Field(..., description="Is conversation admin")
    is_muted: bool = Field(..., description="Has muted notifications")
    unread_count: int = Field(..., description="Unread message count")
    last_read_at: Optional[datetime] = Field(None, description="Last read timestamp")

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """
    Response schema for a single message.

    WHAT: Message details for display.

    WHY: Provides all message information for UI.
    """

    id: int = Field(..., description="Message ID")
    conversation_id: int = Field(..., description="Conversation ID")
    sender_id: int = Field(..., description="Sender user ID")
    sender_name: Optional[str] = Field(None, description="Sender name")
    sender_email: Optional[str] = Field(None, description="Sender email")

    content: str = Field(..., description="Message content")
    content_preview: str = Field(..., description="Preview text")

    reply_to_id: Optional[int] = Field(None, description="Reply target ID")
    reply_to_preview: Optional[str] = Field(None, description="Reply target preview")

    attachment_ids: Optional[List[int]] = Field(None, description="Attached doc IDs")

    is_edited: bool = Field(..., description="Has been edited")
    edited_at: Optional[datetime] = Field(None, description="Edit timestamp")
    is_deleted: bool = Field(..., description="Has been deleted")
    is_system: bool = Field(..., description="Is system message")

    created_at: datetime = Field(..., description="Send timestamp")

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """
    Response schema for a conversation.

    WHAT: Conversation details for display.

    WHY: Provides conversation info for inbox/chat view.
    """

    id: int = Field(..., description="Conversation ID")
    org_id: int = Field(..., description="Organization ID")
    type: ConversationType = Field(..., description="Conversation type")
    title: Optional[str] = Field(None, description="Conversation title")

    entity_type: Optional[str] = Field(None, description="Linked entity type")
    entity_id: Optional[int] = Field(None, description="Linked entity ID")

    created_by: int = Field(..., description="Creator user ID")
    creator_name: Optional[str] = Field(None, description="Creator name")

    participant_count: int = Field(..., description="Number of participants")
    participants: Optional[List[ParticipantResponse]] = Field(
        None, description="Participants (if loaded)"
    )

    last_message_at: Optional[datetime] = Field(None, description="Last message time")
    last_message_preview: Optional[str] = Field(None, description="Last message text")

    unread_count: int = Field(default=0, description="User's unread count")
    is_archived: bool = Field(..., description="Is archived")

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """
    Response schema for conversation list.

    WHAT: Paginated list of conversations.

    WHY: Inbox view support.
    """

    items: List[ConversationResponse] = Field(..., description="Conversations")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")
    total_unread: int = Field(default=0, description="Total unread messages")


class MessageListResponse(BaseModel):
    """
    Response schema for message list.

    WHAT: Messages in a conversation.

    WHY: Chat history display.
    """

    items: List[MessageResponse] = Field(..., description="Messages")
    conversation_id: int = Field(..., description="Conversation ID")
    has_more_before: bool = Field(..., description="More older messages")
    has_more_after: bool = Field(..., description="More newer messages")


class ConversationWithMessagesResponse(BaseModel):
    """
    Response schema for conversation with messages.

    WHAT: Full conversation data.

    WHY: Initial chat load.
    """

    conversation: ConversationResponse = Field(..., description="Conversation")
    messages: List[MessageResponse] = Field(..., description="Recent messages")
    has_more: bool = Field(..., description="More messages available")


class UnreadCountResponse(BaseModel):
    """
    Response schema for unread counts.

    WHAT: Unread message statistics.

    WHY: Badge display.
    """

    total_unread: int = Field(..., description="Total unread messages")
    conversation_count: int = Field(..., description="Conversations with unread")
