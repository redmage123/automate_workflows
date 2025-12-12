"""
Time Entry API Routes.

WHAT: REST API endpoints for time tracking operations.

WHY: Time tracking enables:
1. Recording hours for billing
2. Project budget management
3. Team productivity insights
4. Invoice generation

HOW: Uses FastAPI with dependency injection for auth/db.
All routes require authentication and enforce org-scoping.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_admin
from app.core.exceptions import ValidationError
from app.models.user import User, UserRole
from app.services.time_entry_service import TimeEntryService
from app.services.audit import AuditService
from app.schemas.time_entry import (
    TimeEntryCreateRequest,
    TimeEntryUpdateRequest,
    TimeEntryRejectRequest,
    TimeEntryBulkApproveRequest,
    TimeEntryLinkInvoiceRequest,
    TimeEntryResponse,
    TimeEntryListResponse,
    TimerResponse,
    TimeSummaryResponse,
    DailyBreakdownResponse,
    DailyBreakdownItem,
    ProjectTimeSummaryResponse,
    UserTimeSummaryResponse,
    TimeEntryStatus,
)


router = APIRouter(prefix="/time-entries", tags=["time-entries"])


def _entry_to_response(entry, include_relations: bool = True) -> TimeEntryResponse:
    """
    Convert TimeEntry model to response schema.

    WHAT: Maps model fields to response.

    WHY: Consistent response formatting.
    """
    return TimeEntryResponse(
        id=entry.id,
        org_id=entry.org_id,
        user_id=entry.user_id,
        user_name=entry.user.name if include_relations and entry.user else None,
        user_email=entry.user.email if include_relations and entry.user else None,
        project_id=entry.project_id,
        project_name=entry.project.name if include_relations and entry.project else None,
        ticket_id=entry.ticket_id,
        ticket_subject=entry.ticket.subject if include_relations and entry.ticket else None,
        date=entry.date,
        start_time=entry.start_time,
        end_time=entry.end_time,
        duration_minutes=entry.duration_minutes,
        duration_hours=entry.duration_minutes / 60.0,
        description=entry.description,
        task_type=entry.task_type,
        is_billable=entry.is_billable,
        hourly_rate=entry.hourly_rate,
        amount=entry.amount,
        status=TimeEntryStatus(entry.status),
        submitted_at=entry.submitted_at,
        approved_at=entry.approved_at,
        approved_by=entry.approved_by,
        approver_name=entry.approver.name if include_relations and entry.approver else None,
        rejection_reason=entry.rejection_reason,
        invoice_id=entry.invoice_id,
        is_invoiced=entry.invoice_id is not None,
        timer_started_at=entry.timer_started_at,
        is_running=entry.is_running,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


# ============================================================================
# CRUD Endpoints
# ============================================================================


@router.post("", response_model=TimeEntryResponse)
async def create_time_entry(
    request: TimeEntryCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new time entry.

    WHAT: Records time spent on work.

    WHY: Enables billing and project tracking.
    """
    service = TimeEntryService(session)

    entry = await service.create_entry(
        org_id=current_user.org_id,
        user_id=current_user.id,
        entry_date=request.date,
        description=request.description,
        duration_minutes=request.duration_minutes,
        project_id=request.project_id,
        ticket_id=request.ticket_id,
        task_type=request.task_type,
        is_billable=request.is_billable,
        hourly_rate=request.hourly_rate,
        start_time=request.start_time,
        end_time=request.end_time,
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="time_entry_created",
        resource_type="time_entry",
        resource_id=entry.id,
        details={
            "date": str(entry.date),
            "duration_minutes": entry.duration_minutes,
            "project_id": entry.project_id,
        },
    )

    await session.commit()
    return _entry_to_response(entry, include_relations=False)


@router.get("", response_model=TimeEntryListResponse)
async def list_time_entries(
    user_id: Optional[int] = Query(None, description="Filter by user"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    ticket_id: Optional[int] = Query(None, description="Filter by ticket"),
    status: Optional[TimeEntryStatus] = Query(None, description="Filter by status"),
    is_billable: Optional[bool] = Query(None, description="Filter by billable"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    List time entries with filtering.

    WHAT: Retrieves time entries with optional filters.

    WHY: View and manage time records.

    Notes:
    - Regular users can only see their own entries
    - Admins can see all entries
    """
    service = TimeEntryService(session)
    is_admin = current_user.role == UserRole.ADMIN

    # Non-admins can only see their own entries
    if not is_admin:
        user_id = current_user.id

    entries = await service.get_user_entries(
        user_id=user_id or current_user.id,
        org_id=current_user.org_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )

    # Calculate totals
    total_minutes = sum(e.duration_minutes for e in entries)
    billable_minutes = sum(e.duration_minutes for e in entries if e.is_billable)
    billable_amount = sum(e.amount or Decimal("0") for e in entries if e.is_billable)

    return TimeEntryListResponse(
        items=[_entry_to_response(e, include_relations=False) for e in entries],
        total=len(entries),  # TODO: Get actual total count
        skip=skip,
        limit=limit,
        total_minutes=total_minutes,
        total_hours=total_minutes / 60.0,
        billable_minutes=billable_minutes,
        billable_amount=billable_amount,
    )


@router.get("/my", response_model=TimeEntryListResponse)
async def get_my_time_entries(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get current user's time entries.

    WHAT: Lists user's own time entries.

    WHY: Quick access to personal time records.
    """
    service = TimeEntryService(session)

    entries = await service.get_user_entries(
        user_id=current_user.id,
        org_id=current_user.org_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )

    total_minutes = sum(e.duration_minutes for e in entries)
    billable_minutes = sum(e.duration_minutes for e in entries if e.is_billable)
    billable_amount = sum(e.amount or Decimal("0") for e in entries if e.is_billable)

    return TimeEntryListResponse(
        items=[_entry_to_response(e, include_relations=False) for e in entries],
        total=len(entries),
        skip=skip,
        limit=limit,
        total_minutes=total_minutes,
        total_hours=total_minutes / 60.0,
        billable_minutes=billable_minutes,
        billable_amount=billable_amount,
    )


@router.get("/{entry_id}", response_model=TimeEntryResponse)
async def get_time_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get a specific time entry.

    WHAT: Retrieves entry details.

    WHY: View entry information.
    """
    service = TimeEntryService(session)
    is_admin = current_user.role == UserRole.ADMIN

    entry = await service.get_entry(
        entry_id, current_user.org_id, current_user.id, is_admin
    )
    return _entry_to_response(entry)


@router.patch("/{entry_id}", response_model=TimeEntryResponse)
async def update_time_entry(
    entry_id: int,
    request: TimeEntryUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Update a time entry.

    WHAT: Updates entry fields.

    WHY: Edit draft entries before submission.

    Notes:
    - Only draft or rejected entries can be edited
    - Users can only edit their own entries
    """
    service = TimeEntryService(session)
    is_admin = current_user.role == UserRole.ADMIN

    # Build update dict from non-None values
    updates = {k: v for k, v in request.model_dump().items() if v is not None}

    entry = await service.update_entry(
        entry_id, current_user.org_id, current_user.id, is_admin, **updates
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="time_entry_updated",
        resource_type="time_entry",
        resource_id=entry_id,
        details=updates,
    )

    await session.commit()
    return _entry_to_response(entry)


@router.delete("/{entry_id}")
async def delete_time_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete a time entry.

    WHAT: Removes a time entry.

    WHY: Clean up incorrect entries.

    Notes:
    - Cannot delete invoiced entries
    """
    service = TimeEntryService(session)
    is_admin = current_user.role == UserRole.ADMIN

    await service.delete_entry(
        entry_id, current_user.org_id, current_user.id, is_admin
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="time_entry_deleted",
        resource_type="time_entry",
        resource_id=entry_id,
    )

    await session.commit()
    return {"message": "Time entry deleted"}


# ============================================================================
# Timer Endpoints
# ============================================================================


@router.post("/timer/start", response_model=TimerResponse)
async def start_timer(
    project_id: Optional[int] = Query(None),
    ticket_id: Optional[int] = Query(None),
    description: str = Query("Timer session"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Start a new timer.

    WHAT: Begins time tracking.

    WHY: Real-time time capture.

    Notes:
    - Only one timer can run at a time
    - Creates a new draft entry
    """
    service = TimeEntryService(session)

    entry = await service.start_timer(
        org_id=current_user.org_id,
        user_id=current_user.id,
        project_id=project_id,
        ticket_id=ticket_id,
        description=description,
    )

    await session.commit()

    return TimerResponse(
        entry_id=entry.id,
        is_running=entry.is_running,
        started_at=entry.timer_started_at,
        elapsed_minutes=0,
        total_minutes=entry.duration_minutes,
    )


@router.post("/timer/stop", response_model=TimerResponse)
async def stop_timer(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Stop the running timer.

    WHAT: Stops time tracking.

    WHY: Captures elapsed time.
    """
    service = TimeEntryService(session)

    entry = await service.stop_timer(
        org_id=current_user.org_id,
        user_id=current_user.id,
    )

    await session.commit()

    if not entry:
        return TimerResponse(
            entry_id=0,
            is_running=False,
            started_at=None,
            elapsed_minutes=0,
            total_minutes=0,
        )

    return TimerResponse(
        entry_id=entry.id,
        is_running=entry.is_running,
        started_at=entry.timer_started_at,
        elapsed_minutes=0,
        total_minutes=entry.duration_minutes,
    )


@router.get("/timer/current", response_model=Optional[TimerResponse])
async def get_current_timer(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get current running timer.

    WHAT: Shows active timer status.

    WHY: Display running timer in UI.
    """
    service = TimeEntryService(session)

    entry = await service.get_running_timer(
        org_id=current_user.org_id,
        user_id=current_user.id,
    )

    if not entry:
        return None

    elapsed_minutes = 0
    if entry.timer_started_at:
        elapsed = datetime.utcnow() - entry.timer_started_at
        elapsed_minutes = int(elapsed.total_seconds() / 60)

    return TimerResponse(
        entry_id=entry.id,
        is_running=entry.is_running,
        started_at=entry.timer_started_at,
        elapsed_minutes=elapsed_minutes,
        total_minutes=entry.duration_minutes,
    )


# ============================================================================
# Approval Workflow Endpoints
# ============================================================================


@router.post("/{entry_id}/submit", response_model=TimeEntryResponse)
async def submit_time_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Submit entry for approval.

    WHAT: Changes status to SUBMITTED.

    WHY: Approval workflow for billing.
    """
    service = TimeEntryService(session)

    entry = await service.submit_entry(
        entry_id, current_user.org_id, current_user.id
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="time_entry_submitted",
        resource_type="time_entry",
        resource_id=entry_id,
    )

    await session.commit()
    return _entry_to_response(entry)


@router.post("/{entry_id}/approve", response_model=TimeEntryResponse)
async def approve_time_entry(
    entry_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Approve a submitted entry.

    WHAT: Changes status to APPROVED.

    WHY: Manager approval before invoicing.

    Requires: Admin role
    """
    service = TimeEntryService(session)

    entry = await service.approve_entry(
        entry_id, current_user.org_id, current_user.id
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="time_entry_approved",
        resource_type="time_entry",
        resource_id=entry_id,
    )

    await session.commit()
    return _entry_to_response(entry)


@router.post("/{entry_id}/reject", response_model=TimeEntryResponse)
async def reject_time_entry(
    entry_id: int,
    request: TimeEntryRejectRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Reject a submitted entry.

    WHAT: Changes status to REJECTED.

    WHY: Send back for revision.

    Requires: Admin role
    """
    service = TimeEntryService(session)

    entry = await service.reject_entry(
        entry_id, current_user.org_id, request.reason
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="time_entry_rejected",
        resource_type="time_entry",
        resource_id=entry_id,
        details={"reason": request.reason},
    )

    await session.commit()
    return _entry_to_response(entry)


@router.post("/bulk-approve")
async def bulk_approve_entries(
    request: TimeEntryBulkApproveRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Bulk approve entries.

    WHAT: Approves multiple entries.

    WHY: Efficient approval workflow.

    Requires: Admin role
    """
    service = TimeEntryService(session)

    result = await service.bulk_approve(
        request.entry_ids, current_user.org_id, current_user.id
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="time_entries_bulk_approved",
        resource_type="time_entry",
        details=result,
    )

    await session.commit()
    return result


# ============================================================================
# Reporting Endpoints
# ============================================================================


@router.get("/summary/my", response_model=TimeSummaryResponse)
async def get_my_time_summary(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get current user's time summary.

    WHAT: Aggregated time data.

    WHY: Personal dashboard.
    """
    service = TimeEntryService(session)

    summary = await service.get_user_summary(
        current_user.id, current_user.org_id, start_date, end_date
    )

    return TimeSummaryResponse(
        total_minutes=summary["total_minutes"],
        total_hours=summary["total_hours"],
        billable_minutes=summary["billable_minutes"],
        billable_hours=summary["billable_hours"],
        billable_amount=summary["billable_amount"],
        entry_count=summary["entry_count"],
    )


@router.get("/summary/project/{project_id}", response_model=ProjectTimeSummaryResponse)
async def get_project_time_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get project time summary.

    WHAT: Project-level time totals.

    WHY: Budget tracking.
    """
    service = TimeEntryService(session)

    summary = await service.get_project_summary(project_id, current_user.org_id)

    return ProjectTimeSummaryResponse(
        project_id=project_id,
        total_minutes=summary["total_minutes"],
        total_hours=summary["total_hours"],
        billable_minutes=summary["billable_minutes"],
        billable_hours=summary["billable_hours"],
        billable_amount=summary["billable_amount"],
        invoiced_amount=summary["invoiced_amount"],
        entry_count=summary["entry_count"],
    )


@router.get("/breakdown/daily", response_model=DailyBreakdownResponse)
async def get_daily_breakdown(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    user_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get daily time breakdown.

    WHAT: Time grouped by day.

    WHY: Shows daily work patterns.
    """
    service = TimeEntryService(session)
    is_admin = current_user.role == UserRole.ADMIN

    # Non-admins can only see their own
    if not is_admin:
        user_id = current_user.id

    breakdown = await service.get_daily_breakdown(
        org_id=current_user.org_id,
        user_id=user_id,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date,
    )

    return DailyBreakdownResponse(
        items=[DailyBreakdownItem(**item) for item in breakdown],
        start_date=start_date,
        end_date=end_date,
        total_days=len(breakdown),
    )


@router.get("/uninvoiced", response_model=TimeEntryListResponse)
async def get_uninvoiced_entries(
    project_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Get entries ready for invoicing.

    WHAT: Approved, uninvoiced entries.

    WHY: Invoice generation.

    Requires: Admin role
    """
    service = TimeEntryService(session)

    entries = await service.get_uninvoiced_entries(
        org_id=current_user.org_id,
        project_id=project_id,
        user_id=user_id,
    )

    total_minutes = sum(e.duration_minutes for e in entries)
    billable_amount = sum(e.amount or Decimal("0") for e in entries)

    return TimeEntryListResponse(
        items=[_entry_to_response(e, include_relations=False) for e in entries],
        total=len(entries),
        skip=0,
        limit=len(entries),
        total_minutes=total_minutes,
        total_hours=total_minutes / 60.0,
        billable_minutes=total_minutes,
        billable_amount=billable_amount,
    )


@router.post("/link-invoice")
async def link_entries_to_invoice(
    request: TimeEntryLinkInvoiceRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Link entries to an invoice.

    WHAT: Associates entries with billing.

    WHY: Tracks invoiced time.

    Requires: Admin role
    """
    service = TimeEntryService(session)

    count = await service.link_to_invoice(
        request.entry_ids, request.invoice_id, current_user.org_id
    )

    # Audit log
    audit = AuditService(session)
    await audit.log_action(
        user_id=current_user.id,
        action="time_entries_linked_to_invoice",
        resource_type="invoice",
        resource_id=request.invoice_id,
        details={
            "entry_count": count,
            "entry_ids": request.entry_ids,
        },
    )

    await session.commit()
    return {"message": f"Linked {count} entries to invoice", "linked_count": count}
