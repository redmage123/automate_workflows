"""
Document Pydantic Schemas.

WHAT: Request/Response models for document API endpoints.

WHY: Pydantic schemas provide:
1. Request validation
2. Response serialization
3. OpenAPI documentation
4. Type safety

HOW: Defines schemas for:
- Document upload and metadata
- Access control management
- Search and filtering
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class DocumentAccessLevel(str, Enum):
    """Document access permission levels."""

    VIEW = "view"
    DOWNLOAD = "download"
    EDIT = "edit"


# ============================================================================
# Request Schemas
# ============================================================================


class DocumentUploadRequest(BaseModel):
    """
    Request schema for document upload.

    WHAT: Metadata to accompany file upload.

    WHY: File uploads are handled separately (multipart form data),
    this provides the metadata.
    """

    folder: str = Field(
        default="/",
        max_length=255,
        description="Folder path for organization",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        max_items=20,
        description="Tags for categorization",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Document description",
    )
    entity_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Type of entity to attach to (project, ticket, etc.)",
    )
    entity_id: Optional[int] = Field(
        default=None,
        description="ID of entity to attach to",
    )


class DocumentUpdateRequest(BaseModel):
    """
    Request schema for updating document metadata.

    WHAT: Fields that can be updated after upload.

    WHY: Allows reorganization without re-uploading.
    """

    folder: Optional[str] = Field(
        default=None,
        max_length=255,
        description="New folder path",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        max_items=20,
        description="New tags list",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="New description",
    )


class DocumentShareRequest(BaseModel):
    """
    Request schema for sharing a document.

    WHAT: Details for granting access to users.

    WHY: Allows fine-grained document sharing.
    """

    user_ids: List[int] = Field(
        ...,
        min_items=1,
        max_items=50,
        description="User IDs to grant access to",
    )
    access_level: DocumentAccessLevel = Field(
        default=DocumentAccessLevel.VIEW,
        description="Level of access to grant",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional expiration time for access",
    )


class DocumentRevokeRequest(BaseModel):
    """
    Request schema for revoking document access.

    WHAT: Users to revoke access from.

    WHY: Stop sharing when no longer needed.
    """

    user_ids: List[int] = Field(
        ...,
        min_items=1,
        max_items=50,
        description="User IDs to revoke access from",
    )


class DocumentSearchRequest(BaseModel):
    """
    Request schema for searching documents.

    WHAT: Search and filter parameters.

    WHY: Enables flexible document discovery.
    """

    query: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Search query for filename/description",
    )
    folder: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Filter by folder",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags",
    )
    entity_type: Optional[str] = Field(
        default=None,
        description="Filter by entity type",
    )
    entity_id: Optional[int] = Field(
        default=None,
        description="Filter by entity ID",
    )
    content_type: Optional[str] = Field(
        default=None,
        description="Filter by MIME type",
    )


# ============================================================================
# Response Schemas
# ============================================================================


class DocumentResponse(BaseModel):
    """
    Response schema for a single document.

    WHAT: Document metadata for display.

    WHY: Provides all document details for UI.
    """

    id: int = Field(..., description="Document ID")
    org_id: int = Field(..., description="Organization ID")
    uploaded_by: int = Field(..., description="Uploader user ID")
    uploaded_by_email: Optional[str] = Field(None, description="Uploader email")

    # File info
    filename: str = Field(..., description="Stored filename")
    original_filename: str = Field(..., description="Original upload filename")
    content_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., description="Size in bytes")
    file_size_mb: float = Field(..., description="Size in MB")

    # Organization
    folder: str = Field(..., description="Folder path")
    tags: List[str] = Field(default=[], description="Tags")
    description: Optional[str] = Field(None, description="Description")

    # Entity association
    entity_type: Optional[str] = Field(None, description="Linked entity type")
    entity_id: Optional[int] = Field(None, description="Linked entity ID")

    # Timestamps
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update")

    # Download URL (presigned, expires)
    download_url: Optional[str] = Field(None, description="Presigned download URL")

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """
    Response schema for document list with pagination.

    WHAT: Paginated list of documents.

    WHY: Supports UI pagination and displays totals.
    """

    items: List[DocumentResponse] = Field(..., description="List of documents")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")
    storage_used_bytes: Optional[int] = Field(
        None, description="Total storage used by org"
    )


class DocumentAccessResponse(BaseModel):
    """
    Response schema for document access record.

    WHAT: Access grant details.

    WHY: Shows who has access and at what level.
    """

    id: int = Field(..., description="Access record ID")
    document_id: int = Field(..., description="Document ID")
    user_id: int = Field(..., description="User with access")
    user_email: Optional[str] = Field(None, description="User email")
    access_level: DocumentAccessLevel = Field(..., description="Access level")
    granted_by: int = Field(..., description="Who granted access")
    granted_by_email: Optional[str] = Field(None, description="Grantor email")
    granted_at: datetime = Field(..., description="When access was granted")
    expires_at: Optional[datetime] = Field(None, description="Expiration time")
    is_expired: bool = Field(..., description="Whether access has expired")

    class Config:
        from_attributes = True


class DocumentAccessListResponse(BaseModel):
    """
    Response schema for document access list.

    WHAT: All access records for a document.

    WHY: Shows full sharing status.
    """

    document_id: int = Field(..., description="Document ID")
    access_records: List[DocumentAccessResponse] = Field(
        ..., description="Access records"
    )


class DocumentShareResponse(BaseModel):
    """
    Response schema for share operation.

    WHAT: Result of sharing a document.

    WHY: Confirms successful sharing.
    """

    message: str = Field(..., description="Success message")
    shared_with: int = Field(..., description="Number of users shared with")
    access_records: List[DocumentAccessResponse] = Field(
        ..., description="Created access records"
    )


class UploadUrlResponse(BaseModel):
    """
    Response schema for presigned upload URL.

    WHAT: URL for direct S3 upload.

    WHY: Allows client-side upload to S3 without proxying through backend.
    """

    upload_url: str = Field(..., description="Presigned S3 upload URL")
    document_id: int = Field(..., description="Reserved document ID")
    fields: dict = Field(..., description="Form fields for upload")
    expires_at: datetime = Field(..., description="URL expiration time")


class StorageStatsResponse(BaseModel):
    """
    Response schema for storage statistics.

    WHAT: Organization storage usage.

    WHY: Useful for quotas and billing.
    """

    total_documents: int = Field(..., description="Total document count")
    total_bytes: int = Field(..., description="Total storage used in bytes")
    total_mb: float = Field(..., description="Total storage used in MB")
    total_gb: float = Field(..., description="Total storage used in GB")
    by_content_type: Optional[dict] = Field(
        None, description="Breakdown by content type"
    )
