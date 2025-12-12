"""
Message models.

WHAT: SQLAlchemy models for in-app messaging and conversations.

WHY: In-app messaging enables:
1. Direct communication between team members
2. Client-provider conversations
3. Context-aware messaging (linked to projects/tickets)
4. Reduced email dependency

HOW: Uses SQLAlchemy 2.0 with:
- Conversation-based organization
- Message threading
- Read status tracking
- Entity associations (projects, tickets)
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class ConversationType(str, Enum):
    """
    Conversation types.

    WHAT: Categorizes conversations.

    WHY: Different types have different behaviors:
    - DIRECT: One-to-one messaging
    - GROUP: Multiple participants
    - PROJECT: Linked to a project
    - TICKET: Linked to a ticket
    - SUPPORT: Support channel
    """

    DIRECT = "direct"
    GROUP = "group"
    PROJECT = "project"
    TICKET = "ticket"
    SUPPORT = "support"


class Conversation(Base):
    """
    Conversation/thread model.

    WHAT: Groups messages into conversations.

    WHY: Conversations provide:
    - Message organization
    - Participant management
    - Read status per user
    - Entity linking

    HOW: Each conversation has participants and messages.
    Can be linked to projects, tickets, or be direct messages.
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )

    # Type and title
    type: Mapped[ConversationType] = mapped_column(
        String(20), default=ConversationType.DIRECT.value, nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Entity association (polymorphic)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Creator
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Latest message info (denormalized for performance)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_message_preview: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )

    # Status
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    participants: Mapped[List["ConversationParticipant"]] = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_conversations_org_id", "org_id"),
        Index("ix_conversations_created_by", "created_by"),
        Index("ix_conversations_entity", "entity_type", "entity_id"),
        Index("ix_conversations_last_message", "last_message_at"),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, type={self.type}, title='{self.title}')>"

    @property
    def participant_count(self) -> int:
        """Get number of active participants."""
        return len([p for p in self.participants if not p.left_at])


class ConversationParticipant(Base):
    """
    Conversation participant.

    WHAT: Tracks who is in a conversation.

    WHY: Participants can:
    - Join/leave conversations
    - Have individual read status
    - Mute notifications
    """

    __tablename__ = "conversation_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Join/leave tracking
    joined_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Read status
    last_read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Notifications
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Role in conversation
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="participants"
    )
    user: Mapped["User"] = relationship("User")

    # Indexes
    __table_args__ = (
        Index("ix_conv_participants_conversation_id", "conversation_id"),
        Index("ix_conv_participants_user_id", "user_id"),
        Index(
            "ix_conv_participants_unique",
            "conversation_id",
            "user_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationParticipant("
            f"conversation_id={self.conversation_id}, "
            f"user_id={self.user_id})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if participant is still in conversation."""
        return self.left_at is None


class Message(Base):
    """
    Message model.

    WHAT: Individual message in a conversation.

    WHY: Messages are the core unit of communication:
    - Contain text content
    - Support attachments (via documents)
    - Track read status
    - Support replies/threading
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Reply threading
    reply_to_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("messages.id"), nullable=True
    )

    # Attachments (document IDs)
    attachment_ids: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer), nullable=True
    )

    # Status
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # System message (for join/leave notifications)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    reply_to: Mapped[Optional["Message"]] = relationship(
        "Message", remote_side=[id], backref="replies"
    )

    # Indexes
    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_sender_id", "sender_id"),
        Index("ix_messages_created_at", "created_at"),
        Index("ix_messages_reply_to_id", "reply_to_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Message(id={self.id}, "
            f"conversation_id={self.conversation_id}, "
            f"sender_id={self.sender_id})>"
        )

    @property
    def content_preview(self) -> str:
        """Get a preview of the message content."""
        if self.is_deleted:
            return "[Message deleted]"
        if len(self.content) > 100:
            return self.content[:97] + "..."
        return self.content


class MessageReadReceipt(Base):
    """
    Read receipt for a message.

    WHAT: Tracks who has read which messages.

    WHY: Enables read receipts for:
    - Showing read status indicators
    - Tracking engagement
    - Notification management
    """

    __tablename__ = "message_read_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Indexes
    __table_args__ = (
        Index("ix_msg_read_receipts_message_id", "message_id"),
        Index("ix_msg_read_receipts_user_id", "user_id"),
        Index(
            "ix_msg_read_receipts_unique",
            "message_id",
            "user_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<MessageReadReceipt(message_id={self.message_id}, "
            f"user_id={self.user_id})>"
        )
