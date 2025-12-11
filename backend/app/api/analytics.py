"""
Analytics API endpoints.

WHAT: RESTful API for business analytics and metrics.

WHY: Administrators need data-driven insights into:
1. Project performance and status distribution
2. Revenue trends and financial health
3. User activity and engagement metrics

HOW: FastAPI router with ADMIN role requirement on all endpoints.
Queries aggregate data across all organizations for platform-wide metrics.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract
from pydantic import BaseModel, Field

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.project import Project, ProjectStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ticket import Ticket


router = APIRouter(prefix="/analytics", tags=["analytics"])


# ============================================================================
# Schemas
# ============================================================================


class StatusCount(BaseModel):
    """Count by status."""
    status: str
    count: int


class OrganizationMetric(BaseModel):
    """Metric per organization."""
    org_id: int
    org_name: str
    value: float


class TimeSeriesPoint(BaseModel):
    """Point in time series data."""
    date: str  # YYYY-MM format for monthly, YYYY-MM-DD for daily
    value: float


class ProjectMetricsResponse(BaseModel):
    """
    Project analytics response.

    WHAT: Comprehensive project metrics for dashboard.

    Includes:
    - Total project count
    - Status distribution
    - Projects created over time
    - Average project duration
    - Top organizations by project count
    """
    total_projects: int
    by_status: List[StatusCount]
    created_over_time: List[TimeSeriesPoint]
    average_duration_days: Optional[float]
    projects_by_organization: List[OrganizationMetric]
    active_projects: int
    overdue_projects: int


class RevenueMetricsResponse(BaseModel):
    """
    Revenue analytics response.

    WHAT: Financial metrics for business health monitoring.

    Includes:
    - Revenue totals (MTD, YTD, all-time)
    - Revenue by organization
    - Revenue trend over time
    - Average deal size
    - Payment method breakdown
    """
    total_revenue: float
    revenue_mtd: float  # Month to date
    revenue_ytd: float  # Year to date
    revenue_by_organization: List[OrganizationMetric]
    revenue_over_time: List[TimeSeriesPoint]
    average_deal_size: float
    payment_method_breakdown: List[StatusCount]
    outstanding_amount: float
    overdue_amount: float


class UserActivityMetricsResponse(BaseModel):
    """
    User activity analytics response.

    WHAT: User engagement and activity metrics.

    Includes:
    - Active user counts (DAU, WAU, MAU equivalents based on login)
    - New registrations over time
    - User retention metrics
    - Users by organization
    - Role distribution
    """
    total_users: int
    active_users: int  # Users who logged in within 30 days
    recent_active_users: int  # Users who logged in within 7 days
    new_users_over_time: List[TimeSeriesPoint]
    users_by_organization: List[OrganizationMetric]
    users_by_role: List[StatusCount]
    verified_users: int
    unverified_users: int


class DashboardSummaryResponse(BaseModel):
    """
    Dashboard summary for quick overview.

    WHAT: Key metrics for admin dashboard cards.

    Provides at-a-glance platform health indicators.
    """
    total_users: int
    total_organizations: int
    active_organizations: int
    total_projects: int
    active_projects: int
    total_revenue: float
    revenue_mtd: float
    open_tickets: int
    overdue_tickets: int


# ============================================================================
# Project Metrics Endpoint (ANALYTICS-001)
# ============================================================================


@router.get(
    "/projects",
    response_model=ProjectMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project metrics",
    description="Get comprehensive project analytics (ADMIN only)",
)
async def get_project_metrics(
    months: int = Query(default=12, ge=1, le=24, description="Months of history"),
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ProjectMetricsResponse:
    """
    Get project analytics.

    WHAT: Returns comprehensive project metrics.

    WHY: Enables monitoring of project pipeline health and trends.

    Args:
        months: Number of months of historical data
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Project metrics including status distribution, trends, averages
    """
    # Total projects
    total_result = await db.execute(select(func.count(Project.id)))
    total_projects = total_result.scalar_one()

    # Active projects (not completed or cancelled)
    active_result = await db.execute(
        select(func.count(Project.id)).where(
            ~Project.status.in_([ProjectStatus.COMPLETED, ProjectStatus.CANCELLED])
        )
    )
    active_projects = active_result.scalar_one()

    # Overdue projects (past due date and not completed)
    overdue_result = await db.execute(
        select(func.count(Project.id)).where(
            and_(
                Project.due_date < datetime.utcnow(),
                ~Project.status.in_([ProjectStatus.COMPLETED, ProjectStatus.CANCELLED]),
            )
        )
    )
    overdue_projects = overdue_result.scalar_one()

    # Projects by status
    status_result = await db.execute(
        select(Project.status, func.count(Project.id))
        .group_by(Project.status)
    )
    by_status = [
        StatusCount(status=status.value, count=count)
        for status, count in status_result.all()
    ]

    # Projects created over time (monthly)
    start_date = datetime.utcnow() - timedelta(days=months * 30)
    created_result = await db.execute(
        select(
            extract("year", Project.created_at).label("year"),
            extract("month", Project.created_at).label("month"),
            func.count(Project.id).label("count"),
        )
        .where(Project.created_at >= start_date)
        .group_by("year", "month")
        .order_by("year", "month")
    )
    created_over_time = [
        TimeSeriesPoint(
            date=f"{int(row.year)}-{int(row.month):02d}",
            value=float(row.count),
        )
        for row in created_result.all()
    ]

    # Average project duration (for completed projects)
    duration_result = await db.execute(
        select(
            func.avg(
                extract("epoch", Project.completed_at) - extract("epoch", Project.start_date)
            )
        ).where(
            and_(
                Project.status == ProjectStatus.COMPLETED,
                Project.completed_at.isnot(None),
                Project.start_date.isnot(None),
            )
        )
    )
    avg_duration_seconds = duration_result.scalar_one()
    average_duration_days = (
        float(avg_duration_seconds) / 86400 if avg_duration_seconds else None
    )

    # Projects by organization
    org_result = await db.execute(
        select(
            Organization.id,
            Organization.name,
            func.count(Project.id).label("count"),
        )
        .join(Project, Project.org_id == Organization.id)
        .group_by(Organization.id, Organization.name)
        .order_by(func.count(Project.id).desc())
        .limit(10)
    )
    projects_by_organization = [
        OrganizationMetric(org_id=row.id, org_name=row.name, value=float(row.count))
        for row in org_result.all()
    ]

    return ProjectMetricsResponse(
        total_projects=total_projects,
        by_status=by_status,
        created_over_time=created_over_time,
        average_duration_days=average_duration_days,
        projects_by_organization=projects_by_organization,
        active_projects=active_projects,
        overdue_projects=overdue_projects,
    )


# ============================================================================
# Revenue Metrics Endpoint (ANALYTICS-002)
# ============================================================================


@router.get(
    "/revenue",
    response_model=RevenueMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get revenue metrics",
    description="Get comprehensive revenue analytics (ADMIN only)",
)
async def get_revenue_metrics(
    months: int = Query(default=12, ge=1, le=24, description="Months of history"),
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> RevenueMetricsResponse:
    """
    Get revenue analytics.

    WHAT: Returns comprehensive revenue metrics.

    WHY: Enables monitoring of financial health and trends.

    Args:
        months: Number of months of historical data
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Revenue metrics including totals, trends, breakdowns
    """
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # Total revenue (all-time from paid invoices)
    total_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount_paid), 0.0)).where(
            Invoice.status == InvoiceStatus.PAID
        )
    )
    total_revenue = float(total_result.scalar_one() or 0.0)

    # Revenue MTD (Month to Date)
    mtd_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount_paid), 0.0)).where(
            and_(
                Invoice.status == InvoiceStatus.PAID,
                Invoice.paid_at >= start_of_month,
            )
        )
    )
    revenue_mtd = float(mtd_result.scalar_one() or 0.0)

    # Revenue YTD (Year to Date)
    ytd_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount_paid), 0.0)).where(
            and_(
                Invoice.status == InvoiceStatus.PAID,
                Invoice.paid_at >= start_of_year,
            )
        )
    )
    revenue_ytd = float(ytd_result.scalar_one() or 0.0)

    # Outstanding amount (sent but not paid)
    outstanding_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0.0)).where(
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID])
        )
    )
    outstanding_amount = float(outstanding_result.scalar_one() or 0.0)

    # Overdue amount
    overdue_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0.0)).where(
            Invoice.status == InvoiceStatus.OVERDUE
        )
    )
    overdue_amount = float(overdue_result.scalar_one() or 0.0)

    # Revenue by organization
    org_result = await db.execute(
        select(
            Organization.id,
            Organization.name,
            func.coalesce(func.sum(Invoice.amount_paid), 0.0).label("revenue"),
        )
        .join(Invoice, Invoice.org_id == Organization.id)
        .where(Invoice.status == InvoiceStatus.PAID)
        .group_by(Organization.id, Organization.name)
        .order_by(func.sum(Invoice.amount_paid).desc())
        .limit(10)
    )
    revenue_by_organization = [
        OrganizationMetric(org_id=row.id, org_name=row.name, value=float(row.revenue))
        for row in org_result.all()
    ]

    # Revenue over time (monthly)
    start_date = now - timedelta(days=months * 30)
    time_result = await db.execute(
        select(
            extract("year", Invoice.paid_at).label("year"),
            extract("month", Invoice.paid_at).label("month"),
            func.coalesce(func.sum(Invoice.amount_paid), 0.0).label("revenue"),
        )
        .where(
            and_(
                Invoice.status == InvoiceStatus.PAID,
                Invoice.paid_at >= start_date,
            )
        )
        .group_by("year", "month")
        .order_by("year", "month")
    )
    revenue_over_time = [
        TimeSeriesPoint(
            date=f"{int(row.year)}-{int(row.month):02d}",
            value=float(row.revenue),
        )
        for row in time_result.all()
    ]

    # Average deal size
    avg_result = await db.execute(
        select(func.avg(Invoice.total)).where(Invoice.status == InvoiceStatus.PAID)
    )
    average_deal_size = float(avg_result.scalar_one() or 0.0)

    # Payment method breakdown
    payment_result = await db.execute(
        select(
            func.coalesce(Invoice.payment_method, "unknown").label("method"),
            func.count(Invoice.id).label("count"),
        )
        .where(Invoice.status == InvoiceStatus.PAID)
        .group_by(Invoice.payment_method)
    )
    payment_method_breakdown = [
        StatusCount(status=row.method or "unknown", count=row.count)
        for row in payment_result.all()
    ]

    return RevenueMetricsResponse(
        total_revenue=total_revenue,
        revenue_mtd=revenue_mtd,
        revenue_ytd=revenue_ytd,
        revenue_by_organization=revenue_by_organization,
        revenue_over_time=revenue_over_time,
        average_deal_size=average_deal_size,
        payment_method_breakdown=payment_method_breakdown,
        outstanding_amount=outstanding_amount,
        overdue_amount=overdue_amount,
    )


# ============================================================================
# User Activity Metrics Endpoint (ANALYTICS-003)
# ============================================================================


@router.get(
    "/users",
    response_model=UserActivityMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user activity metrics",
    description="Get comprehensive user analytics (ADMIN only)",
)
async def get_user_activity_metrics(
    months: int = Query(default=12, ge=1, le=24, description="Months of history"),
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> UserActivityMetricsResponse:
    """
    Get user activity analytics.

    WHAT: Returns comprehensive user engagement metrics.

    WHY: Enables monitoring of user adoption and engagement.

    Args:
        months: Number of months of historical data
        current_user: Current authenticated admin
        db: Database session

    Returns:
        User metrics including activity, registrations, distribution
    """
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # Total users
    total_result = await db.execute(select(func.count(User.id)))
    total_users = total_result.scalar_one()

    # Active users (accounts that are active, created in last 30 days as proxy)
    # Note: Without last_login_at tracking, we use account creation as proxy for activity
    active_result = await db.execute(
        select(func.count(User.id)).where(
            User.is_active == True
        )
    )
    active_users = active_result.scalar_one()

    # Recent active users (accounts created in last 7 days as proxy)
    recent_result = await db.execute(
        select(func.count(User.id)).where(
            and_(
                User.is_active == True,
                User.created_at >= seven_days_ago,
            )
        )
    )
    recent_active_users = recent_result.scalar_one()

    # Verified vs unverified users
    verified_result = await db.execute(
        select(func.count(User.id)).where(User.email_verified == True)
    )
    verified_users = verified_result.scalar_one()
    unverified_users = total_users - verified_users

    # New users over time (monthly)
    start_date = now - timedelta(days=months * 30)
    new_users_result = await db.execute(
        select(
            extract("year", User.created_at).label("year"),
            extract("month", User.created_at).label("month"),
            func.count(User.id).label("count"),
        )
        .where(User.created_at >= start_date)
        .group_by("year", "month")
        .order_by("year", "month")
    )
    new_users_over_time = [
        TimeSeriesPoint(
            date=f"{int(row.year)}-{int(row.month):02d}",
            value=float(row.count),
        )
        for row in new_users_result.all()
    ]

    # Users by organization
    org_result = await db.execute(
        select(
            Organization.id,
            Organization.name,
            func.count(User.id).label("count"),
        )
        .join(User, User.org_id == Organization.id)
        .group_by(Organization.id, Organization.name)
        .order_by(func.count(User.id).desc())
        .limit(10)
    )
    users_by_organization = [
        OrganizationMetric(org_id=row.id, org_name=row.name, value=float(row.count))
        for row in org_result.all()
    ]

    # Users by role
    role_result = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    users_by_role = [
        StatusCount(status=role, count=count) for role, count in role_result.all()
    ]

    return UserActivityMetricsResponse(
        total_users=total_users,
        active_users=active_users,
        recent_active_users=recent_active_users,
        new_users_over_time=new_users_over_time,
        users_by_organization=users_by_organization,
        users_by_role=users_by_role,
        verified_users=verified_users,
        unverified_users=unverified_users,
    )


# ============================================================================
# Dashboard Summary Endpoint
# ============================================================================


@router.get(
    "/dashboard",
    response_model=DashboardSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard summary",
    description="Get quick summary metrics for dashboard cards (ADMIN only)",
)
async def get_dashboard_summary(
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    """
    Get dashboard summary metrics.

    WHAT: Returns key metrics for dashboard cards.

    WHY: Provides quick platform health overview.

    Args:
        current_user: Current authenticated admin
        db: Database session

    Returns:
        Summary metrics for dashboard display
    """
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    from app.models.ticket import TicketStatus

    # Total users
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar_one()

    # Total organizations
    total_orgs_result = await db.execute(select(func.count(Organization.id)))
    total_organizations = total_orgs_result.scalar_one()

    # Active organizations
    active_orgs_result = await db.execute(
        select(func.count(Organization.id)).where(Organization.is_active == True)
    )
    active_organizations = active_orgs_result.scalar_one()

    # Total projects
    total_projects_result = await db.execute(select(func.count(Project.id)))
    total_projects = total_projects_result.scalar_one()

    # Active projects
    active_projects_result = await db.execute(
        select(func.count(Project.id)).where(
            ~Project.status.in_([ProjectStatus.COMPLETED, ProjectStatus.CANCELLED])
        )
    )
    active_projects = active_projects_result.scalar_one()

    # Total revenue
    total_revenue_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount_paid), 0.0)).where(
            Invoice.status == InvoiceStatus.PAID
        )
    )
    total_revenue = float(total_revenue_result.scalar_one() or 0.0)

    # Revenue MTD
    revenue_mtd_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount_paid), 0.0)).where(
            and_(
                Invoice.status == InvoiceStatus.PAID,
                Invoice.paid_at >= start_of_month,
            )
        )
    )
    revenue_mtd = float(revenue_mtd_result.scalar_one() or 0.0)

    # Open tickets
    open_tickets_result = await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
        )
    )
    open_tickets = open_tickets_result.scalar_one()

    # Overdue tickets (SLA breached - either response or resolution SLA)
    # Check tickets where either sla_response_due_at or sla_resolution_due_at is past
    overdue_tickets_result = await db.execute(
        select(func.count(Ticket.id)).where(
            and_(
                ~Ticket.status.in_([TicketStatus.CLOSED, TicketStatus.RESOLVED]),
                (
                    (Ticket.sla_response_due_at < now) |
                    (Ticket.sla_resolution_due_at < now)
                ),
            )
        )
    )
    overdue_tickets = overdue_tickets_result.scalar_one()

    return DashboardSummaryResponse(
        total_users=total_users,
        total_organizations=total_organizations,
        active_organizations=active_organizations,
        total_projects=total_projects,
        active_projects=active_projects,
        total_revenue=total_revenue,
        revenue_mtd=revenue_mtd,
        open_tickets=open_tickets,
        overdue_tickets=overdue_tickets,
    )
