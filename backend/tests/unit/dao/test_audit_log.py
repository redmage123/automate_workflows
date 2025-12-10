"""
Audit Log DAO Tests.

WHAT: Unit tests for the AuditLog model and DAO.

WHY: Audit logging is critical for OWASP A09 (Security Logging and Monitoring).
These tests ensure we properly track all security-relevant events including:
- Authentication events (login, logout, failed attempts)
- Authorization changes (role changes, permissions)
- Data mutations (create, update, delete)
- Administrative actions

HOW: Tests use pytest with async fixtures for database operations.
Following TDD, these tests are written FIRST before implementation.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditAction
from app.dao.audit_log import AuditLogDAO


class TestAuditLogModel:
    """Tests for the AuditLog model structure."""

    def test_audit_action_enum_has_required_values(self):
        """
        Verify AuditAction enum includes all security-relevant actions.

        WHY: OWASP A09 requires logging of authentication, authorization,
        and data access events.
        """
        # Authentication events
        assert AuditAction.LOGIN_SUCCESS.value == "LOGIN_SUCCESS"
        assert AuditAction.LOGIN_FAILURE.value == "LOGIN_FAILURE"
        assert AuditAction.LOGOUT.value == "LOGOUT"
        assert AuditAction.PASSWORD_CHANGE.value == "PASSWORD_CHANGE"
        assert AuditAction.PASSWORD_RESET_REQUEST.value == "PASSWORD_RESET_REQUEST"
        assert AuditAction.PASSWORD_RESET_COMPLETE.value == "PASSWORD_RESET_COMPLETE"

        # Authorization events
        assert AuditAction.ROLE_CHANGE.value == "ROLE_CHANGE"
        assert AuditAction.PERMISSION_GRANT.value == "PERMISSION_GRANT"
        assert AuditAction.PERMISSION_REVOKE.value == "PERMISSION_REVOKE"

        # Data mutation events
        assert AuditAction.CREATE.value == "CREATE"
        assert AuditAction.UPDATE.value == "UPDATE"
        assert AuditAction.DELETE.value == "DELETE"

        # Account events
        assert AuditAction.ACCOUNT_ACTIVATED.value == "ACCOUNT_ACTIVATED"
        assert AuditAction.ACCOUNT_DEACTIVATED.value == "ACCOUNT_DEACTIVATED"
        assert AuditAction.EMAIL_VERIFIED.value == "EMAIL_VERIFIED"

    def test_audit_log_model_has_required_fields(self):
        """
        Verify AuditLog model has all fields needed for compliance.

        WHY: Security audits require detailed context about who, what,
        when, where, and why for every logged event.
        """
        # Create a minimal audit log entry
        log = AuditLog(
            actor_user_id=1,
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="auth",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        # Verify required fields
        assert log.actor_user_id == 1
        assert log.action == AuditAction.LOGIN_SUCCESS
        assert log.resource_type == "auth"
        assert log.ip_address == "192.168.1.1"
        assert log.user_agent == "Mozilla/5.0"

        # Optional fields should be None by default
        assert log.resource_id is None
        assert log.org_id is None
        assert log.changes is None
        assert log.extra_data is None


@pytest.mark.asyncio
class TestAuditLogDAO:
    """Tests for the AuditLogDAO data access operations."""

    async def test_create_audit_log(self, db_session: AsyncSession, test_user, test_org):
        """
        Test creating an audit log entry.

        WHY: Every security event must be persistently logged.
        """
        dao = AuditLogDAO(db_session)

        log = await dao.create(
            actor_user_id=test_user.id,
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="auth",
            org_id=test_org.id,
            ip_address="192.168.1.1",
            user_agent="Test Browser",
        )

        assert log.id is not None
        assert log.actor_user_id == test_user.id
        assert log.action == AuditAction.LOGIN_SUCCESS
        assert log.resource_type == "auth"
        assert log.org_id == test_org.id
        assert log.ip_address == "192.168.1.1"
        assert log.created_at is not None

    async def test_create_audit_log_with_changes(self, db_session: AsyncSession, test_user, test_org):
        """
        Test logging data changes with before/after values.

        WHY: For compliance, we need to track what changed, not just that
        something changed.
        """
        dao = AuditLogDAO(db_session)

        changes = {
            "role": {"before": "CLIENT", "after": "ADMIN"},
            "is_active": {"before": True, "after": False},
        }

        log = await dao.create(
            actor_user_id=test_user.id,
            action=AuditAction.ROLE_CHANGE,
            resource_type="user",
            resource_id=42,
            org_id=test_org.id,
            changes=changes,
            ip_address="10.0.0.1",
        )

        assert log.changes == changes
        assert log.resource_id == 42

    async def test_log_authentication_event(self, db_session: AsyncSession, test_user):
        """
        Test the convenience method for logging auth events.

        WHY: Authentication events are the most common audit logs,
        so a dedicated method improves developer experience.
        """
        dao = AuditLogDAO(db_session)

        log = await dao.log_auth_event(
            user_id=test_user.id,
            action=AuditAction.LOGIN_SUCCESS,
            ip_address="192.168.1.100",
            user_agent="Chrome/120.0",
        )

        assert log.action == AuditAction.LOGIN_SUCCESS
        assert log.resource_type == "auth"
        assert log.ip_address == "192.168.1.100"

    async def test_log_failed_login_without_user_id(self, db_session: AsyncSession):
        """
        Test logging failed login attempts (user may not exist).

        WHY: Failed login attempts must be logged even if we don't know
        who the user is (for detecting brute force attacks).
        """
        dao = AuditLogDAO(db_session)

        log = await dao.log_auth_event(
            user_id=None,
            action=AuditAction.LOGIN_FAILURE,
            ip_address="192.168.1.100",
            user_agent="Suspicious Bot",
            extra_data={"attempted_email": "attacker@example.com"},
        )

        assert log.actor_user_id is None
        assert log.action == AuditAction.LOGIN_FAILURE
        assert log.extra_data["attempted_email"] == "attacker@example.com"

    async def test_get_logs_by_user(self, db_session: AsyncSession, test_user, test_org):
        """
        Test retrieving audit logs for a specific user.

        WHY: Security investigations often need to trace all actions
        by a specific user.
        """
        dao = AuditLogDAO(db_session)

        # Create multiple logs for the user
        await dao.log_auth_event(test_user.id, AuditAction.LOGIN_SUCCESS, "1.1.1.1")
        await dao.log_auth_event(test_user.id, AuditAction.LOGOUT, "1.1.1.1")

        logs = await dao.get_by_user(test_user.id)

        assert len(logs) >= 2
        assert all(log.actor_user_id == test_user.id for log in logs)

    async def test_get_logs_by_action(self, db_session: AsyncSession, test_user):
        """
        Test filtering logs by action type.

        WHY: Security teams need to quickly find specific types of events
        (e.g., all failed logins in the last hour).
        """
        dao = AuditLogDAO(db_session)

        # Create logs with different actions
        await dao.log_auth_event(test_user.id, AuditAction.LOGIN_SUCCESS, "1.1.1.1")
        await dao.log_auth_event(test_user.id, AuditAction.LOGIN_FAILURE, "1.1.1.1")
        await dao.log_auth_event(test_user.id, AuditAction.LOGIN_FAILURE, "1.1.1.2")

        failed_logins = await dao.get_by_action(AuditAction.LOGIN_FAILURE)

        assert len(failed_logins) >= 2
        assert all(log.action == AuditAction.LOGIN_FAILURE for log in failed_logins)

    async def test_get_logs_by_ip_address(self, db_session: AsyncSession, test_user):
        """
        Test filtering logs by IP address.

        WHY: Detecting attacks often involves analyzing all activity
        from a suspicious IP address.
        """
        dao = AuditLogDAO(db_session)

        suspicious_ip = "10.0.0.99"
        await dao.log_auth_event(test_user.id, AuditAction.LOGIN_FAILURE, suspicious_ip)
        await dao.log_auth_event(test_user.id, AuditAction.LOGIN_FAILURE, suspicious_ip)
        await dao.log_auth_event(test_user.id, AuditAction.LOGIN_SUCCESS, "1.1.1.1")

        logs_from_ip = await dao.get_by_ip_address(suspicious_ip)

        assert len(logs_from_ip) >= 2
        assert all(log.ip_address == suspicious_ip for log in logs_from_ip)

    async def test_get_logs_by_date_range(self, db_session: AsyncSession, test_user):
        """
        Test filtering logs by time range.

        WHY: Incident response requires analyzing activity within
        specific time windows.
        """
        dao = AuditLogDAO(db_session)

        await dao.log_auth_event(test_user.id, AuditAction.LOGIN_SUCCESS, "1.1.1.1")

        # Query logs from the last hour
        start_time = datetime.utcnow() - timedelta(hours=1)
        end_time = datetime.utcnow() + timedelta(minutes=1)

        logs = await dao.get_by_date_range(start_time, end_time)

        assert len(logs) >= 1
        assert all(start_time <= log.created_at <= end_time for log in logs)

    async def test_get_recent_failed_logins_for_user(self, db_session: AsyncSession, test_user):
        """
        Test counting recent failed login attempts for a user.

        WHY: Account lockout policies need to count recent failures
        to prevent brute force attacks.
        """
        dao = AuditLogDAO(db_session)

        # Create multiple failed login attempts
        for _ in range(5):
            await dao.log_auth_event(test_user.id, AuditAction.LOGIN_FAILURE, "1.1.1.1")

        count = await dao.count_recent_failed_logins(
            user_id=test_user.id,
            minutes=15,
        )

        assert count >= 5

    async def test_get_logs_by_org(self, db_session: AsyncSession, test_user, test_org):
        """
        Test filtering logs by organization.

        WHY: Multi-tenant compliance requires org-scoped audit reports.
        """
        dao = AuditLogDAO(db_session)

        await dao.create(
            actor_user_id=test_user.id,
            action=AuditAction.CREATE,
            resource_type="project",
            resource_id=1,
            org_id=test_org.id,
            ip_address="1.1.1.1",
        )

        logs = await dao.get_by_org(test_org.id)

        assert len(logs) >= 1
        assert all(log.org_id == test_org.id for log in logs)

    async def test_audit_log_immutability(self, db_session: AsyncSession, test_user):
        """
        Test that audit logs cannot be updated (immutable).

        WHY: Audit logs must be tamper-proof. Once written, they should
        never be modified to maintain forensic integrity.
        """
        dao = AuditLogDAO(db_session)

        log = await dao.log_auth_event(test_user.id, AuditAction.LOGIN_SUCCESS, "1.1.1.1")

        # Attempting to update should raise an error or be blocked
        with pytest.raises(Exception):  # Could be custom AuditLogImmutableError
            await dao.update(log.id, action=AuditAction.LOGIN_FAILURE)

    async def test_audit_log_cannot_be_deleted(self, db_session: AsyncSession, test_user):
        """
        Test that audit logs cannot be deleted.

        WHY: Compliance requires retention of audit logs. Deletion
        would allow covering tracks.
        """
        dao = AuditLogDAO(db_session)

        log = await dao.log_auth_event(test_user.id, AuditAction.LOGIN_SUCCESS, "1.1.1.1")

        # Attempting to delete should raise an error
        with pytest.raises(Exception):  # Could be custom AuditLogDeletionError
            await dao.delete(log.id)
