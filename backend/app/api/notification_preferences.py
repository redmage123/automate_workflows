"""
Notification Preferences API endpoints.

WHAT: REST API for managing user notification preferences.

WHY: Users need to control their notification settings:
- Which categories they receive notifications for
- Which channels (email, Slack, in-app) are enabled
- How frequently (immediate, digest, none)

HOW: CRUD endpoints for preferences, protected by authentication.
Security category cannot be disabled (password changes, etc.).
"""

from typing import List, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import ValidationError, ResourceNotFoundError
from app.db.session import get_db
from app.dao.notification_preference import NotificationPreferenceDAO
from app.models.user import User
from app.models.notification_preference import (
    NotificationCategory,
    NotificationFrequency,
)
from app.schemas.notification_preference import (
    NotificationCategoryEnum,
    NotificationFrequencyEnum,
    NotificationPreferenceUpdate,
    NotificationPreferenceBulkUpdate,
    NotificationPreferenceResponse,
    NotificationPreferencesResponse,
    NotificationCategoriesResponse,
    CATEGORY_METADATA,
)
from app.services.audit import AuditService


router = APIRouter(
    prefix="/users/me/notification-preferences",
    tags=["notification-preferences"],
)


@router.get(
    "",
    response_model=NotificationPreferencesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all notification preferences",
    description="Get notification preferences for all categories for the current user",
)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """
    Get all notification preferences for the current user.

    WHAT: Retrieves preferences for all notification categories.

    WHY: Frontend needs all preferences to display settings UI.
    If a preference doesn't exist, returns defaults for that category.

    HOW: Queries all preferences for user, merges with defaults.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict of category -> preference settings
    """
    dao = NotificationPreferenceDAO(db)
    prefs_dict = await dao.get_preferences_as_dict(current_user.id)

    # Convert to response format
    preferences = {}
    for category, pref_data in prefs_dict.items():
        preferences[category] = NotificationPreferenceResponse(
            category=NotificationCategoryEnum(pref_data["category"]),
            channel_email=pref_data["channel_email"],
            channel_slack=pref_data["channel_slack"],
            channel_in_app=pref_data["channel_in_app"],
            frequency=NotificationFrequencyEnum(pref_data["frequency"]),
            is_enabled=pref_data["is_enabled"],
        )

    return NotificationPreferencesResponse(preferences=preferences)


@router.get(
    "/categories",
    response_model=NotificationCategoriesResponse,
    status_code=status.HTTP_200_OK,
    summary="List notification categories",
    description="Get information about available notification categories",
)
async def get_notification_categories(
    current_user: User = Depends(get_current_user),
) -> NotificationCategoriesResponse:
    """
    List available notification categories with metadata.

    WHAT: Returns list of all notification categories with descriptions.

    WHY: Frontend needs category metadata to:
    - Display human-readable labels
    - Show category descriptions
    - Know which categories can be disabled

    HOW: Returns static category metadata from CATEGORY_METADATA.

    Args:
        current_user: Authenticated user (for access control)

    Returns:
        List of category information
    """
    return NotificationCategoriesResponse(
        categories=list(CATEGORY_METADATA.values())
    )


@router.get(
    "/{category}",
    response_model=NotificationPreferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get preference for category",
    description="Get notification preference for a specific category",
)
async def get_notification_preference(
    category: NotificationCategoryEnum,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferenceResponse:
    """
    Get notification preference for a specific category.

    WHAT: Retrieves preference for one notification category.

    WHY: Allows checking settings for a single category.

    HOW: Gets or creates preference with defaults if not exists.

    Args:
        category: Notification category to get
        current_user: Authenticated user
        db: Database session

    Returns:
        Preference settings for the category
    """
    dao = NotificationPreferenceDAO(db)
    model_category = NotificationCategory(category.value)

    pref = await dao.get_or_create_preference(current_user.id, model_category)

    return NotificationPreferenceResponse(
        category=category,
        channel_email=pref.channel_email,
        channel_slack=pref.channel_slack,
        channel_in_app=pref.channel_in_app,
        frequency=NotificationFrequencyEnum(pref.frequency.value),
        is_enabled=pref.is_enabled,
    )


@router.put(
    "/{category}",
    response_model=NotificationPreferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update preference for category",
    description="Update notification preference for a specific category",
)
async def update_notification_preference(
    category: NotificationCategoryEnum,
    update: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferenceResponse:
    """
    Update notification preference for a specific category.

    WHAT: Modifies preference settings for one category.

    WHY: Allows users to customize notification behavior per category.
    Only provided fields are updated.

    HOW: Updates preference in database, enforcing security rules.
    Security category cannot be disabled.

    Args:
        category: Notification category to update
        update: Fields to update (only provided fields changed)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated preference settings

    Raises:
        ValidationError: If trying to disable security notifications
    """
    dao = NotificationPreferenceDAO(db)
    audit = AuditService(db)
    model_category = NotificationCategory(category.value)

    # Convert frequency if provided
    frequency = None
    if update.frequency is not None:
        frequency = NotificationFrequency(update.frequency.value)

    # Update preference
    pref = await dao.update_preference(
        user_id=current_user.id,
        category=model_category,
        channel_email=update.channel_email,
        channel_slack=update.channel_slack,
        channel_in_app=update.channel_in_app,
        frequency=frequency,
        is_enabled=update.is_enabled,
    )

    # Audit log
    await audit.log(
        action="notification_preference_updated",
        user_id=current_user.id,
        org_id=current_user.org_id,
        resource_type="notification_preference",
        resource_id=str(pref.id),
        extra_data={
            "category": category.value,
            "updates": update.model_dump(exclude_unset=True),
        },
    )

    await db.commit()

    return NotificationPreferenceResponse(
        category=category,
        channel_email=pref.channel_email,
        channel_slack=pref.channel_slack,
        channel_in_app=pref.channel_in_app,
        frequency=NotificationFrequencyEnum(pref.frequency.value),
        is_enabled=pref.is_enabled,
    )


@router.put(
    "",
    response_model=NotificationPreferencesResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk update preferences",
    description="Update multiple notification preferences at once",
)
async def bulk_update_notification_preferences(
    update: NotificationPreferenceBulkUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """
    Bulk update multiple notification preferences.

    WHAT: Updates preferences for multiple categories in one request.

    WHY: Allows saving all preferences from settings UI in one API call.
    More efficient than multiple individual updates.

    HOW: Iterates through provided preferences, updates each.
    Returns all preferences (not just updated ones) for UI refresh.

    Args:
        update: List of preference updates with categories
        current_user: Authenticated user
        db: Database session

    Returns:
        All preferences after update

    Raises:
        ValidationError: If trying to disable security notifications
    """
    dao = NotificationPreferenceDAO(db)
    audit = AuditService(db)

    # Convert to dict format for DAO
    preferences_data = []
    for pref_update in update.preferences:
        data = {
            "category": pref_update.category.value,
        }
        if pref_update.channel_email is not None:
            data["channel_email"] = pref_update.channel_email
        if pref_update.channel_slack is not None:
            data["channel_slack"] = pref_update.channel_slack
        if pref_update.channel_in_app is not None:
            data["channel_in_app"] = pref_update.channel_in_app
        if pref_update.frequency is not None:
            data["frequency"] = pref_update.frequency.value
        if pref_update.is_enabled is not None:
            data["is_enabled"] = pref_update.is_enabled
        preferences_data.append(data)

    # Update all preferences
    updated = await dao.update_all_preferences(current_user.id, preferences_data)

    # Audit log bulk update
    await audit.log(
        action="notification_preferences_bulk_updated",
        user_id=current_user.id,
        org_id=current_user.org_id,
        resource_type="notification_preference",
        extra_data={
            "categories_updated": [p.category.value for p in updated],
            "update_count": len(updated),
        },
    )

    await db.commit()

    # Return all preferences (not just updated)
    prefs_dict = await dao.get_preferences_as_dict(current_user.id)

    preferences = {}
    for category, pref_data in prefs_dict.items():
        preferences[category] = NotificationPreferenceResponse(
            category=NotificationCategoryEnum(pref_data["category"]),
            channel_email=pref_data["channel_email"],
            channel_slack=pref_data["channel_slack"],
            channel_in_app=pref_data["channel_in_app"],
            frequency=NotificationFrequencyEnum(pref_data["frequency"]),
            is_enabled=pref_data["is_enabled"],
        )

    return NotificationPreferencesResponse(preferences=preferences)
