"""
Unit tests for Notification Preference DAO.

WHAT: Tests for NotificationPreferenceDAO operations.

WHY: Verifies that:
1. CRUD operations work correctly for notification preferences
2. Default preferences are created properly for new users
3. Security category cannot be disabled
4. Bulk updates work correctly
5. should_notify logic is accurate

HOW: Uses pytest-asyncio with in-memory SQLite database for isolation.
"""

import pytest
from datetime import datetime

from app.dao.notification_preference import NotificationPreferenceDAO
from app.models.notification_preference import (
    NotificationPreference,
    NotificationCategory,
    NotificationFrequency,
    DEFAULT_PREFERENCES,
)
from app.core.exceptions import ValidationError
from tests.factories import OrganizationFactory, UserFactory


class TestNotificationPreferenceDAOCreate:
    """Tests for preference creation."""

    @pytest.mark.asyncio
    async def test_create_default_preferences_success(self, db_session, test_org, test_user):
        """Test creating default preferences for a new user."""
        dao = NotificationPreferenceDAO(db_session)

        preferences = await dao.create_default_preferences(test_user.id)

        # Should create one preference per category
        assert len(preferences) == len(NotificationCategory)

        # Check each category exists
        categories = {pref.category for pref in preferences}
        for category in NotificationCategory:
            assert category in categories

    @pytest.mark.asyncio
    async def test_create_default_preferences_values(self, db_session, test_org, test_user):
        """Test that default preferences match DEFAULT_PREFERENCES."""
        dao = NotificationPreferenceDAO(db_session)

        preferences = await dao.create_default_preferences(test_user.id)

        for pref in preferences:
            expected = DEFAULT_PREFERENCES[pref.category]
            assert pref.channel_email == expected["channel_email"]
            assert pref.channel_slack == expected["channel_slack"]
            assert pref.channel_in_app == expected["channel_in_app"]
            assert pref.frequency == expected["frequency"]
            assert pref.is_enabled == expected["is_enabled"]

    @pytest.mark.asyncio
    async def test_get_or_create_creates_if_not_exists(self, db_session, test_org, test_user):
        """Test that get_or_create creates preference if it doesn't exist."""
        dao = NotificationPreferenceDAO(db_session)

        # Initially no preferences exist
        prefs = await dao.get_user_preferences(test_user.id)
        assert len(prefs) == 0

        # Get or create should create it
        pref = await dao.get_or_create_preference(test_user.id, NotificationCategory.TICKETS)

        assert pref is not None
        assert pref.category == NotificationCategory.TICKETS
        assert pref.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing(self, db_session, test_org, test_user):
        """Test that get_or_create returns existing preference."""
        dao = NotificationPreferenceDAO(db_session)

        # Create preference first
        pref1 = await dao.get_or_create_preference(test_user.id, NotificationCategory.TICKETS)

        # Update it
        pref1.channel_email = False
        await db_session.flush()

        # Get or create should return the existing one
        pref2 = await dao.get_or_create_preference(test_user.id, NotificationCategory.TICKETS)

        assert pref2.id == pref1.id
        assert pref2.channel_email is False  # Retains our update


class TestNotificationPreferenceDAORead:
    """Tests for reading preferences."""

    @pytest.mark.asyncio
    async def test_get_user_preferences(self, db_session, test_org, test_user):
        """Test getting all preferences for a user."""
        dao = NotificationPreferenceDAO(db_session)

        # Create defaults
        await dao.create_default_preferences(test_user.id)

        # Get preferences
        prefs = await dao.get_user_preferences(test_user.id)

        assert len(prefs) == len(NotificationCategory)
        assert all(pref.user_id == test_user.id for pref in prefs)

    @pytest.mark.asyncio
    async def test_get_user_preference_by_category(self, db_session, test_org, test_user):
        """Test getting a specific preference by category."""
        dao = NotificationPreferenceDAO(db_session)

        # Create defaults
        await dao.create_default_preferences(test_user.id)

        # Get specific preference
        pref = await dao.get_user_preference(test_user.id, NotificationCategory.SECURITY)

        assert pref is not None
        assert pref.category == NotificationCategory.SECURITY

    @pytest.mark.asyncio
    async def test_get_user_preference_not_found(self, db_session, test_org, test_user):
        """Test getting preference that doesn't exist."""
        dao = NotificationPreferenceDAO(db_session)

        # No preferences created yet
        pref = await dao.get_user_preference(test_user.id, NotificationCategory.TICKETS)

        assert pref is None

    @pytest.mark.asyncio
    async def test_get_preferences_as_dict(self, db_session, test_org, test_user):
        """Test getting preferences as dictionary."""
        dao = NotificationPreferenceDAO(db_session)

        # Create some preferences
        await dao.get_or_create_preference(test_user.id, NotificationCategory.TICKETS)
        await dao.get_or_create_preference(test_user.id, NotificationCategory.SECURITY)

        # Get as dict
        prefs_dict = await dao.get_preferences_as_dict(test_user.id)

        # Should have all categories with defaults filled in
        assert len(prefs_dict) == len(NotificationCategory)

        # Check structure
        for category in NotificationCategory:
            assert category.value in prefs_dict
            pref_data = prefs_dict[category.value]
            assert "channel_email" in pref_data
            assert "channel_slack" in pref_data
            assert "channel_in_app" in pref_data
            assert "frequency" in pref_data
            assert "is_enabled" in pref_data


class TestNotificationPreferenceDAOUpdate:
    """Tests for updating preferences."""

    @pytest.mark.asyncio
    async def test_update_preference_single_field(self, db_session, test_org, test_user):
        """Test updating a single field."""
        dao = NotificationPreferenceDAO(db_session)

        pref = await dao.update_preference(
            user_id=test_user.id,
            category=NotificationCategory.TICKETS,
            channel_email=False,
        )

        assert pref.channel_email is False
        # Other fields should have defaults
        assert pref.channel_slack == DEFAULT_PREFERENCES[NotificationCategory.TICKETS]["channel_slack"]

    @pytest.mark.asyncio
    async def test_update_preference_multiple_fields(self, db_session, test_org, test_user):
        """Test updating multiple fields at once."""
        dao = NotificationPreferenceDAO(db_session)

        pref = await dao.update_preference(
            user_id=test_user.id,
            category=NotificationCategory.PROPOSALS,
            channel_email=False,
            channel_slack=True,
            frequency=NotificationFrequency.DAILY_DIGEST,
        )

        assert pref.channel_email is False
        assert pref.channel_slack is True
        assert pref.frequency == NotificationFrequency.DAILY_DIGEST

    @pytest.mark.asyncio
    async def test_update_preference_security_cannot_disable(self, db_session, test_org, test_user):
        """Test that security category cannot be disabled."""
        dao = NotificationPreferenceDAO(db_session)

        with pytest.raises(ValidationError) as exc_info:
            await dao.update_preference(
                user_id=test_user.id,
                category=NotificationCategory.SECURITY,
                is_enabled=False,
            )

        assert "Security notifications cannot be disabled" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_update_preference_security_email_cannot_disable(self, db_session, test_org, test_user):
        """Test that security email cannot be disabled."""
        dao = NotificationPreferenceDAO(db_session)

        with pytest.raises(ValidationError) as exc_info:
            await dao.update_preference(
                user_id=test_user.id,
                category=NotificationCategory.SECURITY,
                channel_email=False,
            )

        assert "Security email notifications cannot be disabled" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_update_all_preferences(self, db_session, test_org, test_user):
        """Test bulk updating multiple preferences."""
        dao = NotificationPreferenceDAO(db_session)

        preferences_data = [
            {"category": "tickets", "channel_email": False},
            {"category": "proposals", "frequency": "daily_digest"},
            {"category": "invoices", "is_enabled": False},
        ]

        updated = await dao.update_all_preferences(test_user.id, preferences_data)

        assert len(updated) == 3

        # Verify updates
        tickets_pref = await dao.get_user_preference(test_user.id, NotificationCategory.TICKETS)
        assert tickets_pref.channel_email is False

        proposals_pref = await dao.get_user_preference(test_user.id, NotificationCategory.PROPOSALS)
        assert proposals_pref.frequency == NotificationFrequency.DAILY_DIGEST

        invoices_pref = await dao.get_user_preference(test_user.id, NotificationCategory.INVOICES)
        assert invoices_pref.is_enabled is False


class TestNotificationPreferenceDAOShouldNotify:
    """Tests for should_notify logic."""

    @pytest.mark.asyncio
    async def test_should_notify_default_true(self, db_session, test_org, test_user):
        """Test default notification behavior is enabled."""
        dao = NotificationPreferenceDAO(db_session)

        # Default should allow email
        should_notify = await dao.should_notify(
            test_user.id, NotificationCategory.TICKETS, channel="email"
        )

        assert should_notify is True

    @pytest.mark.asyncio
    async def test_should_notify_disabled_category(self, db_session, test_org, test_user):
        """Test that disabled categories don't send notifications."""
        dao = NotificationPreferenceDAO(db_session)

        # Disable tickets
        await dao.update_preference(
            user_id=test_user.id,
            category=NotificationCategory.TICKETS,
            is_enabled=False,
        )

        should_notify = await dao.should_notify(
            test_user.id, NotificationCategory.TICKETS, channel="email"
        )

        assert should_notify is False

    @pytest.mark.asyncio
    async def test_should_notify_disabled_channel(self, db_session, test_org, test_user):
        """Test that disabled channels don't send notifications."""
        dao = NotificationPreferenceDAO(db_session)

        # Disable email for tickets
        await dao.update_preference(
            user_id=test_user.id,
            category=NotificationCategory.TICKETS,
            channel_email=False,
        )

        should_notify_email = await dao.should_notify(
            test_user.id, NotificationCategory.TICKETS, channel="email"
        )
        should_notify_in_app = await dao.should_notify(
            test_user.id, NotificationCategory.TICKETS, channel="in_app"
        )

        assert should_notify_email is False
        assert should_notify_in_app is True  # Still enabled

    @pytest.mark.asyncio
    async def test_should_notify_frequency_none(self, db_session, test_org, test_user):
        """Test that frequency=NONE prevents notifications."""
        dao = NotificationPreferenceDAO(db_session)

        # Set frequency to NONE
        await dao.update_preference(
            user_id=test_user.id,
            category=NotificationCategory.PROPOSALS,
            frequency=NotificationFrequency.NONE,
        )

        should_notify = await dao.should_notify(
            test_user.id, NotificationCategory.PROPOSALS, channel="email"
        )

        assert should_notify is False

    @pytest.mark.asyncio
    async def test_should_notify_security_always_emails(self, db_session, test_org, test_user):
        """Test that security category always sends email."""
        dao = NotificationPreferenceDAO(db_session)

        # Even without explicit preference, security should notify
        should_notify = await dao.should_notify(
            test_user.id, NotificationCategory.SECURITY, channel="email"
        )

        assert should_notify is True

    @pytest.mark.asyncio
    async def test_should_notify_slack_channel(self, db_session, test_org, test_user):
        """Test slack notification channel."""
        dao = NotificationPreferenceDAO(db_session)

        # Default has slack disabled
        should_notify = await dao.should_notify(
            test_user.id, NotificationCategory.TICKETS, channel="slack"
        )

        assert should_notify is False

        # Enable slack
        await dao.update_preference(
            user_id=test_user.id,
            category=NotificationCategory.TICKETS,
            channel_slack=True,
        )

        should_notify = await dao.should_notify(
            test_user.id, NotificationCategory.TICKETS, channel="slack"
        )

        assert should_notify is True


class TestNotificationPreferenceDAODelete:
    """Tests for deleting preferences."""

    @pytest.mark.asyncio
    async def test_delete_user_preferences(self, db_session, test_org, test_user):
        """Test deleting all preferences for a user."""
        dao = NotificationPreferenceDAO(db_session)

        # Create preferences
        await dao.create_default_preferences(test_user.id)

        # Verify they exist
        prefs = await dao.get_user_preferences(test_user.id)
        assert len(prefs) == len(NotificationCategory)

        # Delete all
        deleted_count = await dao.delete_user_preferences(test_user.id)

        assert deleted_count == len(NotificationCategory)

        # Verify deleted
        prefs = await dao.get_user_preferences(test_user.id)
        assert len(prefs) == 0


class TestNotificationPreferenceDAOMultiTenancy:
    """Tests for multi-tenancy isolation."""

    @pytest.mark.asyncio
    async def test_preferences_isolated_by_user(self, db_session):
        """Test that preferences are isolated per user."""
        org = await OrganizationFactory.create(db_session, name="Test Org")
        user1 = await UserFactory.create(db_session, email="user1@test.com", organization=org)
        user2 = await UserFactory.create(db_session, email="user2@test.com", organization=org)

        dao = NotificationPreferenceDAO(db_session)

        # Create preferences for user1
        await dao.create_default_preferences(user1.id)

        # Update user1's tickets preference
        await dao.update_preference(
            user_id=user1.id,
            category=NotificationCategory.TICKETS,
            channel_email=False,
        )

        # User2's tickets should still be default (no preference exists yet)
        user2_pref = await dao.get_or_create_preference(user2.id, NotificationCategory.TICKETS)

        assert user2_pref.channel_email is True  # Default

        # Verify user1's is still updated
        user1_pref = await dao.get_user_preference(user1.id, NotificationCategory.TICKETS)
        assert user1_pref.channel_email is False

    @pytest.mark.asyncio
    async def test_preferences_count_per_user(self, db_session):
        """Test that each user has their own set of preferences."""
        org = await OrganizationFactory.create(db_session, name="Test Org")
        user1 = await UserFactory.create(db_session, email="user1@test.com", organization=org)
        user2 = await UserFactory.create(db_session, email="user2@test.com", organization=org)

        dao = NotificationPreferenceDAO(db_session)

        # Create preferences for both users
        await dao.create_default_preferences(user1.id)
        await dao.create_default_preferences(user2.id)

        # Each should have full set
        user1_prefs = await dao.get_user_preferences(user1.id)
        user2_prefs = await dao.get_user_preferences(user2.id)

        assert len(user1_prefs) == len(NotificationCategory)
        assert len(user2_prefs) == len(NotificationCategory)

        # All user1 prefs belong to user1
        assert all(p.user_id == user1.id for p in user1_prefs)
        assert all(p.user_id == user2.id for p in user2_prefs)
