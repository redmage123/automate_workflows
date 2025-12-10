"""
Audit Log Data Access Object (DAO).

WHAT: Data access layer for audit log operations.

WHY: OWASP A09 (Security Logging and Monitoring) requires comprehensive
audit logging. This DAO provides:
- Tamper-proof logging (immutable records)
- Convenient methods for common audit events
- Query methods for security investigations
- Rate limiting support (count recent events)

HOW: Extends BaseDAO but overrides update/delete to enforce immutability.
Provides specialized query methods for security analysis.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditAction
from app.core.exceptions import AuditLogImmutableError


class AuditLogDAO:
    """
    Data Access Object for audit log operations.

    WHAT: Provides methods for creating and querying audit logs.

    WHY: Centralizes all audit log database operations with:
    - Immutability enforcement (no updates or deletes)
    - Convenience methods for common patterns
    - Query optimization for security investigations

    HOW: Uses SQLAlchemy async session for all operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize AuditLogDAO with database session.

        WHY: Dependency injection allows easy testing and session management.

        Args:
            session: Async database session
        """
        self.session = session

    async def create(
        self,
        action: AuditAction,
        resource_type: str,
        actor_user_id: Optional[int] = None,
        resource_id: Optional[int] = None,
        org_id: Optional[int] = None,
        changes: Optional[Dict[str, Any]] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """
        Create a new audit log entry.

        WHAT: Persists a security event to the audit log.

        WHY: Every security-relevant action must be logged for compliance
        and forensic analysis.

        Args:
            action: Type of event (from AuditAction enum)
            resource_type: Category of affected resource
            actor_user_id: User who performed the action (nullable for failed logins)
            resource_id: Specific resource ID (nullable)
            org_id: Organization context for multi-tenant filtering
            changes: Before/after values for mutations
            extra_data: Additional context (e.g., attempted_email for failed logins)
            ip_address: Client IP address
            user_agent: Client browser/application info

        Returns:
            The created AuditLog entry

        Raises:
            IntegrityError: If database constraints are violated
        """
        log = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            org_id=org_id,
            changes=changes,
            extra_data=extra_data,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def log_auth_event(
        self,
        user_id: Optional[int],
        action: AuditAction,
        ip_address: str,
        user_agent: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Convenience method for logging authentication events.

        WHAT: Creates audit log entries for auth-related events.

        WHY: Authentication events are the most common audit logs.
        This method simplifies logging with sensible defaults.

        Args:
            user_id: User who authenticated (None for failed attempts with unknown user)
            action: Auth action (LOGIN_SUCCESS, LOGIN_FAILURE, LOGOUT, etc.)
            ip_address: Client IP address
            user_agent: Client browser info
            extra_data: Additional context (e.g., attempted_email for failures)

        Returns:
            The created AuditLog entry
        """
        return await self.create(
            actor_user_id=user_id,
            action=action,
            resource_type="auth",
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data=extra_data,
        )

    async def log_data_change(
        self,
        user_id: int,
        action: AuditAction,
        resource_type: str,
        resource_id: int,
        org_id: int,
        changes: Dict[str, Any],
        ip_address: str,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """
        Convenience method for logging data mutations.

        WHAT: Creates audit log entries for CRUD operations.

        WHY: Data changes must be logged with before/after values
        for compliance and debugging.

        Args:
            user_id: User who made the change
            action: Type of change (CREATE, UPDATE, DELETE)
            resource_type: Type of resource (e.g., "project", "user")
            resource_id: ID of the affected resource
            org_id: Organization owning the resource
            changes: Before/after values
            ip_address: Client IP address
            user_agent: Client browser info

        Returns:
            The created AuditLog entry
        """
        return await self.create(
            actor_user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            org_id=org_id,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def get_by_id(self, log_id: int) -> Optional[AuditLog]:
        """
        Retrieve a single audit log by ID.

        Args:
            log_id: Primary key of the audit log

        Returns:
            The AuditLog if found, None otherwise
        """
        result = await self.session.execute(
            select(AuditLog).where(AuditLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Retrieve audit logs for a specific user.

        WHAT: Gets all audit entries where the user was the actor.

        WHY: Security investigations often need to trace all actions
        by a specific user.

        Args:
            user_id: Actor user ID
            skip: Pagination offset
            limit: Maximum records to return

        Returns:
            List of AuditLog entries for the user
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.actor_user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_action(
        self,
        action: AuditAction,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Retrieve audit logs by action type.

        WHAT: Filters logs to specific action types.

        WHY: Security teams need to quickly find specific event types
        (e.g., all failed logins, all role changes).

        Args:
            action: Action type to filter by
            skip: Pagination offset
            limit: Maximum records to return

        Returns:
            List of AuditLog entries matching the action
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_ip_address(
        self,
        ip_address: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Retrieve audit logs from a specific IP address.

        WHAT: Filters logs by source IP.

        WHY: Detecting attacks often involves analyzing all activity
        from a suspicious IP address.

        Args:
            ip_address: IP address to filter by
            skip: Pagination offset
            limit: Maximum records to return

        Returns:
            List of AuditLog entries from the IP
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.ip_address == ip_address)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Retrieve audit logs within a time range.

        WHAT: Filters logs by timestamp range.

        WHY: Incident response requires analyzing activity within
        specific time windows.

        Args:
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            skip: Pagination offset
            limit: Maximum records to return

        Returns:
            List of AuditLog entries within the range
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.created_at >= start_time)
            .where(AuditLog.created_at <= end_time)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_org(
        self,
        org_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Retrieve audit logs for a specific organization.

        WHAT: Filters logs by organization context.

        WHY: Multi-tenant compliance requires org-scoped audit reports.

        Args:
            org_id: Organization ID
            skip: Pagination offset
            limit: Maximum records to return

        Returns:
            List of AuditLog entries for the organization
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.org_id == org_id)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_recent_failed_logins(
        self,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        minutes: int = 15,
    ) -> int:
        """
        Count recent failed login attempts.

        WHAT: Counts LOGIN_FAILURE events within a time window.

        WHY: Used for account lockout policies and rate limiting
        to prevent brute force attacks.

        Args:
            user_id: Optional user ID to filter by
            ip_address: Optional IP address to filter by
            minutes: Time window in minutes (default 15)

        Returns:
            Number of failed login attempts

        Note: At least one of user_id or ip_address should be provided.
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

        query = (
            select(func.count(AuditLog.id))
            .where(AuditLog.action == AuditAction.LOGIN_FAILURE)
            .where(AuditLog.created_at >= cutoff_time)
        )

        if user_id is not None:
            query = query.where(AuditLog.actor_user_id == user_id)

        if ip_address is not None:
            query = query.where(AuditLog.ip_address == ip_address)

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def update(self, log_id: int, **kwargs: Any) -> None:
        """
        Attempt to update an audit log (BLOCKED).

        WHAT: Raises an error - audit logs are immutable.

        WHY: Audit logs must be tamper-proof. Once written, they cannot
        be modified to maintain forensic integrity.

        Raises:
            AuditLogImmutableError: Always raised - updates not allowed
        """
        raise AuditLogImmutableError(
            "Audit logs are immutable and cannot be updated. "
            "This is required for security compliance."
        )

    async def delete(self, log_id: int) -> None:
        """
        Attempt to delete an audit log (BLOCKED).

        WHAT: Raises an error - audit logs cannot be deleted.

        WHY: Compliance requires retention of audit logs. Deletion
        would allow covering tracks.

        Raises:
            AuditLogImmutableError: Always raised - deletions not allowed
        """
        raise AuditLogImmutableError(
            "Audit logs cannot be deleted. "
            "This is required for security compliance and legal retention."
        )
