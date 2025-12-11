"""
Notification Preference Schemas.

WHAT: Pydantic schemas for notification preference API operations.

WHY: Provides type-safe validation for:
- API request/response bodies
- Preference update operations
- Bulk preference updates

HOW: Uses Pydantic v2 with proper validation and examples.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class NotificationCategoryEnum(str, Enum):
    """
    Notification category values for API.

    WHY: Enum ensures only valid categories are accepted.
    """

    SECURITY = "security"
    TICKETS = "tickets"
    PROPOSALS = "proposals"
    INVOICES = "invoices"
    PROJECTS = "projects"
    WORKFLOWS = "workflows"
    SYSTEM = "system"


class NotificationFrequencyEnum(str, Enum):
    """
    Notification frequency values for API.

    WHY: Enum ensures only valid frequencies are accepted.
    """

    IMMEDIATE = "immediate"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_DIGEST = "weekly_digest"
    NONE = "none"


class NotificationPreferenceBase(BaseModel):
    """
    Base schema with common preference fields.

    WHAT: Shared fields for preference create/update operations.
    """

    channel_email: Optional[bool] = Field(
        default=None,
        description="Enable email notifications for this category",
    )
    channel_slack: Optional[bool] = Field(
        default=None,
        description="Enable Slack notifications for this category",
    )
    channel_in_app: Optional[bool] = Field(
        default=None,
        description="Enable in-app notifications for this category",
    )
    frequency: Optional[NotificationFrequencyEnum] = Field(
        default=None,
        description="How frequently to send notifications",
    )
    is_enabled: Optional[bool] = Field(
        default=None,
        description="Master switch for this category",
    )


class NotificationPreferenceUpdate(NotificationPreferenceBase):
    """
    Schema for updating a single preference.

    WHAT: Request body for PUT /notification-preferences/{category}

    WHY: All fields optional - only provided fields are updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "channel_email": True,
                "channel_slack": False,
                "frequency": "immediate",
            }
        }
    )


class NotificationPreferenceUpdateWithCategory(NotificationPreferenceBase):
    """
    Schema for updating preference with category specified.

    WHAT: Used in bulk update operations.

    WHY: Allows updating multiple categories in one request.
    """

    category: NotificationCategoryEnum = Field(
        ...,
        description="Notification category to update",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "category": "tickets",
                "channel_email": False,
                "frequency": "daily_digest",
            }
        }
    )


class NotificationPreferenceBulkUpdate(BaseModel):
    """
    Schema for bulk updating multiple preferences.

    WHAT: Request body for PUT /notification-preferences

    WHY: Allows saving all preferences in one API call.
    """

    preferences: List[NotificationPreferenceUpdateWithCategory] = Field(
        ...,
        description="List of preference updates",
        min_length=1,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "preferences": [
                    {
                        "category": "tickets",
                        "channel_email": True,
                        "frequency": "immediate",
                    },
                    {
                        "category": "proposals",
                        "channel_email": False,
                        "frequency": "daily_digest",
                    },
                ]
            }
        }
    )


class NotificationPreferenceResponse(BaseModel):
    """
    Schema for a single preference response.

    WHAT: Response body for preference operations.

    WHY: Provides full preference state with all fields.
    """

    category: NotificationCategoryEnum = Field(
        ...,
        description="Notification category",
    )
    channel_email: bool = Field(
        ...,
        description="Email notifications enabled",
    )
    channel_slack: bool = Field(
        ...,
        description="Slack notifications enabled",
    )
    channel_in_app: bool = Field(
        ...,
        description="In-app notifications enabled",
    )
    frequency: NotificationFrequencyEnum = Field(
        ...,
        description="Notification frequency",
    )
    is_enabled: bool = Field(
        ...,
        description="Master enabled switch",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "category": "tickets",
                "channel_email": True,
                "channel_slack": False,
                "channel_in_app": True,
                "frequency": "immediate",
                "is_enabled": True,
            }
        }
    )


class NotificationPreferencesResponse(BaseModel):
    """
    Schema for all preferences response.

    WHAT: Response body for GET /notification-preferences

    WHY: Returns all category preferences in a structured format.
    """

    preferences: Dict[str, NotificationPreferenceResponse] = Field(
        ...,
        description="Dictionary mapping category to preference settings",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "preferences": {
                    "security": {
                        "category": "security",
                        "channel_email": True,
                        "channel_slack": False,
                        "channel_in_app": True,
                        "frequency": "immediate",
                        "is_enabled": True,
                    },
                    "tickets": {
                        "category": "tickets",
                        "channel_email": True,
                        "channel_slack": False,
                        "channel_in_app": True,
                        "frequency": "immediate",
                        "is_enabled": True,
                    },
                }
            }
        }
    )


class CategoryInfo(BaseModel):
    """
    Schema for category information.

    WHAT: Describes a notification category for UI display.

    WHY: Helps frontend render category selection with descriptions.
    """

    value: str = Field(..., description="Category value/key")
    label: str = Field(..., description="Human-readable label")
    description: str = Field(..., description="Category description")
    can_disable: bool = Field(..., description="Whether this category can be disabled")


class NotificationCategoriesResponse(BaseModel):
    """
    Schema for listing available categories.

    WHAT: Response body for GET /notification-preferences/categories

    WHY: Provides metadata about available categories.
    """

    categories: List[CategoryInfo] = Field(
        ...,
        description="List of available notification categories",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "categories": [
                    {
                        "value": "security",
                        "label": "Security",
                        "description": "Password changes, login alerts, security events",
                        "can_disable": False,
                    },
                    {
                        "value": "tickets",
                        "label": "Support Tickets",
                        "description": "Ticket creation, updates, comments, SLA alerts",
                        "can_disable": True,
                    },
                ]
            }
        }
    )


# Category metadata for API responses
CATEGORY_METADATA: Dict[str, CategoryInfo] = {
    "security": CategoryInfo(
        value="security",
        label="Security",
        description="Password changes, login alerts, security events. Cannot be disabled.",
        can_disable=False,
    ),
    "tickets": CategoryInfo(
        value="tickets",
        label="Support Tickets",
        description="Ticket creation, updates, comments, and SLA alerts.",
        can_disable=True,
    ),
    "proposals": CategoryInfo(
        value="proposals",
        label="Proposals",
        description="Proposal sent, approved, and rejected notifications.",
        can_disable=True,
    ),
    "invoices": CategoryInfo(
        value="invoices",
        label="Invoices",
        description="Invoice creation and payment confirmation notifications.",
        can_disable=True,
    ),
    "projects": CategoryInfo(
        value="projects",
        label="Projects",
        description="Project status changes and update notifications.",
        can_disable=True,
    ),
    "workflows": CategoryInfo(
        value="workflows",
        label="Workflows",
        description="Workflow execution results and failure notifications.",
        can_disable=True,
    ),
    "system": CategoryInfo(
        value="system",
        label="System",
        description="System announcements and maintenance notices.",
        can_disable=True,
    ),
}
