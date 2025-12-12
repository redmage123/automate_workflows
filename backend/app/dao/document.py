"""
Document Data Access Object (DAO).

WHAT: Database operations for Document and DocumentAccess models.

WHY: The DAO pattern:
1. Separates data access from business logic
2. Provides consistent API for document operations
3. Enforces org-scoping for multi-tenancy
4. Handles soft delete and access control

HOW: Extends BaseDAO with document-specific queries:
- Entity association (polymorphic)
- Access control management
- Folder/tag organization
- Soft delete support
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dao.base import BaseDAO
from app.models.document import Document, DocumentAccess, DocumentAccessLevel


class DocumentDAO(BaseDAO[Document]):
    """
    Data Access Object for Document model.

    WHAT: Provides CRUD and query operations for documents.

    WHY: Centralizes all document database operations:
    - Enforces org_id scoping for security
    - Handles soft delete
    - Provides entity-based filtering

    HOW: Extends BaseDAO with document-specific methods.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize DocumentDAO.

        Args:
            session: Async database session
        """
        super().__init__(Document, session)

    async def create_document(
        self,
        org_id: int,
        uploaded_by: int,
        filename: str,
        original_filename: str,
        content_type: str,
        file_size: int,
        s3_key: str,
        s3_bucket: str,
        folder: str = "/",
        tags: Optional[List[str]] = None,
        description: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
    ) -> Document:
        """
        Create a new document record.

        WHAT: Creates document metadata after file upload to S3.

        WHY: Separates file storage (S3) from metadata (DB).

        Args:
            org_id: Organization that owns this document
            uploaded_by: User who uploaded the file
            filename: Stored filename (may be sanitized)
            original_filename: Original name from upload
            content_type: MIME type
            file_size: Size in bytes
            s3_key: S3 object key
            s3_bucket: S3 bucket name
            folder: Organization folder path
            tags: List of tags
            description: Optional description
            entity_type: Optional linked entity type
            entity_id: Optional linked entity ID

        Returns:
            Created Document
        """
        return await self.create(
            org_id=org_id,
            uploaded_by=uploaded_by,
            filename=filename,
            original_filename=original_filename,
            content_type=content_type,
            file_size=file_size,
            s3_key=s3_key,
            s3_bucket=s3_bucket,
            folder=folder,
            tags=tags or [],
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    async def get_by_org(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> List[Document]:
        """
        Get documents for an organization.

        WHAT: Retrieves org documents with optional soft-delete filter.

        WHY: Standard list view excludes soft-deleted documents.

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit
            include_deleted: Whether to include soft-deleted documents

        Returns:
            List of documents
        """
        query = select(Document).where(Document.org_id == org_id)

        if not include_deleted:
            query = query.where(Document.deleted_at.is_(None))

        query = (
            query.order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_entity(
        self,
        entity_type: str,
        entity_id: int,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """
        Get documents attached to a specific entity.

        WHAT: Retrieves documents linked to a project/ticket/etc.

        WHY: Shows all documents related to a specific item.

        Args:
            entity_type: Entity type (project, ticket, etc.)
            entity_id: Entity ID
            org_id: Organization ID for security
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of documents for the entity
        """
        result = await self.session.execute(
            select(Document)
            .where(
                Document.org_id == org_id,
                Document.entity_type == entity_type,
                Document.entity_id == entity_id,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_folder(
        self,
        org_id: int,
        folder: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """
        Get documents in a specific folder.

        WHAT: Retrieves documents by folder path.

        WHY: Enables folder-based document organization.

        Args:
            org_id: Organization ID
            folder: Folder path (e.g., "/projects/website")
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of documents in the folder
        """
        result = await self.session.execute(
            select(Document)
            .where(
                Document.org_id == org_id,
                Document.folder == folder,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.filename)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_tags(
        self,
        org_id: int,
        tags: List[str],
        match_all: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """
        Get documents matching tags.

        WHAT: Retrieves documents by tag filtering.

        WHY: Enables tag-based document discovery.

        Args:
            org_id: Organization ID
            tags: List of tags to filter by
            match_all: If True, document must have all tags
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of matching documents
        """
        query = select(Document).where(
            Document.org_id == org_id,
            Document.deleted_at.is_(None),
        )

        if match_all:
            # Document must have all specified tags
            query = query.where(Document.tags.contains(tags))
        else:
            # Document must have at least one of the tags
            query = query.where(Document.tags.overlap(tags))

        result = await self.session.execute(
            query.order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_accessible_for_user(
        self,
        user_id: int,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """
        Get documents accessible to a specific user.

        WHAT: Retrieves documents where user has explicit access.

        WHY: Used for users who need access to specific documents
        without org-wide access.

        Args:
            user_id: User ID
            org_id: Organization ID
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of accessible documents
        """
        result = await self.session.execute(
            select(Document)
            .join(DocumentAccess)
            .where(
                Document.org_id == org_id,
                DocumentAccess.user_id == user_id,
                or_(
                    DocumentAccess.expires_at.is_(None),
                    DocumentAccess.expires_at > datetime.utcnow(),
                ),
                Document.deleted_at.is_(None),
            )
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def soft_delete(self, document_id: int, org_id: int) -> Optional[Document]:
        """
        Soft-delete a document.

        WHAT: Marks document as deleted without removing data.

        WHY: Preserves document history while hiding from views.
        Allows for potential recovery.

        Args:
            document_id: Document ID
            org_id: Organization ID for security

        Returns:
            Updated document or None if not found
        """
        document = await self.get_by_id_and_org(document_id, org_id)
        if not document:
            return None

        document.deleted_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def restore(self, document_id: int, org_id: int) -> Optional[Document]:
        """
        Restore a soft-deleted document.

        WHAT: Removes soft-delete flag.

        WHY: Allows recovery of accidentally deleted documents.

        Args:
            document_id: Document ID
            org_id: Organization ID for security

        Returns:
            Restored document or None if not found
        """
        result = await self.session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.org_id == org_id,
            )
        )
        document = result.scalar_one_or_none()
        if not document:
            return None

        document.deleted_at = None
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def update_metadata(
        self,
        document_id: int,
        org_id: int,
        folder: Optional[str] = None,
        tags: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> Optional[Document]:
        """
        Update document metadata.

        WHAT: Updates folder, tags, or description.

        WHY: Allows reorganization without re-uploading.

        Args:
            document_id: Document ID
            org_id: Organization ID for security
            folder: New folder path (if provided)
            tags: New tags list (if provided)
            description: New description (if provided)

        Returns:
            Updated document or None if not found
        """
        document = await self.get_by_id_and_org(document_id, org_id)
        if not document:
            return None

        if folder is not None:
            document.folder = folder
        if tags is not None:
            document.tags = tags
        if description is not None:
            document.description = description

        document.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def count_by_org(self, org_id: int, include_deleted: bool = False) -> int:
        """
        Count documents for an organization.

        Args:
            org_id: Organization ID
            include_deleted: Whether to include soft-deleted documents

        Returns:
            Document count
        """
        query = select(func.count(Document.id)).where(Document.org_id == org_id)

        if not include_deleted:
            query = query.where(Document.deleted_at.is_(None))

        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_storage_usage(self, org_id: int) -> int:
        """
        Get total storage used by organization.

        WHAT: Sums file sizes for all non-deleted documents.

        WHY: Useful for storage quotas and billing.

        Args:
            org_id: Organization ID

        Returns:
            Total bytes used
        """
        result = await self.session.execute(
            select(func.coalesce(func.sum(Document.file_size), 0)).where(
                Document.org_id == org_id,
                Document.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    async def search(
        self,
        org_id: int,
        query: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """
        Search documents by filename or description.

        WHAT: Full-text search on document metadata.

        WHY: Enables users to find documents quickly.

        Args:
            org_id: Organization ID
            query: Search query string
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of matching documents
        """
        search_pattern = f"%{query}%"
        result = await self.session.execute(
            select(Document)
            .where(
                Document.org_id == org_id,
                Document.deleted_at.is_(None),
                or_(
                    Document.filename.ilike(search_pattern),
                    Document.original_filename.ilike(search_pattern),
                    Document.description.ilike(search_pattern),
                ),
            )
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


class DocumentAccessDAO(BaseDAO[DocumentAccess]):
    """
    Data Access Object for DocumentAccess model.

    WHAT: Provides operations for document access control.

    WHY: Fine-grained access control for documents.

    HOW: Manages access grants with expiration support.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize DocumentAccessDAO.

        Args:
            session: Async database session
        """
        super().__init__(DocumentAccess, session)

    async def grant_access(
        self,
        document_id: int,
        user_id: int,
        granted_by: int,
        access_level: DocumentAccessLevel = DocumentAccessLevel.VIEW,
        expires_at: Optional[datetime] = None,
    ) -> DocumentAccess:
        """
        Grant document access to a user.

        WHAT: Creates an access record for a user.

        WHY: Allows sharing documents with specific users.

        Args:
            document_id: Document ID
            user_id: User to grant access to
            granted_by: User granting the access
            access_level: Level of access
            expires_at: Optional expiration time

        Returns:
            Created DocumentAccess
        """
        # Check if access already exists
        existing = await self.get_user_access(document_id, user_id)
        if existing:
            # Update existing access
            existing.access_level = access_level
            existing.expires_at = expires_at
            existing.granted_by = granted_by
            existing.granted_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        return await self.create(
            document_id=document_id,
            user_id=user_id,
            granted_by=granted_by,
            access_level=access_level,
            expires_at=expires_at,
        )

    async def revoke_access(self, document_id: int, user_id: int) -> bool:
        """
        Revoke document access from a user.

        WHAT: Removes a user's access to a document.

        WHY: Stop sharing when access is no longer needed.

        Args:
            document_id: Document ID
            user_id: User to revoke access from

        Returns:
            True if access was revoked, False if not found
        """
        result = await self.session.execute(
            select(DocumentAccess).where(
                DocumentAccess.document_id == document_id,
                DocumentAccess.user_id == user_id,
            )
        )
        access = result.scalar_one_or_none()
        if not access:
            return False

        await self.session.delete(access)
        await self.session.flush()
        return True

    async def get_user_access(
        self,
        document_id: int,
        user_id: int,
    ) -> Optional[DocumentAccess]:
        """
        Get a user's access record for a document.

        WHAT: Retrieves the access record if exists.

        WHY: Check what level of access a user has.

        Args:
            document_id: Document ID
            user_id: User ID

        Returns:
            DocumentAccess if exists, None otherwise
        """
        result = await self.session.execute(
            select(DocumentAccess).where(
                DocumentAccess.document_id == document_id,
                DocumentAccess.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def check_access(
        self,
        document_id: int,
        user_id: int,
        required_level: DocumentAccessLevel = DocumentAccessLevel.VIEW,
    ) -> bool:
        """
        Check if user has required access level.

        WHAT: Verifies user has sufficient permissions.

        WHY: Authorization check before allowing operations.

        Args:
            document_id: Document ID
            user_id: User ID
            required_level: Minimum required access level

        Returns:
            True if user has access, False otherwise
        """
        access = await self.get_user_access(document_id, user_id)
        if not access:
            return False

        if access.is_expired:
            return False

        # Access levels are ordered: VIEW < DOWNLOAD < EDIT
        level_order = {
            DocumentAccessLevel.VIEW: 0,
            DocumentAccessLevel.DOWNLOAD: 1,
            DocumentAccessLevel.EDIT: 2,
        }

        return level_order[access.access_level] >= level_order[required_level]

    async def get_document_access_list(
        self,
        document_id: int,
    ) -> List[DocumentAccess]:
        """
        Get all access records for a document.

        WHAT: Lists all users with access to a document.

        WHY: Shows document sharing status.

        Args:
            document_id: Document ID

        Returns:
            List of access records
        """
        result = await self.session.execute(
            select(DocumentAccess)
            .where(DocumentAccess.document_id == document_id)
            .order_by(DocumentAccess.granted_at.desc())
        )
        return list(result.scalars().all())

    async def get_user_documents_access(
        self,
        user_id: int,
    ) -> List[DocumentAccess]:
        """
        Get all documents a user has access to.

        WHAT: Lists all access grants for a user.

        WHY: Shows what documents a user can access.

        Args:
            user_id: User ID

        Returns:
            List of access records
        """
        result = await self.session.execute(
            select(DocumentAccess)
            .where(
                DocumentAccess.user_id == user_id,
                or_(
                    DocumentAccess.expires_at.is_(None),
                    DocumentAccess.expires_at > datetime.utcnow(),
                ),
            )
            .order_by(DocumentAccess.granted_at.desc())
        )
        return list(result.scalars().all())

    async def cleanup_expired(self) -> int:
        """
        Remove expired access records.

        WHAT: Deletes access records past their expiration.

        WHY: Cleanup task to remove stale access grants.

        Returns:
            Number of records deleted
        """
        from sqlalchemy import delete

        result = await self.session.execute(
            delete(DocumentAccess).where(
                DocumentAccess.expires_at.isnot(None),
                DocumentAccess.expires_at < datetime.utcnow(),
            )
        )
        await self.session.flush()
        return result.rowcount
