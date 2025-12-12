"""
Document management API endpoints.

WHAT: RESTful API for document upload, download, and access control.

WHY: Documents are essential for client collaboration:
1. Share project specifications and contracts
2. Attach files to tickets and proposals
3. Control access with fine-grained permissions
4. Organize with folders and tags

HOW: FastAPI router with:
- Multipart file upload support
- Presigned S3 URLs for download
- Access control management
- Audit logging for all operations

Security Considerations:
- File type validation to prevent malicious uploads
- Size limits to prevent DoS
- Access control enforced at service layer
- Presigned URLs expire after configured time
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import (
    DocumentNotFoundError,
    DocumentAccessDeniedError,
    ValidationError,
)
from app.db.session import get_db
from app.models.user import User
from app.models.document import DocumentAccessLevel
from app.services.document_service import DocumentService
from app.services.audit import AuditService
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdateRequest,
    DocumentShareRequest,
    DocumentRevokeRequest,
    DocumentAccessResponse,
    DocumentAccessListResponse,
    DocumentShareResponse,
    StorageStatsResponse,
    DocumentAccessLevel as SchemaAccessLevel,
)


router = APIRouter(prefix="/documents", tags=["documents"])


# ============================================================================
# Helper Functions
# ============================================================================


async def _document_to_response(
    document,
    db: AsyncSession,
    include_download_url: bool = False,
    user_id: Optional[int] = None,
) -> DocumentResponse:
    """
    Convert Document model to response schema.

    WHAT: Transforms DB model to API response.

    WHY: Enriches with calculated fields and optionally download URL.
    """
    from app.dao.user import UserDAO

    user_dao = UserDAO(db)
    uploader = await user_dao.get_by_id(document.uploaded_by)

    response = DocumentResponse(
        id=document.id,
        org_id=document.org_id,
        uploaded_by=document.uploaded_by,
        uploaded_by_email=uploader.email if uploader else None,
        filename=document.filename,
        original_filename=document.original_filename,
        content_type=document.content_type,
        file_size=document.file_size,
        file_size_mb=document.file_size_mb,
        folder=document.folder,
        tags=document.tags or [],
        description=document.description,
        entity_type=document.entity_type,
        entity_id=document.entity_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )

    if include_download_url and user_id:
        service = DocumentService(db)
        try:
            response.download_url = await service.get_download_url(
                document.id, document.org_id, user_id
            )
        except DocumentAccessDeniedError:
            pass  # User doesn't have download access

    return response


async def _access_to_response(
    access,
    db: AsyncSession,
) -> DocumentAccessResponse:
    """Convert DocumentAccess model to response schema."""
    from app.dao.user import UserDAO

    user_dao = UserDAO(db)
    user = await user_dao.get_by_id(access.user_id)
    grantor = await user_dao.get_by_id(access.granted_by)

    return DocumentAccessResponse(
        id=access.id,
        document_id=access.document_id,
        user_id=access.user_id,
        user_email=user.email if user else None,
        access_level=SchemaAccessLevel(access.access_level.value),
        granted_by=access.granted_by,
        granted_by_email=grantor.email if grantor else None,
        granted_at=access.granted_at,
        expires_at=access.expires_at,
        is_expired=access.is_expired,
    )


# Allowed content types for upload
ALLOWED_CONTENT_TYPES = {
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "text/markdown",
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    # Archives
    "application/zip",
    "application/x-zip-compressed",
    "application/gzip",
    # Other
    "application/json",
    "application/xml",
}


# ============================================================================
# Document Endpoints
# ============================================================================


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document",
    description="Upload a new document to storage",
)
async def upload_document(
    file: UploadFile = File(..., description="File to upload"),
    folder: str = Form(default="/", description="Folder path"),
    tags: Optional[str] = Form(default=None, description="Comma-separated tags"),
    description: Optional[str] = Form(default=None, description="Document description"),
    entity_type: Optional[str] = Form(default=None, description="Entity type to attach to"),
    entity_id: Optional[int] = Form(default=None, description="Entity ID to attach to"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Upload a document.

    WHAT: Uploads file to S3 and creates metadata record.

    WHY: Enables document sharing and attachment to entities.

    Security: Validates file type and size before upload.
    """
    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            message=f"File type not allowed: {file.content_type}",
            allowed_types=list(ALLOWED_CONTENT_TYPES),
        )

    # Parse tags
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    service = DocumentService(db)
    document = await service.upload_document(
        org_id=current_user.org_id,
        user_id=current_user.id,
        file=file.file,
        filename=file.filename,
        content_type=file.content_type,
        folder=folder,
        tags=tag_list,
        description=description,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_create(
        resource_type="document",
        resource_id=document.id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={
            "filename": document.original_filename,
            "content_type": document.content_type,
            "file_size": document.file_size,
            "folder": folder,
        },
    )

    return await _document_to_response(document, db)


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List documents",
    description="Get list of documents with optional filtering",
)
async def list_documents(
    folder: Optional[str] = Query(None, description="Filter by folder"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    search: Optional[str] = Query(None, description="Search query"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """
    List documents.

    WHAT: Retrieves documents with filtering and pagination.

    WHY: Enables document discovery and organization.
    """
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    service = DocumentService(db)
    result = await service.list_documents(
        org_id=current_user.org_id,
        user_id=current_user.id,
        folder=folder,
        tags=tag_list,
        entity_type=entity_type,
        entity_id=entity_id,
        search_query=search,
        skip=skip,
        limit=limit,
    )

    items = []
    for doc in result["items"]:
        items.append(await _document_to_response(doc, db))

    return DocumentListResponse(
        items=items,
        total=result["total"],
        skip=result["skip"],
        limit=result["limit"],
        storage_used_bytes=result["storage_used_bytes"],
    )


@router.get(
    "/stats",
    response_model=StorageStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get storage statistics",
    description="Get document storage usage statistics",
)
async def get_storage_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StorageStatsResponse:
    """
    Get storage statistics.

    WHAT: Returns storage usage for the organization.

    WHY: Useful for quota monitoring and billing.
    """
    from app.dao.document import DocumentDAO

    doc_dao = DocumentDAO(db)
    total_count = await doc_dao.count_by_org(current_user.org_id)
    total_bytes = await doc_dao.get_storage_usage(current_user.org_id)

    return StorageStatsResponse(
        total_documents=total_count,
        total_bytes=total_bytes,
        total_mb=total_bytes / (1024 * 1024),
        total_gb=total_bytes / (1024 * 1024 * 1024),
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document",
    description="Get document details by ID",
)
async def get_document(
    document_id: int,
    include_download_url: bool = Query(
        False, description="Include presigned download URL"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Get document details.

    WHAT: Retrieves document metadata by ID.

    WHY: View document information before downloading.
    """
    service = DocumentService(db)
    document = await service.get_document(
        document_id=document_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
    )

    return await _document_to_response(
        document,
        db,
        include_download_url=include_download_url,
        user_id=current_user.id,
    )


@router.get(
    "/{document_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Get download URL",
    description="Get presigned URL for downloading the document",
)
async def get_download_url(
    document_id: int,
    expires_in: int = Query(
        3600, ge=60, le=86400, description="URL expiration in seconds"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get download URL.

    WHAT: Generates a presigned S3 URL for download.

    WHY: Allows direct download from S3 without proxying.

    Security: URL expires after configured time.
    """
    service = DocumentService(db)
    url = await service.get_download_url(
        document_id=document_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        expires_in=expires_in,
    )

    return {
        "download_url": url,
        "expires_in": expires_in,
    }


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update document",
    description="Update document metadata",
)
async def update_document(
    document_id: int,
    data: DocumentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Update document metadata.

    WHAT: Updates folder, tags, or description.

    WHY: Allows reorganization without re-uploading.
    """
    from app.dao.document import DocumentDAO

    # Get document first
    service = DocumentService(db)
    document = await service.get_document(
        document_id=document_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
    )

    # Only owner or edit access can update
    if document.uploaded_by != current_user.id:
        from app.dao.document import DocumentAccessDAO

        access_dao = DocumentAccessDAO(db)
        has_access = await access_dao.check_access(
            document_id, current_user.id, DocumentAccessLevel.EDIT
        )
        if not has_access:
            raise DocumentAccessDeniedError(
                message="You don't have permission to update this document",
                document_id=document_id,
            )

    # Update metadata
    doc_dao = DocumentDAO(db)
    updated = await doc_dao.update_metadata(
        document_id=document_id,
        org_id=current_user.org_id,
        folder=data.folder,
        tags=data.tags,
        description=data.description,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="document",
        resource_id=document_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data=data.model_dump(exclude_unset=True),
    )

    return await _document_to_response(updated, db)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Delete a document (soft delete by default)",
)
async def delete_document(
    document_id: int,
    hard_delete: bool = Query(False, description="Permanently delete from storage"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete document.

    WHAT: Soft-deletes (default) or hard-deletes a document.

    WHY: Soft delete preserves history; hard delete frees storage.
    """
    service = DocumentService(db)
    await service.delete_document(
        document_id=document_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        hard_delete=hard_delete,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_delete(
        resource_type="document",
        resource_id=document_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={"hard_delete": hard_delete},
    )


# ============================================================================
# Access Control Endpoints
# ============================================================================


@router.post(
    "/{document_id}/share",
    response_model=DocumentShareResponse,
    status_code=status.HTTP_200_OK,
    summary="Share document",
    description="Grant access to document for specified users",
)
async def share_document(
    document_id: int,
    data: DocumentShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentShareResponse:
    """
    Share document with users.

    WHAT: Grants access to specified users.

    WHY: Enables document sharing with team members.
    """
    service = DocumentService(db)
    access_records = await service.share_document(
        document_id=document_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        share_with=data.user_ids,
        access_level=DocumentAccessLevel(data.access_level.value),
        expires_at=data.expires_at,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="document",
        resource_id=document_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={
            "action": "share",
            "shared_with": data.user_ids,
            "access_level": data.access_level.value,
        },
    )

    # Convert to responses
    access_responses = []
    for access in access_records:
        access_responses.append(await _access_to_response(access, db))

    return DocumentShareResponse(
        message=f"Document shared with {len(access_records)} users",
        shared_with=len(access_records),
        access_records=access_responses,
    )


@router.post(
    "/{document_id}/revoke",
    status_code=status.HTTP_200_OK,
    summary="Revoke access",
    description="Revoke document access from specified users",
)
async def revoke_access(
    document_id: int,
    data: DocumentRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Revoke document access.

    WHAT: Removes access from specified users.

    WHY: Stop sharing when no longer needed.
    """
    service = DocumentService(db)
    revoked_count = await service.revoke_access(
        document_id=document_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        revoke_from=data.user_ids,
    )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_update(
        resource_type="document",
        resource_id=document_id,
        actor_user_id=current_user.id,
        org_id=current_user.org_id,
        extra_data={
            "action": "revoke_access",
            "revoked_from": data.user_ids,
        },
    )

    return {
        "message": f"Access revoked from {revoked_count} users",
        "revoked_count": revoked_count,
    }


@router.get(
    "/{document_id}/access",
    response_model=DocumentAccessListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get access list",
    description="Get list of users with access to the document",
)
async def get_access_list(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentAccessListResponse:
    """
    Get access list.

    WHAT: Lists all users with access to a document.

    WHY: Shows sharing status.
    """
    service = DocumentService(db)
    access_records = await service.get_access_list(
        document_id=document_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
    )

    access_responses = []
    for access in access_records:
        access_responses.append(await _access_to_response(access, db))

    return DocumentAccessListResponse(
        document_id=document_id,
        access_records=access_responses,
    )
