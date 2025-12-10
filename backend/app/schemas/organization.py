"""
Pydantic schemas for organization endpoints.

WHY: Schemas define request/response contracts for organization management,
providing validation, documentation, and type safety.
"""

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    """
    Organization creation request schema.

    WHY: Validates organization creation data with required fields.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Organization name",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Organization description",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Acme Corporation",
                "description": "Leading provider of automation services",
            }
        }


class OrganizationUpdate(BaseModel):
    """
    Organization update request schema.

    WHY: Allows partial updates with optional fields.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Organization name",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Organization description",
    )
    settings: dict | None = Field(
        default=None,
        description="Organization settings (JSON)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Acme Corporation",
                "description": "Updated description",
                "settings": {"theme": "dark", "notifications_enabled": True},
            }
        }


class OrganizationResponse(BaseModel):
    """
    Organization response schema.

    WHY: Returns organization data with all fields.
    """

    id: int = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    description: str | None = Field(None, description="Organization description")
    settings: dict = Field(default_factory=dict, description="Organization settings")
    is_active: bool = Field(..., description="Whether organization is active")
    created_at: str = Field(..., description="Organization creation timestamp")
    updated_at: str = Field(..., description="Organization last update timestamp")

    class Config:
        from_attributes = True  # Enable ORM mode for SQLAlchemy models
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Acme Corporation",
                "description": "Leading provider of automation services",
                "settings": {"theme": "light", "notifications_enabled": True},
                "is_active": True,
                "created_at": "2025-10-12T10:30:00",
                "updated_at": "2025-10-12T15:45:00",
            }
        }
