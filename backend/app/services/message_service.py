"""
Message Service.

WHAT: Business logic for in-app messaging operations.

WHY: The service layer:
1. Encapsulates messaging business logic
2. Coordinates between DAOs
3. Enforces business rules (participation, permissions)
4. Handles conversation lifecycle management

HOW: Orchestrates MessageDAO, ConversationDAO, and related DAOs
while validating operations against business rules.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.message import (
    ConversationDAO,
    ConversationParticipantDAO,
    MessageDAO,
    MessageReadReceiptDAO,
)
from app.dao.user import UserDAO
from app.models.message import (
    Conversation,
    ConversationType,
    ConversationParticipant,
    Message,
    MessageReadReceipt,
)
from app.core.exceptions import (
    MessageError,
    ConversationNotFoundError,
    MessageNotFoundError,
    NotParticipantError,
    AuthorizationError,
    ValidationError,
)


class MessageService:
    """
    Service for in-app messaging operations.

    WHAT: Provides business logic for conversations and messages.

    WHY: In-app messaging enables:
    - Direct communication between team members
    - Client-provider conversations
    - Context-aware messaging (linked to projects/tickets)
    - Reduced email dependency

    HOW: Coordinates DAOs and enforces business rules.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize MessageService.

        Args:
            session: Async database session
        """
        self.session = session
        self.conversation_dao = ConversationDAO(session)
        self.participant_dao = ConversationParticipantDAO(session)
        self.message_dao = MessageDAO(session)
        self.read_receipt_dao = MessageReadReceiptDAO(session)
        self.user_dao = UserDAO(session)

    # =========================================================================
    # Conversation Management
    # =========================================================================

    async def create_conversation(
        self,
        org_id: int,
        user_id: int,
        type: ConversationType = ConversationType.DIRECT,
        title: Optional[str] = None,
        participant_ids: Optional[List[int]] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
    ) -> Conversation:
        """
        Create a new conversation.

        WHAT: Creates a conversation thread with participants.

        WHY: Conversations organize messages into threads.

        Args:
            org_id: Organization ID
            user_id: User creating the conversation
            type: Conversation type
            title: Optional title for group/entity conversations
            participant_ids: Initial participant user IDs
            entity_type: Optional linked entity type (project, ticket)
            entity_id: Optional linked entity ID

        Returns:
            Created Conversation

        Raises:
            ValidationError: If validation fails
            MessageError: If creation fails
        """
        # Validate participants exist in same org
        if participant_ids:
            for pid in participant_ids:
                user = await self.user_dao.get_by_id_and_org(pid, org_id)
                if not user:
                    raise ValidationError(
                        message=f"User {pid} not found in organization",
                        details={"user_id": pid},
                    )

        # For direct conversations, ensure only 2 participants
        if type == ConversationType.DIRECT:
            if not participant_ids or len(participant_ids) != 1:
                raise ValidationError(
                    message="Direct conversations require exactly one other participant",
                    details={"participant_count": len(participant_ids) if participant_ids else 0},
                )

        # For group conversations, require title
        if type == ConversationType.GROUP and not title:
            raise ValidationError(
                message="Group conversations require a title",
            )

        # For entity conversations, require entity info
        if type in [ConversationType.PROJECT, ConversationType.TICKET]:
            if not entity_type or not entity_id:
                raise ValidationError(
                    message="Entity conversations require entity_type and entity_id",
                )

            # Check if conversation already exists for this entity
            existing = await self.conversation_dao.get_by_entity(
                entity_type, entity_id, org_id
            )
            if existing:
                raise ValidationError(
                    message="Conversation already exists for this entity",
                    details={"conversation_id": existing.id},
                )

        conversation = await self.conversation_dao.create_conversation(
            org_id=org_id,
            created_by=user_id,
            type=type,
            title=title,
            entity_type=entity_type,
            entity_id=entity_id,
            participant_ids=participant_ids,
        )

        return conversation

    async def get_or_create_direct_conversation(
        self,
        org_id: int,
        user_id: int,
        recipient_id: int,
        initial_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get or create a direct conversation between two users.

        WHAT: Finds existing or creates new direct conversation.

        WHY: Direct messages should reuse existing conversations.

        Args:
            org_id: Organization ID
            user_id: User initiating
            recipient_id: Recipient user ID
            initial_message: Optional first message

        Returns:
            Dict with conversation and optional initial message

        Raises:
            ValidationError: If recipient doesn't exist
        """
        # Validate recipient exists
        recipient = await self.user_dao.get_by_id_and_org(recipient_id, org_id)
        if not recipient:
            raise ValidationError(
                message="Recipient not found",
                details={"recipient_id": recipient_id},
            )

        if user_id == recipient_id:
            raise ValidationError(
                message="Cannot start conversation with yourself",
            )

        conversation = await self.conversation_dao.get_or_create_direct(
            org_id, user_id, recipient_id
        )

        result = {"conversation": conversation, "message": None}

        if initial_message:
            message = await self.send_message(
                conversation_id=conversation.id,
                org_id=org_id,
                user_id=user_id,
                content=initial_message,
            )
            result["message"] = message

        return result

    async def get_conversation(
        self,
        conversation_id: int,
        org_id: int,
        user_id: int,
    ) -> Conversation:
        """
        Get a conversation by ID.

        WHAT: Retrieves conversation details.

        WHY: View conversation information.

        Args:
            conversation_id: Conversation ID
            org_id: Organization ID
            user_id: Requesting user

        Returns:
            Conversation

        Raises:
            ConversationNotFoundError: If not found
            NotParticipantError: If user is not a participant
        """
        conversation = await self.conversation_dao.get_by_id_and_org(
            conversation_id, org_id
        )
        if not conversation:
            raise ConversationNotFoundError(
                message="Conversation not found",
                conversation_id=conversation_id,
            )

        # Check if user is a participant
        is_participant = await self.participant_dao.is_participant(
            conversation_id, user_id
        )
        if not is_participant:
            raise NotParticipantError(
                message="You are not a participant in this conversation",
                conversation_id=conversation_id,
                user_id=user_id,
            )

        return conversation

    async def get_user_conversations(
        self,
        user_id: int,
        org_id: int,
        type: Optional[ConversationType] = None,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get conversations for a user.

        WHAT: Lists user's conversations.

        WHY: Shows inbox/conversation list.

        Args:
            user_id: User ID
            org_id: Organization ID
            type: Optional type filter
            include_archived: Include archived conversations
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dict with conversations and metadata
        """
        conversations = await self.conversation_dao.get_user_conversations(
            user_id=user_id,
            org_id=org_id,
            type=type,
            include_archived=include_archived,
            skip=skip,
            limit=limit,
        )

        total_unread = await self.conversation_dao.count_unread_for_user(
            user_id, org_id
        )

        return {
            "items": conversations,
            "total_unread": total_unread,
            "skip": skip,
            "limit": limit,
        }

    async def get_conversation_for_entity(
        self,
        entity_type: str,
        entity_id: int,
        org_id: int,
        user_id: int,
    ) -> Optional[Conversation]:
        """
        Get conversation linked to an entity.

        WHAT: Finds conversation for project/ticket/etc.

        WHY: Context-aware messaging.

        Args:
            entity_type: Entity type (project, ticket)
            entity_id: Entity ID
            org_id: Organization ID
            user_id: Requesting user

        Returns:
            Conversation if exists and user is participant
        """
        conversation = await self.conversation_dao.get_by_entity(
            entity_type, entity_id, org_id
        )

        if conversation:
            is_participant = await self.participant_dao.is_participant(
                conversation.id, user_id
            )
            if not is_participant:
                return None

        return conversation

    async def archive_conversation(
        self,
        conversation_id: int,
        org_id: int,
        user_id: int,
    ) -> Conversation:
        """
        Archive a conversation.

        WHAT: Marks conversation as archived.

        WHY: Hide old conversations without deleting.

        Args:
            conversation_id: Conversation ID
            org_id: Organization ID
            user_id: Requesting user

        Returns:
            Updated conversation

        Raises:
            ConversationNotFoundError: If not found
            NotParticipantError: If not a participant
            AuthorizationError: If not admin
        """
        conversation = await self.get_conversation(
            conversation_id, org_id, user_id
        )

        # Check if user is admin of conversation
        participants = await self.participant_dao.get_participants(conversation_id)
        user_participant = next(
            (p for p in participants if p.user_id == user_id), None
        )

        if not user_participant or not user_participant.is_admin:
            raise AuthorizationError(
                message="Only conversation admins can archive conversations",
            )

        return await self.conversation_dao.archive_conversation(
            conversation_id, org_id
        )

    # =========================================================================
    # Participant Management
    # =========================================================================

    async def add_participants(
        self,
        conversation_id: int,
        org_id: int,
        user_id: int,
        user_ids_to_add: List[int],
    ) -> List[ConversationParticipant]:
        """
        Add participants to a conversation.

        WHAT: Adds users to conversation.

        WHY: Expand group conversations.

        Args:
            conversation_id: Conversation ID
            org_id: Organization ID
            user_id: Requesting user (must be admin)
            user_ids_to_add: User IDs to add

        Returns:
            List of new participants

        Raises:
            ConversationNotFoundError: If not found
            AuthorizationError: If not admin
            ValidationError: If invalid users
        """
        conversation = await self.get_conversation(
            conversation_id, org_id, user_id
        )

        # Can't add participants to direct conversations
        if conversation.type == ConversationType.DIRECT.value:
            raise ValidationError(
                message="Cannot add participants to direct conversations",
            )

        # Check if requester is admin
        participants = await self.participant_dao.get_participants(conversation_id)
        user_participant = next(
            (p for p in participants if p.user_id == user_id), None
        )

        if not user_participant or not user_participant.is_admin:
            raise AuthorizationError(
                message="Only conversation admins can add participants",
            )

        # Validate and add users
        added = []
        for uid in user_ids_to_add:
            user = await self.user_dao.get_by_id_and_org(uid, org_id)
            if not user:
                raise ValidationError(
                    message=f"User {uid} not found in organization",
                    details={"user_id": uid},
                )

            participant = await self.participant_dao.add_participant(
                conversation_id, uid
            )
            added.append(participant)

            # Send system message about user joining
            await self.message_dao.create_message(
                conversation_id=conversation_id,
                sender_id=user_id,
                content=f"{user.name} was added to the conversation",
                is_system=True,
            )

        return added

    async def remove_participant(
        self,
        conversation_id: int,
        org_id: int,
        user_id: int,
        user_id_to_remove: int,
    ) -> bool:
        """
        Remove a participant from a conversation.

        WHAT: Removes user from conversation.

        WHY: Leave or kick from group.

        Args:
            conversation_id: Conversation ID
            org_id: Organization ID
            user_id: Requesting user
            user_id_to_remove: User to remove

        Returns:
            True if removed

        Raises:
            AuthorizationError: If not admin and not self
        """
        conversation = await self.get_conversation(
            conversation_id, org_id, user_id
        )

        # Can remove self
        if user_id == user_id_to_remove:
            result = await self.participant_dao.remove_participant(
                conversation_id, user_id_to_remove
            )
            if result:
                user = await self.user_dao.get_by_id(user_id)
                await self.message_dao.create_message(
                    conversation_id=conversation_id,
                    sender_id=user_id,
                    content=f"{user.name if user else 'User'} left the conversation",
                    is_system=True,
                )
            return result

        # Otherwise must be admin
        participants = await self.participant_dao.get_participants(conversation_id)
        user_participant = next(
            (p for p in participants if p.user_id == user_id), None
        )

        if not user_participant or not user_participant.is_admin:
            raise AuthorizationError(
                message="Only conversation admins can remove participants",
            )

        result = await self.participant_dao.remove_participant(
            conversation_id, user_id_to_remove
        )

        if result:
            removed_user = await self.user_dao.get_by_id(user_id_to_remove)
            await self.message_dao.create_message(
                conversation_id=conversation_id,
                sender_id=user_id,
                content=f"{removed_user.name if removed_user else 'User'} was removed from the conversation",
                is_system=True,
            )

        return result

    async def get_participants(
        self,
        conversation_id: int,
        org_id: int,
        user_id: int,
    ) -> List[ConversationParticipant]:
        """
        Get conversation participants.

        WHAT: Lists participants.

        WHY: Show who's in conversation.

        Args:
            conversation_id: Conversation ID
            org_id: Organization ID
            user_id: Requesting user

        Returns:
            List of participants
        """
        # Verify user has access
        await self.get_conversation(conversation_id, org_id, user_id)

        return await self.participant_dao.get_participants(conversation_id)

    # =========================================================================
    # Message Management
    # =========================================================================

    async def send_message(
        self,
        conversation_id: int,
        org_id: int,
        user_id: int,
        content: str,
        reply_to_id: Optional[int] = None,
        attachment_ids: Optional[List[int]] = None,
    ) -> Message:
        """
        Send a message in a conversation.

        WHAT: Creates a new message.

        WHY: Core messaging functionality.

        Args:
            conversation_id: Conversation ID
            org_id: Organization ID
            user_id: Sender user ID
            content: Message content
            reply_to_id: Optional message ID to reply to
            attachment_ids: Optional document IDs to attach

        Returns:
            Created Message

        Raises:
            ConversationNotFoundError: If conversation not found
            NotParticipantError: If user is not a participant
            ValidationError: If validation fails
        """
        # Verify user has access
        await self.get_conversation(conversation_id, org_id, user_id)

        # Validate content
        if not content or not content.strip():
            raise ValidationError(
                message="Message content cannot be empty",
            )

        if len(content) > 5000:
            raise ValidationError(
                message="Message content exceeds maximum length",
                details={"max_length": 5000, "actual_length": len(content)},
            )

        # Validate reply target if provided
        if reply_to_id:
            reply_messages = await self.message_dao.get_conversation_messages(
                conversation_id, limit=1000
            )
            reply_target = next(
                (m for m in reply_messages if m.id == reply_to_id), None
            )
            if not reply_target:
                raise ValidationError(
                    message="Reply target message not found in this conversation",
                    details={"reply_to_id": reply_to_id},
                )

        # Create message
        message = await self.message_dao.create_message(
            conversation_id=conversation_id,
            sender_id=user_id,
            content=content.strip(),
            reply_to_id=reply_to_id,
            attachment_ids=attachment_ids,
        )

        return message

    async def get_messages(
        self,
        conversation_id: int,
        org_id: int,
        user_id: int,
        before_id: Optional[int] = None,
        after_id: Optional[int] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get messages in a conversation.

        WHAT: Retrieves message history.

        WHY: Display conversation messages.

        Args:
            conversation_id: Conversation ID
            org_id: Organization ID
            user_id: Requesting user
            before_id: Get messages before this ID
            after_id: Get messages after this ID
            limit: Max messages to return

        Returns:
            Dict with messages and pagination info
        """
        # Verify user has access
        await self.get_conversation(conversation_id, org_id, user_id)

        messages = await self.message_dao.get_conversation_messages(
            conversation_id=conversation_id,
            before_id=before_id,
            after_id=after_id,
            limit=limit + 1,  # Get one extra to check for more
        )

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        return {
            "items": messages,
            "conversation_id": conversation_id,
            "has_more_before": before_id is not None or (not before_id and has_more),
            "has_more_after": after_id is not None and has_more,
        }

    async def edit_message(
        self,
        message_id: int,
        org_id: int,
        user_id: int,
        new_content: str,
    ) -> Message:
        """
        Edit a message.

        WHAT: Updates message content.

        WHY: Allow editing own messages.

        Args:
            message_id: Message ID
            org_id: Organization ID
            user_id: Requesting user (must be sender)
            new_content: New message content

        Returns:
            Updated message

        Raises:
            MessageNotFoundError: If not found
            AuthorizationError: If not sender
        """
        if not new_content or not new_content.strip():
            raise ValidationError(
                message="Message content cannot be empty",
            )

        message = await self.message_dao.edit_message(
            message_id, user_id, new_content.strip()
        )

        if not message:
            raise MessageNotFoundError(
                message="Message not found or you are not the sender",
                message_id=message_id,
            )

        return message

    async def delete_message(
        self,
        message_id: int,
        org_id: int,
        user_id: int,
    ) -> bool:
        """
        Delete a message.

        WHAT: Soft-deletes a message.

        WHY: Hide unwanted messages.

        Args:
            message_id: Message ID
            org_id: Organization ID
            user_id: Requesting user (must be sender)

        Returns:
            True if deleted

        Raises:
            MessageNotFoundError: If not found
        """
        result = await self.message_dao.delete_message(message_id, user_id)

        if not result:
            raise MessageNotFoundError(
                message="Message not found or you are not the sender",
                message_id=message_id,
            )

        return result

    async def search_messages(
        self,
        org_id: int,
        user_id: int,
        query: str,
        limit: int = 50,
    ) -> List[Message]:
        """
        Search messages user can see.

        WHAT: Full-text message search.

        WHY: Find past messages.

        Args:
            org_id: Organization ID
            user_id: User ID
            query: Search query
            limit: Max results

        Returns:
            Matching messages
        """
        if not query or len(query) < 2:
            raise ValidationError(
                message="Search query must be at least 2 characters",
            )

        return await self.message_dao.search_messages(
            org_id, user_id, query, limit
        )

    # =========================================================================
    # Read Status Management
    # =========================================================================

    async def mark_conversation_read(
        self,
        conversation_id: int,
        org_id: int,
        user_id: int,
    ) -> None:
        """
        Mark all messages in a conversation as read.

        WHAT: Updates read status for conversation.

        WHY: Clear unread indicators.

        Args:
            conversation_id: Conversation ID
            org_id: Organization ID
            user_id: User ID
        """
        # Verify access
        await self.get_conversation(conversation_id, org_id, user_id)

        await self.participant_dao.mark_as_read(conversation_id, user_id)

    async def mark_message_read(
        self,
        message_id: int,
        org_id: int,
        user_id: int,
    ) -> MessageReadReceipt:
        """
        Mark a specific message as read.

        WHAT: Creates read receipt.

        WHY: Individual message read tracking.

        Args:
            message_id: Message ID
            org_id: Organization ID
            user_id: User ID

        Returns:
            Read receipt
        """
        # Get message to verify access
        message = await self.message_dao.get_by_id(message_id)
        if not message:
            raise MessageNotFoundError(
                message="Message not found",
                message_id=message_id,
            )

        # Verify user is participant
        is_participant = await self.participant_dao.is_participant(
            message.conversation_id, user_id
        )
        if not is_participant:
            raise NotParticipantError(
                message="You are not a participant in this conversation",
                conversation_id=message.conversation_id,
                user_id=user_id,
            )

        return await self.read_receipt_dao.mark_read(message_id, user_id)

    async def get_unread_count(
        self,
        org_id: int,
        user_id: int,
    ) -> Dict[str, int]:
        """
        Get unread message counts.

        WHAT: Gets unread statistics.

        WHY: Badge display.

        Args:
            org_id: Organization ID
            user_id: User ID

        Returns:
            Dict with unread counts
        """
        total = await self.conversation_dao.count_unread_for_user(user_id, org_id)

        # Count conversations with unread messages
        conversations = await self.conversation_dao.get_user_conversations(
            user_id, org_id, skip=0, limit=1000
        )
        with_unread = sum(
            1 for c in conversations
            if any(
                p.unread_count > 0
                for p in c.participants
                if p.user_id == user_id
            )
        )

        return {
            "total_unread": total,
            "conversation_count": with_unread,
        }
