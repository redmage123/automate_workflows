# Development Framework - Automation Services Platform

## Overview

This document provides a high-level overview of the development framework, methodologies, and processes for the Automation Services Platform.

## Quick Links

- **CLAUDE.md**: Comprehensive development guidelines
- **Master Kanban Board**: `docs/kanban/master-board.md`
- **Specialized Agents**: `.claude/agents/`
- **Sub-boards**: `docs/kanban/`

## Development Methodology

### Agile + DevOps + TDD

We follow an **Agile** methodology with **DevOps** practices and strict **Test-Driven Development** (TDD):

1. **Sprint-based delivery**: 2-4 week sprints
2. **Planning Poker**: All features estimated using Fibonacci scale (1, 2, 3, 5, 8, 13, 21)
3. **Kanban boards**: Visual workflow management with priority-based execution
4. **Test-Driven Development**: Write tests BEFORE implementation (RED → GREEN → REFACTOR)
5. **Continuous Integration**: Automated testing, linting, security scanning on every PR
6. **Continuous Deployment**: Automated deployments to production on merge to main

### Code Standards (Non-Negotiable)

#### 1. DAO Pattern
**ALL** database operations must use the Data Access Object pattern:
- Create DAO classes in `app/dao/`
- Services call DAOs, never direct SQLAlchemy queries
- Ensures separation of concerns and testability

#### 2. Custom Exceptions
**NEVER** throw base `Exception` class:
- Define custom exceptions in `app/core/exceptions.py`
- Include HTTP status codes and contextual data
- Enables consistent error handling across API

#### 3. Documentation
**CRITICAL**: Document **WHY**, not just what:
- Every function must explain its purpose and rationale
- Include context: Why this approach vs alternatives?
- Example: "WHY: We use Fernet encryption because..."

#### 4. Test-Driven Development
**MANDATORY**: Tests before implementation:
- Write failing test (RED)
- Implement minimal code to pass (GREEN)
- Refactor while keeping tests green (REFACTOR)
- Minimum 80% code coverage

#### 5. Security (OWASP Top 10)
All code must comply with OWASP security standards:
- A01: Broken Access Control → RBAC + org-scoping
- A02: Cryptographic Failures → Encrypt sensitive data
- A03: Injection → Parameterized queries
- A07: Authentication Failures → Strong JWT + bcrypt
- *(See CLAUDE.md for full checklist)*

#### 6. Accessibility (WCAG 2.1 Level AA)
All UI must be accessible from day one:
- Semantic HTML with ARIA labels
- Keyboard navigation
- Screen reader compatible
- Color contrast ratios (4.5:1 minimum)
- *(See CLAUDE.md for full requirements)*

## Specialized Agent Framework

Development work is distributed across 5 specialized agents, each with domain expertise:

### 1. Architecture Agent (`.claude/agents/architecture.md`)
**Responsibilities:**
- System design and architectural decisions
- Design pattern selection
- Scalability planning
- Technology evaluation

**When to consult:**
- Designing new features or systems
- Choosing between architectural patterns
- Planning for scale or performance

### 2. Test Design Agent (`.claude/agents/test-design.md`)
**Responsibilities:**
- Test strategy and test plan creation
- Test case design
- Quality assurance standards
- TDD enforcement

**When to consult:**
- Before implementing any feature (write tests first!)
- Designing test coverage strategy
- Setting up testing infrastructure

### 3. Software Implementation Agent (`.claude/agents/implementation.md`)
**Responsibilities:**
- Code development following TDD
- DAO pattern implementation
- Comprehensive documentation
- Code refactoring

**When to consult:**
- Writing production code
- Implementing business logic
- Refactoring existing code

### 4. Cybersecurity Agent (`.claude/agents/security.md`)
**Responsibilities:**
- OWASP Top 10 compliance
- Security audits and vulnerability assessment
- Secure coding practices
- Penetration testing

**When to consult:**
- Before implementing auth/security features
- Reviewing code for security vulnerabilities
- Planning security testing

### 5. DevOps Agent (`.claude/agents/devops.md`)
**Responsibilities:**
- CI/CD pipeline management
- Infrastructure as code
- Deployment automation
- Monitoring and observability

**When to consult:**
- Setting up deployment pipelines
- Infrastructure changes
- Performance monitoring

## Kanban Board Structure

### Master Board (`docs/kanban/master-board.md`)
- **Total Scope**: 514 story points across 7 sprints
- **MVP Timeline**: 4-5 months
- **Current Sprint**: Sprint 1 (Foundation) - 48 points, 2 weeks

### Sub-Boards
1. `auth-security.md` - Authentication & security features
2. `billing-payments.md` - Stripe integration, invoicing
3. `workflows.md` - n8n integration features
4. `client-portal.md` - Client-facing features
5. `admin-portal.md` - Admin management features

### Priority Order (Must Follow)
1. **P0 - Critical**: Core infrastructure & security
2. **P1 - High**: Authentication & authorization
3. **P2 - High**: Project & proposal management
4. **P2 - Medium**: Billing & payments
5. **P2 - Medium**: n8n workflow integration
6. **P3 - Medium**: Ticketing & notifications
7. **P3 - Low**: Admin tools & analytics

## Development Workflow

### For Each New Feature:

1. **Planning** (Architecture Agent)
   - Add to Kanban board
   - Estimate with Planning Poker
   - Review architectural design
   - Document decisions

2. **Security Review** (Cybersecurity Agent)
   - Evaluate OWASP compliance
   - Identify security requirements
   - Plan security testing

3. **Test Design** (Test Design Agent)
   - Create test plan
   - Write test cases
   - Define acceptance criteria

4. **TDD Implementation** (Implementation Agent)
   - Write failing tests (RED)
   - Implement code (GREEN)
   - Refactor (REFACTOR)
   - Document WHY

5. **DevOps** (DevOps Agent)
   - Update CI/CD pipeline
   - Deploy to staging
   - Monitor metrics

6. **Review & Merge**
   - Code review
   - All quality gates pass
   - Merge to main
   - Auto-deploy to production

## Quality Gates

### Before Merging Any PR:
- [ ] All tests pass (unit + integration + e2e)
- [ ] Code coverage >= 80%
- [ ] No security vulnerabilities (Bandit, npm audit)
- [ ] No accessibility violations (axe)
- [ ] Type checking passes (mypy, TypeScript)
- [ ] Linting passes (ruff, ESLint)
- [ ] DAO pattern used (if database access)
- [ ] Custom exceptions (no base Exception)
- [ ] Comprehensive documentation (WHY included)
- [ ] Code review approved by relevant agents
- [ ] Security review completed (OWASP checklist)
- [ ] Accessibility review (WCAG checklist)

## Current Sprint (Sprint 1)

### Goals:
- Set up project infrastructure
- Implement core security foundation
- Establish development patterns

### This Week's Tasks:
1. ✅ Project structure created
2. ✅ CLAUDE.md documentation
3. ✅ Specialized agents created
4. ✅ Kanban boards created
5. ⏳ Docker Compose infrastructure
6. ⏳ PostgreSQL + Alembic migrations
7. ⏳ Custom exception hierarchy
8. ⏳ JWT authentication system

### Sprint 1 Deliverables (48 points):
- Docker Compose with Traefik, PostgreSQL, Redis, n8n
- Database models and migrations
- JWT authentication
- RBAC middleware
- Custom exception hierarchy
- OWASP security headers
- Test infrastructure
- CI/CD pipeline (GitHub Actions)

## Getting Started

### 1. Read Core Documentation
- **Start here**: `CLAUDE.md` - Complete development guidelines
- Review agent responsibilities in `.claude/agents/`
- Check current sprint in `docs/kanban/master-board.md`

### 2. Set Up Environment
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Frontend
cd frontend
npm install
```

### 3. Follow the Board
- Check `docs/kanban/master-board.md` for current sprint
- Pick highest priority task (top of TODO column)
- Follow agent workflows for implementation

### 4. Implement with TDD
- Consult Test Design agent for test plan
- Write tests FIRST
- Implement code to pass tests
- Refactor while keeping tests green

### 5. Submit for Review
- Create PR with comprehensive description
- Ensure all quality gates pass
- Request review from relevant agents
- Address feedback and merge

## Key Principles

1. **Security First**: OWASP compliance is non-negotiable
2. **Accessibility First**: WCAG compliance from day one
3. **Test-Driven**: No code without tests
4. **Document WHY**: Explain rationale, not just what
5. **DAO Pattern**: Separate data access from business logic
6. **Custom Exceptions**: Structured error handling
7. **Agent Collaboration**: Leverage specialized expertise
8. **Kanban Discipline**: Follow priority order
9. **Definition of Done**: Meet all quality gates
10. **Continuous Improvement**: Retrospectives and refinement

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)

---

**Note**: This is a living document. Update as the project evolves and new patterns emerge.
