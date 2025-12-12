"""
Time Entry Pydantic Schemas.

WHAT: Request/Response models for time tracking API endpoints.

WHY: Pydantic schemas provide:
1. Request validation
2. Response serialization
3. OpenAPI documentation
4. Type safety

HOW: Defines schemas for:
- Time entry CRUD
- Timer operations
- Approval workflow
- Reporting aggregations
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class TimeEntryStatus(str, Enum):
    """Time entry status values."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    INVOICED = "invoiced"
    REJECTED = "rejected"


# ============================================================================
# Request Schemas
# ============================================================================


class TimeEntryCreateRequest(BaseModel):
    """
    Request schema for creating a time entry.

    WHAT: Fields needed to create a time entry.

    WHY: Validates time entry data before creation.
    """

    date: date = Field(..., description="Date of work")
    description: str = Field(
        ..., min_length=1, max_length=1000, description="Description of work done"
    )
    duration_minutes: int = Field(
        default=0, ge=0, le=1440, description="Duration in minutes (max 24 hours)"
    )
    project_id: Optional[int] = Field(None, description="Project ID")
    ticket_id: Optional[int] = Field(None, description="Ticket ID")
    task_type: Optional[str] = Field(
        None, max_length=50, description="Task type (development, meeting, etc.)"
    )
    is_billable: bool = Field(default=True, description="Whether time is billable")
    hourly_rate: Optional[Decimal] = Field(
        None, ge=0, description="Hourly rate for billing"
    )
    start_time: Optional[datetime] = Field(None, description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v, info):
        """Ensure end_time is after start_time."""
        if v and info.data.get("start_time") and v < info.data["start_time"]:
            raise ValueError("End time must be after start time")
        return v


class TimeEntryUpdateRequest(BaseModel):
    """
    Request schema for updating a time entry.

    WHAT: Fields that can be updated on a time entry.

    WHY: Allows partial updates to entries.
    """

    date: Optional[date] = Field(None, description="Date of work")
    description: Optional[str] = Field(
        None, min_length=1, max_length=1000, description="Description of work"
    )
    duration_minutes: Optional[int] = Field(
        None, ge=0, le=1440, description="Duration in minutes"
    )
    project_id: Optional[int] = Field(None, description="Project ID")
    ticket_id: Optional[int] = Field(None, description="Ticket ID")
    task_type: Optional[str] = Field(None, max_length=50, description="Task type")
    is_billable: Optional[bool] = Field(None, description="Whether billable")
    hourly_rate: Optional[Decimal] = Field(None, ge=0, description="Hourly rate")
    start_time: Optional[datetime] = Field(None, description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")


class TimeEntryRejectRequest(BaseModel):
    """
    Request schema for rejecting a time entry.

    WHAT: Reason for rejection.

    WHY: Provides feedback to submitter.
    """

    reason: str = Field(
        ..., min_length=1, max_length=500, description="Rejection reason"
    )


class TimeEntryBulkApproveRequest(BaseModel):
    """
    Request schema for bulk approval.

    WHAT: List of entry IDs to approve.

    WHY: Allows approving multiple entries at once.
    """

    entry_ids: List[int] = Field(
        ..., min_items=1, max_items=100, description="Entry IDs to approve"
    )


class TimeEntryLinkInvoiceRequest(BaseModel):
    """
    Request schema for linking entries to invoice.

    WHAT: Entry IDs and invoice ID.

    WHY: Associates entries with billing.
    """

    entry_ids: List[int] = Field(
        ..., min_items=1, max_items=100, description="Entry IDs to link"
    )
    invoice_id: int = Field(..., description="Invoice to link to")


class TimeEntryFilterRequest(BaseModel):
    """
    Request schema for filtering time entries.

    WHAT: Filter parameters for listing entries.

    WHY: Enables flexible querying.
    """

    user_id: Optional[int] = Field(None, description="Filter by user")
    project_id: Optional[int] = Field(None, description="Filter by project")
    ticket_id: Optional[int] = Field(None, description="Filter by ticket")
    status: Optional[TimeEntryStatus] = Field(None, description="Filter by status")
    is_billable: Optional[bool] = Field(None, description="Filter by billable")
    start_date: Optional[date] = Field(None, description="Filter from date")
    end_date: Optional[date] = Field(None, description="Filter to date")


# ============================================================================
# Response Schemas
# ============================================================================


class TimeEntryResponse(BaseModel):
    """
    Response schema for a single time entry.

    WHAT: Time entry details for display.

    WHY: Provides all entry information for UI.
    """

    id: int = Field(..., description="Entry ID")
    org_id: int = Field(..., description="Organization ID")
    user_id: int = Field(..., description="User ID")
    user_name: Optional[str] = Field(None, description="User name")
    user_email: Optional[str] = Field(None, description="User email")

    # Association
    project_id: Optional[int] = Field(None, description="Project ID")
    project_name: Optional[str] = Field(None, description="Project name")
    ticket_id: Optional[int] = Field(None, description="Ticket ID")
    ticket_subject: Optional[str] = Field(None, description="Ticket subject")

    # Time
    date: date = Field(..., description="Date of work")
    start_time: Optional[datetime] = Field(None, description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")
    duration_minutes: int = Field(..., description="Duration in minutes")
    duration_hours: float = Field(..., description="Duration in hours")

    # Description
    description: str = Field(..., description="Work description")
    task_type: Optional[str] = Field(None, description="Task type")

    # Billing
    is_billable: bool = Field(..., description="Is billable")
    hourly_rate: Optional[Decimal] = Field(None, description="Hourly rate")
    amount: Optional[Decimal] = Field(None, description="Calculated amount")

    # Status
    status: TimeEntryStatus = Field(..., description="Entry status")
    submitted_at: Optional[datetime] = Field(None, description="Submission time")
    approved_at: Optional[datetime] = Field(None, description="Approval time")
    approved_by: Optional[int] = Field(None, description="Approver ID")
    approver_name: Optional[str] = Field(None, description="Approver name")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason")

    # Invoice
    invoice_id: Optional[int] = Field(None, description="Invoice ID")
    is_invoiced: bool = Field(..., description="Has been invoiced")

    # Timer
    timer_started_at: Optional[datetime] = Field(None, description="Timer start")
    is_running: bool = Field(..., description="Timer running")

    # Timestamps
    created_at: datetime = Field(..., description="Created timestamp")
    updated_at: Optional[datetime] = Field(None, description="Updated timestamp")

    class Config:
        from_attributes = True


class TimeEntryListResponse(BaseModel):
    """
    Response schema for time entry list with pagination.

    WHAT: Paginated list of time entries.

    WHY: Supports UI pagination and displays totals.
    """

    items: List[TimeEntryResponse] = Field(..., description="List of entries")
    total: int = Field(..., description="Total count")
    skip: int = Field(..., description="Offset used")
    limit: int = Field(..., description="Limit used")
    total_minutes: int = Field(default=0, description="Total minutes in result")
    total_hours: float = Field(default=0, description="Total hours in result")
    billable_minutes: int = Field(default=0, description="Billable minutes")
    billable_amount: Decimal = Field(
        default=Decimal("0"), description="Total billable amount"
    )


class TimerResponse(BaseModel):
    """
    Response schema for timer operations.

    WHAT: Timer status information.

    WHY: Shows current timer state.
    """

    entry_id: int = Field(..., description="Entry ID")
    is_running: bool = Field(..., description="Timer running")
    started_at: Optional[datetime] = Field(None, description="Start time")
    elapsed_minutes: int = Field(default=0, description="Elapsed minutes")
    total_minutes: int = Field(..., description="Total logged minutes")


class TimeSummaryResponse(BaseModel):
    """
    Response schema for time summary.

    WHAT: Aggregated time data.

    WHY: Dashboard and reporting.
    """

    total_minutes: int = Field(..., description="Total minutes")
    total_hours: float = Field(..., description="Total hours")
    billable_minutes: int = Field(..., description="Billable minutes")
    billable_hours: float = Field(..., description="Billable hours")
    non_billable_minutes: int = Field(default=0, description="Non-billable minutes")
    non_billable_hours: float = Field(default=0, description="Non-billable hours")
    billable_amount: Decimal = Field(..., description="Billable amount")
    invoiced_amount: Optional[Decimal] = Field(None, description="Invoiced amount")
    entry_count: int = Field(..., description="Number of entries")


class DailyBreakdownItem(BaseModel):
    """Single day's time breakdown."""

    date: date = Field(..., description="Date")
    total_minutes: int = Field(..., description="Total minutes")
    total_hours: float = Field(..., description="Total hours")
    billable_minutes: int = Field(..., description="Billable minutes")
    billable_hours: float = Field(..., description="Billable hours")
    entry_count: int = Field(..., description="Entry count")


class DailyBreakdownResponse(BaseModel):
    """
    Response schema for daily breakdown.

    WHAT: Time grouped by day.

    WHY: Shows daily work patterns.
    """

    items: List[DailyBreakdownItem] = Field(..., description="Daily items")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    total_days: int = Field(..., description="Number of days")


class ProjectTimeSummaryResponse(BaseModel):
    """
    Response schema for project time summary.

    WHAT: Project-level time totals.

    WHY: Project budget tracking.
    """

    project_id: int = Field(..., description="Project ID")
    project_name: Optional[str] = Field(None, description="Project name")
    total_minutes: int = Field(..., description="Total minutes")
    total_hours: float = Field(..., description="Total hours")
    billable_minutes: int = Field(..., description="Billable minutes")
    billable_hours: float = Field(..., description="Billable hours")
    billable_amount: Decimal = Field(..., description="Billable amount")
    invoiced_amount: Decimal = Field(..., description="Invoiced amount")
    remaining_budget_hours: Optional[float] = Field(
        None, description="Remaining budget hours"
    )
    entry_count: int = Field(..., description="Entry count")


class UserTimeSummaryResponse(BaseModel):
    """
    Response schema for user time summary.

    WHAT: User-level time totals.

    WHY: Workload tracking.
    """

    user_id: int = Field(..., description="User ID")
    user_name: Optional[str] = Field(None, description="User name")
    user_email: Optional[str] = Field(None, description="User email")
    total_minutes: int = Field(..., description="Total minutes")
    total_hours: float = Field(..., description="Total hours")
    billable_minutes: int = Field(..., description="Billable minutes")
    billable_hours: float = Field(..., description="Billable hours")
    billable_amount: Decimal = Field(..., description="Billable amount")
    entry_count: int = Field(..., description="Entry count")
    avg_daily_hours: float = Field(default=0, description="Average daily hours")
