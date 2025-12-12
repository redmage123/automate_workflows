"""
Message Data Access Object (DAO).

WHAT: Database operations for messaging models.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for messaging operations
3. Enforces org-scoping for multi-tenancy
4. Handles conversation and message queries

HOW: Extends BaseDAO with messaging-specific queries:
- Conversation management
- Message creation and retrieval
- Read status tracking
- Participant management
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.message import (
    Conversation,
    ConversationType,
    ConversationParticipant,
    Message,
    MessageReadReceipt,
)


class ConversationDAO(BaseDAO[Conversation]):
    """
    Data Access Object for Conversation model.

    WHAT: Provides operations for conversations.

    WHY: Centralizes conversation management.

    HOW: Extends BaseDAO with conversation-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize ConversationDAO."""
        super().__init__(Conversation, session)

    async def create_conversation(
        self,
        org_id: int,
        created_by: int,
        type: ConversationType = ConversationType.DIRECT,
        title: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        participant_ids: Optional[List[int]] = None,
    ) -> Conversation:
        """
        Create a new conversation.

        WHAT: Creates conversation with participants.

        WHY: Sets up messaging thread.

        Args:
            org_id: Organization ID
            created_by: User creating the conversation
            type: Conversation type
            title: Optional title
            entity_type: Optional linked entity type
            entity_id: Optional linked entity ID
            participant_ids: Initial participant IDs

        Returns:
            Created Conversation
        """
        conversation = await self.create(
            org_id=org_id,
            created_by=created_by,
            type=type.value if isinstance(type, ConversationType) else type,
            title=title,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        # Add creator as participant and admin
        participant_dao = ConversationParticipantDAO(self.session)
        await participant_dao.add_participant(
            conversation_id=conversation.id,
            user_id=created_by,
            is_admin=True,
        )

        # Add other participants
        if participant_ids:
            for user_id in participant_ids:
                if user_id != created_by:
                    await participant_dao.add_participant(
                        conversation_id=conversation.id,
                        user_id=user_id,
                    )

        await self.session.refresh(conversation)
        return conversation

    async def get_user_conversations(
        self,
        user_id: int,
        org_id: int,
        type: Optional[ConversationType] = None,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Conversation]:
        """
        Get conversations for a user.

        WHAT: Retrieves user's conversations.

        WHY: Shows inbox/conversation list.

        Args:
            user_id: User ID
            org_id: Organization ID
            type: Optional type filter
            include_archived: Include archived conversations
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of conversations
        """
        query = (
            select(Conversation)
            .join(ConversationParticipant)
            .where(
                Conversation.org_id == org_id,
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
            )
        )

        if type:
            query = query.where(
                Conversation.type == (type.value if isinstance(type, ConversationType) else type)
            )

        if not include_archived:
            query = query.where(Conversation.is_archived == False)

        query = query.order_by(Conversation.last_message_at.desc().nullslast())

        result = await self.session.execute(
            query.offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_or_create_direct(
        self,
        org_id: int,
        user1_id: int,
        user2_id: int,
    ) -> Conversation:
        """
        Get or create a direct conversation between two users.

        WHAT: Finds existing or creates new direct conversation.

        WHY: Direct messages should reuse existing conversations.

        Args:
            org_id: Organization ID
            user1_id: First user ID
            user2_id: Second user ID

        Returns:
            Existing or new Conversation
        """
        # Find existing direct conversation between these users
        subq1 = (
            select(ConversationParticipant.conversation_id)
            .where(ConversationParticipant.user_id == user1_id)
        )
        subq2 = (
            select(ConversationParticipant.conversation_id)
            .where(ConversationParticipant.user_id == user2_id)
        )

        result = await self.session.execute(
            select(Conversation)
            .where(
                Conversation.org_id == org_id,
                Conversation.type == ConversationType.DIRECT.value,
                Conversation.id.in_(subq1),
                Conversation.id.in_(subq2),
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # Create new direct conversation
        return await self.create_conversation(
            org_id=org_id,
            created_by=user1_id,
            type=ConversationType.DIRECT,
            participant_ids=[user2_id],
        )

    async def get_by_entity(
        self,
        entity_type: str,
        entity_id: int,
        org_id: int,
    ) -> Optional[Conversation]:
        """
        Get conversation linked to an entity.

        WHAT: Finds conversation for a project/ticket/etc.

        WHY: Entity-based conversations.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            org_id: Organization ID

        Returns:
            Conversation if exists
        """
        result = await self.session.execute(
            select(Conversation).where(
                Conversation.org_id == org_id,
                Conversation.entity_type == entity_type,
                Conversation.entity_id == entity_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_last_message(
        self,
        conversation_id: int,
        message_preview: str,
    ) -> None:
        """
        Update conversation's last message info.

        WHAT: Updates denormalized last message data.

        WHY: Performance optimization for listing.

        Args:
            conversation_id: Conversation ID
            message_preview: Preview text
        """
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                last_message_at=datetime.utcnow(),
                last_message_preview=message_preview[:200],
            )
        )
        await self.session.flush()

    async def archive_conversation(
        self,
        conversation_id: int,
        org_id: int,
    ) -> Optional[Conversation]:
        """
        Archive a conversation.

        WHAT: Marks conversation as archived.

        WHY: Hide old conversations without deleting.

        Args:
            conversation_id: Conversation ID
            org_id: Organization ID

        Returns:
            Updated conversation
        """
        conversation = await self.get_by_id_and_org(conversation_id, org_id)
        if conversation:
            conversation.is_archived = True
            await self.session.flush()
            await self.session.refresh(conversation)
        return conversation

    async def count_unread_for_user(
        self,
        user_id: int,
        org_id: int,
    ) -> int:
        """
        Count total unread messages for a user.

        WHAT: Gets unread message count.

        WHY: Badge display for notifications.

        Args:
            user_id: User ID
            org_id: Organization ID

        Returns:
            Unread count
        """
        result = await self.session.execute(
            select(func.sum(ConversationParticipant.unread_count))
            .join(Conversation)
            .where(
                Conversation.org_id == org_id,
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        return result.scalar_one() or 0


class ConversationParticipantDAO(BaseDAO[ConversationParticipant]):
    """
    Data Access Object for ConversationParticipant model.

    WHAT: Manages conversation participants.

    WHY: Handles join/leave and read status.
    """

    def __init__(self, session: AsyncSession):
        """Initialize ConversationParticipantDAO."""
        super().__init__(ConversationParticipant, session)

    async def add_participant(
        self,
        conversation_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> ConversationParticipant:
        """
        Add a participant to a conversation.

        WHAT: Creates participant record.

        WHY: Adds user to conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            is_admin: Whether user is admin

        Returns:
            Created participant
        """
        # Check if already a participant (may have left)
        result = await self.session.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Rejoin if left
            if existing.left_at:
                existing.left_at = None
                existing.joined_at = datetime.utcnow()
                await self.session.flush()
                await self.session.refresh(existing)
            return existing

        return await self.create(
            conversation_id=conversation_id,
            user_id=user_id,
            is_admin=is_admin,
        )

    async def remove_participant(
        self,
        conversation_id: int,
        user_id: int,
    ) -> bool:
        """
        Remove a participant from a conversation.

        WHAT: Marks participant as left.

        WHY: Soft-remove for history.

        Args:
            conversation_id: Conversation ID
            user_id: User ID

        Returns:
            True if removed
        """
        result = await self.session.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
            )
        )
        participant = result.scalar_one_or_none()

        if participant and not participant.left_at:
            participant.left_at = datetime.utcnow()
            await self.session.flush()
            return True
        return False

    async def get_participants(
        self,
        conversation_id: int,
        active_only: bool = True,
    ) -> List[ConversationParticipant]:
        """
        Get conversation participants.

        WHAT: Lists participants.

        WHY: Show who's in conversation.

        Args:
            conversation_id: Conversation ID
            active_only: Only active participants

        Returns:
            List of participants
        """
        query = select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id
        )

        if active_only:
            query = query.where(ConversationParticipant.left_at.is_(None))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def is_participant(
        self,
        conversation_id: int,
        user_id: int,
    ) -> bool:
        """
        Check if user is a participant.

        WHAT: Validates participation.

        WHY: Access control.

        Args:
            conversation_id: Conversation ID
            user_id: User ID

        Returns:
            True if active participant
        """
        result = await self.session.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None

    async def mark_as_read(
        self,
        conversation_id: int,
        user_id: int,
    ) -> None:
        """
        Mark conversation as read for a user.

        WHAT: Updates read status.

        WHY: Tracks read state.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
        """
        await self.session.execute(
            update(ConversationParticipant)
            .where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
            )
            .values(
                last_read_at=datetime.utcnow(),
                unread_count=0,
            )
        )
        await self.session.flush()

    async def increment_unread(
        self,
        conversation_id: int,
        exclude_user_id: int,
    ) -> None:
        """
        Increment unread count for all participants except sender.

        WHAT: Updates unread counts.

        WHY: Notification tracking.

        Args:
            conversation_id: Conversation ID
            exclude_user_id: Sender to exclude
        """
        await self.session.execute(
            update(ConversationParticipant)
            .where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id != exclude_user_id,
                ConversationParticipant.left_at.is_(None),
            )
            .values(
                unread_count=ConversationParticipant.unread_count + 1,
            )
        )
        await self.session.flush()


class MessageDAO(BaseDAO[Message]):
    """
    Data Access Object for Message model.

    WHAT: Provides operations for messages.

    WHY: Centralizes message management.

    HOW: Extends BaseDAO with message-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """Initialize MessageDAO."""
        super().__init__(Message, session)

    async def create_message(
        self,
        conversation_id: int,
        sender_id: int,
        content: str,
        reply_to_id: Optional[int] = None,
        attachment_ids: Optional[List[int]] = None,
        is_system: bool = False,
    ) -> Message:
        """
        Create a new message.

        WHAT: Creates message in conversation.

        WHY: Send messages.

        Args:
            conversation_id: Conversation ID
            sender_id: Sender user ID
            content: Message content
            reply_to_id: Optional reply target
            attachment_ids: Optional attachment document IDs
            is_system: Whether system message

        Returns:
            Created Message
        """
        message = await self.create(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            reply_to_id=reply_to_id,
            attachment_ids=attachment_ids,
            is_system=is_system,
        )

        # Update conversation's last message
        conv_dao = ConversationDAO(self.session)
        await conv_dao.update_last_message(
            conversation_id,
            content[:200],
        )

        # Increment unread for other participants
        if not is_system:
            participant_dao = ConversationParticipantDAO(self.session)
            await participant_dao.increment_unread(conversation_id, sender_id)

        return message

    async def get_conversation_messages(
        self,
        conversation_id: int,
        before_id: Optional[int] = None,
        after_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Message]:
        """
        Get messages in a conversation.

        WHAT: Retrieves conversation messages.

        WHY: Display message history.

        Args:
            conversation_id: Conversation ID
            before_id: Get messages before this ID
            after_id: Get messages after this ID
            limit: Max messages to return

        Returns:
            List of messages
        """
        query = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.is_deleted == False,
        )

        if before_id:
            query = query.where(Message.id < before_id)
        if after_id:
            query = query.where(Message.id > after_id)

        query = query.order_by(Message.created_at.desc()).limit(limit)

        result = await self.session.execute(query)
        messages = list(result.scalars().all())

        # Return in chronological order
        return list(reversed(messages))

    async def edit_message(
        self,
        message_id: int,
        sender_id: int,
        new_content: str,
    ) -> Optional[Message]:
        """
        Edit a message.

        WHAT: Updates message content.

        WHY: Allow editing own messages.

        Args:
            message_id: Message ID
            sender_id: Must be sender
            new_content: New content

        Returns:
            Updated message or None
        """
        result = await self.session.execute(
            select(Message).where(
                Message.id == message_id,
                Message.sender_id == sender_id,
            )
        )
        message = result.scalar_one_or_none()

        if not message or message.is_deleted:
            return None

        message.content = new_content
        message.is_edited = True
        message.edited_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def delete_message(
        self,
        message_id: int,
        sender_id: int,
    ) -> bool:
        """
        Soft-delete a message.

        WHAT: Marks message as deleted.

        WHY: Hide without removing.

        Args:
            message_id: Message ID
            sender_id: Must be sender

        Returns:
            True if deleted
        """
        result = await self.session.execute(
            select(Message).where(
                Message.id == message_id,
                Message.sender_id == sender_id,
            )
        )
        message = result.scalar_one_or_none()

        if not message:
            return False

        message.is_deleted = True
        message.deleted_at = datetime.utcnow()
        await self.session.flush()
        return True

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
        search_pattern = f"%{query}%"

        result = await self.session.execute(
            select(Message)
            .join(Conversation)
            .join(ConversationParticipant)
            .where(
                Conversation.org_id == org_id,
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
                Message.is_deleted == False,
                Message.content.ilike(search_pattern),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class MessageReadReceiptDAO(BaseDAO[MessageReadReceipt]):
    """
    Data Access Object for MessageReadReceipt.

    WHAT: Tracks message read status.

    WHY: Read receipts for messages.
    """

    def __init__(self, session: AsyncSession):
        """Initialize MessageReadReceiptDAO."""
        super().__init__(MessageReadReceipt, session)

    async def mark_read(
        self,
        message_id: int,
        user_id: int,
    ) -> MessageReadReceipt:
        """
        Mark a message as read.

        WHAT: Creates read receipt.

        WHY: Track read status.

        Args:
            message_id: Message ID
            user_id: User ID

        Returns:
            Read receipt
        """
        # Check if already read
        result = await self.session.execute(
            select(MessageReadReceipt).where(
                MessageReadReceipt.message_id == message_id,
                MessageReadReceipt.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        return await self.create(
            message_id=message_id,
            user_id=user_id,
        )

    async def get_readers(
        self,
        message_id: int,
    ) -> List[MessageReadReceipt]:
        """
        Get who has read a message.

        WHAT: Lists read receipts.

        WHY: Show read status.

        Args:
            message_id: Message ID

        Returns:
            List of read receipts
        """
        result = await self.session.execute(
            select(MessageReadReceipt).where(
                MessageReadReceipt.message_id == message_id
            )
        )
        return list(result.scalars().all())
