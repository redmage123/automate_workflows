"""
Integration tests for Analytics API.

WHAT: Tests for analytics endpoints.

WHY: Analytics provide business insights that drive decisions:
1. Project metrics for pipeline management
2. Revenue metrics for financial health
3. User activity for engagement tracking

HOW: Uses pytest-asyncio with AsyncClient for HTTP testing.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    OrganizationFactory,
    UserFactory,
    ProjectFactory,
    InvoiceFactory,
    TicketFactory,
)
from app.models.project import ProjectStatus
from app.models.invoice import InvoiceStatus


class TestProjectMetrics:
    """Integration tests for project metrics endpoint."""

    @pytest.mark.asyncio
    async def test_get_project_metrics(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting project metrics as admin.

        WHY: Admins need project pipeline visibility.
        """
        org = await OrganizationFactory.create(db_session, name="Project Metrics Org")
        await UserFactory.create_admin(
            db_session, email="projmetrics@test.com", password="Password123!", organization=org
        )

        # Create projects in various states
        await ProjectFactory.create(
            db_session, name="Draft Project", status=ProjectStatus.DRAFT, organization=org
        )
        await ProjectFactory.create(
            db_session,
            name="In Progress Project",
            status=ProjectStatus.IN_PROGRESS,
            organization=org,
        )
        await ProjectFactory.create(
            db_session,
            name="Completed Project",
            status=ProjectStatus.COMPLETED,
            organization=org,
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "projmetrics@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get project metrics
        response = await client.get(
            "/api/analytics/projects", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_projects" in data
        assert data["total_projects"] >= 3
        assert "by_status" in data
        assert "active_projects" in data
        assert "overdue_projects" in data
        assert "created_over_time" in data
        assert "projects_by_organization" in data

    @pytest.mark.asyncio
    async def test_project_metrics_status_breakdown(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test project metrics includes correct status breakdown.

        WHY: Status distribution helps with pipeline analysis.
        """
        org = await OrganizationFactory.create(db_session, name="Status Breakdown Org")
        await UserFactory.create_admin(
            db_session, email="statusbreakdown@test.com", password="Password123!", organization=org
        )

        # Create specific number of projects per status
        for _ in range(2):
            await ProjectFactory.create(
                db_session, name="Draft", status=ProjectStatus.DRAFT, organization=org
            )
        for _ in range(3):
            await ProjectFactory.create(
                db_session,
                name="In Progress",
                status=ProjectStatus.IN_PROGRESS,
                organization=org,
            )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "statusbreakdown@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get project metrics
        response = await client.get(
            "/api/analytics/projects", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        status_map = {s["status"]: s["count"] for s in data["by_status"]}
        assert "draft" in status_map
        assert "in_progress" in status_map

    @pytest.mark.asyncio
    async def test_project_metrics_forbidden_for_client(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that clients cannot access project metrics.

        WHY: RBAC - analytics are admin-only.
        """
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_client(
            db_session, email="projclient@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "projclient@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to get metrics
        response = await client.get(
            "/api/analytics/projects", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403


class TestRevenueMetrics:
    """Integration tests for revenue metrics endpoint."""

    @pytest.mark.asyncio
    async def test_get_revenue_metrics(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting revenue metrics as admin.

        WHY: Financial visibility is critical for business health.
        """
        org = await OrganizationFactory.create(db_session, name="Revenue Metrics Org")
        await UserFactory.create_admin(
            db_session, email="revmetrics@test.com", password="Password123!", organization=org
        )

        # Create paid invoices
        await InvoiceFactory.create_paid(
            db_session,
            organization=org,
            total=Decimal("1000.00"),
            payment_method="card",
        )
        await InvoiceFactory.create_paid(
            db_session,
            organization=org,
            total=Decimal("2000.00"),
            payment_method="bank_transfer",
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "revmetrics@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get revenue metrics
        response = await client.get(
            "/api/analytics/revenue", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_revenue" in data
        assert "revenue_mtd" in data
        assert "revenue_ytd" in data
        assert "average_deal_size" in data
        assert "payment_method_breakdown" in data
        assert "revenue_by_organization" in data
        assert "revenue_over_time" in data

    @pytest.mark.asyncio
    async def test_revenue_metrics_totals(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test revenue metrics calculates totals correctly.

        WHY: Accurate financial reporting is essential.
        """
        org = await OrganizationFactory.create(db_session, name="Revenue Totals Org")
        await UserFactory.create_admin(
            db_session, email="revtotals@test.com", password="Password123!", organization=org
        )

        # Create invoices with known amounts
        await InvoiceFactory.create_paid(
            db_session, organization=org, subtotal=Decimal("1000.00"), total=Decimal("1080.00")
        )
        await InvoiceFactory.create_paid(
            db_session, organization=org, subtotal=Decimal("500.00"), total=Decimal("540.00")
        )
        # Create sent but unpaid invoice (should not count in total_revenue)
        await InvoiceFactory.create_sent(
            db_session, organization=org, total=Decimal("2000.00")
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "revtotals@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get revenue metrics
        response = await client.get(
            "/api/analytics/revenue", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        # Total revenue should only include paid invoices
        assert data["total_revenue"] >= 1620.00  # 1080 + 540

    @pytest.mark.asyncio
    async def test_revenue_metrics_outstanding(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test revenue metrics includes outstanding amounts.

        WHY: Track receivables for cash flow management.
        """
        org = await OrganizationFactory.create(db_session, name="Outstanding Org")
        await UserFactory.create_admin(
            db_session, email="outstanding@test.com", password="Password123!", organization=org
        )

        # Create unpaid sent invoice
        await InvoiceFactory.create_sent(
            db_session, organization=org, total=Decimal("5000.00"), amount_paid=Decimal("0")
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "outstanding@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get revenue metrics
        response = await client.get(
            "/api/analytics/revenue", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "outstanding_amount" in data
        assert data["outstanding_amount"] >= 5000.00


class TestUserActivityMetrics:
    """Integration tests for user activity metrics endpoint."""

    @pytest.mark.asyncio
    async def test_get_user_activity_metrics(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting user activity metrics as admin.

        WHY: User engagement metrics inform product decisions.
        """
        org = await OrganizationFactory.create(db_session, name="User Activity Org")
        await UserFactory.create_admin(
            db_session, email="useractivity@test.com", password="Password123!", organization=org
        )

        # Create additional users
        await UserFactory.create_client(
            db_session, email="actuser1@test.com", password="Password123!", organization=org
        )
        await UserFactory.create_client(
            db_session, email="actuser2@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "useractivity@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get user activity metrics
        response = await client.get(
            "/api/analytics/users", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert data["total_users"] >= 3
        assert "active_users" in data
        assert "recent_active_users" in data
        assert "new_users_over_time" in data
        assert "users_by_organization" in data
        assert "users_by_role" in data
        assert "verified_users" in data
        assert "unverified_users" in data

    @pytest.mark.asyncio
    async def test_user_metrics_role_breakdown(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test user metrics includes role distribution.

        WHY: Understand user composition for access control analysis.
        """
        org = await OrganizationFactory.create(db_session, name="Role Breakdown Org")
        await UserFactory.create_admin(
            db_session, email="rolebreakdown@test.com", password="Password123!", organization=org
        )
        # Create clients
        for i in range(3):
            await UserFactory.create_client(
                db_session,
                email=f"roleclient{i}@test.com",
                password="Password123!",
                organization=org,
            )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "rolebreakdown@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get user activity metrics
        response = await client.get(
            "/api/analytics/users", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        role_map = {r["status"]: r["count"] for r in data["users_by_role"]}
        assert "ADMIN" in role_map or "admin" in [r["status"].lower() for r in data["users_by_role"]]


class TestDashboardSummary:
    """Integration tests for dashboard summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_dashboard_summary(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test getting dashboard summary metrics.

        WHY: Quick overview for admin dashboard cards.
        """
        org = await OrganizationFactory.create(db_session, name="Dashboard Org")
        await UserFactory.create_admin(
            db_session, email="dashboard@test.com", password="Password123!", organization=org
        )

        # Create various data
        await ProjectFactory.create(db_session, name="Dashboard Project", organization=org)
        await InvoiceFactory.create_paid(db_session, organization=org)
        await TicketFactory.create(
            db_session, subject="Dashboard Ticket", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "dashboard@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get dashboard summary
        response = await client.get(
            "/api/analytics/dashboard", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "total_organizations" in data
        assert "active_organizations" in data
        assert "total_projects" in data
        assert "active_projects" in data
        assert "total_revenue" in data
        assert "revenue_mtd" in data
        assert "open_tickets" in data
        assert "overdue_tickets" in data

    @pytest.mark.asyncio
    async def test_dashboard_summary_counts(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test dashboard summary has accurate counts.

        WHY: Dashboard cards must show accurate numbers.
        """
        org1 = await OrganizationFactory.create(db_session, name="Count Org 1")
        org2 = await OrganizationFactory.create(db_session, name="Count Org 2", is_active=False)
        await UserFactory.create_admin(
            db_session, email="countadmin@test.com", password="Password123!", organization=org1
        )
        await UserFactory.create_client(
            db_session, email="countclient@test.com", password="Password123!", organization=org1
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "countadmin@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Get dashboard summary
        response = await client.get(
            "/api/analytics/dashboard", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        # Should have at least 2 users and 2 orgs
        assert data["total_users"] >= 2
        assert data["total_organizations"] >= 2
        # Only org1 is active
        assert data["active_organizations"] >= 1

    @pytest.mark.asyncio
    async def test_dashboard_forbidden_for_client(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that clients cannot access dashboard summary.

        WHY: RBAC - analytics are admin-only.
        """
        org = await OrganizationFactory.create(db_session)
        await UserFactory.create_client(
            db_session, email="dashclient@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "dashclient@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Try to get dashboard
        response = await client.get(
            "/api/analytics/dashboard", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403


class TestAnalyticsMonthsParameter:
    """Integration tests for analytics months parameter."""

    @pytest.mark.asyncio
    async def test_custom_months_parameter(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test analytics with custom months parameter.

        WHY: Users may want different time ranges.
        """
        org = await OrganizationFactory.create(db_session, name="Months Param Org")
        await UserFactory.create_admin(
            db_session, email="monthsparam@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "monthsparam@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Test with different months values
        response = await client.get(
            "/api/analytics/projects?months=6",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        response = await client.get(
            "/api/analytics/revenue?months=24",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_months_parameter(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test analytics rejects invalid months parameter.

        WHY: Validation prevents resource abuse.
        """
        org = await OrganizationFactory.create(db_session, name="Invalid Months Org")
        await UserFactory.create_admin(
            db_session, email="invalidmonths@test.com", password="Password123!", organization=org
        )

        # Login
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "invalidmonths@test.com", "password": "Password123!"},
        )
        token = login_response.json()["access_token"]

        # Test with out-of-range months
        response = await client.get(
            "/api/analytics/projects?months=100",  # Max is 24
            headers={"Authorization": f"Bearer {token}"},
        )
        # Validation error returns 400 or 422 depending on framework config
        assert response.status_code in [400, 422]
