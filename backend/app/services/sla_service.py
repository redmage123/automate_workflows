"""
SLA (Service Level Agreement) service for ticket management.

WHAT: Service for calculating and monitoring SLA timers for support tickets.

WHY: SLA compliance is critical for customer satisfaction and contractual
obligations. This service provides:
- SLA due date calculations based on priority
- Warning detection for approaching deadlines
- Breach detection for missed SLAs
- Business hours support (future enhancement)

HOW: Uses ticket priority to look up SLA configuration and calculates
due dates from ticket creation time. Provides methods to check SLA status
and get tickets at risk of breach.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.ticket import (
    Ticket,
    TicketStatus,
    TicketPriority,
    SLA_CONFIG,
)
from app.dao.ticket import TicketDAO
from app.core.exceptions import ValidationError, TicketNotFoundError


# Logger for SLA service events
logger = logging.getLogger(__name__)


# Warning threshold - percentage of SLA time elapsed before warning
SLA_WARNING_THRESHOLD = 0.75  # 75% of SLA time elapsed


class SLAService:
    """
    Service for SLA calculations and monitoring.

    WHAT: Business logic layer for SLA management.

    WHY: Centralizes SLA logic with:
    - Consistent due date calculations
    - Priority-based SLA configuration
    - Warning and breach detection
    - Integration with audit logging

    HOW: Uses TicketDAO for data access and SLA_CONFIG for priority-based
    timeframes. Provides methods for calculating, checking, and monitoring SLAs.

    Example:
        async def check_sla_status(ticket_id: int, db: AsyncSession):
            sla = SLAService(db)
            status = await sla.get_sla_status(ticket_id)
            if status["response"]["breached"]:
                await send_escalation_email(ticket_id)
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize SLA service with database session.

        Args:
            session: Async database session for ticket queries
        """
        self._session = session
        self._dao = TicketDAO(session)

    def calculate_response_due_at(
        self,
        priority: TicketPriority,
        created_at: datetime,
    ) -> datetime:
        """
        Calculate response SLA due date.

        WHAT: Determines when first response is due.

        WHY: First response time is a key customer satisfaction metric
        and often a contractual requirement.

        HOW: Looks up response_hours from SLA_CONFIG based on priority
        and adds to created_at timestamp.

        Args:
            priority: Ticket priority level
            created_at: Ticket creation timestamp

        Returns:
            Datetime when first response is due
        """
        config = SLA_CONFIG.get(priority, SLA_CONFIG[TicketPriority.MEDIUM])
        return created_at + timedelta(hours=config["response_hours"])

    def calculate_resolution_due_at(
        self,
        priority: TicketPriority,
        created_at: datetime,
    ) -> datetime:
        """
        Calculate resolution SLA due date.

        WHAT: Determines when ticket should be resolved.

        WHY: Resolution time is critical for maintaining customer trust
        and meeting contractual obligations.

        HOW: Looks up resolution_hours from SLA_CONFIG based on priority
        and adds to created_at timestamp.

        Args:
            priority: Ticket priority level
            created_at: Ticket creation timestamp

        Returns:
            Datetime when resolution is due
        """
        config = SLA_CONFIG.get(priority, SLA_CONFIG[TicketPriority.MEDIUM])
        return created_at + timedelta(hours=config["resolution_hours"])

    def get_sla_config_for_priority(
        self,
        priority: TicketPriority,
    ) -> Dict[str, int]:
        """
        Get SLA configuration for a priority level.

        WHAT: Returns the SLA hours for response and resolution.

        WHY: Useful for displaying SLA info to users when creating tickets
        or viewing ticket details.

        Args:
            priority: Ticket priority level

        Returns:
            Dict with response_hours and resolution_hours
        """
        return SLA_CONFIG.get(priority, SLA_CONFIG[TicketPriority.MEDIUM])

    def calculate_time_remaining(
        self,
        due_at: Optional[datetime],
        reference_time: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate time remaining until SLA deadline.

        WHAT: Returns detailed breakdown of time remaining.

        WHY: Enables display of countdown timers and progress bars
        in the UI for SLA monitoring.

        HOW: Calculates delta between now and due date, returns
        breakdown in hours, minutes, seconds and total seconds.

        Args:
            due_at: SLA due datetime
            reference_time: Current time (defaults to UTC now)

        Returns:
            Dict with hours, minutes, seconds, total_seconds, is_breached
            or None if due_at is not set
        """
        if due_at is None:
            return None

        now = reference_time or datetime.utcnow()
        delta = due_at - now
        total_seconds = delta.total_seconds()

        if total_seconds <= 0:
            return {
                "hours": 0,
                "minutes": 0,
                "seconds": 0,
                "total_seconds": 0,
                "is_breached": True,
                "formatted": "BREACHED",
            }

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)

        # Format as human-readable string
        if hours > 24:
            days = hours // 24
            remaining_hours = hours % 24
            formatted = f"{days}d {remaining_hours}h"
        elif hours > 0:
            formatted = f"{hours}h {minutes}m"
        elif minutes > 0:
            formatted = f"{minutes}m {seconds}s"
        else:
            formatted = f"{seconds}s"

        return {
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
            "total_seconds": int(total_seconds),
            "is_breached": False,
            "formatted": formatted,
        }

    def is_in_warning_zone(
        self,
        created_at: datetime,
        due_at: Optional[datetime],
        reference_time: Optional[datetime] = None,
    ) -> bool:
        """
        Check if SLA is in warning zone (approaching breach).

        WHAT: Determines if SLA is at risk of breach.

        WHY: Enables proactive escalation before SLA is breached,
        allowing time to take corrective action.

        HOW: Calculates percentage of SLA time elapsed and compares
        to SLA_WARNING_THRESHOLD (default 75%).

        Args:
            created_at: Ticket creation timestamp
            due_at: SLA due datetime
            reference_time: Current time (defaults to UTC now)

        Returns:
            True if in warning zone (75%+ elapsed) but not yet breached
        """
        if due_at is None:
            return False

        now = reference_time or datetime.utcnow()

        # Check if already breached
        if now >= due_at:
            return False  # Not warning, it's breached

        # Calculate percentage elapsed
        total_time = (due_at - created_at).total_seconds()
        elapsed_time = (now - created_at).total_seconds()

        if total_time <= 0:
            return False

        percentage_elapsed = elapsed_time / total_time
        return percentage_elapsed >= SLA_WARNING_THRESHOLD

    async def get_sla_status(
        self,
        ticket_id: int,
        org_id: int,
    ) -> Dict[str, Any]:
        """
        Get comprehensive SLA status for a ticket.

        WHAT: Returns full SLA status including response and resolution.

        WHY: Single method to get all SLA information for display
        in ticket details view.

        HOW: Fetches ticket, calculates status for both response and
        resolution SLAs, includes warnings and time remaining.

        Args:
            ticket_id: ID of the ticket
            org_id: Organization ID for security scoping

        Returns:
            Dict with response and resolution SLA status

        Raises:
            TicketNotFoundError: If ticket doesn't exist or access denied
        """
        ticket = await self._dao.get_by_id(ticket_id, org_id)
        if not ticket:
            raise TicketNotFoundError(
                message="Ticket not found",
                details={"ticket_id": ticket_id},
            )

        now = datetime.utcnow()

        # Response SLA status
        response_status = {
            "due_at": ticket.sla_response_due_at.isoformat()
            if ticket.sla_response_due_at
            else None,
            "responded_at": ticket.first_response_at.isoformat()
            if ticket.first_response_at
            else None,
            "is_met": ticket.first_response_at is not None,
            "is_breached": ticket.is_sla_response_breached,
            "is_warning": self.is_in_warning_zone(
                ticket.created_at,
                ticket.sla_response_due_at,
            )
            if not ticket.first_response_at
            else False,
            "time_remaining": self.calculate_time_remaining(
                ticket.sla_response_due_at
            )
            if not ticket.first_response_at
            else None,
        }

        # Resolution SLA status
        is_resolved = ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
        resolution_status = {
            "due_at": ticket.sla_resolution_due_at.isoformat()
            if ticket.sla_resolution_due_at
            else None,
            "resolved_at": ticket.resolved_at.isoformat()
            if ticket.resolved_at
            else None,
            "is_met": is_resolved and (
                ticket.resolved_at is not None
                and ticket.sla_resolution_due_at is not None
                and ticket.resolved_at <= ticket.sla_resolution_due_at
            ),
            "is_breached": ticket.is_sla_resolution_breached,
            "is_warning": self.is_in_warning_zone(
                ticket.created_at,
                ticket.sla_resolution_due_at,
            )
            if not is_resolved
            else False,
            "time_remaining": self.calculate_time_remaining(
                ticket.sla_resolution_due_at
            )
            if not is_resolved
            else None,
        }

        return {
            "ticket_id": ticket_id,
            "priority": ticket.priority.value,
            "status": ticket.status.value,
            "sla_config": self.get_sla_config_for_priority(ticket.priority),
            "response": response_status,
            "resolution": resolution_status,
        }

    async def get_at_risk_tickets(
        self,
        org_id: int,
        include_breached: bool = True,
        include_warning: bool = True,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get tickets at risk of SLA breach.

        WHAT: Returns tickets that are breached or in warning zone.

        WHY: Enables SLA dashboard showing tickets needing attention,
        with prioritization for escalation.

        HOW: Queries for tickets with SLA due dates in the past (breached)
        or within warning threshold.

        Args:
            org_id: Organization ID for security scoping
            include_breached: Include already breached tickets
            include_warning: Include tickets in warning zone

        Returns:
            Dict with 'breached' and 'warning' lists of ticket info
        """
        result: Dict[str, List[Dict[str, Any]]] = {
            "breached": [],
            "warning": [],
        }

        if include_breached:
            breached = await self._dao.get_sla_breached_tickets(org_id)
            for ticket in breached:
                result["breached"].append(
                    self._ticket_to_sla_summary(ticket)
                )

        if include_warning:
            warning = await self._dao.get_sla_warning_tickets(
                org_id,
                warning_threshold_hours=2,  # 2 hours warning
            )
            # Filter to only include tickets in actual warning zone
            for ticket in warning:
                if self.is_in_warning_zone(
                    ticket.created_at,
                    ticket.sla_response_due_at,
                ) or self.is_in_warning_zone(
                    ticket.created_at,
                    ticket.sla_resolution_due_at,
                ):
                    result["warning"].append(
                        self._ticket_to_sla_summary(ticket)
                    )

        return result

    def _ticket_to_sla_summary(self, ticket: Ticket) -> Dict[str, Any]:
        """
        Convert ticket to SLA summary dict.

        WHAT: Creates compact SLA info dict for lists.

        WHY: Consistent format for ticket lists in SLA dashboards.

        Args:
            ticket: Ticket model instance

        Returns:
            Dict with key ticket and SLA info
        """
        return {
            "id": ticket.id,
            "subject": ticket.subject,
            "priority": ticket.priority.value,
            "status": ticket.status.value,
            "created_at": ticket.created_at.isoformat(),
            "response_sla": {
                "due_at": ticket.sla_response_due_at.isoformat()
                if ticket.sla_response_due_at
                else None,
                "is_breached": ticket.is_sla_response_breached,
                "time_remaining": self.calculate_time_remaining(
                    ticket.sla_response_due_at
                ),
            },
            "resolution_sla": {
                "due_at": ticket.sla_resolution_due_at.isoformat()
                if ticket.sla_resolution_due_at
                else None,
                "is_breached": ticket.is_sla_resolution_breached,
                "time_remaining": self.calculate_time_remaining(
                    ticket.sla_resolution_due_at
                ),
            },
        }

    async def recalculate_sla_for_priority_change(
        self,
        ticket_id: int,
        org_id: int,
        new_priority: TicketPriority,
    ) -> Ticket:
        """
        Recalculate SLA dates when priority changes.

        WHAT: Updates SLA due dates based on new priority.

        WHY: When priority is escalated (or de-escalated), the SLA
        commitments change and due dates must be recalculated.

        HOW: Fetches ticket, recalculates due dates from original
        created_at using new priority's SLA config.

        Args:
            ticket_id: ID of the ticket
            org_id: Organization ID for security scoping
            new_priority: New priority level

        Returns:
            Updated ticket with new SLA dates

        Raises:
            TicketNotFoundError: If ticket doesn't exist
            ValidationError: If ticket is already resolved/closed
        """
        ticket = await self._dao.get_by_id(ticket_id, org_id)
        if not ticket:
            raise TicketNotFoundError(
                message="Ticket not found",
                details={"ticket_id": ticket_id},
            )

        if ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            raise ValidationError(
                message="Cannot recalculate SLA for resolved/closed ticket",
                details={"ticket_id": ticket_id, "status": ticket.status.value},
            )

        # Only recalculate if response hasn't been made yet
        if ticket.first_response_at is None:
            ticket.sla_response_due_at = self.calculate_response_due_at(
                new_priority,
                ticket.created_at,
            )

        # Always recalculate resolution if not resolved
        ticket.sla_resolution_due_at = self.calculate_resolution_due_at(
            new_priority,
            ticket.created_at,
        )

        ticket.priority = new_priority
        await self._session.flush()
        await self._session.refresh(ticket)

        logger.info(
            f"Recalculated SLA for ticket {ticket_id} with new priority {new_priority.value}"
        )

        return ticket


# Dependency for FastAPI routes
async def get_sla_service(session: AsyncSession) -> SLAService:
    """
    FastAPI dependency for getting SLA service.

    WHAT: Creates an SLAService instance with the current session.

    WHY: Allows using SLAService as a FastAPI dependency with
    automatic session management.

    Example:
        @router.get("/tickets/{ticket_id}/sla")
        async def get_ticket_sla(
            ticket_id: int,
            db: AsyncSession = Depends(get_db),
            sla_service: SLAService = Depends(get_sla_service)
        ):
            return await sla_service.get_sla_status(ticket_id)
    """
    return SLAService(session)
