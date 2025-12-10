# ADR-001: Project Structure and Architecture Foundation

## Status
**Accepted**

## Date
2025-12-10

## Context

### Problem Statement
We are building an **Automation Services Platform** - a multi-tenant SaaS application that enables automation service providers to manage client workflows using n8n as the workflow execution engine. The project requires:

1. A well-organized codebase that supports the development team
2. Clear separation of concerns between layers
3. Consistent patterns across the codebase
4. Support for test-driven development (TDD)
5. Scalable architecture that can grow with the platform

### Current State
The backend has an initial structure in place with:
- FastAPI application with factory pattern
- Custom exception hierarchy
- Base DAO with org-scoping support
- SQLAlchemy models with mixins
- Initial authentication and organization modules
- Test structure (unit/integration/e2e)

The frontend directory exists but is empty.

### Requirements
- **Backend**: Python/FastAPI with PostgreSQL
- **Frontend**: React with TypeScript
- **Database**: PostgreSQL (required)
- **Methodology**: TDD with pair programming
- **Patterns**: DAO, DRY, SRP, custom exceptions

## Decision

### Backend Structure

We will maintain and extend the existing backend structure:

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application factory
│   │
│   ├── api/                       # API Layer - FastAPI routers
│   │   ├── __init__.py
│   │   ├── auth.py               # Authentication endpoints
│   │   ├── organizations.py      # Organization management
│   │   ├── projects.py           # Project CRUD (to create)
│   │   ├── proposals.py          # Proposal management (to create)
│   │   ├── billing.py            # Stripe integration (to create)
│   │   ├── workflows.py          # n8n integration (to create)
│   │   ├── tickets.py            # Support ticketing (to create)
│   │   └── webhooks.py           # Webhook receivers (to create)
│   │
│   ├── core/                      # Core utilities and configuration
│   │   ├── __init__.py
│   │   ├── config.py             # Settings management
│   │   ├── exceptions.py         # Custom exception hierarchy
│   │   ├── exception_handlers.py # FastAPI exception handlers
│   │   ├── auth.py               # JWT and authentication utilities
│   │   ├── security.py           # Password hashing, encryption (to create)
│   │   └── deps.py               # FastAPI dependencies (to create)
│   │
│   ├── dao/                       # Data Access Objects
│   │   ├── __init__.py
│   │   ├── base.py               # Base DAO with CRUD operations
│   │   ├── user.py               # User DAO
│   │   ├── organization.py       # Organization DAO (to create)
│   │   ├── project.py            # Project DAO (to create)
│   │   ├── proposal.py           # Proposal DAO (to create)
│   │   ├── invoice.py            # Invoice DAO (to create)
│   │   ├── workflow.py           # Workflow DAO (to create)
│   │   └── ticket.py             # Ticket DAO (to create)
│   │
│   ├── models/                    # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py               # Base model with mixins
│   │   ├── user.py               # User model
│   │   ├── organization.py       # Organization model
│   │   ├── project.py            # Project model (to create)
│   │   ├── proposal.py           # Proposal model (to create)
│   │   ├── invoice.py            # Invoice model (to create)
│   │   ├── workflow.py           # Workflow models (to create)
│   │   ├── ticket.py             # Ticket model (to create)
│   │   └── audit.py              # Audit log model (to create)
│   │
│   ├── schemas/                   # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── auth.py               # Auth request/response schemas
│   │   ├── organization.py       # Organization schemas
│   │   ├── project.py            # Project schemas (to create)
│   │   ├── proposal.py           # Proposal schemas (to create)
│   │   ├── billing.py            # Billing schemas (to create)
│   │   ├── workflow.py           # Workflow schemas (to create)
│   │   └── ticket.py             # Ticket schemas (to create)
│   │
│   ├── services/                  # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth.py               # Authentication service (to create)
│   │   ├── organization.py       # Organization service (to create)
│   │   ├── project.py            # Project service (to create)
│   │   ├── proposal.py           # Proposal service (to create)
│   │   ├── billing.py            # Stripe integration (to create)
│   │   ├── workflow.py           # n8n integration (to create)
│   │   ├── notification.py       # Email/Slack service (to create)
│   │   └── pdf.py                # PDF generation (to create)
│   │
│   ├── middleware/                # Custom middleware
│   │   ├── __init__.py
│   │   ├── security_headers.py   # Security headers middleware
│   │   ├── rate_limit.py         # Rate limiting (to create)
│   │   └── audit.py              # Audit logging (to create)
│   │
│   ├── jobs/                      # Background jobs (Dramatiq)
│   │   ├── __init__.py
│   │   ├── email.py              # Email sending jobs (to create)
│   │   ├── pdf.py                # PDF generation jobs (to create)
│   │   └── sla.py                # SLA monitoring jobs (to create)
│   │
│   └── db/                        # Database utilities
│       ├── __init__.py
│       └── session.py            # Database session management
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Pytest fixtures
│   ├── factories.py              # Test data factories
│   │
│   ├── unit/                      # Unit tests (fast, isolated)
│   │   ├── __init__.py
│   │   ├── core/                 # Core module tests
│   │   ├── dao/                  # DAO tests
│   │   ├── services/             # Service tests (to create)
│   │   └── middleware/           # Middleware tests
│   │
│   ├── integration/               # Integration tests (database)
│   │   ├── __init__.py
│   │   └── api/                  # API endpoint tests
│   │
│   └── e2e/                       # End-to-end tests
│       └── __init__.py
│
├── alembic/                       # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                 # Migration files
│
├── pyproject.toml                # Python project configuration
├── alembic.ini                   # Alembic configuration
├── Dockerfile                    # Docker build configuration
└── README.md                     # Backend documentation
```

### Frontend Structure

We will create a React application with the following structure:

```
frontend/
├── src/
│   ├── index.tsx                  # Application entry point
│   ├── App.tsx                    # Root component with routing
│   │
│   ├── components/                # Reusable UI components
│   │   ├── common/               # Shared components
│   │   │   ├── Button/
│   │   │   ├── Input/
│   │   │   ├── Modal/
│   │   │   ├── Table/
│   │   │   ├── Card/
│   │   │   └── Loading/
│   │   ├── layout/               # Layout components
│   │   │   ├── Header/
│   │   │   ├── Sidebar/
│   │   │   ├── Footer/
│   │   │   └── MainLayout/
│   │   └── forms/                # Form components
│   │       ├── LoginForm/
│   │       ├── RegisterForm/
│   │       └── ProjectForm/
│   │
│   ├── pages/                     # Page components (routes)
│   │   ├── auth/
│   │   │   ├── Login.tsx
│   │   │   ├── Register.tsx
│   │   │   └── ForgotPassword.tsx
│   │   ├── dashboard/
│   │   │   └── Dashboard.tsx
│   │   ├── projects/
│   │   │   ├── ProjectList.tsx
│   │   │   └── ProjectDetail.tsx
│   │   ├── proposals/
│   │   │   ├── ProposalList.tsx
│   │   │   └── ProposalDetail.tsx
│   │   ├── billing/
│   │   │   └── InvoiceList.tsx
│   │   ├── workflows/
│   │   │   └── WorkflowList.tsx
│   │   ├── tickets/
│   │   │   ├── TicketList.tsx
│   │   │   └── TicketDetail.tsx
│   │   ├── admin/
│   │   │   ├── UserManagement.tsx
│   │   │   └── OrgManagement.tsx
│   │   └── settings/
│   │       └── Settings.tsx
│   │
│   ├── hooks/                     # Custom React hooks
│   │   ├── useAuth.ts
│   │   ├── useApi.ts
│   │   ├── useProjects.ts
│   │   └── useNotification.ts
│   │
│   ├── services/                  # API client services
│   │   ├── api.ts                # Base API client (axios)
│   │   ├── auth.ts               # Auth API calls
│   │   ├── projects.ts           # Project API calls
│   │   ├── proposals.ts          # Proposal API calls
│   │   ├── billing.ts            # Billing API calls
│   │   ├── workflows.ts          # Workflow API calls
│   │   └── tickets.ts            # Ticket API calls
│   │
│   ├── store/                     # State management
│   │   ├── index.ts              # Store configuration
│   │   ├── authSlice.ts          # Auth state
│   │   └── uiSlice.ts            # UI state (modals, notifications)
│   │
│   ├── types/                     # TypeScript type definitions
│   │   ├── api.ts                # API response types
│   │   ├── auth.ts               # Auth types
│   │   ├── project.ts            # Project types
│   │   └── common.ts             # Shared types
│   │
│   ├── utils/                     # Utility functions
│   │   ├── format.ts             # Formatting utilities
│   │   ├── validation.ts         # Validation helpers
│   │   └── storage.ts            # Local storage utilities
│   │
│   └── styles/                    # Global styles
│       ├── globals.css           # Global CSS
│       └── tailwind.css          # Tailwind imports
│
├── public/                        # Static assets
│   ├── index.html
│   └── favicon.ico
│
├── tests/                         # Frontend tests
│   ├── components/
│   ├── pages/
│   └── hooks/
│
├── package.json                   # NPM dependencies
├── tsconfig.json                  # TypeScript configuration
├── tailwind.config.js             # Tailwind configuration
├── vite.config.ts                 # Vite configuration
└── README.md                      # Frontend documentation
```

### Project Root Structure

```
automate_workflow/
├── backend/                       # Python/FastAPI backend
├── frontend/                      # React/TypeScript frontend
├── docs/
│   ├── adr/                      # Architecture Decision Records
│   ├── api/                      # API documentation
│   ├── kanban/                   # Kanban boards
│   └── specs/                    # Specifications
├── infra/                         # Infrastructure configuration
├── docker-compose.yml             # Docker Compose configuration
├── docker-compose.override.yml    # Local development overrides
├── CLAUDE.md                      # Development guidelines
├── README.md                      # Project overview
└── .env.example                   # Environment variables template
```

## Consequences

### Positive

1. **Clear Separation of Concerns**
   - API layer handles HTTP concerns only
   - Service layer contains business logic
   - DAO layer handles all database operations
   - Models define data structure

2. **Testability**
   - Each layer can be tested in isolation
   - DAOs can be mocked for service tests
   - Services can be mocked for API tests
   - Clear test structure (unit/integration/e2e)

3. **Maintainability**
   - New features follow established patterns
   - Easy to find code by feature/domain
   - Consistent naming conventions

4. **Scalability**
   - Modules can be extracted to microservices
   - Clear boundaries between domains
   - Support for horizontal scaling

5. **Developer Experience**
   - Familiar structure for Python/React developers
   - IDE navigation and refactoring support
   - Easy onboarding for new team members

### Negative

1. **Initial Overhead**
   - More files and directories to create
   - Boilerplate for simple features
   - Learning curve for team

2. **Potential Over-Engineering**
   - Some features may not need all layers
   - Risk of premature abstraction

### Mitigation

- Use code generation for boilerplate where possible
- Allow pragmatic shortcuts for simple features with documentation
- Regular architecture reviews to prevent over-engineering

## Implementation Guide

### Phase 1: Backend Foundation (Current)
1. ✅ Custom exception hierarchy
2. ✅ Base DAO with org-scoping
3. ✅ SQLAlchemy models with mixins
4. ✅ FastAPI application factory
5. ✅ Security headers middleware
6. ⏳ Complete authentication flow
7. ⏳ Core dependencies (deps.py)

### Phase 2: Frontend Setup
1. Initialize React project with Vite
2. Configure TypeScript and Tailwind
3. Create base layout components
4. Set up routing (React Router)
5. Configure API client (axios)
6. Implement auth flow

### Phase 3: Core Features
1. Organization management
2. Project CRUD
3. Proposal workflow
4. Stripe integration
5. n8n integration

### Phase 4: Support Features
1. Ticketing system
2. Notifications
3. Admin dashboard
4. Analytics

## Related ADRs

- ADR-002: Authentication and Authorization (to create)
- ADR-003: Multi-Tenancy Implementation (to create)
- ADR-004: n8n Integration Strategy (to create)

## References

- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [React Project Structure](https://react.dev/learn/thinking-in-react)
- [DAO Pattern](https://www.oracle.com/java/technologies/data-access-object.html)
