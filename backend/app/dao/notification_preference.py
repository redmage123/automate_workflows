"""
Notification Preference DAO (Data Access Object).

WHAT: Data access layer for notification preference operations.

WHY: Centralizes all database operations for notification preferences,
ensuring consistent access patterns and security enforcement.

HOW: Uses SQLAlchemy async sessions with proper error handling
and type safety.
"""

import logging
from typing import Optional, List, Dict, Any

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.models.notification_preference import (
    NotificationPreference,
    NotificationCategory,
    NotificationFrequency,
    DEFAULT_PREFERENCES,
)
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
)


logger = logging.getLogger(__name__)


class NotificationPreferenceDAO(BaseDAO[NotificationPreference]):
    """
    DAO for NotificationPreference operations.

    WHAT: Handles all database operations for notification preferences.

    WHY: Provides:
    - CRUD operations for preferences
    - Default preference creation for new users
    - Bulk operations for preference management
    - Type-safe operations with proper validation

    HOW: Extends BaseDAO with preference-specific methods.
    Uses SQLAlchemy async queries with session management.

    Example:
        dao = NotificationPreferenceDAO(session)
        prefs = await dao.get_user_preferences(user_id=1)
        await dao.update_preference(user_id=1, category="tickets", channel_email=False)
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize DAO with database session.

        Args:
            session: Async SQLAlchemy session
        """
        super().__init__(NotificationPreference, session)

    async def get_user_preferences(
        self,
        user_id: int,
    ) -> List[NotificationPreference]:
        """
        Get all notification preferences for a user.

        WHAT: Retrieves all category preferences for a user.

        WHY: Used for displaying preferences UI and checking
        notification settings.

        HOW: Queries all preferences for user_id.

        Args:
            user_id: User ID to get preferences for

        Returns:
            List of NotificationPreference objects
        """
        query = select(NotificationPreference).where(
            NotificationPreference.user_id == user_id
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_user_preference(
        self,
        user_id: int,
        category: NotificationCategory,
    ) -> Optional[NotificationPreference]:
        """
        Get a specific preference for a user.

        WHAT: Retrieves preference for a specific category.

        WHY: Used for checking notification settings before sending.

        HOW: Queries by user_id and category.

        Args:
            user_id: User ID
            category: Notification category

        Returns:
            NotificationPreference or None if not found
        """
        query = select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.category == category,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create_preference(
        self,
        user_id: int,
        category: NotificationCategory,
    ) -> NotificationPreference:
        """
        Get preference or create with defaults if not exists.

        WHAT: Ensures a preference exists for a category.

        WHY: Provides consistent behavior when preference hasn't
        been explicitly set by user.

        HOW: Tries to get existing, creates with defaults if not found.

        Args:
            user_id: User ID
            category: Notification category

        Returns:
            Existing or newly created NotificationPreference
        """
        pref = await self.get_user_preference(user_id, category)

        if pref is not None:
            return pref

        # Create with defaults
        defaults = DEFAULT_PREFERENCES.get(category, {})
        pref = NotificationPreference(
            user_id=user_id,
            category=category,
            channel_email=defaults.get("channel_email", True),
            channel_slack=defaults.get("channel_slack", False),
            channel_in_app=defaults.get("channel_in_app", True),
            frequency=defaults.get("frequency", NotificationFrequency.IMMEDIATE),
            is_enabled=defaults.get("is_enabled", True),
        )

        self.session.add(pref)
        await self.session.flush()
        await self.session.refresh(pref)

        logger.info(
            f"Created default preference for user {user_id}, category {category.value}"
        )

        return pref

    async def create_default_preferences(
        self,
        user_id: int,
    ) -> List[NotificationPreference]:
        """
        Create default preferences for all categories for a new user.

        WHAT: Initializes preferences with sensible defaults.

        WHY: New users should have preferences ready to use
        without explicit configuration.

        HOW: Creates a preference for each category using DEFAULT_PREFERENCES.

        Args:
            user_id: User ID to create preferences for

        Returns:
            List of created NotificationPreference objects
        """
        preferences = []

        for category, defaults in DEFAULT_PREFERENCES.items():
            pref = NotificationPreference(
                user_id=user_id,
                category=category,
                channel_email=defaults["channel_email"],
                channel_slack=defaults["channel_slack"],
                channel_in_app=defaults["channel_in_app"],
                frequency=defaults["frequency"],
                is_enabled=defaults["is_enabled"],
            )
            self.session.add(pref)
            preferences.append(pref)

        await self.session.flush()

        # Refresh all to get IDs
        for pref in preferences:
            await self.session.refresh(pref)

        logger.info(
            f"Created {len(preferences)} default preferences for user {user_id}"
        )

        return preferences

    async def update_preference(
        self,
        user_id: int,
        category: NotificationCategory,
        *,
        channel_email: Optional[bool] = None,
        channel_slack: Optional[bool] = None,
        channel_in_app: Optional[bool] = None,
        frequency: Optional[NotificationFrequency] = None,
        is_enabled: Optional[bool] = None,
    ) -> NotificationPreference:
        """
        Update a notification preference.

        WHAT: Modifies preference settings for a category.

        WHY: Allows users to customize their notification behavior.

        HOW: Gets or creates preference, updates provided fields.
        Enforces security category cannot be disabled.

        Args:
            user_id: User ID
            category: Notification category to update
            channel_email: Update email channel setting
            channel_slack: Update Slack channel setting
            channel_in_app: Update in-app channel setting
            frequency: Update notification frequency
            is_enabled: Update enabled status

        Returns:
            Updated NotificationPreference

        Raises:
            ValidationError: If trying to disable security notifications
        """
        # Enforce security category cannot be disabled
        if category == NotificationCategory.SECURITY:
            if is_enabled is False:
                raise ValidationError(
                    message="Security notifications cannot be disabled",
                    details={"category": category.value},
                )
            if channel_email is False:
                raise ValidationError(
                    message="Security email notifications cannot be disabled",
                    details={"category": category.value},
                )

        pref = await self.get_or_create_preference(user_id, category)

        # Update only provided fields
        if channel_email is not None:
            pref.channel_email = channel_email
        if channel_slack is not None:
            pref.channel_slack = channel_slack
        if channel_in_app is not None:
            pref.channel_in_app = channel_in_app
        if frequency is not None:
            pref.frequency = frequency
        if is_enabled is not None:
            pref.is_enabled = is_enabled

        await self.session.flush()
        await self.session.refresh(pref)

        logger.info(
            f"Updated preference for user {user_id}, category {category.value}"
        )

        return pref

    async def update_all_preferences(
        self,
        user_id: int,
        preferences_data: List[Dict[str, Any]],
    ) -> List[NotificationPreference]:
        """
        Update multiple preferences at once.

        WHAT: Bulk update preferences from a list of category settings.

        WHY: Allows saving all preferences in one operation from UI.

        HOW: Iterates through provided data, updates each category.

        Args:
            user_id: User ID
            preferences_data: List of dicts with category and settings

        Returns:
            List of updated NotificationPreference objects

        Example:
            await dao.update_all_preferences(user_id=1, preferences_data=[
                {"category": "tickets", "channel_email": False},
                {"category": "proposals", "frequency": "daily_digest"},
            ])
        """
        updated = []

        for pref_data in preferences_data:
            category_str = pref_data.get("category")
            if not category_str:
                continue

            try:
                category = NotificationCategory(category_str)
            except ValueError:
                logger.warning(f"Invalid category: {category_str}")
                continue

            pref = await self.update_preference(
                user_id=user_id,
                category=category,
                channel_email=pref_data.get("channel_email"),
                channel_slack=pref_data.get("channel_slack"),
                channel_in_app=pref_data.get("channel_in_app"),
                frequency=NotificationFrequency(pref_data["frequency"])
                if pref_data.get("frequency")
                else None,
                is_enabled=pref_data.get("is_enabled"),
            )
            updated.append(pref)

        return updated

    async def should_notify(
        self,
        user_id: int,
        category: NotificationCategory,
        channel: str = "email",
    ) -> bool:
        """
        Check if notification should be sent to user for category/channel.

        WHAT: Determines if a notification should be sent.

        WHY: Called before sending any notification to respect user preferences.

        HOW: Gets preference, checks enabled status and channel setting.

        Args:
            user_id: User ID
            category: Notification category
            channel: Channel to check ("email", "slack", "in_app")

        Returns:
            True if notification should be sent
        """
        # Security category always sends email
        if category == NotificationCategory.SECURITY and channel == "email":
            return True

        pref = await self.get_or_create_preference(user_id, category)

        if not pref.is_enabled:
            return False

        if pref.frequency == NotificationFrequency.NONE:
            return False

        if channel == "email":
            return pref.channel_email
        elif channel == "slack":
            return pref.channel_slack
        elif channel == "in_app":
            return pref.channel_in_app
        else:
            return False

    async def delete_user_preferences(
        self,
        user_id: int,
    ) -> int:
        """
        Delete all preferences for a user.

        WHAT: Removes all preference records for a user.

        WHY: Used when user account is deleted (cascade should handle this,
        but explicit method is available).

        HOW: Deletes all rows where user_id matches.

        Args:
            user_id: User ID to delete preferences for

        Returns:
            Number of preferences deleted
        """
        query = delete(NotificationPreference).where(
            NotificationPreference.user_id == user_id
        )
        result = await self.session.execute(query)
        await self.session.flush()

        deleted_count = result.rowcount
        logger.info(f"Deleted {deleted_count} preferences for user {user_id}")

        return deleted_count

    async def get_preferences_as_dict(
        self,
        user_id: int,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get all preferences as a dictionary keyed by category.

        WHAT: Returns preferences in a format suitable for API responses.

        WHY: Easier to work with in frontend than list of objects.

        HOW: Fetches all preferences, converts to dict structure.

        Args:
            user_id: User ID

        Returns:
            Dict mapping category name to preference settings
        """
        prefs = await self.get_user_preferences(user_id)

        # Start with defaults for all categories
        result = {}
        for category in NotificationCategory:
            defaults = DEFAULT_PREFERENCES.get(category, {})
            result[category.value] = {
                "category": category.value,
                "channel_email": defaults.get("channel_email", True),
                "channel_slack": defaults.get("channel_slack", False),
                "channel_in_app": defaults.get("channel_in_app", True),
                "frequency": defaults.get("frequency", NotificationFrequency.IMMEDIATE).value,
                "is_enabled": defaults.get("is_enabled", True),
            }

        # Override with actual preferences
        for pref in prefs:
            result[pref.category.value] = {
                "category": pref.category.value,
                "channel_email": pref.channel_email,
                "channel_slack": pref.channel_slack,
                "channel_in_app": pref.channel_in_app,
                "frequency": pref.frequency.value,
                "is_enabled": pref.is_enabled,
            }

        return result
