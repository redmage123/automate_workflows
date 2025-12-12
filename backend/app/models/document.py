"""
Document management models.

WHAT: SQLAlchemy models for document storage and access control.

WHY: Documents are essential for client collaboration:
1. Share project specifications, contracts, assets
2. Attach files to tickets and proposals
3. Organize files in folders with tags
4. Control access with fine-grained permissions

HOW: Uses SQLAlchemy 2.0 with:
- S3 reference storage (files stored in S3, metadata in DB)
- Polymorphic entity associations (link to any entity type)
- Access control with expiration support
- Soft delete for data retention
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    BigInteger,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class DocumentAccessLevel(str, Enum):
    """
    Document access permission levels.

    WHAT: Defines what users can do with a document.

    WHY: Fine-grained access control:
    - VIEW: Can see document metadata and preview
    - DOWNLOAD: Can download the file
    - EDIT: Can update metadata and replace file
    """

    VIEW = "view"
    DOWNLOAD = "download"
    EDIT = "edit"


class Document(Base):
    """
    Document storage metadata.

    WHAT: Metadata for uploaded documents with S3 storage.

    WHY: Clients need to share documents (contracts, specifications, assets)
    with service providers. S3 provides scalable, secure storage.

    HOW: Stores file metadata in PostgreSQL, actual files in S3.
    Supports polymorphic associations to link documents to any entity.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    uploaded_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # File metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # S3 storage location
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(100), nullable=False)

    # Organization
    folder: Mapped[str] = mapped_column(String(255), default="/", nullable=False)
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), default=[])
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Polymorphic associations
    # WHY: Documents can be attached to projects, proposals, tickets, etc.
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    uploader: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by])
    access_records: Mapped[List["DocumentAccess"]] = relationship(
        "DocumentAccess", back_populates="document", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_documents_org_id", "org_id"),
        Index("ix_documents_folder", "folder"),
        Index("ix_documents_entity", "entity_type", "entity_id"),
        Index("ix_documents_uploaded_by", "uploaded_by"),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.filename}', org_id={self.org_id})>"

    @property
    def is_deleted(self) -> bool:
        """Check if document is soft-deleted."""
        return self.deleted_at is not None

    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return self.file_size / (1024 * 1024)

    @property
    def s3_url(self) -> str:
        """Get the S3 URL for the document."""
        return f"s3://{self.s3_bucket}/{self.s3_key}"


class DocumentAccess(Base):
    """
    Access control for documents.

    WHAT: Tracks who can view/download specific documents.

    WHY: Documents may contain sensitive information. Fine-grained
    access control ensures only authorized users can access them.

    HOW: Each record grants a specific access level to a user.
    Access can be time-limited with expires_at.
    """

    __tablename__ = "document_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    access_level: Mapped[DocumentAccessLevel] = mapped_column(
        SQLEnum(
            DocumentAccessLevel,
            name="documentaccesslevel",
            create_type=False,
            values_callable=lambda enum: [e.value for e in enum],
        ),
        default=DocumentAccessLevel.VIEW,
        nullable=False,
    )
    granted_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document", back_populates="access_records"
    )
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    grantor: Mapped["User"] = relationship("User", foreign_keys=[granted_by])

    # Indexes
    __table_args__ = (
        Index("ix_document_access_document_id", "document_id"),
        Index("ix_document_access_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentAccess(id={self.id}, "
            f"document_id={self.document_id}, "
            f"user_id={self.user_id}, "
            f"level={self.access_level.value})>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if access has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if access is still valid (not expired)."""
        return not self.is_expired
