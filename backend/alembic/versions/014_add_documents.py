"""
Add documents and document_access tables.

WHAT: Creates tables for document management with S3 storage.

WHY: Documents are essential for client collaboration:
- Share files attached to projects, tickets, proposals
- Fine-grained access control with expiration
- S3 storage for scalability

Revision ID: 014
Revises: 013
Create Date: 2024-01-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create documents and document_access tables.

    WHAT: Creates document management infrastructure.

    WHY: Enables file sharing and collaboration features.

    HOW: Creates tables with proper indexes and foreign keys.
    """

    # Create document access level enum
    # WHY: PostgreSQL native enum for type safety
    document_access_level_enum = sa.Enum(
        "view",
        "download",
        "edit",
        name="documentaccesslevel",
    )
    document_access_level_enum.create(op.get_bind(), checkfirst=True)

    # Create documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # File metadata
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        # S3 storage
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("s3_bucket", sa.String(100), nullable=False),
        # Organization
        sa.Column("folder", sa.String(255), nullable=False, server_default="/"),
        sa.Column("tags", ARRAY(sa.String()), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        # Polymorphic associations
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    # Create document_access table
    op.create_table(
        "document_access",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "access_level",
            document_access_level_enum,
            nullable=False,
            server_default="view",
        ),
        sa.Column(
            "granted_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )

    # Create indexes for documents
    op.create_index("ix_documents_org_id", "documents", ["org_id"])
    op.create_index("ix_documents_folder", "documents", ["folder"])
    op.create_index("ix_documents_entity", "documents", ["entity_type", "entity_id"])
    op.create_index("ix_documents_uploaded_by", "documents", ["uploaded_by"])
    op.create_index("ix_documents_s3_key", "documents", ["s3_key"], unique=True)

    # Create indexes for document_access
    op.create_index("ix_document_access_document_id", "document_access", ["document_id"])
    op.create_index("ix_document_access_user_id", "document_access", ["user_id"])
    # Unique constraint: one access record per document/user pair
    op.create_index(
        "ix_document_access_unique",
        "document_access",
        ["document_id", "user_id"],
        unique=True,
    )


def downgrade() -> None:
    """
    Drop documents and document_access tables.

    WHAT: Removes document management infrastructure.

    WHY: Allows rollback if needed.
    """

    # Drop indexes
    op.drop_index("ix_document_access_unique", table_name="document_access")
    op.drop_index("ix_document_access_user_id", table_name="document_access")
    op.drop_index("ix_document_access_document_id", table_name="document_access")
    op.drop_index("ix_documents_s3_key", table_name="documents")
    op.drop_index("ix_documents_uploaded_by", table_name="documents")
    op.drop_index("ix_documents_entity", table_name="documents")
    op.drop_index("ix_documents_folder", table_name="documents")
    op.drop_index("ix_documents_org_id", table_name="documents")

    # Drop tables
    op.drop_table("document_access")
    op.drop_table("documents")

    # Drop enum
    sa.Enum(name="documentaccesslevel").drop(op.get_bind(), checkfirst=True)
