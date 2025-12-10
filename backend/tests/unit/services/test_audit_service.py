"""
Audit Service Tests.

WHAT: Unit tests for the AuditService.

WHY: The audit service is critical for OWASP A09 compliance, providing
comprehensive security event logging. These tests ensure:
- Authentication events are properly logged
- Account lifecycle events are tracked
- Data mutation events include before/after values
- Context is correctly captured from request middleware
- Errors in logging don't break business operations

HOW: Tests use pytest async fixtures with mock sessions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit import AuditService
from app.models.audit_log import AuditLog, AuditAction
from app.middleware.request_context import RequestContext, _request_context


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_audit_log():
    """Create a mock AuditLog object."""
    log = MagicMock(spec=AuditLog)
    log.id = 1
    log.action = AuditAction.LOGIN_SUCCESS
    log.resource_type = "auth"
    log.actor_user_id = 123
    log.ip_address = "192.168.1.1"
    return log


@pytest.fixture
def request_context():
    """Set up a request context for testing."""
    ctx = RequestContext(
        request_id="test-request-id",
        ip_address="192.168.1.100",
        user_agent="TestBrowser/1.0",
        path="/api/test",
        method="POST",
    )
    token = _request_context.set(ctx)
    yield ctx
    _request_context.reset(token)


class TestAuditServiceInit:
    """Tests for AuditService initialization."""

    def test_init_creates_dao(self, mock_session):
        """
        Test that initialization creates DAO with session.

        WHY: Service should properly initialize its DAO dependency.
        """
        service = AuditService(mock_session)
        assert service.dao is not None
        assert service._session == mock_session


@pytest.mark.asyncio
class TestAuditServiceContextExtraction:
    """Tests for context extraction from request middleware."""

    async def test_get_context_with_middleware(self, mock_session, request_context):
        """
        Test context extraction when middleware has set context.

        WHY: Service should automatically get IP/user-agent from context.
        """
        service = AuditService(mock_session)
        ip, ua = service._get_context()

        assert ip == "192.168.1.100"
        assert ua == "TestBrowser/1.0"

    async def test_get_context_without_middleware(self, mock_session):
        """
        Test context extraction when no middleware context exists.

        WHY: Service should handle missing context gracefully.
        """
        # Ensure no context is set
        _request_context.set(None)

        service = AuditService(mock_session)
        ip, ua = service._get_context()

        assert ip is None
        assert ua is None


@pytest.mark.asyncio
class TestAuditServiceLogEvent:
    """Tests for the generic log_event method."""

    async def test_log_event_creates_audit_log(self, mock_session, request_context):
        """
        Test that log_event creates an audit log entry.

        WHY: Core logging functionality must work correctly.
        """
        # Set up mock DAO
        mock_log = MagicMock(spec=AuditLog)
        mock_log.id = 1

        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=mock_log)

        result = await service.log_event(
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="auth",
            actor_user_id=123,
        )

        assert result is not None
        service.dao.create.assert_called_once()

        # Verify context was captured
        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["ip_address"] == "192.168.1.100"
        assert call_kwargs["user_agent"] == "TestBrowser/1.0"
        assert call_kwargs["actor_user_id"] == 123
        assert call_kwargs["action"] == AuditAction.LOGIN_SUCCESS

    async def test_log_event_allows_ip_override(self, mock_session, request_context):
        """
        Test that explicit IP overrides context IP.

        WHY: Sometimes we need to log a different IP than the request origin.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_event(
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="auth",
            ip_address="10.0.0.1",  # Override
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["ip_address"] == "10.0.0.1"

    async def test_log_event_handles_exception_gracefully(self, mock_session):
        """
        Test that exceptions don't propagate from logging.

        WHY: Audit logging failures should NEVER break business operations.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(side_effect=Exception("DB error"))

        # Should not raise
        result = await service.log_event(
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="auth",
        )

        assert result is None  # Returns None on failure


@pytest.mark.asyncio
class TestAuditServiceAuthEvents:
    """Tests for authentication event logging methods."""

    async def test_log_login_success(self, mock_session, request_context):
        """
        Test logging successful login.

        WHY: Successful logins must be tracked for security analysis.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_login_success(user_id=123, org_id=456)

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.LOGIN_SUCCESS
        assert call_kwargs["resource_type"] == "auth"
        assert call_kwargs["actor_user_id"] == 123
        assert call_kwargs["org_id"] == 456

    async def test_log_login_failure_with_user(self, mock_session, request_context):
        """
        Test logging failed login for known user.

        WHY: Failed logins for valid users indicate password guessing.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_login_failure(
            attempted_email="user@example.com",
            user_id=123,
            reason="Invalid password",
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.LOGIN_FAILURE
        assert call_kwargs["actor_user_id"] == 123
        assert call_kwargs["extra_data"]["attempted_email"] == "user@example.com"
        assert call_kwargs["extra_data"]["reason"] == "Invalid password"

    async def test_log_login_failure_unknown_user(self, mock_session, request_context):
        """
        Test logging failed login for unknown user.

        WHY: Failed logins with unknown emails indicate enumeration attacks.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_login_failure(
            attempted_email="attacker@example.com",
            user_id=None,
            reason="User not found",
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.LOGIN_FAILURE
        assert call_kwargs["actor_user_id"] is None
        assert call_kwargs["extra_data"]["attempted_email"] == "attacker@example.com"

    async def test_log_logout(self, mock_session, request_context):
        """
        Test logging user logout.

        WHY: Logout events help track session duration and detect forced logouts.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_logout(user_id=123, org_id=456)

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.LOGOUT
        assert call_kwargs["actor_user_id"] == 123
        assert call_kwargs["org_id"] == 456

    async def test_log_password_change(self, mock_session, request_context):
        """
        Test logging password change.

        WHY: Password changes are security-critical events.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_password_change(user_id=123, org_id=456)

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.PASSWORD_CHANGE
        assert call_kwargs["actor_user_id"] == 123

    async def test_log_password_reset_request(self, mock_session, request_context):
        """
        Test logging password reset request.

        WHY: Reset requests may indicate account takeover attempts.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_password_reset_request(
            email="user@example.com",
            user_id=123,
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.PASSWORD_RESET_REQUEST
        assert call_kwargs["extra_data"]["email"] == "user@example.com"

    async def test_log_password_reset_complete(self, mock_session, request_context):
        """
        Test logging completed password reset.

        WHY: Completed resets confirm successful password change.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_password_reset_complete(user_id=123, org_id=456)

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.PASSWORD_RESET_COMPLETE


@pytest.mark.asyncio
class TestAuditServiceAccountEvents:
    """Tests for account lifecycle event logging."""

    async def test_log_account_created(self, mock_session, request_context):
        """
        Test logging account creation.

        WHY: Account creation must be tracked for growth and abuse detection.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_account_created(
            user_id=123,
            org_id=456,
            extra_data={"email": "new@example.com"},
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.ACCOUNT_CREATED
        assert call_kwargs["resource_type"] == "user"
        assert call_kwargs["resource_id"] == 123
        assert call_kwargs["org_id"] == 456

    async def test_log_account_created_by_admin(self, mock_session, request_context):
        """
        Test logging account creation by admin.

        WHY: Admin-created accounts have different audit trail.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_account_created(
            user_id=124,  # New user
            org_id=456,
            created_by=123,  # Admin who created it
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["actor_user_id"] == 123  # Admin is actor
        assert call_kwargs["resource_id"] == 124  # New user is resource

    async def test_log_email_verified(self, mock_session, request_context):
        """
        Test logging email verification.

        WHY: Email verification is important for account security.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_email_verified(user_id=123, org_id=456)

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.EMAIL_VERIFIED


@pytest.mark.asyncio
class TestAuditServiceOrgEvents:
    """Tests for organization event logging."""

    async def test_log_org_created(self, mock_session, request_context):
        """
        Test logging organization creation.

        WHY: Org creation is tracked for multi-tenant auditing.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_org_created(
            org_id=456,
            created_by_user_id=123,
            org_name="Test Org",
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.ORG_CREATED
        assert call_kwargs["resource_type"] == "organization"
        assert call_kwargs["resource_id"] == 456
        assert call_kwargs["extra_data"]["org_name"] == "Test Org"

    async def test_log_user_joined_org(self, mock_session, request_context):
        """
        Test logging user joining organization.

        WHY: Membership changes are important for access control auditing.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_user_joined_org(
            user_id=123,
            org_id=456,
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.USER_JOINED_ORG


@pytest.mark.asyncio
class TestAuditServiceRoleEvents:
    """Tests for role and permission event logging."""

    async def test_log_role_change(self, mock_session, request_context):
        """
        Test logging role change with before/after values.

        WHY: Role changes are security-critical and need full audit trail.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_role_change(
            user_id=124,
            changed_by_user_id=123,
            old_role="CLIENT",
            new_role="ADMIN",
            org_id=456,
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.ROLE_CHANGE
        assert call_kwargs["actor_user_id"] == 123  # Admin making change
        assert call_kwargs["resource_id"] == 124  # User being changed
        assert call_kwargs["changes"]["role"]["before"] == "CLIENT"
        assert call_kwargs["changes"]["role"]["after"] == "ADMIN"


@pytest.mark.asyncio
class TestAuditServiceDataEvents:
    """Tests for data mutation event logging."""

    async def test_log_create(self, mock_session, request_context):
        """
        Test logging resource creation.

        WHY: All data creation must be audited.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_create(
            resource_type="project",
            resource_id=789,
            actor_user_id=123,
            org_id=456,
            extra_data={"name": "New Project"},
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.CREATE
        assert call_kwargs["resource_type"] == "project"
        assert call_kwargs["resource_id"] == 789

    async def test_log_update(self, mock_session, request_context):
        """
        Test logging resource update with changes.

        WHY: Updates need before/after values for complete audit trail.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        changes = {
            "status": {"before": "draft", "after": "published"},
            "title": {"before": "Old Title", "after": "New Title"},
        }

        await service.log_update(
            resource_type="project",
            resource_id=789,
            actor_user_id=123,
            org_id=456,
            changes=changes,
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.UPDATE
        assert call_kwargs["changes"] == changes

    async def test_log_delete(self, mock_session, request_context):
        """
        Test logging resource deletion.

        WHY: Deletions must be tracked for compliance and recovery.
        """
        service = AuditService(mock_session)
        service.dao = AsyncMock()
        service.dao.create = AsyncMock(return_value=MagicMock())

        await service.log_delete(
            resource_type="project",
            resource_id=789,
            actor_user_id=123,
            org_id=456,
            extra_data={"name": "Deleted Project"},
        )

        call_kwargs = service.dao.create.call_args.kwargs
        assert call_kwargs["action"] == AuditAction.DELETE
        assert call_kwargs["extra_data"]["name"] == "Deleted Project"
