"""
Messages API Routes.

WHAT: REST API endpoints for in-app messaging operations.

WHY: In-app messaging enables:
1. Direct communication between team members
2. Client-provider conversations
3. Context-aware messaging (linked to projects/tickets)
4. Reduced email dependency

HOW: Uses FastAPI with dependency injection for auth/db.
All routes require authentication and enforce org-scoping.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.message import ConversationType
from app.services.message_service import MessageService
from app.services.audit import AuditService
from app.schemas.message import (
    ConversationCreateRequest,
    DirectMessageRequest,
    MessageCreateRequest,
    MessageUpdateRequest,
    AddParticipantsRequest,
    ParticipantResponse,
    MessageResponse,
    ConversationResponse,
    ConversationListResponse,
    MessageListResponse,
    ConversationWithMessagesResponse,
    UnreadCountResponse,
    ConversationType as SchemaConversationType,
)


router = APIRouter(prefix="/messages", tags=["messages"])


def _conversation_to_response(
    conversation,
    user_id: int,
    include_participants: bool = False,
) -> ConversationResponse:
    """
    Convert Conversation model to response schema.

    WHAT: Maps model fields to response.

    WHY: Consistent response formatting.
    """
    participants = None
    unread_count = 0

    if include_participants and conversation.participants:
        participants = [
            ParticipantResponse(
                id=p.id,
                user_id=p.user_id,
                user_name=p.user.name if p.user else None,
                user_email=p.user.email if p.user else None,
                joined_at=p.joined_at,
                left_at=p.left_at,
                is_active=p.is_active,
                is_admin=p.is_admin,
                is_muted=p.is_muted,
                unread_count=p.unread_count,
                last_read_at=p.last_read_at,
            )
            for p in conversation.participants
        ]
        # Get current user's unread count
        user_participant = next(
            (p for p in conversation.participants if p.user_id == user_id),
            None,
        )
        if user_participant:
            unread_count = user_participant.unread_count

    return ConversationResponse(
        id=conversation.id,
        org_id=conversation.org_id,
        type=SchemaConversationType(conversation.type),
        title=conversation.title,
        entity_type=conversation.entity_type,
        entity_id=conversation.entity_id,
        created_by=conversation.created_by,
        creator_name=conversation.creator.name if conversation.creator else None,
        participant_count=conversation.participant_count,
        participants=participants,
        last_message_at=conversation.last_message_at,
        last_message_preview=conversation.last_message_preview,
        unread_count=unread_count,
        is_archived=conversation.is_archived,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _message_to_response(message, reply_preview: Optional[str] = None) -> MessageResponse:
    """
    Convert Message model to response schema.

    WHAT: Maps model fields to response.

    WHY: Consistent response formatting.
    """
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_name=message.sender.name if message.sender else None,
        sender_email=message.sender.email if message.sender else None,
        content=message.content if not message.is_deleted else "[Message deleted]",
        content_preview=message.content_preview,
        reply_to_id=message.reply_to_id,
        reply_to_preview=reply_preview,
        attachment_ids=message.attachment_ids,
        is_edited=message.is_edited,
        edited_at=message.edited_at,
        is_deleted=message.is_deleted,
        is_system=message.is_system,
        created_at=message.created_at,
    )


# ============================================================================
# Conversation Endpoints
# ============================================================================


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new conversation.

    WHAT: Creates a conversation thread with participants.

    WHY: Start new group or entity-linked conversations.
    """
    service = MessageService(session)

    conversation = await service.create_conversation(
        org_id=current_user.org_id,
        user_id=current_user.id,
        type=ConversationType(request.type.value),
        title=request.title,
        participant_ids=request.participant_ids,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="conversation_created",
        resource_type="conversation",
        resource_id=conversation.id,
        details={
            "type": conversation.type,
            "participant_count": len(request.participant_ids) + 1,
        },
    )

    await session.commit()
    return _conversation_to_response(conversation, current_user.id, include_participants=True)


@router.post("/direct", response_model=ConversationWithMessagesResponse)
async def start_direct_message(
    request: DirectMessageRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Start or continue a direct message conversation.

    WHAT: Gets or creates a direct conversation between two users.

    WHY: Simplified direct messaging with automatic conversation reuse.
    """
    service = MessageService(session)

    result = await service.get_or_create_direct_conversation(
        org_id=current_user.org_id,
        user_id=current_user.id,
        recipient_id=request.recipient_id,
        initial_message=request.initial_message,
    )

    conversation = result["conversation"]

    # Get recent messages
    messages_data = await service.get_messages(
        conversation_id=conversation.id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        limit=50,
    )

    await session.commit()

    return ConversationWithMessagesResponse(
        conversation=_conversation_to_response(conversation, current_user.id, include_participants=True),
        messages=[_message_to_response(m) for m in messages_data["items"]],
        has_more=messages_data["has_more_before"],
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    type: Optional[SchemaConversationType] = Query(None, description="Filter by type"),
    include_archived: bool = Query(False, description="Include archived"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    List user's conversations.

    WHAT: Retrieves conversations the user participates in.

    WHY: Inbox view for messaging.
    """
    service = MessageService(session)

    conv_type = ConversationType(type.value) if type else None

    result = await service.get_user_conversations(
        user_id=current_user.id,
        org_id=current_user.org_id,
        type=conv_type,
        include_archived=include_archived,
        skip=skip,
        limit=limit,
    )

    return ConversationListResponse(
        items=[_conversation_to_response(c, current_user.id) for c in result["items"]],
        total=len(result["items"]),
        skip=result["skip"],
        limit=result["limit"],
        total_unread=result["total_unread"],
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get a conversation with recent messages.

    WHAT: Retrieves conversation details and message history.

    WHY: Open a conversation view.
    """
    service = MessageService(session)

    conversation = await service.get_conversation(
        conversation_id, current_user.org_id, current_user.id
    )

    # Get recent messages
    messages_data = await service.get_messages(
        conversation_id=conversation_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        limit=50,
    )

    # Mark conversation as read
    await service.mark_conversation_read(
        conversation_id, current_user.org_id, current_user.id
    )
    await session.commit()

    return ConversationWithMessagesResponse(
        conversation=_conversation_to_response(conversation, current_user.id, include_participants=True),
        messages=[_message_to_response(m) for m in messages_data["items"]],
        has_more=messages_data["has_more_before"],
    )


@router.get("/entity/{entity_type}/{entity_id}", response_model=Optional[ConversationResponse])
async def get_entity_conversation(
    entity_type: str,
    entity_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get conversation linked to an entity.

    WHAT: Finds conversation for project/ticket.

    WHY: Context-aware messaging from entity views.
    """
    service = MessageService(session)

    conversation = await service.get_conversation_for_entity(
        entity_type=entity_type,
        entity_id=entity_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
    )

    if not conversation:
        return None

    return _conversation_to_response(conversation, current_user.id, include_participants=True)


@router.post("/conversations/{conversation_id}/archive", response_model=ConversationResponse)
async def archive_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Archive a conversation.

    WHAT: Marks conversation as archived.

    WHY: Hide old conversations without deleting.

    Note: Requires conversation admin role.
    """
    service = MessageService(session)

    conversation = await service.archive_conversation(
        conversation_id, current_user.org_id, current_user.id
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="conversation_archived",
        resource_type="conversation",
        resource_id=conversation_id,
    )

    await session.commit()
    return _conversation_to_response(conversation, current_user.id)


# ============================================================================
# Participant Endpoints
# ============================================================================


@router.get("/conversations/{conversation_id}/participants", response_model=List[ParticipantResponse])
async def get_participants(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get conversation participants.

    WHAT: Lists who is in the conversation.

    WHY: Show participant list in UI.
    """
    service = MessageService(session)

    participants = await service.get_participants(
        conversation_id, current_user.org_id, current_user.id
    )

    return [
        ParticipantResponse(
            id=p.id,
            user_id=p.user_id,
            user_name=p.user.name if p.user else None,
            user_email=p.user.email if p.user else None,
            joined_at=p.joined_at,
            left_at=p.left_at,
            is_active=p.is_active,
            is_admin=p.is_admin,
            is_muted=p.is_muted,
            unread_count=p.unread_count,
            last_read_at=p.last_read_at,
        )
        for p in participants
    ]


@router.post("/conversations/{conversation_id}/participants", response_model=List[ParticipantResponse])
async def add_participants(
    conversation_id: int,
    request: AddParticipantsRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Add participants to a conversation.

    WHAT: Adds users to conversation.

    WHY: Expand group conversations.

    Note: Requires conversation admin role. Cannot add to direct conversations.
    """
    service = MessageService(session)

    participants = await service.add_participants(
        conversation_id=conversation_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        user_ids_to_add=request.user_ids,
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="participants_added",
        resource_type="conversation",
        resource_id=conversation_id,
        details={"added_user_ids": request.user_ids},
    )

    await session.commit()

    return [
        ParticipantResponse(
            id=p.id,
            user_id=p.user_id,
            user_name=p.user.name if p.user else None,
            user_email=p.user.email if p.user else None,
            joined_at=p.joined_at,
            left_at=p.left_at,
            is_active=p.is_active,
            is_admin=p.is_admin,
            is_muted=p.is_muted,
            unread_count=p.unread_count,
            last_read_at=p.last_read_at,
        )
        for p in participants
    ]


@router.delete("/conversations/{conversation_id}/participants/{user_id}")
async def remove_participant(
    conversation_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Remove a participant from a conversation.

    WHAT: Removes user from conversation.

    WHY: Leave or kick from group.

    Note: Users can remove themselves. Admins can remove others.
    """
    service = MessageService(session)

    await service.remove_participant(
        conversation_id=conversation_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        user_id_to_remove=user_id,
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="participant_removed",
        resource_type="conversation",
        resource_id=conversation_id,
        details={"removed_user_id": user_id},
    )

    await session.commit()
    return {"message": "Participant removed"}


@router.post("/conversations/{conversation_id}/leave")
async def leave_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Leave a conversation.

    WHAT: Removes self from conversation.

    WHY: User wants to exit a conversation.
    """
    service = MessageService(session)

    await service.remove_participant(
        conversation_id=conversation_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        user_id_to_remove=current_user.id,
    )

    await session.commit()
    return {"message": "Left conversation"}


# ============================================================================
# Message Endpoints
# ============================================================================


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: int,
    request: MessageCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Send a message in a conversation.

    WHAT: Creates a new message.

    WHY: Core messaging functionality.
    """
    service = MessageService(session)

    message = await service.send_message(
        conversation_id=conversation_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        content=request.content,
        reply_to_id=request.reply_to_id,
        attachment_ids=request.attachment_ids,
    )

    await session.commit()
    return _message_to_response(message)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages(
    conversation_id: int,
    before_id: Optional[int] = Query(None, description="Get messages before this ID"),
    after_id: Optional[int] = Query(None, description="Get messages after this ID"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get messages in a conversation.

    WHAT: Retrieves message history.

    WHY: Load more messages (pagination).
    """
    service = MessageService(session)

    result = await service.get_messages(
        conversation_id=conversation_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        before_id=before_id,
        after_id=after_id,
        limit=limit,
    )

    return MessageListResponse(
        items=[_message_to_response(m) for m in result["items"]],
        conversation_id=result["conversation_id"],
        has_more_before=result["has_more_before"],
        has_more_after=result["has_more_after"],
    )


@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def edit_message(
    message_id: int,
    request: MessageUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Edit a message.

    WHAT: Updates message content.

    WHY: Allow editing own messages.

    Note: Only the sender can edit. Shows "edited" indicator.
    """
    service = MessageService(session)

    message = await service.edit_message(
        message_id=message_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        new_content=request.content,
    )

    await session.commit()
    return _message_to_response(message)


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete a message.

    WHAT: Soft-deletes a message.

    WHY: Hide unwanted messages.

    Note: Only the sender can delete. Message shows "[Message deleted]".
    """
    service = MessageService(session)

    await service.delete_message(
        message_id=message_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
    )

    await session.commit()
    return {"message": "Message deleted"}


@router.get("/search", response_model=List[MessageResponse])
async def search_messages(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Search messages.

    WHAT: Full-text message search.

    WHY: Find past messages across conversations.

    Note: Only searches conversations user participates in.
    """
    service = MessageService(session)

    messages = await service.search_messages(
        org_id=current_user.org_id,
        user_id=current_user.id,
        query=q,
        limit=limit,
    )

    return [_message_to_response(m) for m in messages]


# ============================================================================
# Read Status Endpoints
# ============================================================================


@router.post("/conversations/{conversation_id}/read")
async def mark_conversation_read(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Mark conversation as read.

    WHAT: Clears unread count for conversation.

    WHY: User has viewed the messages.
    """
    service = MessageService(session)

    await service.mark_conversation_read(
        conversation_id, current_user.org_id, current_user.id
    )

    await session.commit()
    return {"message": "Marked as read"}


@router.get("/unread", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get unread message count.

    WHAT: Total unread messages.

    WHY: Badge display in navigation.
    """
    service = MessageService(session)

    counts = await service.get_unread_count(
        org_id=current_user.org_id,
        user_id=current_user.id,
    )

    return UnreadCountResponse(
        total_unread=counts["total_unread"],
        conversation_count=counts["conversation_count"],
    )
