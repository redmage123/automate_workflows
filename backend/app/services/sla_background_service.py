"""
SLA Breach Background Service.

WHAT: Background service that periodically checks for SLA breaches
and sends notifications to relevant stakeholders.

WHY: Proactive SLA monitoring ensures:
1. Tickets approaching SLA breach get attention before it's too late
2. Breached SLAs are immediately escalated
3. No duplicate notifications are sent
4. All SLA events are logged for auditing

HOW: Uses APScheduler to run every 5 minutes:
1. Query tickets in warning zone or breached
2. Check if notification was already sent
3. Send notifications to assignee and org admins
4. Update notification tracking fields
5. Log all actions for audit trail
"""

import logging
from datetime import datetime
from typing import List, Optional, Callable

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.models.ticket import Ticket, TicketStatus
from app.services.email import get_email_service
from app.services.audit import AuditService
from app.dao.user import UserDAO
from app.models.user import User, UserRole


logger = logging.getLogger(__name__)


# SLA check interval in seconds (5 minutes default)
SLA_CHECK_INTERVAL_SECONDS = getattr(settings, "SLA_CHECK_INTERVAL_SECONDS", 300)


class SLABackgroundService:
    """
    Background service for SLA breach monitoring.

    WHAT: Periodically checks all active tickets for SLA status
    and sends notifications when thresholds are crossed.

    WHY: Provides proactive SLA management:
    - Warning at 75% elapsed (gives time to act)
    - Breach notification when SLA is missed
    - Escalation to admins for visibility
    - Duplicate prevention via tracking fields

    HOW: Scheduled job runs every 5 minutes using APScheduler.
    Uses Redis-backed job store for persistence across restarts.

    Example:
        service = SLABackgroundService()
        await service.check_all_sla_breaches()
    """

    def __init__(self, session_factory: Optional[Callable[[], AsyncSession]] = None):
        """
        Initialize SLA background service.

        Args:
            session_factory: Optional factory for creating database sessions.
                           If not provided, creates sessions from settings.
        """
        self._session_factory = session_factory
        self._email_service = None

    async def _get_session(self) -> AsyncSession:
        """Get a database session for the job."""
        if self._session_factory:
            return self._session_factory()

        # Create engine and session on demand
        engine = create_async_engine(
            settings.ASYNC_DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
        )
        async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        return async_session()

    def _get_email_service(self):
        """Get email service instance."""
        if self._email_service is None:
            self._email_service = get_email_service()
        return self._email_service

    async def check_all_sla_breaches(self) -> dict:
        """
        Main job function: Check all active tickets for SLA status.

        WHAT: Scans all open/in-progress tickets and sends notifications
        for those in warning zone or breached.

        WHY: Centralized SLA checking ensures no tickets are missed
        and notifications are consistent.

        HOW:
        1. Query tickets not in resolved/closed status
        2. Check each for warning zone and breach status
        3. Send notifications where needed
        4. Track sent notifications to prevent duplicates

        Returns:
            Dict with counts of warnings and breaches processed
        """
        logger.info("Starting SLA breach check job")
        start_time = datetime.utcnow()

        stats = {
            "response_warnings": 0,
            "response_breaches": 0,
            "resolution_warnings": 0,
            "resolution_breaches": 0,
            "errors": 0,
        }

        session = await self._get_session()
        try:
            # Get all active tickets (not resolved or closed)
            tickets = await self._get_active_tickets(session)
            logger.info(f"Checking SLA status for {len(tickets)} active tickets")

            for ticket in tickets:
                try:
                    # Check response SLA
                    response_result = await self._check_response_sla(session, ticket)
                    if response_result == "warning":
                        stats["response_warnings"] += 1
                    elif response_result == "breach":
                        stats["response_breaches"] += 1

                    # Check resolution SLA
                    resolution_result = await self._check_resolution_sla(session, ticket)
                    if resolution_result == "warning":
                        stats["resolution_warnings"] += 1
                    elif resolution_result == "breach":
                        stats["resolution_breaches"] += 1

                except Exception as e:
                    logger.error(f"Error checking SLA for ticket {ticket.id}: {e}")
                    stats["errors"] += 1

            await session.commit()

        except Exception as e:
            logger.error(f"Error in SLA breach check job: {e}")
            await session.rollback()
            raise

        finally:
            await session.close()

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"SLA breach check completed in {elapsed:.2f}s. "
            f"Warnings: {stats['response_warnings'] + stats['resolution_warnings']}, "
            f"Breaches: {stats['response_breaches'] + stats['resolution_breaches']}, "
            f"Errors: {stats['errors']}"
        )

        return stats

    async def _get_active_tickets(self, session: AsyncSession) -> List[Ticket]:
        """
        Get all active tickets that need SLA checking.

        WHAT: Queries tickets that are not resolved or closed.

        WHY: Only active tickets need SLA monitoring.
        Resolved/closed tickets have completed their lifecycle.

        Args:
            session: Database session

        Returns:
            List of active Ticket objects
        """
        query = select(Ticket).where(
            Ticket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED])
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def _check_response_sla(
        self, session: AsyncSession, ticket: Ticket
    ) -> Optional[str]:
        """
        Check response SLA status and send notifications if needed.

        Args:
            session: Database session
            ticket: Ticket to check

        Returns:
            "warning", "breach", or None if no action needed
        """
        # Skip if already responded
        if ticket.first_response_at is not None:
            return None

        # Skip if no SLA set
        if ticket.sla_response_due_at is None:
            return None

        now = datetime.utcnow()

        # Check for breach first (more severe)
        if ticket.is_sla_response_breached:
            if ticket.sla_response_breach_sent_at is None:
                await self._send_sla_breach_notification(
                    session, ticket, "response"
                )
                ticket.sla_response_breach_sent_at = now
                await session.flush()
                return "breach"

        # Check for warning (75% elapsed)
        elif ticket.is_sla_response_warning_zone:
            if ticket.sla_response_warning_sent_at is None:
                await self._send_sla_warning_notification(
                    session, ticket, "response"
                )
                ticket.sla_response_warning_sent_at = now
                await session.flush()
                return "warning"

        return None

    async def _check_resolution_sla(
        self, session: AsyncSession, ticket: Ticket
    ) -> Optional[str]:
        """
        Check resolution SLA status and send notifications if needed.

        Args:
            session: Database session
            ticket: Ticket to check

        Returns:
            "warning", "breach", or None if no action needed
        """
        # Skip if already resolved
        if ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            return None

        # Skip if no SLA set
        if ticket.sla_resolution_due_at is None:
            return None

        now = datetime.utcnow()

        # Check for breach first (more severe)
        if ticket.is_sla_resolution_breached:
            if ticket.sla_resolution_breach_sent_at is None:
                await self._send_sla_breach_notification(
                    session, ticket, "resolution"
                )
                ticket.sla_resolution_breach_sent_at = now
                await session.flush()
                return "breach"

        # Check for warning (75% elapsed)
        elif ticket.is_sla_resolution_warning_zone:
            if ticket.sla_resolution_warning_sent_at is None:
                await self._send_sla_warning_notification(
                    session, ticket, "resolution"
                )
                ticket.sla_resolution_warning_sent_at = now
                await session.flush()
                return "warning"

        return None

    async def _send_sla_warning_notification(
        self, session: AsyncSession, ticket: Ticket, sla_type: str
    ) -> None:
        """
        Send SLA warning notification.

        WHAT: Sends notification when SLA is 75% elapsed.

        WHY: Gives team time to act before breach occurs.

        Args:
            session: Database session
            ticket: Ticket with approaching SLA
            sla_type: "response" or "resolution"
        """
        email_service = self._get_email_service()
        audit = AuditService(session)

        # Get recipients (assignee + org admins)
        recipients = await self._get_notification_recipients(session, ticket)

        # Calculate remaining time
        if sla_type == "response":
            remaining_seconds = ticket.sla_response_remaining_seconds
            due_at = ticket.sla_response_due_at
        else:
            remaining_seconds = ticket.sla_resolution_remaining_seconds
            due_at = ticket.sla_resolution_due_at

        remaining_minutes = int(remaining_seconds / 60) if remaining_seconds else 0

        # Format time remaining for display
        if remaining_minutes >= 60:
            hours = remaining_minutes // 60
            mins = remaining_minutes % 60
            time_remaining = f"{hours}h {mins}m"
        else:
            time_remaining = f"{remaining_minutes}m"

        # Get customer info
        customer_name = "Unknown"
        if ticket.created_by:
            customer_name = ticket.created_by.name

        # Get assigned to name
        assigned_to = None
        if ticket.assigned_to:
            assigned_to = ticket.assigned_to.name

        for recipient in recipients:
            try:
                await email_service.send_sla_warning_email(
                    to_email=recipient.email,
                    user_name=recipient.name,
                    ticket_id=ticket.id,
                    ticket_subject=ticket.subject,
                    ticket_priority=ticket.priority.value,
                    sla_type=sla_type,
                    sla_status="warning",
                    due_at=due_at.strftime("%Y-%m-%d %H:%M UTC") if due_at else "N/A",
                    customer_name=customer_name,
                    assigned_to=assigned_to,
                    time_remaining=time_remaining,
                )
                logger.info(
                    f"Sent {sla_type} SLA warning for ticket {ticket.id} to {recipient.email}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to send SLA warning email for ticket {ticket.id} to {recipient.email}: {e}"
                )

        # Audit log
        await audit.log(
            action="sla_warning_sent",
            user_id=None,  # System action
            org_id=ticket.org_id,
            resource_type="ticket",
            resource_id=str(ticket.id),
            extra_data={
                "sla_type": sla_type,
                "remaining_minutes": remaining_minutes,
                "recipients_count": len(recipients),
            },
        )

    async def _send_sla_breach_notification(
        self, session: AsyncSession, ticket: Ticket, sla_type: str
    ) -> None:
        """
        Send SLA breach notification.

        WHAT: Sends notification when SLA is breached.

        WHY: Escalates breached tickets for immediate attention.

        Args:
            session: Database session
            ticket: Ticket with breached SLA
            sla_type: "response" or "resolution"
        """
        email_service = self._get_email_service()
        audit = AuditService(session)

        # Get recipients (assignee + org admins)
        recipients = await self._get_notification_recipients(session, ticket)

        # Get breach time
        if sla_type == "response":
            due_at = ticket.sla_response_due_at
        else:
            due_at = ticket.sla_resolution_due_at

        breach_minutes = 0
        if due_at:
            breach_minutes = int((datetime.utcnow() - due_at).total_seconds() / 60)

        # Format overdue time for display
        if breach_minutes >= 60:
            hours = breach_minutes // 60
            mins = breach_minutes % 60
            time_remaining = f"{hours}h {mins}m overdue"
        else:
            time_remaining = f"{breach_minutes}m overdue"

        # Get customer info
        customer_name = "Unknown"
        if ticket.created_by:
            customer_name = ticket.created_by.name

        # Get assigned to name
        assigned_to = None
        if ticket.assigned_to:
            assigned_to = ticket.assigned_to.name

        for recipient in recipients:
            try:
                # Use same method as warning, with status="breached"
                await email_service.send_sla_warning_email(
                    to_email=recipient.email,
                    user_name=recipient.name,
                    ticket_id=ticket.id,
                    ticket_subject=ticket.subject,
                    ticket_priority=ticket.priority.value,
                    sla_type=sla_type,
                    sla_status="breached",
                    due_at=due_at.strftime("%Y-%m-%d %H:%M UTC") if due_at else "N/A",
                    customer_name=customer_name,
                    assigned_to=assigned_to,
                    time_remaining=time_remaining,
                )
                logger.info(
                    f"Sent {sla_type} SLA breach for ticket {ticket.id} to {recipient.email}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to send SLA breach email for ticket {ticket.id} to {recipient.email}: {e}"
                )

        # Audit log
        await audit.log(
            action="sla_breach_sent",
            user_id=None,  # System action
            org_id=ticket.org_id,
            resource_type="ticket",
            resource_id=str(ticket.id),
            extra_data={
                "sla_type": sla_type,
                "breach_minutes": breach_minutes,
                "recipients_count": len(recipients),
            },
        )

    async def _get_notification_recipients(
        self, session: AsyncSession, ticket: Ticket
    ) -> List[User]:
        """
        Get users who should receive SLA notifications.

        WHAT: Determines notification recipients for a ticket.

        WHY: Ensures right people are notified:
        - Assigned user (if any)
        - All admins in the organization

        Args:
            session: Database session
            ticket: Ticket to get recipients for

        Returns:
            List of User objects to notify
        """
        recipients = []
        user_ids_added = set()

        user_dao = UserDAO(User, session)

        # Add assignee if exists
        if ticket.assigned_to_user_id:
            assignee = await user_dao.get_by_id(ticket.assigned_to_user_id)
            if assignee and assignee.is_active:
                recipients.append(assignee)
                user_ids_added.add(assignee.id)

        # Add org admins
        query = select(User).where(
            and_(
                User.org_id == ticket.org_id,
                User.role == UserRole.ADMIN,
                User.is_active == True,
            )
        )
        result = await session.execute(query)
        admins = result.scalars().all()

        for admin in admins:
            if admin.id not in user_ids_added:
                recipients.append(admin)
                user_ids_added.add(admin.id)

        return recipients


# Singleton instance for the scheduler
_sla_service: Optional[SLABackgroundService] = None


def get_sla_service() -> SLABackgroundService:
    """Get or create SLA background service instance."""
    global _sla_service
    if _sla_service is None:
        _sla_service = SLABackgroundService()
    return _sla_service
