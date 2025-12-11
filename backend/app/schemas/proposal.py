"""
Pydantic schemas for proposal endpoints.

WHAT: Request/response schemas for proposal management API.

WHY: Schemas define API contracts for proposal operations:
1. Validate incoming request data including line items
2. Document API for OpenAPI/Swagger
3. Provide type safety for handlers
4. Control which fields are exposed (hide internal notes from clients)

HOW: Uses Pydantic v2 with Field validators, nested models for line items,
and ORM mode for SQLAlchemy integration.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class ProposalStatus(str, Enum):
    """
    Proposal approval workflow status.

    WHY: Mirrors the SQLAlchemy enum for API consistency.
    """

    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVISED = "revised"


class LineItem(BaseModel):
    """
    Proposal line item schema.

    WHAT: Represents a single line item in a proposal.

    WHY: Structured line items enable:
    - Itemized pricing display
    - Automatic total calculation
    - Easy revision and comparison
    """

    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Line item description",
    )
    quantity: float = Field(
        ...,
        gt=0,
        description="Quantity of items/hours",
    )
    unit_price: float = Field(
        ...,
        ge=0,
        description="Price per unit",
    )
    amount: float = Field(
        default=0,
        ge=0,
        description="Total amount (quantity * unit_price)",
    )

    @model_validator(mode="after")
    def calculate_amount(self) -> "LineItem":
        """
        Auto-calculate amount from quantity and unit_price.

        WHY: Ensures amount is always consistent with quantity * unit_price,
        even if client provides incorrect amount.
        """
        self.amount = round(self.quantity * self.unit_price, 2)
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "description": "Workflow automation development",
                "quantity": 20,
                "unit_price": 150.00,
                "amount": 3000.00,
            }
        }


class ProposalCreate(BaseModel):
    """
    Proposal creation request schema.

    WHAT: Validates data for creating a new proposal.

    WHY: Ensures all required fields are present and valid.
    Proposals start in DRAFT status automatically.
    """

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Proposal title",
    )
    description: str | None = Field(
        default=None,
        max_length=10000,
        description="Scope of work description",
    )
    project_id: int = Field(
        ...,
        gt=0,
        description="Associated project ID",
    )
    line_items: list[LineItem] | None = Field(
        default=None,
        description="List of line items with pricing",
    )
    discount_percent: float | None = Field(
        default=0,
        ge=0,
        le=100,
        description="Discount percentage (0-100)",
    )
    tax_percent: float | None = Field(
        default=0,
        ge=0,
        le=100,
        description="Tax percentage (0-100)",
    )
    valid_until: datetime | None = Field(
        default=None,
        description="Proposal expiration date",
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
        description="Internal notes (not visible to client)",
    )
    client_notes: str | None = Field(
        default=None,
        max_length=5000,
        description="Notes visible to client",
    )
    terms: str | None = Field(
        default=None,
        max_length=10000,
        description="Terms and conditions",
    )

    @field_validator("valid_until")
    @classmethod
    def valid_until_in_future(cls, v: datetime | None) -> datetime | None:
        """
        Validate valid_until is in the future.

        WHY: Cannot create proposal that's already expired.
        """
        if v is not None and v < datetime.utcnow():
            raise ValueError("valid_until must be in the future")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Website Automation Proposal",
                "description": "Proposal for automating lead capture workflow",
                "project_id": 1,
                "line_items": [
                    {
                        "description": "Discovery and planning",
                        "quantity": 8,
                        "unit_price": 150.00,
                        "amount": 1200.00,
                    },
                    {
                        "description": "Workflow development",
                        "quantity": 24,
                        "unit_price": 150.00,
                        "amount": 3600.00,
                    },
                    {
                        "description": "Testing and deployment",
                        "quantity": 8,
                        "unit_price": 150.00,
                        "amount": 1200.00,
                    },
                ],
                "discount_percent": 10,
                "tax_percent": 0,
                "valid_until": "2025-02-28T23:59:59",
                "client_notes": "Pricing valid for 30 days",
                "terms": "50% deposit required to begin work",
            }
        }


class ProposalUpdate(BaseModel):
    """
    Proposal update request schema.

    WHAT: Validates data for updating an existing proposal.

    WHY: Allows partial updates - only provided fields are modified.
    Can only update proposals in DRAFT status.
    """

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Proposal title",
    )
    description: str | None = Field(
        default=None,
        max_length=10000,
        description="Scope of work description",
    )
    line_items: list[LineItem] | None = Field(
        default=None,
        description="List of line items with pricing",
    )
    discount_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Discount percentage (0-100)",
    )
    tax_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Tax percentage (0-100)",
    )
    valid_until: datetime | None = Field(
        default=None,
        description="Proposal expiration date",
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
        description="Internal notes (not visible to client)",
    )
    client_notes: str | None = Field(
        default=None,
        max_length=5000,
        description="Notes visible to client",
    )
    terms: str | None = Field(
        default=None,
        max_length=10000,
        description="Terms and conditions",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Updated Proposal Title",
                "discount_percent": 15,
                "line_items": [
                    {
                        "description": "Updated line item",
                        "quantity": 10,
                        "unit_price": 175.00,
                        "amount": 1750.00,
                    }
                ],
            }
        }


class ProposalReject(BaseModel):
    """
    Proposal rejection request schema.

    WHAT: Captures rejection reason from client.

    WHY: Understanding why proposals are rejected helps improve
    future proposals and track conversion issues.
    """

    reason: str | None = Field(
        default=None,
        max_length=2000,
        description="Reason for rejection",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Budget constraints - please revise pricing",
            }
        }


class ProposalRevise(BaseModel):
    """
    Proposal revision request schema.

    WHAT: Data for creating a revised version of a proposal.

    WHY: Revisions allow updating pricing/scope while preserving
    the original proposal for audit trail and comparison.
    """

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New title (optional, defaults to original)",
    )
    description: str | None = Field(
        default=None,
        max_length=10000,
        description="New description (optional)",
    )
    line_items: list[LineItem] | None = Field(
        default=None,
        description="New line items (optional)",
    )
    discount_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="New discount percentage",
    )
    tax_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="New tax percentage",
    )
    valid_until: datetime | None = Field(
        default=None,
        description="New expiration date",
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
        description="Internal notes",
    )
    client_notes: str | None = Field(
        default=None,
        max_length=5000,
        description="Client-visible notes",
    )
    terms: str | None = Field(
        default=None,
        max_length=10000,
        description="Terms and conditions",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "discount_percent": 15,
                "client_notes": "Revised pricing per your feedback",
            }
        }


class ProposalResponse(BaseModel):
    """
    Proposal response schema.

    WHAT: Structure for proposal data in API responses.

    WHY: Controls which fields are exposed and adds computed properties.
    Note: 'notes' field is internal-only - filtered based on user role.
    """

    id: int = Field(..., description="Proposal ID")
    title: str = Field(..., description="Proposal title")
    description: str | None = Field(None, description="Scope description")
    status: ProposalStatus = Field(..., description="Current proposal status")
    project_id: int = Field(..., description="Associated project ID")
    org_id: int = Field(..., description="Organization ID")
    version: int = Field(..., description="Proposal version number")
    previous_version_id: int | None = Field(None, description="Previous version ID")
    line_items: list[dict[str, Any]] | None = Field(None, description="Line items")
    subtotal: float = Field(..., description="Sum of line items")
    discount_percent: float | None = Field(None, description="Discount percentage")
    discount_amount: float | None = Field(None, description="Calculated discount")
    tax_percent: float | None = Field(None, description="Tax percentage")
    tax_amount: float | None = Field(None, description="Calculated tax")
    total: float = Field(..., description="Final total amount")
    valid_until: datetime | None = Field(None, description="Expiration date")
    sent_at: datetime | None = Field(None, description="When sent to client")
    viewed_at: datetime | None = Field(None, description="When client viewed")
    approved_at: datetime | None = Field(None, description="When approved")
    rejected_at: datetime | None = Field(None, description="When rejected")
    rejection_reason: str | None = Field(None, description="Rejection reason")
    notes: str | None = Field(None, description="Internal notes (ADMIN only)")
    client_notes: str | None = Field(None, description="Client-visible notes")
    terms: str | None = Field(None, description="Terms and conditions")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    is_editable: bool = Field(..., description="Whether proposal can be edited")
    is_expired: bool = Field(..., description="Whether proposal has expired")
    can_be_approved: bool = Field(..., description="Whether can be approved")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "title": "Website Automation Proposal",
                "description": "Proposal for automating lead capture",
                "status": "sent",
                "project_id": 1,
                "org_id": 1,
                "version": 1,
                "previous_version_id": None,
                "line_items": [
                    {"description": "Development", "quantity": 40, "unit_price": 150, "amount": 6000}
                ],
                "subtotal": 6000.00,
                "discount_percent": 10,
                "discount_amount": 600.00,
                "tax_percent": 0,
                "tax_amount": 0,
                "total": 5400.00,
                "valid_until": "2025-02-28T23:59:59",
                "sent_at": "2025-01-15T10:00:00",
                "viewed_at": None,
                "approved_at": None,
                "rejected_at": None,
                "rejection_reason": None,
                "notes": None,
                "client_notes": "Valid for 30 days",
                "terms": "50% deposit required",
                "created_at": "2025-01-14T09:00:00",
                "updated_at": "2025-01-15T10:00:00",
                "is_editable": False,
                "is_expired": False,
                "can_be_approved": True,
            }
        }


class ProposalListResponse(BaseModel):
    """
    Paginated proposal list response schema.

    WHAT: Wrapper for paginated proposal list responses.

    WHY: Provides pagination metadata alongside items.
    """

    items: list[ProposalResponse] = Field(..., description="List of proposals")
    total: int = Field(..., description="Total proposals matching filters")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum items per page")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": 1,
                        "title": "Website Automation Proposal",
                        "status": "sent",
                        "project_id": 1,
                        "org_id": 1,
                        "total": 5400.00,
                    }
                ],
                "total": 8,
                "skip": 0,
                "limit": 10,
            }
        }


class ProposalStats(BaseModel):
    """
    Proposal statistics response schema.

    WHAT: Aggregated proposal metrics for dashboards.

    WHY: Quick overview of proposal pipeline without fetching all data.
    """

    total: int = Field(..., description="Total proposals")
    by_status: dict[str, int] = Field(..., description="Count by status")
    pending_count: int = Field(..., description="Sent + viewed proposals")
    total_value: float = Field(..., description="Sum of all proposal totals")
    approved_value: float = Field(..., description="Sum of approved proposals")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 20,
                "by_status": {
                    "draft": 3,
                    "sent": 4,
                    "viewed": 2,
                    "approved": 8,
                    "rejected": 2,
                    "expired": 1,
                    "revised": 0,
                },
                "pending_count": 6,
                "total_value": 125000.00,
                "approved_value": 85000.00,
            }
        }
