"""
Test factories for creating test data.

WHY: Factories provide a consistent, reusable way to create test objects,
reducing duplication and making tests more maintainable. Using factories
instead of manual object creation ensures tests stay consistent when models change.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.project import Project, ProjectStatus, ProjectPriority
from app.models.proposal import Proposal, ProposalStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketCategory
from app.models.integration import (
    CalendarIntegration,
    WebhookEndpoint,
    WebhookDelivery,
    CalendarProvider,
    WebhookEventType,
)
from app.dao.user import UserDAO
from app.dao.project import ProjectDAO
from app.dao.proposal import ProposalDAO
from app.dao.invoice import InvoiceDAO
from app.dao.ticket import TicketDAO, TicketCommentDAO, TicketAttachmentDAO
from app.dao.integration import (
    CalendarIntegrationDAO,
    WebhookEndpointDAO,
    WebhookDeliveryDAO,
)
from app.core.auth import hash_password


class OrganizationFactory:
    """
    Factory for creating Organization test instances.

    WHY: Centralizes organization creation logic for tests,
    ensuring consistent test data across all test suites.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        name: str = "Test Organization",
        description: Optional[str] = None,
        settings: Optional[dict] = None,
        is_active: bool = True,
    ) -> Organization:
        """
        Create an organization for testing.

        Args:
            session: Database session
            name: Organization name
            description: Organization description
            settings: JSONB settings
            is_active: Whether organization is active

        Returns:
            Created Organization instance
        """
        org = Organization(
            name=name,
            description=description or f"Description for {name}",
            settings=settings or {},
            is_active=is_active,
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)
        return org


class UserFactory:
    """
    Factory for creating User test instances.

    WHY: Provides consistent user creation with proper password hashing
    and organization relationships for testing authentication and authorization.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        email: str = "test@example.com",
        password: str = "TestPassword123!",
        name: str = "Test User",
        role: UserRole = UserRole.CLIENT,
        org_id: Optional[int] = None,
        is_active: bool = True,
        organization: Optional[Organization] = None,
    ) -> User:
        """
        Create a user for testing.

        WHY: Tests need users with different roles and organizations
        to verify RBAC and multi-tenancy features.

        Args:
            session: Database session
            email: User email (must be unique)
            password: Plain text password (will be hashed)
            name: User's full name
            role: User role (ADMIN or CLIENT)
            org_id: Organization ID
            is_active: Whether user is active
            organization: Organization instance (will create one if not provided)

        Returns:
            Created User instance
        """
        # Create organization if not provided
        if organization is None and org_id is None:
            organization = await OrganizationFactory.create(session, name=f"Org for {email}")
            org_id = organization.id
        elif organization is not None:
            org_id = organization.id

        user_dao = UserDAO(User, session)
        hashed_password = hash_password(password)

        user = await user_dao.create_user(
            email=email,
            hashed_password=hashed_password,
            name=name,
            org_id=org_id,
            role=role.value,
        )

        # Set is_active if different from default
        if not is_active:
            user.is_active = is_active
            await session.commit()
            await session.refresh(user)

        return user

    @staticmethod
    async def create_admin(
        session: AsyncSession,
        email: str = "admin@example.com",
        password: str = "AdminPassword123!",
        name: str = "Admin User",
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
    ) -> User:
        """
        Create an admin user for testing.

        WHY: Many tests require admin users to test privileged operations.
        """
        return await UserFactory.create(
            session=session,
            email=email,
            password=password,
            name=name,
            role=UserRole.ADMIN,
            org_id=org_id,
            organization=organization,
        )

    @staticmethod
    async def create_client(
        session: AsyncSession,
        email: str = "client@example.com",
        password: str = "ClientPassword123!",
        name: str = "Client User",
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
    ) -> User:
        """
        Create a client user for testing.

        WHY: Most users are clients, so this is a common test scenario.
        """
        return await UserFactory.create(
            session=session,
            email=email,
            password=password,
            name=name,
            role=UserRole.CLIENT,
            org_id=org_id,
            organization=organization,
        )


class TestDataBuilder:
    """
    Builder for creating complex test scenarios.

    WHY: Some tests require multiple related objects. This builder
    provides a fluent API for creating complex test data scenarios.
    """

    def __init__(self, session: AsyncSession):
        """Initialize builder with database session."""
        self.session = session
        self.organizations: list[Organization] = []
        self.users: list[User] = []

    async def with_organization(
        self,
        name: str = "Test Organization",
        **kwargs,
    ) -> "TestDataBuilder":
        """Add an organization to the test data."""
        org = await OrganizationFactory.create(self.session, name=name, **kwargs)
        self.organizations.append(org)
        return self

    async def with_admin(
        self,
        email: str = "admin@example.com",
        org_index: int = -1,
        **kwargs,
    ) -> "TestDataBuilder":
        """
        Add an admin user to the test data.

        Args:
            email: User email
            org_index: Index of organization in self.organizations (-1 for last)
            **kwargs: Additional user creation arguments
        """
        org = self.organizations[org_index] if self.organizations else None
        user = await UserFactory.create_admin(self.session, email=email, organization=org, **kwargs)
        self.users.append(user)
        return self

    async def with_client(
        self,
        email: str = "client@example.com",
        org_index: int = -1,
        **kwargs,
    ) -> "TestDataBuilder":
        """
        Add a client user to the test data.

        Args:
            email: User email
            org_index: Index of organization in self.organizations (-1 for last)
            **kwargs: Additional user creation arguments
        """
        org = self.organizations[org_index] if self.organizations else None
        user = await UserFactory.create_client(
            self.session, email=email, organization=org, **kwargs
        )
        self.users.append(user)
        return self

    async def with_multi_tenant_setup(self) -> "TestDataBuilder":
        """
        Create a complete multi-tenant test scenario.

        WHY: Tests org-scoping by creating two organizations,
        each with an admin and a client user.

        Returns:
            Builder with:
            - 2 organizations
            - 4 users (1 admin + 1 client per org)
        """
        # Organization 1
        await self.with_organization(name="Acme Corp")
        await self.with_admin(email="admin1@acme.com")
        await self.with_client(email="client1@acme.com")

        # Organization 2
        await self.with_organization(name="Wayne Enterprises")
        await self.with_admin(email="admin2@wayne.com")
        await self.with_client(email="client2@wayne.com")

        return self

    def get_organization(self, index: int = 0) -> Organization:
        """Get organization by index."""
        return self.organizations[index]

    def get_user(self, index: int = 0) -> User:
        """Get user by index."""
        return self.users[index]


class ProjectFactory:
    """
    Factory for creating Project test instances.

    WHY: Centralizes project creation logic for tests,
    ensuring consistent test data across all test suites.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        name: str = "Test Project",
        description: Optional[str] = None,
        status: ProjectStatus = ProjectStatus.DRAFT,
        priority: ProjectPriority = ProjectPriority.MEDIUM,
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
        estimated_hours: Optional[float] = None,
        actual_hours: Optional[float] = None,
        start_date: Optional[datetime] = None,
        due_date: Optional[datetime] = None,
    ) -> Project:
        """
        Create a project for testing.

        Args:
            session: Database session
            name: Project name
            description: Project description
            status: Project status
            priority: Project priority
            org_id: Organization ID
            organization: Organization instance (will create one if not provided)
            estimated_hours: Estimated hours
            actual_hours: Actual hours spent
            start_date: Start date
            due_date: Due date

        Returns:
            Created Project instance
        """
        # Create organization if not provided
        if organization is None and org_id is None:
            organization = await OrganizationFactory.create(session, name=f"Org for {name}")
            org_id = organization.id
        elif organization is not None:
            org_id = organization.id

        project_dao = ProjectDAO(session)
        project = await project_dao.create(
            name=name,
            description=description or f"Description for {name}",
            status=status,
            priority=priority,
            org_id=org_id,
            estimated_hours=estimated_hours,
            actual_hours=actual_hours or 0,
            start_date=start_date,
            due_date=due_date,
        )

        return project

    @staticmethod
    async def create_in_progress(
        session: AsyncSession,
        name: str = "In Progress Project",
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
        **kwargs,
    ) -> Project:
        """Create an in-progress project."""
        return await ProjectFactory.create(
            session=session,
            name=name,
            status=ProjectStatus.IN_PROGRESS,
            org_id=org_id,
            organization=organization,
            start_date=datetime.utcnow() - timedelta(days=7),
            **kwargs,
        )

    @staticmethod
    async def create_overdue(
        session: AsyncSession,
        name: str = "Overdue Project",
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
        **kwargs,
    ) -> Project:
        """Create an overdue project (due date in past, not completed)."""
        return await ProjectFactory.create(
            session=session,
            name=name,
            status=ProjectStatus.IN_PROGRESS,
            org_id=org_id,
            organization=organization,
            start_date=datetime.utcnow() - timedelta(days=30),
            due_date=datetime.utcnow() - timedelta(days=7),
            **kwargs,
        )


class ProposalFactory:
    """
    Factory for creating Proposal test instances.

    WHY: Centralizes proposal creation logic for tests,
    ensuring consistent test data across all test suites.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        title: str = "Test Proposal",
        description: Optional[str] = None,
        status: ProposalStatus = ProposalStatus.DRAFT,
        project_id: Optional[int] = None,
        project: Optional[Project] = None,
        org_id: Optional[int] = None,
        line_items: Optional[List[Dict[str, Any]]] = None,
        discount_percent: float = 0,
        tax_percent: float = 0,
        valid_until: Optional[datetime] = None,
        notes: Optional[str] = None,
        client_notes: Optional[str] = None,
        terms: Optional[str] = None,
    ) -> Proposal:
        """
        Create a proposal for testing.

        Args:
            session: Database session
            title: Proposal title
            description: Proposal description
            status: Proposal status
            project_id: Project ID
            project: Project instance (will create one if not provided)
            org_id: Organization ID (derived from project if not provided)
            line_items: List of line item dicts
            discount_percent: Discount percentage
            tax_percent: Tax percentage
            valid_until: Expiration date
            notes: Internal notes
            client_notes: Client-visible notes
            terms: Terms and conditions

        Returns:
            Created Proposal instance
        """
        # Create project if not provided
        if project is None and project_id is None:
            project = await ProjectFactory.create(session, name=f"Project for {title}")
            project_id = project.id
            org_id = project.org_id
        elif project is not None:
            project_id = project.id
            org_id = project.org_id

        # Default line items
        if line_items is None:
            line_items = [
                {"description": "Development", "quantity": 10, "unit_price": 100, "amount": 1000},
                {"description": "Testing", "quantity": 5, "unit_price": 100, "amount": 500},
            ]

        # Calculate totals
        subtotal = sum(item.get("amount", 0) for item in line_items)
        discount_amount = subtotal * (discount_percent / 100)
        subtotal_after_discount = subtotal - discount_amount
        tax_amount = subtotal_after_discount * (tax_percent / 100)
        total = subtotal_after_discount + tax_amount

        proposal_dao = ProposalDAO(session)
        proposal = await proposal_dao.create(
            title=title,
            description=description or f"Description for {title}",
            status=status,
            project_id=project_id,
            org_id=org_id,
            line_items=line_items,
            subtotal=subtotal,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            tax_percent=tax_percent,
            tax_amount=tax_amount,
            total=total,
            valid_until=valid_until or (datetime.utcnow() + timedelta(days=30)),
            notes=notes,
            client_notes=client_notes,
            terms=terms,
        )

        return proposal

    @staticmethod
    async def create_sent(
        session: AsyncSession,
        title: str = "Sent Proposal",
        project: Optional[Project] = None,
        **kwargs,
    ) -> Proposal:
        """Create a sent proposal."""
        proposal = await ProposalFactory.create(
            session=session,
            title=title,
            project=project,
            **kwargs,
        )
        # Update status to sent
        proposal_dao = ProposalDAO(session)
        return await proposal_dao.send_proposal(proposal.id, proposal.org_id)

    @staticmethod
    async def create_approved(
        session: AsyncSession,
        title: str = "Approved Proposal",
        project: Optional[Project] = None,
        **kwargs,
    ) -> Proposal:
        """Create an approved proposal."""
        proposal = await ProposalFactory.create_sent(
            session=session,
            title=title,
            project=project,
            **kwargs,
        )
        # Update status to approved
        proposal_dao = ProposalDAO(session)
        return await proposal_dao.approve_proposal(proposal.id, proposal.org_id)


class InvoiceFactory:
    """
    Factory for creating Invoice test instances.

    WHY: Centralizes invoice creation logic for tests,
    ensuring consistent test data across all test suites.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        invoice_number: Optional[str] = None,
        status: InvoiceStatus = InvoiceStatus.DRAFT,
        proposal_id: Optional[int] = None,
        proposal: Optional[Proposal] = None,
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
        subtotal: Decimal = Decimal("1000.00"),
        discount_amount: Decimal = Decimal("0"),
        tax_amount: Decimal = Decimal("80.00"),
        total: Optional[Decimal] = None,
        amount_paid: Decimal = Decimal("0"),
        issue_date: Optional[date] = None,
        due_date: Optional[date] = None,
        stripe_payment_intent_id: Optional[str] = None,
        stripe_checkout_session_id: Optional[str] = None,
        payment_method: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Invoice:
        """
        Create an invoice for testing.

        Args:
            session: Database session
            invoice_number: Invoice number (auto-generated if not provided)
            status: Invoice status
            proposal_id: Proposal ID
            proposal: Proposal instance
            org_id: Organization ID
            organization: Organization instance (will create one if not provided)
            subtotal: Subtotal amount
            discount_amount: Discount amount
            tax_amount: Tax amount
            total: Total amount (calculated if not provided)
            amount_paid: Amount already paid
            issue_date: Issue date
            due_date: Due date
            stripe_payment_intent_id: Stripe PaymentIntent ID
            stripe_checkout_session_id: Stripe Checkout Session ID
            payment_method: Payment method
            notes: Notes

        Returns:
            Created Invoice instance
        """
        # Handle organization
        if organization is None and org_id is None:
            organization = await OrganizationFactory.create(session, name="Org for Invoice")
            org_id = organization.id
        elif organization is not None:
            org_id = organization.id

        # Handle proposal
        if proposal is not None:
            proposal_id = proposal.id
            org_id = proposal.org_id

        # Generate invoice number if not provided
        if invoice_number is None:
            invoice_dao = InvoiceDAO(session)
            sequence = await invoice_dao.get_next_invoice_number_sequence(org_id)
            invoice_number = Invoice.generate_invoice_number(org_id, sequence)

        # Calculate total if not provided
        if total is None:
            total = subtotal - discount_amount + tax_amount

        # Default dates
        if issue_date is None:
            issue_date = date.today()
        if due_date is None:
            due_date = date.today() + timedelta(days=30)

        invoice_dao = InvoiceDAO(session)
        invoice = await invoice_dao.create(
            invoice_number=invoice_number,
            status=status,
            proposal_id=proposal_id,
            org_id=org_id,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total=total,
            amount_paid=amount_paid,
            issue_date=issue_date,
            due_date=due_date,
            stripe_payment_intent_id=stripe_payment_intent_id,
            stripe_checkout_session_id=stripe_checkout_session_id,
            payment_method=payment_method,
            notes=notes,
        )

        return invoice

    @staticmethod
    async def create_sent(
        session: AsyncSession,
        organization: Optional[Organization] = None,
        **kwargs,
    ) -> Invoice:
        """Create a sent invoice."""
        invoice = await InvoiceFactory.create(
            session=session,
            organization=organization,
            **kwargs,
        )
        invoice_dao = InvoiceDAO(session)
        return await invoice_dao.send_invoice(invoice.id, invoice.org_id)

    @staticmethod
    async def create_paid(
        session: AsyncSession,
        organization: Optional[Organization] = None,
        **kwargs,
    ) -> Invoice:
        """Create a paid invoice."""
        invoice = await InvoiceFactory.create_sent(
            session=session,
            organization=organization,
            **kwargs,
        )
        invoice_dao = InvoiceDAO(session)
        return await invoice_dao.mark_paid(invoice.id, invoice.org_id)

    @staticmethod
    async def create_from_proposal(
        session: AsyncSession,
        proposal: Proposal,
        due_days: int = 30,
    ) -> Invoice:
        """Create an invoice from an approved proposal."""
        invoice_dao = InvoiceDAO(session)
        return await invoice_dao.create_from_proposal(proposal, due_days=due_days)


class N8nEnvironmentFactory:
    """
    Factory for creating N8nEnvironment test instances.

    WHY: Centralizes n8n environment creation logic for tests,
    handling API key encryption automatically.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        name: str = "Test n8n Environment",
        base_url: str = "https://n8n.example.com",
        api_key: str = "test-api-key-12345",
        webhook_url: Optional[str] = None,
        is_active: bool = True,
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
    ):
        """
        Create an n8n environment for testing.

        Args:
            session: Database session
            name: Environment name
            base_url: n8n instance URL
            api_key: API key (will be encrypted)
            webhook_url: Optional webhook URL
            is_active: Whether environment is active
            org_id: Organization ID
            organization: Organization instance

        Returns:
            Created N8nEnvironment instance
        """
        from app.dao.n8n_environment import N8nEnvironmentDAO

        # Create organization if not provided
        if organization is None and org_id is None:
            organization = await OrganizationFactory.create(session, name=f"Org for {name}")
            org_id = organization.id
        elif organization is not None:
            org_id = organization.id

        env_dao = N8nEnvironmentDAO(session)
        return await env_dao.create_environment(
            org_id=org_id,
            name=name,
            base_url=base_url,
            api_key=api_key,
            webhook_url=webhook_url,
            is_active=is_active,
        )


class WorkflowTemplateFactory:
    """
    Factory for creating WorkflowTemplate test instances.

    WHY: Centralizes template creation logic for tests.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        name: str = "Test Template",
        description: Optional[str] = None,
        category: Optional[str] = None,
        n8n_template_id: Optional[str] = None,
        default_parameters: Optional[dict] = None,
        is_public: bool = True,
        created_by_org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
    ):
        """
        Create a workflow template for testing.

        Args:
            session: Database session
            name: Template name
            description: Template description
            category: Template category
            n8n_template_id: n8n template ID
            default_parameters: Default parameters
            is_public: Whether template is public
            created_by_org_id: Creating organization ID
            organization: Organization instance

        Returns:
            Created WorkflowTemplate instance
        """
        from app.dao.workflow_template import WorkflowTemplateDAO

        # Handle organization for private templates
        if organization is not None:
            created_by_org_id = organization.id

        template_dao = WorkflowTemplateDAO(session)
        return await template_dao.create_template(
            name=name,
            description=description or f"Description for {name}",
            category=category,
            n8n_template_id=n8n_template_id,
            default_parameters=default_parameters,
            is_public=is_public,
            created_by_org_id=created_by_org_id,
        )

    @staticmethod
    async def create_private(
        session: AsyncSession,
        name: str = "Private Template",
        organization: Optional[Organization] = None,
        **kwargs,
    ):
        """Create a private template for an organization."""
        if organization is None:
            organization = await OrganizationFactory.create(session, name=f"Org for {name}")

        return await WorkflowTemplateFactory.create(
            session=session,
            name=name,
            is_public=False,
            organization=organization,
            **kwargs,
        )


class WorkflowInstanceFactory:
    """
    Factory for creating WorkflowInstance test instances.

    WHY: Centralizes workflow instance creation logic for tests.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        name: str = "Test Workflow Instance",
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
        project_id: Optional[int] = None,
        project: Optional[Project] = None,
        template_id: Optional[int] = None,
        n8n_environment_id: Optional[int] = None,
        n8n_workflow_id: Optional[str] = None,
        parameters: Optional[dict] = None,
        status=None,
    ):
        """
        Create a workflow instance for testing.

        Args:
            session: Database session
            name: Instance name
            org_id: Organization ID
            organization: Organization instance
            project_id: Project ID
            project: Project instance
            template_id: Template ID
            n8n_environment_id: n8n environment ID
            n8n_workflow_id: n8n workflow ID
            parameters: Custom parameters
            status: Workflow status

        Returns:
            Created WorkflowInstance instance
        """
        from app.dao.workflow_instance import WorkflowInstanceDAO
        from app.models.workflow import WorkflowStatus

        # Handle organization
        if organization is None and org_id is None:
            organization = await OrganizationFactory.create(session, name=f"Org for {name}")
            org_id = organization.id
        elif organization is not None:
            org_id = organization.id

        # Handle project
        if project is not None:
            project_id = project.id

        instance_dao = WorkflowInstanceDAO(session)
        return await instance_dao.create_instance(
            org_id=org_id,
            name=name,
            template_id=template_id,
            project_id=project_id,
            n8n_environment_id=n8n_environment_id,
            n8n_workflow_id=n8n_workflow_id,
            parameters=parameters,
            status=status or WorkflowStatus.DRAFT,
        )

    @staticmethod
    async def create_active(
        session: AsyncSession,
        name: str = "Active Workflow",
        organization: Optional[Organization] = None,
        **kwargs,
    ):
        """Create an active workflow instance."""
        from app.models.workflow import WorkflowStatus

        return await WorkflowInstanceFactory.create(
            session=session,
            name=name,
            organization=organization,
            status=WorkflowStatus.ACTIVE,
            n8n_workflow_id="n8n-test-workflow-id",
            **kwargs,
        )


class ExecutionLogFactory:
    """
    Factory for creating ExecutionLog test instances.

    WHY: Centralizes execution log creation logic for tests.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        workflow_instance_id: int,
        n8n_execution_id: Optional[str] = None,
        status=None,
        input_data: Optional[dict] = None,
    ):
        """
        Create an execution log for testing.

        Args:
            session: Database session
            workflow_instance_id: Workflow instance ID
            n8n_execution_id: n8n execution ID
            status: Execution status
            input_data: Input data

        Returns:
            Created ExecutionLog instance
        """
        from app.dao.execution_log import ExecutionLogDAO
        from app.models.workflow import ExecutionStatus

        log_dao = ExecutionLogDAO(session)
        return await log_dao.create_log(
            workflow_instance_id=workflow_instance_id,
            n8n_execution_id=n8n_execution_id or f"exec-{workflow_instance_id}-test",
            status=status or ExecutionStatus.RUNNING,
            input_data=input_data,
        )

    @staticmethod
    async def create_completed(
        session: AsyncSession,
        workflow_instance_id: int,
        success: bool = True,
        output_data: Optional[dict] = None,
        error_message: Optional[str] = None,
    ):
        """Create a completed execution log."""
        from app.dao.execution_log import ExecutionLogDAO
        from app.models.workflow import ExecutionStatus

        log = await ExecutionLogFactory.create(
            session=session,
            workflow_instance_id=workflow_instance_id,
        )

        log_dao = ExecutionLogDAO(session)
        status = ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED
        return await log_dao.complete_execution(
            log_id=log.id,
            status=status,
            output_data=output_data,
            error_message=error_message,
        )


class TicketFactory:
    """
    Factory for creating Ticket test instances.

    WHY: Centralizes ticket creation logic for tests,
    handling SLA calculations automatically.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        subject: str = "Test Ticket",
        description: str = "Test ticket description",
        status: TicketStatus = TicketStatus.OPEN,
        priority: TicketPriority = TicketPriority.MEDIUM,
        category: TicketCategory = TicketCategory.SUPPORT,
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
        project_id: Optional[int] = None,
        project: Optional[Project] = None,
        created_by_user_id: Optional[int] = None,
        created_by: Optional[User] = None,
        assigned_to_user_id: Optional[int] = None,
        assigned_to: Optional[User] = None,
    ) -> Ticket:
        """
        Create a ticket for testing.

        Args:
            session: Database session
            subject: Ticket subject
            description: Ticket description
            status: Ticket status
            priority: Ticket priority
            category: Ticket category
            org_id: Organization ID
            organization: Organization instance
            project_id: Project ID
            project: Project instance
            created_by_user_id: Creator user ID
            created_by: Creator user instance
            assigned_to_user_id: Assignee user ID
            assigned_to: Assignee user instance

        Returns:
            Created Ticket instance
        """
        # Handle organization
        if organization is not None:
            org_id = organization.id
        elif org_id is None:
            organization = await OrganizationFactory.create(session, name=f"Org for {subject}")
            org_id = organization.id

        # Handle project
        if project is not None:
            project_id = project.id

        # Handle creator
        if created_by is not None:
            created_by_user_id = created_by.id
        elif created_by_user_id is None:
            created_by = await UserFactory.create(
                session,
                email=f"ticket-creator-{datetime.utcnow().timestamp()}@example.com",
                org_id=org_id,
            )
            created_by_user_id = created_by.id

        # Handle assignee
        if assigned_to is not None:
            assigned_to_user_id = assigned_to.id

        ticket_dao = TicketDAO(session)
        ticket = await ticket_dao.create(
            org_id=org_id,
            created_by_user_id=created_by_user_id,
            subject=subject,
            description=description,
            priority=priority,
            category=category,
            project_id=project_id,
            assigned_to_user_id=assigned_to_user_id,
        )

        # Update status if not OPEN (default)
        # For test purposes, directly set status to bypass transition validation
        if status != TicketStatus.OPEN:
            ticket.status = status
            if status == TicketStatus.RESOLVED:
                ticket.resolved_at = datetime.utcnow()
            elif status == TicketStatus.CLOSED:
                ticket.closed_at = datetime.utcnow()
            await session.commit()
            await session.refresh(ticket)

        return ticket

    @staticmethod
    async def create_urgent(
        session: AsyncSession,
        subject: str = "Urgent Ticket",
        organization: Optional[Organization] = None,
        created_by: Optional[User] = None,
        **kwargs,
    ) -> Ticket:
        """Create an urgent priority ticket."""
        return await TicketFactory.create(
            session=session,
            subject=subject,
            priority=TicketPriority.URGENT,
            organization=organization,
            created_by=created_by,
            **kwargs,
        )

    @staticmethod
    async def create_in_progress(
        session: AsyncSession,
        subject: str = "In Progress Ticket",
        organization: Optional[Organization] = None,
        created_by: Optional[User] = None,
        assigned_to: Optional[User] = None,
        **kwargs,
    ) -> Ticket:
        """Create an in-progress ticket with assignee."""
        return await TicketFactory.create(
            session=session,
            subject=subject,
            status=TicketStatus.IN_PROGRESS,
            organization=organization,
            created_by=created_by,
            assigned_to=assigned_to,
            **kwargs,
        )

    @staticmethod
    async def create_resolved(
        session: AsyncSession,
        subject: str = "Resolved Ticket",
        organization: Optional[Organization] = None,
        created_by: Optional[User] = None,
        **kwargs,
    ) -> Ticket:
        """Create a resolved ticket."""
        return await TicketFactory.create(
            session=session,
            subject=subject,
            status=TicketStatus.RESOLVED,
            organization=organization,
            created_by=created_by,
            **kwargs,
        )


class TicketCommentFactory:
    """
    Factory for creating TicketComment test instances.

    WHY: Centralizes comment creation logic for tests.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        ticket_id: int,
        user_id: int,
        content: str = "Test comment",
        is_internal: bool = False,
    ):
        """
        Create a ticket comment for testing.

        Args:
            session: Database session
            ticket_id: Ticket ID
            user_id: User ID
            content: Comment content
            is_internal: Whether this is an internal note

        Returns:
            Created TicketComment instance
        """
        comment_dao = TicketCommentDAO(session)
        return await comment_dao.create(
            ticket_id=ticket_id,
            user_id=user_id,
            content=content,
            is_internal=is_internal,
        )

    @staticmethod
    async def create_internal(
        session: AsyncSession,
        ticket_id: int,
        user_id: int,
        content: str = "Internal note",
    ):
        """Create an internal note comment."""
        return await TicketCommentFactory.create(
            session=session,
            ticket_id=ticket_id,
            user_id=user_id,
            content=content,
            is_internal=True,
        )


class DocumentFactory:
    """
    Factory for creating Document test instances.

    WHY: Centralizes document creation logic for tests,
    enabling consistent test data for document management features.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        filename: str = "test_document.pdf",
        original_filename: str = "Test Document.pdf",
        content_type: str = "application/pdf",
        file_size: int = 1024000,
        s3_key: Optional[str] = None,
        s3_bucket: str = "test-bucket",
        folder: str = "/",
        tags: Optional[List[str]] = None,
        description: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
        uploaded_by: Optional[int] = None,
        uploader: Optional[User] = None,
    ):
        """
        Create a document for testing.

        Args:
            session: Database session
            filename: Stored filename
            original_filename: Original upload filename
            content_type: MIME type
            file_size: Size in bytes
            s3_key: S3 object key (auto-generated if not provided)
            s3_bucket: S3 bucket name
            folder: Folder path
            tags: List of tags
            description: Document description
            entity_type: Linked entity type
            entity_id: Linked entity ID
            org_id: Organization ID
            organization: Organization instance
            uploaded_by: Uploader user ID
            uploader: Uploader user instance

        Returns:
            Created Document instance
        """
        from app.dao.document import DocumentDAO

        # Handle organization
        if organization is not None:
            org_id = organization.id
        elif org_id is None:
            organization = await OrganizationFactory.create(
                session, name=f"Org for {filename}"
            )
            org_id = organization.id

        # Handle uploader
        if uploader is not None:
            uploaded_by = uploader.id
        elif uploaded_by is None:
            uploader = await UserFactory.create(
                session,
                email=f"uploader-{datetime.utcnow().timestamp()}@example.com",
                org_id=org_id,
            )
            uploaded_by = uploader.id

        # Generate S3 key if not provided
        if s3_key is None:
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            s3_key = f"orgs/{org_id}/documents/{unique_id}_{filename}"

        doc_dao = DocumentDAO(session)
        document = await doc_dao.create_document(
            org_id=org_id,
            uploaded_by=uploaded_by,
            filename=filename,
            original_filename=original_filename,
            content_type=content_type,
            file_size=file_size,
            s3_key=s3_key,
            s3_bucket=s3_bucket,
            folder=folder,
            tags=tags,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        return document

    @staticmethod
    async def create_for_project(
        session: AsyncSession,
        project: Project,
        filename: str = "project_document.pdf",
        uploader: Optional[User] = None,
        **kwargs,
    ):
        """Create a document attached to a project."""
        return await DocumentFactory.create(
            session=session,
            filename=filename,
            organization=None,
            org_id=project.org_id,
            entity_type="project",
            entity_id=project.id,
            uploader=uploader,
            **kwargs,
        )

    @staticmethod
    async def create_for_ticket(
        session: AsyncSession,
        ticket: Ticket,
        filename: str = "ticket_attachment.pdf",
        uploader: Optional[User] = None,
        **kwargs,
    ):
        """Create a document attached to a ticket."""
        return await DocumentFactory.create(
            session=session,
            filename=filename,
            organization=None,
            org_id=ticket.org_id,
            entity_type="ticket",
            entity_id=ticket.id,
            uploader=uploader,
            **kwargs,
        )


class CalendarIntegrationFactory:
    """
    Factory for creating CalendarIntegration test instances.

    WHY: Centralizes calendar integration creation logic for tests,
    enabling consistent test data for external integration features.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        provider: str = CalendarProvider.GOOGLE.value,
        provider_email: Optional[str] = None,
        access_token: str = "test_access_token_12345",
        refresh_token: str = "test_refresh_token_67890",
        token_expires_at: Optional[datetime] = None,
        calendar_id: Optional[str] = None,
        calendar_name: Optional[str] = "Test Calendar",
        sync_enabled: bool = True,
        sync_projects: bool = True,
        sync_tickets: bool = False,
        sync_invoices: bool = False,
        is_active: bool = True,
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
        user_id: Optional[int] = None,
        user: Optional[User] = None,
    ) -> CalendarIntegration:
        """
        Create a calendar integration for testing.

        Args:
            session: Database session
            provider: Calendar provider (google, outlook, etc.)
            provider_email: Email from provider
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            token_expires_at: Token expiration time
            calendar_id: Calendar ID
            calendar_name: Calendar display name
            sync_enabled: Whether sync is enabled
            sync_projects: Sync projects to calendar
            sync_tickets: Sync tickets to calendar
            sync_invoices: Sync invoices to calendar
            is_active: Whether integration is active
            org_id: Organization ID
            organization: Organization instance
            user_id: User ID
            user: User instance

        Returns:
            Created CalendarIntegration instance
        """
        # Handle organization
        if organization is not None:
            org_id = organization.id
        elif org_id is None:
            organization = await OrganizationFactory.create(
                session, name=f"Org for calendar integration"
            )
            org_id = organization.id

        # Handle user
        if user is not None:
            user_id = user.id
        elif user_id is None:
            user = await UserFactory.create(
                session,
                email=f"cal-user-{datetime.utcnow().timestamp()}@example.com",
                org_id=org_id,
            )
            user_id = user.id

        # Set default token expiration
        if token_expires_at is None:
            token_expires_at = datetime.utcnow() + timedelta(hours=1)

        # Set default provider email
        if provider_email is None:
            provider_email = f"calendar-{user_id}@{provider}.com"

        dao = CalendarIntegrationDAO(session)
        integration = CalendarIntegration(
            user_id=user_id,
            org_id=org_id,
            provider=provider,
            provider_email=provider_email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            calendar_id=calendar_id,
            calendar_name=calendar_name,
            sync_enabled=sync_enabled,
            sync_projects=sync_projects,
            sync_tickets=sync_tickets,
            sync_invoices=sync_invoices,
            is_active=is_active,
        )
        return await dao.create(integration)

    @staticmethod
    async def create_expired(
        session: AsyncSession,
        user: Optional[User] = None,
        organization: Optional[Organization] = None,
        **kwargs,
    ) -> CalendarIntegration:
        """Create a calendar integration with expired token."""
        return await CalendarIntegrationFactory.create(
            session=session,
            user=user,
            organization=organization,
            token_expires_at=datetime.utcnow() - timedelta(hours=1),
            **kwargs,
        )

    @staticmethod
    async def create_inactive(
        session: AsyncSession,
        user: Optional[User] = None,
        organization: Optional[Organization] = None,
        **kwargs,
    ) -> CalendarIntegration:
        """Create an inactive calendar integration."""
        return await CalendarIntegrationFactory.create(
            session=session,
            user=user,
            organization=organization,
            is_active=False,
            error_message="Integration disabled by user",
            **kwargs,
        )


class WebhookEndpointFactory:
    """
    Factory for creating WebhookEndpoint test instances.

    WHY: Centralizes webhook endpoint creation logic for tests,
    enabling consistent test data for webhook features.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        name: str = "Test Webhook",
        description: Optional[str] = None,
        url: str = "https://example.com/webhook",
        secret: Optional[str] = None,
        events: Optional[List[str]] = None,
        headers: Optional[Dict[str, str]] = None,
        is_active: bool = True,
        retry_enabled: bool = True,
        max_retries: int = 3,
        org_id: Optional[int] = None,
        organization: Optional[Organization] = None,
        created_by_id: Optional[int] = None,
        created_by: Optional[User] = None,
    ) -> WebhookEndpoint:
        """
        Create a webhook endpoint for testing.

        Args:
            session: Database session
            name: Webhook name
            description: Webhook description
            url: Webhook URL
            secret: Signing secret (auto-generated if not provided)
            events: Event types to subscribe to
            headers: Custom headers
            is_active: Whether endpoint is active
            retry_enabled: Whether retries are enabled
            max_retries: Maximum retry attempts
            org_id: Organization ID
            organization: Organization instance
            created_by_id: Creator user ID
            created_by: Creator user instance

        Returns:
            Created WebhookEndpoint instance
        """
        import secrets as sec

        # Handle organization
        if organization is not None:
            org_id = organization.id
        elif org_id is None:
            organization = await OrganizationFactory.create(
                session, name=f"Org for {name}"
            )
            org_id = organization.id

        # Handle creator
        if created_by is not None:
            created_by_id = created_by.id

        # Generate secret if not provided
        if secret is None:
            secret = f"whsec_{sec.token_urlsafe(32)}"

        # Default events
        if events is None:
            events = [WebhookEventType.TICKET_CREATED.value]

        dao = WebhookEndpointDAO(session)
        endpoint = WebhookEndpoint(
            org_id=org_id,
            name=name,
            description=description or f"Description for {name}",
            url=url,
            secret=secret,
            events=events,
            headers=headers,
            is_active=is_active,
            retry_enabled=retry_enabled,
            max_retries=max_retries,
            created_by_id=created_by_id,
        )
        return await dao.create(endpoint)

    @staticmethod
    async def create_all_events(
        session: AsyncSession,
        name: str = "All Events Webhook",
        organization: Optional[Organization] = None,
        **kwargs,
    ) -> WebhookEndpoint:
        """Create a webhook subscribed to all events."""
        return await WebhookEndpointFactory.create(
            session=session,
            name=name,
            organization=organization,
            events=["*"],
            **kwargs,
        )

    @staticmethod
    async def create_ticket_events(
        session: AsyncSession,
        name: str = "Ticket Webhook",
        organization: Optional[Organization] = None,
        **kwargs,
    ) -> WebhookEndpoint:
        """Create a webhook subscribed to ticket events."""
        return await WebhookEndpointFactory.create(
            session=session,
            name=name,
            organization=organization,
            events=["ticket.*"],
            **kwargs,
        )


class WebhookDeliveryFactory:
    """
    Factory for creating WebhookDelivery test instances.

    WHY: Centralizes webhook delivery creation logic for tests,
    enabling consistent test data for delivery tracking features.
    """

    @staticmethod
    async def create(
        session: AsyncSession,
        endpoint: WebhookEndpoint,
        event_type: str = WebhookEventType.TICKET_CREATED.value,
        event_id: Optional[str] = None,
        request_body: Optional[Dict[str, Any]] = None,
        response_status: Optional[int] = None,
        response_body: Optional[str] = None,
        delivered: bool = False,
        attempt_count: int = 1,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> WebhookDelivery:
        """
        Create a webhook delivery for testing.

        Args:
            session: Database session
            endpoint: Webhook endpoint
            event_type: Event type
            event_id: Event ID (auto-generated if not provided)
            request_body: Request payload
            response_status: HTTP response status
            response_body: HTTP response body
            delivered: Whether delivery succeeded
            attempt_count: Number of attempts
            duration_ms: Request duration in ms
            error_message: Error message if failed

        Returns:
            Created WebhookDelivery instance
        """
        import uuid

        if event_id is None:
            event_id = str(uuid.uuid4())

        if request_body is None:
            request_body = {
                "event_type": event_type,
                "event_id": event_id,
                "data": {"test": True},
            }

        dao = WebhookDeliveryDAO(session)
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            event_type=event_type,
            event_id=event_id,
            request_url=endpoint.url,
            request_headers={"Content-Type": "application/json"},
            request_body=request_body,
            response_status=response_status,
            response_body=response_body,
            delivered=delivered,
            attempt_count=attempt_count,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        return await dao.create(delivery)

    @staticmethod
    async def create_successful(
        session: AsyncSession,
        endpoint: WebhookEndpoint,
        **kwargs,
    ) -> WebhookDelivery:
        """Create a successful webhook delivery."""
        return await WebhookDeliveryFactory.create(
            session=session,
            endpoint=endpoint,
            delivered=True,
            response_status=200,
            response_body='{"status": "ok"}',
            duration_ms=150,
            **kwargs,
        )

    @staticmethod
    async def create_failed(
        session: AsyncSession,
        endpoint: WebhookEndpoint,
        **kwargs,
    ) -> WebhookDelivery:
        """Create a failed webhook delivery."""
        return await WebhookDeliveryFactory.create(
            session=session,
            endpoint=endpoint,
            delivered=False,
            response_status=500,
            response_body='{"error": "Internal Server Error"}',
            duration_ms=5000,
            error_message="HTTP 500",
            **kwargs,
        )

    @staticmethod
    async def create_pending_retry(
        session: AsyncSession,
        endpoint: WebhookEndpoint,
        **kwargs,
    ) -> WebhookDelivery:
        """Create a delivery pending retry."""
        delivery = await WebhookDeliveryFactory.create(
            session=session,
            endpoint=endpoint,
            delivered=False,
            response_status=503,
            error_message="Service Unavailable",
            **kwargs,
        )
        # Set next retry time
        delivery.next_retry_at = datetime.utcnow() - timedelta(minutes=1)
        await session.commit()
        await session.refresh(delivery)
        return delivery
