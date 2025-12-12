"""
Document Service.

WHAT: Business logic for document management with S3 storage.

WHY: The service layer:
1. Encapsulates document business logic
2. Handles S3 operations (upload, download, delete)
3. Manages access control
4. Provides presigned URLs

HOW: Coordinates between DocumentDAO and S3 client,
enforcing access rules and providing storage abstraction.
"""

import uuid
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, BinaryIO
from sqlalchemy.ext.asyncio import AsyncSession
import boto3
from botocore.exceptions import ClientError

from app.dao.document import DocumentDAO, DocumentAccessDAO
from app.dao.user import UserDAO
from app.models.document import Document, DocumentAccess, DocumentAccessLevel
from app.core.config import settings
from app.core.exceptions import (
    DocumentNotFoundError,
    DocumentAccessDeniedError,
    DocumentUploadError,
    DocumentStorageError,
    ValidationError,
)


class DocumentService:
    """
    Service for document management.

    WHAT: Provides business logic for document operations.

    WHY: Documents are a core collaboration feature:
    - Share files with team members
    - Attach to projects/tickets/proposals
    - Control access with permissions

    HOW: Uses S3 for file storage, PostgreSQL for metadata.
    Access control is enforced at service layer.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize DocumentService.

        Args:
            session: Async database session
        """
        self.session = session
        self.document_dao = DocumentDAO(session)
        self.access_dao = DocumentAccessDAO(session)
        self.user_dao = UserDAO(session)

        # Initialize S3 client
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.bucket_name = settings.S3_BUCKET_NAME

    def _generate_s3_key(
        self,
        org_id: int,
        filename: str,
        folder: str = "/",
    ) -> str:
        """
        Generate a unique S3 key for a document.

        WHAT: Creates a unique path in S3.

        WHY: Prevents filename collisions and organizes by org.

        Args:
            org_id: Organization ID
            filename: Original filename
            folder: Folder path

        Returns:
            S3 key string
        """
        # Sanitize folder path
        folder = folder.strip("/")
        if folder:
            folder = f"{folder}/"

        # Generate unique filename with UUID prefix
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = filename.replace(" ", "_")

        return f"orgs/{org_id}/documents/{folder}{unique_id}_{safe_filename}"

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for storage.

        WHAT: Removes potentially dangerous characters.

        WHY: Security - prevents path traversal and encoding issues.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path separators and null bytes
        filename = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")

        # Limit length
        if len(filename) > 200:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = f"{name[:190]}.{ext}" if ext else name[:200]

        return filename

    async def upload_document(
        self,
        org_id: int,
        user_id: int,
        file: BinaryIO,
        filename: str,
        content_type: str,
        folder: str = "/",
        tags: Optional[List[str]] = None,
        description: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
    ) -> Document:
        """
        Upload a document to S3 and create metadata.

        WHAT: Stores file in S3 and creates DB record.

        WHY: Single operation for complete document upload.

        Args:
            org_id: Organization ID
            user_id: User uploading the document
            file: File content (binary IO)
            filename: Original filename
            content_type: MIME type
            folder: Organization folder path
            tags: Optional tags
            description: Optional description
            entity_type: Optional entity type to attach to
            entity_id: Optional entity ID to attach to

        Returns:
            Created Document

        Raises:
            DocumentUploadError: If upload fails
            DocumentStorageError: If S3 operation fails
        """
        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)

        # Generate S3 key
        s3_key = self._generate_s3_key(org_id, safe_filename, folder)

        # Get file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning

        # Validate file size (e.g., 100MB limit)
        max_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_size:
            raise DocumentUploadError(
                message=f"File size exceeds maximum allowed ({max_size / 1024 / 1024}MB)",
                file_size=file_size,
                max_size=max_size,
            )

        # Upload to S3
        try:
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "Metadata": {
                        "org_id": str(org_id),
                        "uploaded_by": str(user_id),
                    },
                },
            )
        except ClientError as e:
            raise DocumentStorageError(
                message="Failed to upload file to storage",
                error=str(e),
            )

        # Create database record
        try:
            document = await self.document_dao.create_document(
                org_id=org_id,
                uploaded_by=user_id,
                filename=safe_filename,
                original_filename=filename,
                content_type=content_type,
                file_size=file_size,
                s3_key=s3_key,
                s3_bucket=self.bucket_name,
                folder=folder,
                tags=tags,
                description=description,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            return document
        except Exception as e:
            # Clean up S3 if DB creation fails
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            except Exception:
                pass
            raise DocumentUploadError(
                message="Failed to create document record",
                error=str(e),
            )

    async def get_document(
        self,
        document_id: int,
        org_id: int,
        user_id: int,
        check_access: bool = True,
    ) -> Document:
        """
        Get document metadata.

        WHAT: Retrieves document details by ID.

        WHY: View document information without downloading.

        Args:
            document_id: Document ID
            org_id: Organization ID
            user_id: Requesting user ID
            check_access: Whether to verify user has access

        Returns:
            Document

        Raises:
            DocumentNotFoundError: If document doesn't exist
            DocumentAccessDeniedError: If user lacks access
        """
        document = await self.document_dao.get_by_id_and_org(document_id, org_id)
        if not document or document.is_deleted:
            raise DocumentNotFoundError(
                message="Document not found",
                document_id=document_id,
            )

        if check_access:
            # Document owner always has access
            if document.uploaded_by != user_id:
                has_access = await self.access_dao.check_access(
                    document_id, user_id, DocumentAccessLevel.VIEW
                )
                if not has_access:
                    raise DocumentAccessDeniedError(
                        message="You don't have access to this document",
                        document_id=document_id,
                    )

        return document

    async def get_download_url(
        self,
        document_id: int,
        org_id: int,
        user_id: int,
        expires_in: int = 3600,
    ) -> str:
        """
        Generate presigned download URL.

        WHAT: Creates a temporary S3 URL for downloading.

        WHY: Allows direct download from S3 without proxying.

        Args:
            document_id: Document ID
            org_id: Organization ID
            user_id: Requesting user ID
            expires_in: URL expiration in seconds (default 1 hour)

        Returns:
            Presigned S3 URL

        Raises:
            DocumentNotFoundError: If document doesn't exist
            DocumentAccessDeniedError: If user lacks download access
        """
        document = await self.get_document(document_id, org_id, user_id)

        # Check download permission
        if document.uploaded_by != user_id:
            has_access = await self.access_dao.check_access(
                document_id, user_id, DocumentAccessLevel.DOWNLOAD
            )
            if not has_access:
                raise DocumentAccessDeniedError(
                    message="You don't have download access to this document",
                    document_id=document_id,
                )

        # Generate presigned URL
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": document.s3_bucket,
                    "Key": document.s3_key,
                    "ResponseContentDisposition": f'attachment; filename="{document.original_filename}"',
                },
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            raise DocumentStorageError(
                message="Failed to generate download URL",
                error=str(e),
            )

    async def delete_document(
        self,
        document_id: int,
        org_id: int,
        user_id: int,
        hard_delete: bool = False,
    ) -> None:
        """
        Delete a document.

        WHAT: Soft-deletes (default) or hard-deletes a document.

        WHY: Soft delete preserves history; hard delete frees storage.

        Args:
            document_id: Document ID
            org_id: Organization ID
            user_id: Requesting user ID
            hard_delete: If True, permanently delete from S3

        Raises:
            DocumentNotFoundError: If document doesn't exist
            DocumentAccessDeniedError: If user lacks edit access
        """
        document = await self.get_document(
            document_id, org_id, user_id, check_access=False
        )

        # Only owner can delete
        if document.uploaded_by != user_id:
            has_access = await self.access_dao.check_access(
                document_id, user_id, DocumentAccessLevel.EDIT
            )
            if not has_access:
                raise DocumentAccessDeniedError(
                    message="You don't have permission to delete this document",
                    document_id=document_id,
                )

        if hard_delete:
            # Delete from S3
            try:
                self.s3_client.delete_object(
                    Bucket=document.s3_bucket,
                    Key=document.s3_key,
                )
            except ClientError as e:
                raise DocumentStorageError(
                    message="Failed to delete file from storage",
                    error=str(e),
                )

            # Hard delete from DB
            await self.document_dao.delete(document_id)
        else:
            # Soft delete
            await self.document_dao.soft_delete(document_id, org_id)

    async def share_document(
        self,
        document_id: int,
        org_id: int,
        user_id: int,
        share_with: List[int],
        access_level: DocumentAccessLevel = DocumentAccessLevel.VIEW,
        expires_at: Optional[datetime] = None,
    ) -> List[DocumentAccess]:
        """
        Share document with users.

        WHAT: Grants access to specified users.

        WHY: Enables document sharing with team members.

        Args:
            document_id: Document ID
            org_id: Organization ID
            user_id: User sharing the document
            share_with: List of user IDs to share with
            access_level: Level of access to grant
            expires_at: Optional expiration time

        Returns:
            List of created access records

        Raises:
            DocumentNotFoundError: If document doesn't exist
            DocumentAccessDeniedError: If user can't share
        """
        document = await self.get_document(
            document_id, org_id, user_id, check_access=False
        )

        # Only owner or users with edit access can share
        if document.uploaded_by != user_id:
            has_access = await self.access_dao.check_access(
                document_id, user_id, DocumentAccessLevel.EDIT
            )
            if not has_access:
                raise DocumentAccessDeniedError(
                    message="You don't have permission to share this document",
                    document_id=document_id,
                )

        # Grant access to each user
        access_records = []
        for target_user_id in share_with:
            # Verify user exists and is in same org
            target_user = await self.user_dao.get_by_id(target_user_id)
            if not target_user or target_user.org_id != org_id:
                continue  # Skip invalid users

            access = await self.access_dao.grant_access(
                document_id=document_id,
                user_id=target_user_id,
                granted_by=user_id,
                access_level=access_level,
                expires_at=expires_at,
            )
            access_records.append(access)

        return access_records

    async def revoke_access(
        self,
        document_id: int,
        org_id: int,
        user_id: int,
        revoke_from: List[int],
    ) -> int:
        """
        Revoke document access from users.

        WHAT: Removes access from specified users.

        WHY: Stop sharing when no longer needed.

        Args:
            document_id: Document ID
            org_id: Organization ID
            user_id: User revoking access
            revoke_from: List of user IDs to revoke from

        Returns:
            Number of access records revoked

        Raises:
            DocumentNotFoundError: If document doesn't exist
            DocumentAccessDeniedError: If user can't manage access
        """
        document = await self.get_document(
            document_id, org_id, user_id, check_access=False
        )

        # Only owner or users with edit access can revoke
        if document.uploaded_by != user_id:
            has_access = await self.access_dao.check_access(
                document_id, user_id, DocumentAccessLevel.EDIT
            )
            if not has_access:
                raise DocumentAccessDeniedError(
                    message="You don't have permission to manage access",
                    document_id=document_id,
                )

        revoked_count = 0
        for target_user_id in revoke_from:
            if await self.access_dao.revoke_access(document_id, target_user_id):
                revoked_count += 1

        return revoked_count

    async def list_documents(
        self,
        org_id: int,
        user_id: int,
        folder: Optional[str] = None,
        tags: Optional[List[str]] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        search_query: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        List documents with filtering.

        WHAT: Retrieves documents matching criteria.

        WHY: Flexible document discovery.

        Args:
            org_id: Organization ID
            user_id: Requesting user ID
            folder: Optional folder filter
            tags: Optional tags filter
            entity_type: Optional entity type filter
            entity_id: Optional entity ID filter
            search_query: Optional search string
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Dict with documents and metadata
        """
        documents = []

        if entity_type and entity_id:
            documents = await self.document_dao.get_by_entity(
                entity_type, entity_id, org_id, skip, limit
            )
        elif folder:
            documents = await self.document_dao.get_by_folder(
                org_id, folder, skip, limit
            )
        elif tags:
            documents = await self.document_dao.get_by_tags(
                org_id, tags, match_all=False, skip=skip, limit=limit
            )
        elif search_query:
            documents = await self.document_dao.search(
                org_id, search_query, skip, limit
            )
        else:
            documents = await self.document_dao.get_by_org(org_id, skip, limit)

        total = await self.document_dao.count_by_org(org_id)
        storage_used = await self.document_dao.get_storage_usage(org_id)

        return {
            "items": documents,
            "total": total,
            "skip": skip,
            "limit": limit,
            "storage_used_bytes": storage_used,
        }

    async def get_access_list(
        self,
        document_id: int,
        org_id: int,
        user_id: int,
    ) -> List[DocumentAccess]:
        """
        Get access list for a document.

        WHAT: Lists all users with access to a document.

        WHY: Shows sharing status.

        Args:
            document_id: Document ID
            org_id: Organization ID
            user_id: Requesting user ID

        Returns:
            List of access records

        Raises:
            DocumentNotFoundError: If document doesn't exist
            DocumentAccessDeniedError: If user can't view access list
        """
        document = await self.get_document(
            document_id, org_id, user_id, check_access=False
        )

        # Only owner or users with edit access can see access list
        if document.uploaded_by != user_id:
            has_access = await self.access_dao.check_access(
                document_id, user_id, DocumentAccessLevel.EDIT
            )
            if not has_access:
                raise DocumentAccessDeniedError(
                    message="You don't have permission to view access list",
                    document_id=document_id,
                )

        return await self.access_dao.get_document_access_list(document_id)
