# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Automation Services Platform** - A comprehensive SaaS platform for managing automation services, client onboarding, proposals, payments, ticketing, and n8n workflow orchestration.

### Tech Stack
- **Backend**: FastAPI (Python 3.11+), SQLAlchemy 2.0, PostgreSQL
- **Frontend**: React + TypeScript + Tailwind CSS
- **Infrastructure**: Docker Compose, Traefik, Redis, n8n
- **Database**: PostgreSQL (required)

---

## CRITICAL DIRECTIVES (NON-NEGOTIABLE)

### 1. Architecture Decision Records (ADRs) FIRST
**MANDATORY**: Before ANY implementation, create an ADR in `docs/adr/`.

ADR Format:
```markdown
# ADR-XXX: [Title]

## Status
Proposed | Accepted | Deprecated | Superseded

## Context
What is the issue we're addressing? Why is this decision needed?

## Decision
What is the change we're proposing/have agreed to implement?

## Consequences
What are the positive and negative results of this decision?

## Implementation Guide
Step-by-step implementation instructions.
```

**ADRs are your implementation guide.** Do not deviate from accepted ADRs.

### 2. Read Existing APIs Before Writing Code
**MANDATORY**: Before writing ANY code:
1. Read all related existing files
2. Check existing function signatures and parameters
3. Verify import paths and module structure
4. Understand existing patterns in the codebase

This prevents:
- Parameter mismatches
- Function redefinitions
- Import errors
- Breaking existing functionality

### 3. No Stubs, No TODOs, No Partial Implementation
**NEVER** implement stubs or leave TODOs. Every task must be **fully implemented**.

```python
# ❌ FORBIDDEN
def process_payment(self, amount: float) -> bool:
    # TODO: Implement payment processing
    pass

# ❌ FORBIDDEN
def process_payment(self, amount: float) -> bool:
    raise NotImplementedError("Coming soon")

# ✅ REQUIRED: Full implementation
def process_payment(self, amount: float) -> bool:
    """
    Process a payment through Stripe.

    WHAT: Charges the customer's payment method for the specified amount.

    WHY: Enables billing for automation services after proposal approval.
    We use Stripe because it handles PCI compliance, reducing our security
    burden while providing reliable payment processing with webhook support.

    HOW: Creates a PaymentIntent via Stripe API, handles the response,
    and updates our database with the transaction status.

    Args:
        amount: Payment amount in dollars (converted to cents for Stripe)

    Returns:
        True if payment succeeded, False otherwise

    Raises:
        PaymentError: If Stripe API call fails
        ValidationError: If amount is invalid
    """
    if amount <= 0:
        raise ValidationError(
            message="Payment amount must be positive",
            details={"amount": amount}
        )

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency="usd",
            # ... full implementation
        )
        return intent.status == "succeeded"
    except stripe.error.StripeError as e:
        raise PaymentError(
            message="Payment processing failed",
            details={"stripe_error": str(e)},
            original_exception=e
        )
```

### 4. Documentation: WHAT, WHY, and HOW
**CRITICAL**: All code must be extensively documented explaining:
- **WHAT**: What does this code do?
- **WHY**: Why is this approach chosen? What problem does it solve?
- **HOW**: How does it work? What's the algorithm/approach?

Every function, class, and module MUST have comprehensive docstrings.

### 5. Custom Exception Handling
**NEVER** throw or catch base exceptions. Always wrap in custom exceptions.

```python
# ❌ WRONG - Throwing base exception
raise Exception("Database connection failed")

# ❌ WRONG - Catching base exception without wrapping
try:
    result = some_operation()
except Exception as e:
    logger.error(e)
    raise

# ✅ CORRECT - Custom exception with context
raise DatabaseConnectionError(
    message="Failed to connect to PostgreSQL",
    details={"host": db_host, "database": db_name},
    retry_after=30
)

# ✅ CORRECT - Wrapping caught exceptions
try:
    result = some_operation()
except SomeLibraryError as e:
    raise ServiceError(
        message="Operation failed",
        details={"operation": "some_operation"},
        original_exception=e
    )
```

All custom exceptions defined in `app/core/exceptions.py`.

### 6. DAO Pattern (Data Access Object)
**REQUIRED**: All database operations must use the DAO pattern.

```python
# ❌ WRONG: Direct query in service
async def get_user(user_id: int):
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

# ✅ CORRECT: Using DAO
async def get_user(user_id: int):
    return await user_dao.get_by_id(user_id)
```

Structure:
- `app/dao/` - All DAO classes
- Each model has a corresponding DAO
- DAOs encapsulate ALL database queries
- Services call DAOs, never direct SQLAlchemy

### 7. Design Patterns: DRY and SRP
**DRY (Don't Repeat Yourself)**:
- Extract common logic into shared utilities
- Use base classes for common DAO/Service patterns
- Create reusable components

**SRP (Single Responsibility Principle)**:
- Each class/module has ONE responsibility
- Split large files into focused modules
- Separate concerns (auth, business logic, data access)

### 8. Pair Programming with Two Agents
Each task requires **two agents working together**:
- **Primary Agent**: Implements the feature
- **Review Agent**: Reviews, tests, validates

Agent Pairings:
- Architecture + Security → System design review
- Test Design + Implementation → TDD workflow
- Implementation + DevOps → Deployment preparation
- Security + Implementation → Secure coding review

---

## Development Methodology

### Agile Framework with TDD Sprints

**Sprint Structure:**
1. **Sprint Planning**: Define scope, create ADRs
2. **TDD Development**: Red → Green → Refactor
3. **Pair Programming**: Two agents per task
4. **Sprint Review**: Demo and retrospective

**TDD Cycle (MANDATORY):**
```
1. RED:      Write a failing test first
2. GREEN:   Write minimal code to pass the test
3. REFACTOR: Improve code while keeping tests green
```

**Test Coverage Requirements:**
- Minimum 80% code coverage
- Unit tests: Fast, isolated, mock dependencies
- Integration tests: Real database, test transactions
- E2E tests: Full user flows

### Specialized Agent Framework

**1. Architecture Agent** (`/.claude/agents/architecture.md`)
- System design and ADR creation
- Design pattern selection
- Scalability planning
- API contract definition

**2. Test Design Agent** (`/.claude/agents/test-design.md`)
- Test strategy creation
- Test case design
- TDD enforcement
- Coverage analysis

**3. Software Implementation Agent** (`/.claude/agents/implementation.md`)
- Code development following TDD
- DAO pattern implementation
- Full documentation (WHAT/WHY/HOW)
- No stubs or TODOs

**4. Cybersecurity Agent** (`/.claude/agents/security.md`)
- OWASP Top 10 compliance
- Security audits
- Secure coding review
- Penetration testing

**5. DevOps Agent** (`/.claude/agents/devops.md`)
- CI/CD pipeline management
- Infrastructure as code
- Deployment automation
- Monitoring setup

---

## Code Standards

### File Structure
```
backend/
├── app/
│   ├── api/           # FastAPI routers
│   ├── core/          # Core utilities (config, security, exceptions)
│   ├── dao/           # Data Access Objects
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # Business logic
│   └── main.py        # Application entry point
├── tests/
│   ├── unit/          # Unit tests
│   ├── integration/   # Integration tests
│   └── e2e/           # End-to-end tests
└── alembic/           # Database migrations

frontend/
├── src/
│   ├── components/    # React components
│   ├── hooks/         # Custom hooks
│   ├── pages/         # Page components
│   ├── services/      # API clients
│   ├── store/         # State management
│   └── utils/         # Utilities
└── tests/             # Frontend tests

docs/
├── adr/               # Architecture Decision Records
├── api/               # API documentation
├── kanban/            # Kanban boards
└── specs/             # Specifications
```

### Naming Conventions

**Python:**
- Classes: `PascalCase` (e.g., `UserDAO`, `PaymentService`)
- Functions/variables: `snake_case` (e.g., `get_user_by_id`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_COUNT`)
- Private: `_leading_underscore` (e.g., `_internal_method`)

**TypeScript/React:**
- Components: `PascalCase` (e.g., `UserProfile`)
- Functions/variables: `camelCase` (e.g., `getUserById`)
- Constants: `UPPER_SNAKE_CASE` or `camelCase`
- Types/Interfaces: `PascalCase` with prefix (e.g., `IUserProps`, `TUserState`)

### Import Organization

```python
# Standard library
import os
from datetime import datetime
from typing import Optional, List

# Third-party
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Local - absolute imports only
from app.core.exceptions import ValidationError
from app.dao.user_dao import UserDAO
from app.schemas.user import UserCreate, UserResponse
```

### Security (OWASP Top 10)

All code must comply with OWASP Top 10:
- **A01: Broken Access Control** → RBAC + org-scoping on every endpoint
- **A02: Cryptographic Failures** → Encrypt sensitive data (Fernet for API keys)
- **A03: Injection** → Parameterized queries via SQLAlchemy ORM
- **A04: Insecure Design** → Security by design, ADRs include security review
- **A05: Security Misconfiguration** → Secure defaults, security headers
- **A06: Vulnerable Components** → Regular dependency updates
- **A07: Authentication Failures** → JWT with short expiration, bcrypt
- **A08: Software Integrity** → Webhook signature validation
- **A09: Security Logging** → Comprehensive audit logs
- **A10: SSRF** → Validate all external URLs

### Accessibility (WCAG 2.1 Level AA)

All UI must meet WCAG 2.1 Level AA:
- Semantic HTML with ARIA labels
- Keyboard navigation for all elements
- Screen reader compatibility
- Color contrast ratios (4.5:1 minimum)
- Focus indicators
- Form labels and error messages

---

## Workflow: Adding a New Feature

### Step 1: Create ADR
```bash
# Create ADR file
touch docs/adr/ADR-XXX-feature-name.md
```

Document:
- Context and problem
- Decision and rationale
- Implementation guide
- Security considerations

### Step 2: Architecture Review
- Architecture Agent reviews ADR
- Security Agent validates OWASP compliance
- ADR status updated to "Accepted"

### Step 3: TDD Implementation
```bash
# 1. Write failing tests first
pytest tests/unit/test_new_feature.py -v  # Should FAIL

# 2. Implement feature
# ... write code following ADR ...

# 3. Tests pass
pytest tests/unit/test_new_feature.py -v  # Should PASS

# 4. Refactor if needed (tests still pass)
```

### Step 4: Pair Review
- Implementation Agent completes feature
- Review Agent validates:
  - Tests cover requirements
  - Documentation complete (WHAT/WHY/HOW)
  - No stubs or TODOs
  - DAO pattern followed
  - Custom exceptions used
  - ADR followed

### Step 5: Integration
- Integration tests pass
- Code merged to main
- DevOps Agent handles deployment

---

## Common Patterns

### Adding a New Model

1. **Create ADR** for the model design
2. **Create SQLAlchemy model** in `app/models/`
3. **Create Pydantic schemas** in `app/schemas/`
4. **Create DAO** in `app/dao/`
5. **Generate migration**: `alembic revision --autogenerate -m "Add X model"`
6. **Write tests** in `tests/unit/dao/test_x_dao.py`
7. **Implement service** in `app/services/`

### Adding a New API Endpoint

1. **Create ADR** for the endpoint
2. **Write integration test** in `tests/integration/api/`
3. **Create router** in `app/api/`
4. **Add to main router** in `app/main.py`
5. **Document with OpenAPI** docstrings
6. **Add RBAC decorator**
7. **Implement service logic**
8. **Add audit logging**

---

## Development Commands

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Database
alembic upgrade head                    # Run migrations
alembic revision --autogenerate -m ""   # Create migration

# Testing (TDD)
pytest                                  # Run all tests
pytest --cov=app --cov-report=html     # With coverage
pytest -v tests/unit                   # Unit tests only
pytest -v tests/integration            # Integration tests

# Code quality
black app tests                        # Format
ruff check app tests                   # Lint
mypy app                              # Type check
```

### Frontend
```bash
cd frontend
npm install

npm run dev          # Development server
npm run build        # Production build
npm run lint         # ESLint
npm run type-check   # TypeScript
npm test             # Run tests
```

### Docker
```bash
docker-compose up -d                   # Start all services
docker-compose logs -f backend         # View logs
docker-compose exec backend pytest     # Run tests
docker-compose down -v                 # Stop and clean
```

---

## Architecture

### System Design Principles
1. **Microservice-Ready Monolith**: Design for future extraction
2. **Domain-Driven Design**: Clear bounded contexts
3. **API-First**: Backend exposes REST API
4. **Event-Driven**: Use events for cross-context communication

### Multi-Tenancy & RBAC
- **Organization-Based Tenancy**: All data scoped to `org_id`
- **Role-Based Access Control**:
  - `ADMIN`: Full access across all organizations
  - `CLIENT`: Access limited to their organization

### Data Flow
```
Request → Traefik (TLS) → FastAPI → JWT Validation → RBAC → DAO → PostgreSQL
```

---

## Kanban Board Structure

Master board: `docs/kanban/master-board.md`

Sub-boards:
- `docs/kanban/auth-security.md`
- `docs/kanban/billing-payments.md`
- `docs/kanban/workflows.md`
- `docs/kanban/client-portal.md`
- `docs/kanban/admin-portal.md`

**Priority Order:**
1. Core infrastructure & security
2. Authentication & authorization
3. Organization & user management
4. Project & proposal management
5. Billing & payments
6. n8n workflow integration
7. Ticketing system
8. Notifications
9. Admin tools & analytics

---

## Important Rules

1. **ADRs before implementation** - No code without accepted ADR
2. **Read existing code first** - Prevent parameter/import errors
3. **No stubs or TODOs** - Full implementation only
4. **Document WHAT/WHY/HOW** - Comprehensive docstrings
5. **Custom exceptions only** - Never throw/catch base Exception
6. **DAO pattern required** - No direct database queries in services
7. **TDD mandatory** - Tests before implementation
8. **Pair programming** - Two agents per task
9. **80% coverage minimum** - Enforced in CI
10. **Security review required** - OWASP compliance on all features

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [React Documentation](https://react.dev/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [n8n API Documentation](https://docs.n8n.io/api/)
