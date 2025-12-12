"""
Unit tests for DocumentDAO and DocumentAccessDAO.

WHAT: Tests for document data access operations.

WHY: Ensures document management works correctly:
- Document CRUD operations
- Folder/tag organization
- Access control management
- Soft delete/restore
- Search functionality
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.document import DocumentDAO, DocumentAccessDAO
from app.models.document import Document, DocumentAccess, DocumentAccessLevel


class TestDocumentDAO:
    """
    Test suite for DocumentDAO.

    WHAT: Tests all DAO methods for document management.

    WHY: Verifies correct database operations and organization.
    """

    @pytest_asyncio.fixture
    async def setup_data(self, db_session: AsyncSession):
        """
        Set up test data.

        WHY: Creates necessary related records (org, user)
        for document tests.
        """
        from tests.factories import (
            OrganizationFactory,
            UserFactory,
        )

        # Create organization
        org = await OrganizationFactory.create(
            db_session, name="Test Org"
        )

        # Create user
        user = await UserFactory.create(
            db_session,
            email="test@example.com",
            org_id=org.id,
        )

        # Create another user for sharing tests
        other_user = await UserFactory.create(
            db_session,
            email="other@example.com",
            org_id=org.id,
        )

        await db_session.commit()

        return {
            "org": org,
            "user": user,
            "other_user": other_user,
        }

    @pytest.mark.asyncio
    async def test_create_document(self, db_session: AsyncSession, setup_data):
        """
        Test creating a document.

        WHAT: Creates a document and verifies it's saved correctly.

        WHY: Basic functionality test for document creation.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        document = await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="test_doc.pdf",
            original_filename="Test Document.pdf",
            content_type="application/pdf",
            file_size=1024000,  # ~1MB
            s3_key="orgs/1/documents/abc123_test_doc.pdf",
            s3_bucket="test-bucket",
            folder="/projects",
            tags=["project", "documentation"],
            description="A test document",
        )

        assert document is not None
        assert document.id is not None
        assert document.filename == "test_doc.pdf"
        assert document.original_filename == "Test Document.pdf"
        assert document.content_type == "application/pdf"
        assert document.file_size == 1024000
        assert document.folder == "/projects"
        assert document.tags == ["project", "documentation"]
        assert document.description == "A test document"
        assert document.deleted_at is None

    @pytest.mark.asyncio
    async def test_create_document_with_entity(self, db_session: AsyncSession, setup_data):
        """
        Test creating a document attached to an entity.

        WHAT: Creates a document linked to a project/ticket.

        WHY: Verifies polymorphic entity associations work.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        document = await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="spec.pdf",
            original_filename="Project Specification.pdf",
            content_type="application/pdf",
            file_size=2048000,
            s3_key="orgs/1/documents/abc123_spec.pdf",
            s3_bucket="test-bucket",
            entity_type="project",
            entity_id=42,
        )

        assert document.entity_type == "project"
        assert document.entity_id == 42

    @pytest.mark.asyncio
    async def test_get_by_org(self, db_session: AsyncSession, setup_data):
        """
        Test getting documents by organization.

        WHAT: Creates documents and retrieves them by org.

        WHY: Verifies org-scoping works correctly.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Create multiple documents
        for i in range(5):
            await dao.create_document(
                org_id=data["org"].id,
                uploaded_by=data["user"].id,
                filename=f"doc_{i}.pdf",
                original_filename=f"Document {i}.pdf",
                content_type="application/pdf",
                file_size=1000 * (i + 1),
                s3_key=f"orgs/{data['org'].id}/documents/doc_{i}.pdf",
                s3_bucket="test-bucket",
            )

        documents = await dao.get_by_org(data["org"].id)
        assert len(documents) == 5
        # Should be ordered by created_at desc (newest first)

    @pytest.mark.asyncio
    async def test_get_by_org_excludes_deleted(self, db_session: AsyncSession, setup_data):
        """
        Test that soft-deleted documents are excluded by default.

        WHAT: Creates and soft-deletes documents.

        WHY: Verifies soft delete filtering works.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Create documents
        doc1 = await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="active.pdf",
            original_filename="Active.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/active.pdf",
            s3_bucket="test-bucket",
        )

        doc2 = await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="deleted.pdf",
            original_filename="Deleted.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/deleted.pdf",
            s3_bucket="test-bucket",
        )

        # Soft delete one
        await dao.soft_delete(doc2.id, data["org"].id)

        # Get documents (default excludes deleted)
        documents = await dao.get_by_org(data["org"].id)
        assert len(documents) == 1
        assert documents[0].id == doc1.id

        # Get documents including deleted
        all_documents = await dao.get_by_org(data["org"].id, include_deleted=True)
        assert len(all_documents) == 2

    @pytest.mark.asyncio
    async def test_get_by_entity(self, db_session: AsyncSession, setup_data):
        """
        Test getting documents by entity.

        WHAT: Creates documents for different entities.

        WHY: Verifies entity filtering works.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Create documents for different entities
        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="project_doc.pdf",
            original_filename="Project Doc.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/project_doc.pdf",
            s3_bucket="test-bucket",
            entity_type="project",
            entity_id=1,
        )

        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="ticket_doc.pdf",
            original_filename="Ticket Doc.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/ticket_doc.pdf",
            s3_bucket="test-bucket",
            entity_type="ticket",
            entity_id=2,
        )

        # Get project documents
        project_docs = await dao.get_by_entity("project", 1, data["org"].id)
        assert len(project_docs) == 1
        assert project_docs[0].filename == "project_doc.pdf"

        # Get ticket documents
        ticket_docs = await dao.get_by_entity("ticket", 2, data["org"].id)
        assert len(ticket_docs) == 1
        assert ticket_docs[0].filename == "ticket_doc.pdf"

    @pytest.mark.asyncio
    async def test_get_by_folder(self, db_session: AsyncSession, setup_data):
        """
        Test getting documents by folder.

        WHAT: Creates documents in different folders.

        WHY: Verifies folder organization works.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Create documents in different folders
        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="root_doc.pdf",
            original_filename="Root Doc.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/root_doc.pdf",
            s3_bucket="test-bucket",
            folder="/",
        )

        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="project_doc.pdf",
            original_filename="Project Doc.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/project_doc.pdf",
            s3_bucket="test-bucket",
            folder="/projects",
        )

        # Get root folder documents
        root_docs = await dao.get_by_folder(data["org"].id, "/")
        assert len(root_docs) == 1
        assert root_docs[0].filename == "root_doc.pdf"

        # Get projects folder documents
        project_docs = await dao.get_by_folder(data["org"].id, "/projects")
        assert len(project_docs) == 1
        assert project_docs[0].filename == "project_doc.pdf"

    @pytest.mark.asyncio
    async def test_get_by_tags(self, db_session: AsyncSession, setup_data):
        """
        Test getting documents by tags.

        WHAT: Creates documents with different tags.

        WHY: Verifies tag filtering works (ANY match).
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Create documents with different tags
        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="doc1.pdf",
            original_filename="Doc 1.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/doc1.pdf",
            s3_bucket="test-bucket",
            tags=["important", "project-a"],
        )

        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="doc2.pdf",
            original_filename="Doc 2.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/doc2.pdf",
            s3_bucket="test-bucket",
            tags=["important", "project-b"],
        )

        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="doc3.pdf",
            original_filename="Doc 3.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/doc3.pdf",
            s3_bucket="test-bucket",
            tags=["archive"],
        )

        # Get documents with "important" tag (ANY match)
        important_docs = await dao.get_by_tags(data["org"].id, ["important"])
        assert len(important_docs) == 2

        # Get documents with "project-a" OR "project-b" tags
        project_docs = await dao.get_by_tags(data["org"].id, ["project-a", "project-b"])
        assert len(project_docs) == 2

    @pytest.mark.asyncio
    async def test_get_by_tags_match_all(self, db_session: AsyncSession, setup_data):
        """
        Test getting documents by tags with match_all.

        WHAT: Creates documents with different tags.

        WHY: Verifies tag filtering works (ALL match).
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Create documents with different tags
        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="doc1.pdf",
            original_filename="Doc 1.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/doc1.pdf",
            s3_bucket="test-bucket",
            tags=["important", "urgent", "project-a"],
        )

        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="doc2.pdf",
            original_filename="Doc 2.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/doc2.pdf",
            s3_bucket="test-bucket",
            tags=["important"],
        )

        # Get documents with ALL of "important" AND "urgent" tags
        urgent_important = await dao.get_by_tags(
            data["org"].id, ["important", "urgent"], match_all=True
        )
        assert len(urgent_important) == 1
        assert urgent_important[0].filename == "doc1.pdf"

    @pytest.mark.asyncio
    async def test_soft_delete_and_restore(self, db_session: AsyncSession, setup_data):
        """
        Test soft delete and restore operations.

        WHAT: Creates, soft-deletes, and restores a document.

        WHY: Verifies soft delete functionality works.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Create document
        document = await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="deleteme.pdf",
            original_filename="Delete Me.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/deleteme.pdf",
            s3_bucket="test-bucket",
        )
        assert document.deleted_at is None

        # Soft delete
        deleted = await dao.soft_delete(document.id, data["org"].id)
        assert deleted is not None
        assert deleted.deleted_at is not None

        # Restore
        restored = await dao.restore(document.id, data["org"].id)
        assert restored is not None
        assert restored.deleted_at is None

    @pytest.mark.asyncio
    async def test_update_metadata(self, db_session: AsyncSession, setup_data):
        """
        Test updating document metadata.

        WHAT: Creates and updates document metadata.

        WHY: Verifies metadata updates work correctly.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Create document
        document = await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="updateme.pdf",
            original_filename="Update Me.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/updateme.pdf",
            s3_bucket="test-bucket",
            folder="/",
            tags=["initial"],
            description="Initial description",
        )

        # Update metadata
        updated = await dao.update_metadata(
            document.id,
            data["org"].id,
            folder="/new-folder",
            tags=["updated", "modified"],
            description="Updated description",
        )

        assert updated is not None
        assert updated.folder == "/new-folder"
        assert updated.tags == ["updated", "modified"]
        assert updated.description == "Updated description"
        assert updated.updated_at is not None

    @pytest.mark.asyncio
    async def test_count_by_org(self, db_session: AsyncSession, setup_data):
        """
        Test counting documents by organization.

        WHAT: Creates documents and counts them.

        WHY: Verifies counting works correctly.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Initially no documents
        count = await dao.count_by_org(data["org"].id)
        assert count == 0

        # Create documents
        for i in range(3):
            await dao.create_document(
                org_id=data["org"].id,
                uploaded_by=data["user"].id,
                filename=f"doc_{i}.pdf",
                original_filename=f"Doc {i}.pdf",
                content_type="application/pdf",
                file_size=1000,
                s3_key=f"orgs/{data['org'].id}/documents/doc_{i}.pdf",
                s3_bucket="test-bucket",
            )

        count = await dao.count_by_org(data["org"].id)
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_storage_usage(self, db_session: AsyncSession, setup_data):
        """
        Test getting storage usage.

        WHAT: Creates documents and calculates storage.

        WHY: Verifies storage calculation works.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Initially no storage used
        usage = await dao.get_storage_usage(data["org"].id)
        assert usage == 0

        # Create documents with different sizes
        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="small.pdf",
            original_filename="Small.pdf",
            content_type="application/pdf",
            file_size=1000,  # 1KB
            s3_key=f"orgs/{data['org'].id}/documents/small.pdf",
            s3_bucket="test-bucket",
        )

        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="large.pdf",
            original_filename="Large.pdf",
            content_type="application/pdf",
            file_size=5000,  # 5KB
            s3_key=f"orgs/{data['org'].id}/documents/large.pdf",
            s3_bucket="test-bucket",
        )

        usage = await dao.get_storage_usage(data["org"].id)
        assert usage == 6000  # 1KB + 5KB

    @pytest.mark.asyncio
    async def test_search(self, db_session: AsyncSession, setup_data):
        """
        Test searching documents.

        WHAT: Creates documents and searches by text.

        WHY: Verifies search functionality works.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Create documents with different names/descriptions
        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="contract.pdf",
            original_filename="Contract Agreement.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/contract.pdf",
            s3_bucket="test-bucket",
            description="Legal contract for Project X",
        )

        await dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["user"].id,
            filename="invoice.pdf",
            original_filename="Invoice 2024.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/invoice.pdf",
            s3_bucket="test-bucket",
            description="Billing invoice for services",
        )

        # Search by filename
        contract_results = await dao.search(data["org"].id, "contract")
        assert len(contract_results) == 1
        assert contract_results[0].filename == "contract.pdf"

        # Search by description
        billing_results = await dao.search(data["org"].id, "billing")
        assert len(billing_results) == 1
        assert billing_results[0].filename == "invoice.pdf"

        # Search with no results
        no_results = await dao.search(data["org"].id, "nonexistent")
        assert len(no_results) == 0

    @pytest.mark.asyncio
    async def test_pagination(self, db_session: AsyncSession, setup_data):
        """
        Test document pagination.

        WHAT: Creates documents and retrieves with skip/limit.

        WHY: Pagination is needed for large document lists.
        """
        dao = DocumentDAO(db_session)
        data = await setup_data

        # Create 10 documents
        for i in range(10):
            await dao.create_document(
                org_id=data["org"].id,
                uploaded_by=data["user"].id,
                filename=f"doc_{i}.pdf",
                original_filename=f"Doc {i}.pdf",
                content_type="application/pdf",
                file_size=1000,
                s3_key=f"orgs/{data['org'].id}/documents/doc_{i}.pdf",
                s3_bucket="test-bucket",
            )

        # Get first page (3 items)
        page1 = await dao.get_by_org(data["org"].id, skip=0, limit=3)
        assert len(page1) == 3

        # Get second page
        page2 = await dao.get_by_org(data["org"].id, skip=3, limit=3)
        assert len(page2) == 3

        # Pages should have different documents
        page1_ids = {d.id for d in page1}
        page2_ids = {d.id for d in page2}
        assert page1_ids.isdisjoint(page2_ids)


class TestDocumentAccessDAO:
    """
    Test suite for DocumentAccessDAO.

    WHAT: Tests all DAO methods for document access control.

    WHY: Verifies access control functionality works correctly.
    """

    @pytest_asyncio.fixture
    async def setup_data(self, db_session: AsyncSession):
        """
        Set up test data.

        WHY: Creates necessary related records for access tests.
        """
        from tests.factories import (
            OrganizationFactory,
            UserFactory,
        )

        # Create organization
        org = await OrganizationFactory.create(
            db_session, name="Test Org"
        )

        # Create users
        owner = await UserFactory.create(
            db_session,
            email="owner@example.com",
            org_id=org.id,
        )

        user1 = await UserFactory.create(
            db_session,
            email="user1@example.com",
            org_id=org.id,
        )

        user2 = await UserFactory.create(
            db_session,
            email="user2@example.com",
            org_id=org.id,
        )

        # Create document
        doc_dao = DocumentDAO(db_session)
        document = await doc_dao.create_document(
            org_id=org.id,
            uploaded_by=owner.id,
            filename="shared.pdf",
            original_filename="Shared Document.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{org.id}/documents/shared.pdf",
            s3_bucket="test-bucket",
        )

        await db_session.commit()

        return {
            "org": org,
            "owner": owner,
            "user1": user1,
            "user2": user2,
            "document": document,
        }

    @pytest.mark.asyncio
    async def test_grant_access(self, db_session: AsyncSession, setup_data):
        """
        Test granting document access.

        WHAT: Grants access and verifies it's saved correctly.

        WHY: Basic functionality test for access control.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        access = await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
            access_level=DocumentAccessLevel.VIEW,
        )

        assert access is not None
        assert access.document_id == data["document"].id
        assert access.user_id == data["user1"].id
        assert access.access_level == DocumentAccessLevel.VIEW
        assert access.granted_by == data["owner"].id
        assert access.expires_at is None

    @pytest.mark.asyncio
    async def test_grant_access_with_expiration(self, db_session: AsyncSession, setup_data):
        """
        Test granting time-limited access.

        WHAT: Grants access with expiration and verifies.

        WHY: Access should be time-limited for security.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        expires = datetime.utcnow() + timedelta(days=7)
        access = await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
            access_level=DocumentAccessLevel.DOWNLOAD,
            expires_at=expires,
        )

        assert access.expires_at is not None
        assert access.is_expired is False

    @pytest.mark.asyncio
    async def test_grant_access_updates_existing(self, db_session: AsyncSession, setup_data):
        """
        Test that granting access updates existing record.

        WHAT: Grants access twice to same user.

        WHY: Should update, not create duplicate.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        # Grant VIEW access
        access1 = await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
            access_level=DocumentAccessLevel.VIEW,
        )

        # Grant EDIT access (should update)
        access2 = await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
            access_level=DocumentAccessLevel.EDIT,
        )

        assert access1.id == access2.id
        assert access2.access_level == DocumentAccessLevel.EDIT

    @pytest.mark.asyncio
    async def test_revoke_access(self, db_session: AsyncSession, setup_data):
        """
        Test revoking document access.

        WHAT: Grants and then revokes access.

        WHY: Users should be able to stop sharing.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        # Grant access
        await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
        )

        # Verify access exists
        access = await dao.get_user_access(data["document"].id, data["user1"].id)
        assert access is not None

        # Revoke access
        result = await dao.revoke_access(data["document"].id, data["user1"].id)
        assert result is True

        # Verify access is gone
        access = await dao.get_user_access(data["document"].id, data["user1"].id)
        assert access is None

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_access(self, db_session: AsyncSession, setup_data):
        """
        Test revoking access that doesn't exist.

        WHAT: Attempts to revoke nonexistent access.

        WHY: Should return False gracefully.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        result = await dao.revoke_access(data["document"].id, data["user1"].id)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_access_view(self, db_session: AsyncSession, setup_data):
        """
        Test checking VIEW access level.

        WHAT: Grants VIEW and checks various levels.

        WHY: VIEW should only allow VIEW, not DOWNLOAD or EDIT.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
            access_level=DocumentAccessLevel.VIEW,
        )

        assert await dao.check_access(data["document"].id, data["user1"].id, DocumentAccessLevel.VIEW) is True
        assert await dao.check_access(data["document"].id, data["user1"].id, DocumentAccessLevel.DOWNLOAD) is False
        assert await dao.check_access(data["document"].id, data["user1"].id, DocumentAccessLevel.EDIT) is False

    @pytest.mark.asyncio
    async def test_check_access_download(self, db_session: AsyncSession, setup_data):
        """
        Test checking DOWNLOAD access level.

        WHAT: Grants DOWNLOAD and checks various levels.

        WHY: DOWNLOAD should allow VIEW and DOWNLOAD, not EDIT.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
            access_level=DocumentAccessLevel.DOWNLOAD,
        )

        assert await dao.check_access(data["document"].id, data["user1"].id, DocumentAccessLevel.VIEW) is True
        assert await dao.check_access(data["document"].id, data["user1"].id, DocumentAccessLevel.DOWNLOAD) is True
        assert await dao.check_access(data["document"].id, data["user1"].id, DocumentAccessLevel.EDIT) is False

    @pytest.mark.asyncio
    async def test_check_access_edit(self, db_session: AsyncSession, setup_data):
        """
        Test checking EDIT access level.

        WHAT: Grants EDIT and checks various levels.

        WHY: EDIT should allow all levels.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
            access_level=DocumentAccessLevel.EDIT,
        )

        assert await dao.check_access(data["document"].id, data["user1"].id, DocumentAccessLevel.VIEW) is True
        assert await dao.check_access(data["document"].id, data["user1"].id, DocumentAccessLevel.DOWNLOAD) is True
        assert await dao.check_access(data["document"].id, data["user1"].id, DocumentAccessLevel.EDIT) is True

    @pytest.mark.asyncio
    async def test_check_access_expired(self, db_session: AsyncSession, setup_data):
        """
        Test checking expired access.

        WHAT: Grants access that has expired.

        WHY: Expired access should be denied.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        # Grant expired access
        expired_time = datetime.utcnow() - timedelta(hours=1)
        await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
            access_level=DocumentAccessLevel.EDIT,
            expires_at=expired_time,
        )

        # Should be denied even though level is EDIT
        assert await dao.check_access(data["document"].id, data["user1"].id, DocumentAccessLevel.VIEW) is False

    @pytest.mark.asyncio
    async def test_get_document_access_list(self, db_session: AsyncSession, setup_data):
        """
        Test getting all access records for a document.

        WHAT: Grants access to multiple users.

        WHY: Shows who has access to a document.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        # Grant access to multiple users
        await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
            access_level=DocumentAccessLevel.VIEW,
        )

        await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user2"].id,
            granted_by=data["owner"].id,
            access_level=DocumentAccessLevel.EDIT,
        )

        access_list = await dao.get_document_access_list(data["document"].id)
        assert len(access_list) == 2

    @pytest.mark.asyncio
    async def test_get_user_documents_access(self, db_session: AsyncSession, setup_data):
        """
        Test getting all documents a user has access to.

        WHAT: Grants access to user for multiple documents.

        WHY: Shows what documents a user can access.
        """
        dao = DocumentAccessDAO(db_session)
        doc_dao = DocumentDAO(db_session)
        data = await setup_data

        # Create another document
        doc2 = await doc_dao.create_document(
            org_id=data["org"].id,
            uploaded_by=data["owner"].id,
            filename="doc2.pdf",
            original_filename="Doc 2.pdf",
            content_type="application/pdf",
            file_size=1000,
            s3_key=f"orgs/{data['org'].id}/documents/doc2.pdf",
            s3_bucket="test-bucket",
        )

        # Grant access to user1 for both documents
        await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
        )

        await dao.grant_access(
            document_id=doc2.id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
        )

        access_list = await dao.get_user_documents_access(data["user1"].id)
        assert len(access_list) == 2

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, db_session: AsyncSession, setup_data):
        """
        Test cleanup of expired access records.

        WHAT: Creates expired and non-expired access, then cleans up.

        WHY: Removes stale access records.
        """
        dao = DocumentAccessDAO(db_session)
        data = await setup_data

        # Create expired access
        expired_time = datetime.utcnow() - timedelta(days=1)
        await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user1"].id,
            granted_by=data["owner"].id,
            expires_at=expired_time,
        )

        # Create non-expired access
        future_time = datetime.utcnow() + timedelta(days=7)
        await dao.grant_access(
            document_id=data["document"].id,
            user_id=data["user2"].id,
            granted_by=data["owner"].id,
            expires_at=future_time,
        )

        # Cleanup
        deleted_count = await dao.cleanup_expired()
        assert deleted_count == 1

        # Verify expired is gone, non-expired remains
        access1 = await dao.get_user_access(data["document"].id, data["user1"].id)
        access2 = await dao.get_user_access(data["document"].id, data["user2"].id)
        assert access1 is None
        assert access2 is not None
