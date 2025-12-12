"""
Workflow Version Pydantic Schemas.

WHAT: Request/Response models for workflow version API endpoints.

WHY: Pydantic schemas provide:
1. Request validation
2. Response serialization
3. OpenAPI documentation
4. Type safety

HOW: Defines schemas for:
- Creating versions
- Retrieving version history
- Restoring versions
- Comparing versions
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


# ============================================================================
# Base Schemas
# ============================================================================


class WorkflowVersionBase(BaseModel):
    """
    Base schema for workflow version data.

    WHAT: Common fields shared across version schemas.

    WHY: Reduces duplication and ensures consistency.
    """

    workflow_json: Dict[str, Any] = Field(
        ...,
        description="Complete n8n workflow JSON definition",
    )
    change_description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Description of what changed in this version",
    )


# ============================================================================
# Request Schemas
# ============================================================================


class WorkflowVersionCreateRequest(WorkflowVersionBase):
    """
    Request schema for creating a new workflow version.

    WHAT: Input data for version creation.

    WHY: Validates that required workflow JSON is provided
    with an optional change description.
    """

    set_as_current: bool = Field(
        default=True,
        description="Whether to mark this version as current",
    )


class WorkflowVersionRestoreRequest(BaseModel):
    """
    Request schema for restoring a workflow version.

    WHAT: Input data for version restoration.

    WHY: Allows users to specify the version number to restore
    with an optional description explaining why.
    """

    restore_description: Optional[str] = Field(
        None,
        max_length=500,
        description="Description of why this version is being restored",
    )


class WorkflowVersionCompareRequest(BaseModel):
    """
    Request schema for comparing two versions.

    WHAT: Input data for version comparison.

    WHY: Allows users to specify which two versions to compare.
    """

    version_a: int = Field(
        ...,
        ge=1,
        description="First version number to compare",
    )
    version_b: int = Field(
        ...,
        ge=1,
        description="Second version number to compare",
    )


# ============================================================================
# Response Schemas
# ============================================================================


class WorkflowVersionResponse(BaseModel):
    """
    Response schema for a single workflow version.

    WHAT: Output data for a workflow version.

    WHY: Provides all version details for display.
    """

    id: int = Field(..., description="Version database ID")
    workflow_instance_id: int = Field(..., description="Parent workflow instance ID")
    version_number: int = Field(..., description="Sequential version number")
    workflow_json: Dict[str, Any] = Field(..., description="Workflow JSON definition")
    change_description: Optional[str] = Field(None, description="Change description")
    created_by: int = Field(..., description="User ID who created this version")
    created_by_email: Optional[str] = Field(None, description="Creator's email")
    is_current: bool = Field(..., description="Whether this is the active version")
    created_at: datetime = Field(..., description="When this version was created")

    class Config:
        from_attributes = True


class WorkflowVersionListResponse(BaseModel):
    """
    Response schema for version list with pagination.

    WHAT: Paginated list of workflow versions.

    WHY: Supports UI pagination and displays version count.
    """

    items: List[WorkflowVersionResponse] = Field(
        ...,
        description="List of versions",
    )
    total: int = Field(
        ...,
        description="Total number of versions",
    )
    workflow_instance_id: int = Field(
        ...,
        description="Parent workflow instance ID",
    )
    current_version: Optional[int] = Field(
        None,
        description="Current active version number",
    )


class WorkflowVersionCompareResponse(BaseModel):
    """
    Response schema for version comparison.

    WHAT: Side-by-side comparison of two versions.

    WHY: Enables diff visualization in the UI.
    """

    version_a: Dict[str, Any] = Field(
        ...,
        description="First version details",
    )
    version_b: Dict[str, Any] = Field(
        ...,
        description="Second version details",
    )


class WorkflowVersionRestoreResponse(BaseModel):
    """
    Response schema for version restoration.

    WHAT: Confirmation of successful restoration.

    WHY: Returns the new version created from restoration.
    """

    message: str = Field(..., description="Success message")
    restored_version: WorkflowVersionResponse = Field(
        ...,
        description="The restored version (now current)",
    )
    new_version_number: int = Field(
        ...,
        description="New version number assigned",
    )
