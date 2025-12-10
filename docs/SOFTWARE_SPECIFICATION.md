# Software Specification Document
# Automation Services Platform

**Version:** 1.0
**Last Updated:** 2025-10-12
**Repository:** https://github.com/redmage123/automate
**Status:** Foundation Phase

---

## Table of Contents

1. [Use Case](#use-case)
2. [Problem Statement](#problem-statement)
3. [High-Level Solution](#high-level-solution)
4. [Functional Specifications](#functional-specifications)
5. [Non-Functional Specifications](#non-functional-specifications)
6. [Architecture](#architecture)
7. [Technology Stack](#technology-stack)
8. [Security & Compliance](#security--compliance)
9. [Development Methodology](#development-methodology)
10. [Glossary](#glossary)

---

## Use Case

### Primary Use Case: Automation Services Provider Platform

**Actor:** Small-to-medium automation services business owner/operator

**Goal:** Provide a comprehensive platform to manage the entire client lifecycle for automation services, from onboarding to project delivery, billing, and ongoing support.

**Scenario:**

1. **Client Onboarding**: A new client discovers the automation services business and fills out an onboarding form detailing their automation needs
2. **Proposal Generation**: The service provider reviews the requirements and generates a professional proposal with pricing
3. **Payment Processing**: Client approves the proposal and makes payment via Stripe integration
4. **Project Management**: Service provider creates a project, assigns workflows, and tracks progress
5. **Workflow Automation**: n8n workflows are provisioned and executed for the client's automation needs
6. **Ongoing Support**: Client submits support tickets, receives notifications, and tracks project status
7. **Administration**: Service provider manages multiple client organizations, monitors analytics, and maintains the platform

**Value Proposition:**
- **For Service Providers**: Streamlined operations, automated billing, centralized workflow management
- **For Clients**: Transparent project tracking, professional proposals, self-service support portal
- **For Both**: Secure multi-tenant platform with role-based access control

---

## Problem Statement

### Business Problem

Automation services providers face multiple operational challenges:

1. **Fragmented Tooling**: Client onboarding, project management, billing, and automation workflows exist in separate, disconnected tools
2. **Manual Processes**: Proposal generation, invoice creation, and workflow provisioning require significant manual effort
3. **Lack of Client Visibility**: Clients have no self-service portal to track project status, submit tickets, or view invoices
4. **Security Concerns**: Managing multiple client organizations requires robust access controls and data isolation
5. **Scalability Issues**: As the business grows, manual processes become bottlenecks
6. **Compliance Requirements**: OWASP security standards and WCAG accessibility compliance are critical but often neglected

### Technical Problem

Existing solutions fail to address automation service providers' unique needs:

- **Generic Project Management Tools**: Lack automation workflow integration and billing capabilities
- **Automation Platforms (n8n, Zapier)**: Don't include client management or billing features
- **Invoicing Software**: No project tracking or automation capabilities
- **Custom Solutions**: High development cost, maintenance burden, and technical debt

### Gap Analysis

| Need | Existing Solutions | Gap |
|------|-------------------|-----|
| Client onboarding + proposals | Separate tools (Google Forms + Word) | No integration, manual data entry |
| Payment processing | Stripe dashboard | No connection to projects/proposals |
| Workflow management | n8n standalone | No multi-tenant support, no client portal |
| Support ticketing | Email or separate helpdesk | No project context, no SLA tracking |
| Multi-tenancy | Build from scratch | No standardized solution |

---

## High-Level Solution

### Solution Overview

The **Automation Services Platform** is a full-stack, multi-tenant SaaS application that unifies client management, project tracking, proposal generation, payment processing, workflow automation, and support ticketing into a single, secure platform.

### Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Browser                          │
│                      (Next.js 14 Frontend)                      │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │ HTTPS (Traefik Reverse Proxy)
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                    FastAPI Backend (Python 3.11+)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │     API      │  │   Services   │  │     DAOs     │          │
│  │  Endpoints   │─▶│  (Business   │─▶│  (Database   │          │
│  │              │  │    Logic)    │  │    Access)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┬──────────────┐
        │               │               │              │
        ▼               ▼               ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌─────────┐ ┌──────────────┐
│  PostgreSQL  │ │    Redis     │ │ Stripe  │ │     n8n      │
│  (Database)  │ │  (Sessions,  │ │  (Pay-  │ │  (Workflow   │
│              │ │   Queues)    │ │  ments) │ │  Automation) │
└──────────────┘ └──────────────┘ └─────────┘ └──────────────┘
```

### Key Differentiators

1. **Integrated Workflow Management**: Native n8n integration with multi-tenant support
2. **End-to-End Client Lifecycle**: Onboarding → Proposal → Payment → Delivery → Support
3. **Security by Design**: OWASP Top 10 compliance, RBAC, organization-level data isolation
4. **Accessibility First**: WCAG 2.1 Level AA compliance from day one
5. **Developer-Friendly**: DAO pattern, comprehensive documentation, TDD methodology
6. **Future-Proof**: Microservice architecture with Rust services planned for high-performance components

---

## Functional Specifications

### F1. Authentication & Authorization

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F1.1 | User Registration | Email-based registration with email verification | P0 |
| F1.2 | User Login | JWT-based authentication with bcrypt password hashing | P0 |
| F1.3 | OAuth Integration | Google OAuth for SSO (future: SAML/OIDC) | P1 |
| F1.4 | Role-Based Access Control | Two roles: ADMIN (service provider) and CLIENT | P0 |
| F1.5 | Organization Scoping | Multi-tenant data isolation at database level | P0 |
| F1.6 | Session Management | Token refresh, logout, session expiration | P0 |
| F1.7 | Password Reset | Email-based password reset flow | P1 |
| F1.8 | Audit Logging | Log all authentication and authorization events | P0 |

### F2. Client Onboarding

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F2.1 | Onboarding Form | Multi-step form capturing client needs and requirements | P2 |
| F2.2 | Organization Creation | Automatically create organization for new clients | P2 |
| F2.3 | Project Initialization | Create initial project from onboarding data | P2 |
| F2.4 | Notification | Notify admin of new onboarding submissions | P2 |

### F3. Project Management

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F3.1 | Create Project | ADMIN creates projects for client organizations | P2 |
| F3.2 | List Projects | View all projects (org-scoped for CLIENT, all for ADMIN) | P2 |
| F3.3 | Project Details | View project details, status, associated workflows | P2 |
| F3.4 | Update Project Status | Change project status (Draft, In Progress, Completed, etc.) | P2 |
| F3.5 | Project Kanban View | Visual kanban board for project workflow | P2 |
| F3.6 | Project Search/Filter | Filter projects by status, organization, date range | P3 |

### F4. Proposals & Agreements

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F4.1 | Create Proposal | Generate proposal with line items, pricing, terms | P2 |
| F4.2 | Proposal Templates | Reusable proposal templates for common services | P3 |
| F4.3 | Proposal PDF Generation | Export proposal as PDF (WeasyPrint) | P2 |
| F4.4 | Proposal Approval | CLIENT can approve or reject proposals | P2 |
| F4.5 | E-Signature | Electronic signature capture for approved proposals | P3 |
| F4.6 | Proposal Versioning | Track proposal revisions and history | P3 |

### F5. Billing & Payments

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F5.1 | Stripe Integration | Stripe Checkout for payment processing | P2 |
| F5.2 | Invoice Generation | Auto-generate invoices on payment success | P2 |
| F5.3 | Invoice PDF | PDF export of invoices | P2 |
| F5.4 | Stripe Webhooks | Handle payment confirmation, refunds, disputes | P2 |
| F5.5 | Subscription Management | Recurring billing for ongoing services | P2 |
| F5.6 | Payment History | View all payments and invoices | P3 |
| F5.7 | Refund Processing | ADMIN can issue refunds via Stripe | P3 |

### F6. Workflow Automation (n8n Integration)

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F6.1 | n8n Environment Setup | ADMIN configures n8n instance(s) with encrypted credentials | P2 |
| F6.2 | Workflow Template Library | Pre-built workflow templates for common automations | P2 |
| F6.3 | Create Workflow Instance | Provision workflow from template for specific project | P2 |
| F6.4 | Trigger Workflow Execution | Manually or automatically trigger workflows | P2 |
| F6.5 | Execution Logs | View workflow execution history and results | P2 |
| F6.6 | Webhook Receiver | Receive webhook callbacks from n8n workflows | P2 |
| F6.7 | Multi-n8n Support | Support multiple n8n instances for different tiers | P3 |
| F6.8 | Workflow Budget Limits | Set execution limits per organization | P3 |

### F7. Support Ticketing

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F7.1 | Create Ticket | CLIENT and ADMIN can create support tickets | P3 |
| F7.2 | List Tickets | View all tickets (org-scoped for CLIENT) | P3 |
| F7.3 | Ticket Details | View ticket history, comments, attachments | P3 |
| F7.4 | Update Ticket Status | Open, In Progress, Resolved, Closed | P3 |
| F7.5 | SLA Tracking | Track response and resolution SLAs | P3 |
| F7.6 | SLA Breach Alerts | Notify ADMIN when SLA is about to breach | P3 |
| F7.7 | Ticket Comments | Threaded comments on tickets | P3 |

### F8. Notifications

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F8.1 | Email Notifications | Send email via Resend service | P3 |
| F8.2 | Email Templates | HTML email templates for common events | P3 |
| F8.3 | Slack Webhooks | Send notifications to Slack channels | P3 |
| F8.4 | Notification Preferences | User-configurable notification settings | P3 |
| F8.5 | Event Notifications | Notify on project updates, payments, SLA breaches | P3 |

### F9. Admin Portal

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F9.1 | Admin Dashboard | Overview of system health, recent activity | P3 |
| F9.2 | User Management | CRUD operations on users | P3 |
| F9.3 | Organization Management | CRUD operations on organizations | P3 |
| F9.4 | Audit Log Viewer | View all audit logs with filtering | P3 |
| F9.5 | System Metrics | Analytics on projects, revenue, user activity | P3 |
| F9.6 | n8n Environment Management | Configure n8n instances and credentials | P2 |

### F10. Client Portal

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F10.1 | Client Dashboard | View active projects, recent invoices, tickets | P2 |
| F10.2 | Project Tracking | View project status and progress | P2 |
| F10.3 | Invoice Access | View and download invoices | P2 |
| F10.4 | Ticket Management | Create and track support tickets | P3 |
| F10.5 | Organization Settings | Update organization details | P2 |

---

## Non-Functional Specifications

### NF1. Performance

| ID | Requirement | Specification | Measurement |
|----|-------------|---------------|-------------|
| NF1.1 | API Response Time | < 200ms for 95th percentile | Prometheus metrics |
| NF1.2 | Page Load Time | < 2s for initial load (LCP) | Web Vitals |
| NF1.3 | Database Query Performance | < 100ms for 99th percentile | APM tracing |
| NF1.4 | Concurrent Users | Support 1,000 concurrent users initially | Load testing |
| NF1.5 | Throughput | Handle 10,000 requests/minute | Load testing |

### NF2. Scalability

| ID | Requirement | Specification | Measurement |
|----|-------------|---------------|-------------|
| NF2.1 | Horizontal Scaling | Backend services stateless, horizontally scalable | Architecture review |
| NF2.2 | Database Scaling | PostgreSQL read replicas for read-heavy operations | Infrastructure |
| NF2.3 | Caching | Redis caching for frequently accessed data | Cache hit rate |
| NF2.4 | Background Jobs | Dramatiq workers for async tasks (scaling independently) | Worker count |
| NF2.5 | Multi-Tenancy | Support 10,000+ organizations on single instance | Database design |

### NF3. Security (OWASP Top 10 Compliance)

| ID | Requirement | Specification | Validation |
|----|-------------|---------------|------------|
| NF3.1 | Access Control (A01) | RBAC with org-scoping at DAO level | Security audit |
| NF3.2 | Cryptographic Failures (A02) | Fernet encryption for sensitive data, bcrypt for passwords | Code review |
| NF3.3 | Injection (A03) | Parameterized queries, input validation (Pydantic) | SAST scanning |
| NF3.4 | Insecure Design (A04) | Security-first architecture, threat modeling | Architecture review |
| NF3.5 | Security Misconfiguration (A05) | Security headers (HSTS, CSP, X-Frame-Options) | Security scanner |
| NF3.6 | Vulnerable Components (A06) | Automated dependency scanning (Bandit, npm audit) | CI/CD pipeline |
| NF3.7 | Authentication Failures (A07) | JWT with short expiration, rate limiting on login | Penetration testing |
| NF3.8 | Software Integrity (A08) | Webhook signature verification (Stripe, n8n) | Integration tests |
| NF3.9 | Logging Failures (A09) | Comprehensive audit logging to Sentry | Log analysis |
| NF3.10 | SSRF (A10) | Allowlist for external API calls | Code review |

### NF4. Reliability

| ID | Requirement | Specification | Measurement |
|----|-------------|---------------|-------------|
| NF4.1 | Uptime | 99.9% uptime (< 8.76 hours downtime/year) | Monitoring |
| NF4.2 | Error Rate | < 0.1% error rate | APM metrics |
| NF4.3 | Data Backup | Daily PostgreSQL backups, 30-day retention | Backup verification |
| NF4.4 | Disaster Recovery | RPO < 24 hours, RTO < 4 hours | DR testing |
| NF4.5 | Health Checks | Health endpoints for all services | Monitoring |

### NF5. Accessibility (WCAG 2.1 Level AA)

| ID | Requirement | Specification | Validation |
|----|-------------|---------------|------------|
| NF5.1 | Keyboard Navigation | All interactive elements keyboard-accessible | Manual testing |
| NF5.2 | Screen Reader Support | Semantic HTML with ARIA labels | Screen reader testing |
| NF5.3 | Color Contrast | 4.5:1 contrast ratio for text | axe-core automation |
| NF5.4 | Focus Indicators | Visible focus indicators on all interactive elements | Visual inspection |
| NF5.5 | Form Accessibility | Labels, error messages, validation feedback | axe-core automation |
| NF5.6 | Alternative Text | Alt text for all images | Content audit |

### NF6. Maintainability

| ID | Requirement | Specification | Validation |
|----|-------------|---------------|------------|
| NF6.1 | Code Coverage | ≥ 80% test coverage | pytest/Jest reports |
| NF6.2 | Documentation | All functions documented with WHY explanations | Code review |
| NF6.3 | DAO Pattern | All database operations via DAOs | Architecture review |
| NF6.4 | Custom Exceptions | No base Exception usage | Linting rules |
| NF6.5 | Type Safety | Full type hints (Python), TypeScript (frontend) | mypy/tsc |
| NF6.6 | Code Quality | Linting passes (ruff, ESLint) | CI/CD pipeline |

### NF7. Usability

| ID | Requirement | Specification | Measurement |
|----|-------------|---------------|-------------|
| NF7.1 | Responsive Design | Mobile-friendly (320px+) | Device testing |
| NF7.2 | Loading States | Clear loading indicators for async operations | UX review |
| NF7.3 | Error Handling | User-friendly error messages | UX review |
| NF7.4 | Toast Notifications | Non-intrusive success/error notifications | UX review |
| NF7.5 | Onboarding | Clear user onboarding flow | User testing |

### NF8. Observability

| ID | Requirement | Specification | Validation |
|----|-------------|---------------|------------|
| NF8.1 | Structured Logging | JSON logs with request IDs | Log analysis |
| NF8.2 | Error Tracking | Sentry integration for error monitoring | Incident response |
| NF8.3 | Metrics | Prometheus metrics for all services | Dashboard review |
| NF8.4 | Tracing | OpenTelemetry tracing for request flows | APM review |
| NF8.5 | Alerting | Alerts for critical errors, performance degradation | On-call rotation |

### NF9. Deployment

| ID | Requirement | Specification | Validation |
|----|-------------|---------------|------------|
| NF9.1 | CI/CD | GitHub Actions for automated testing and deployment | Pipeline execution |
| NF9.2 | Containerization | Docker containers for all services | Docker Compose |
| NF9.3 | Zero-Downtime | Rolling deployments with health checks | Deployment testing |
| NF9.4 | Infrastructure as Code | Docker Compose for local/production parity | IaC review |
| NF9.5 | SSL/TLS | HTTPS everywhere via Traefik + Let's Encrypt | Security scan |

### NF10. Compliance

| ID | Requirement | Specification | Validation |
|----|-------------|---------------|------------|
| NF10.1 | GDPR | Data export, deletion, consent management (future) | Legal review |
| NF10.2 | PCI DSS | Payment data handled by Stripe (no card storage) | Compliance audit |
| NF10.3 | OWASP Top 10 | Compliance with all OWASP Top 10 categories | Security audit |
| NF10.4 | WCAG 2.1 AA | Full accessibility compliance | Accessibility audit |

---

## Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                              │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      Next.js 14 Frontend (SPA)                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │  │
│  │  │   Client    │  │    Admin    │  │  Auth UI    │  │  Components │ │  │
│  │  │   Portal    │  │   Portal    │  │  (NextAuth) │  │  (shadcn)   │ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ HTTPS / WebSocket
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                              REVERSE PROXY LAYER                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │           Traefik (Load Balancer, SSL Termination, Routing)          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
                ▼                 ▼                 ▼
┌───────────────────────┐ ┌───────────────┐ ┌─────────────────────┐
│   BACKEND SERVICE     │ │  WORKER POOL  │ │   n8n INSTANCE      │
│   (FastAPI)           │ │  (Dramatiq)   │ │   (Workflows)       │
│                       │ │               │ │                     │
│ ┌─────────────────┐   │ │ ┌───────────┐ │ │ ┌─────────────────┐ │
│ │   API Routes    │   │ │ │  SLA Job  │ │ │ │  Workflow Exec  │ │
│ │  /auth, /api/*  │   │ │ │  Email    │ │ │ │  Webhook Recv   │ │
│ └────────┬────────┘   │ │ │  Notif    │ │ │ └─────────────────┘ │
│          │            │ │ └───────────┘ │ │                     │
│ ┌────────▼────────┐   │ └───────┬───────┘ └─────────────────────┘
│ │  Middleware     │   │         │
│ │  - CORS         │   │         │
│ │  - Auth         │   │         │
│ │  - RBAC         │   │         │
│ │  - Audit Log    │   │         │
│ └────────┬────────┘   │         │
│          │            │         │
│ ┌────────▼────────┐   │         │
│ │    Services     │   │         │
│ │  - AuthService  │   │         │
│ │  - ProjectServ  │   │         │
│ │  - BillingServ  │   │         │
│ │  - WorkflowServ │   │         │
│ └────────┬────────┘   │         │
│          │            │         │
│ ┌────────▼────────┐   │         │
│ │      DAOs       │   │         │
│ │  - UserDAO      │   │         │
│ │  - ProjectDAO   │   │         │
│ │  - InvoiceDAO   │   │         │
│ │  - WorkflowDAO  │   │         │
│ └────────┬────────┘   │         │
│          │            │         │
└──────────┼────────────┘         │
           │                      │
           │    ┌─────────────────┼─────────────────┐
           │    │                 │                 │
           ▼    ▼                 ▼                 ▼
┌─────────────────────┐ ┌─────────────────┐ ┌──────────────────┐
│   PostgreSQL 15     │ │    Redis 7      │ │   External APIs  │
│   - User data       │ │  - Sessions     │ │  - Stripe        │
│   - Projects        │ │  - Token cache  │ │  - Resend (email)│
│   - Invoices        │ │  - Job queue    │ │  - Slack         │
│   - Workflows       │ │  - Rate limit   │ │                  │
│   - Audit logs      │ │                 │ │                  │
└─────────────────────┘ └─────────────────┘ └──────────────────┘
```

### Data Flow: Client Onboarding → Payment

```
┌───────────┐
│  CLIENT   │
│  Browser  │
└─────┬─────┘
      │
      │ 1. Submit Onboarding Form
      ▼
┌─────────────────────┐
│   Next.js Frontend  │
│  - Form validation  │
│  - POST /api/       │
│    onboarding       │
└─────┬───────────────┘
      │
      │ 2. Create Organization + Project
      ▼
┌─────────────────────────────────────────┐
│        FastAPI Backend                  │
│  ┌───────────────────────────────────┐  │
│  │  OnboardingService                │  │
│  │  - Create Organization            │  │
│  │  - Create Project                 │  │
│  │  - Send notification to ADMIN     │  │
│  └──────┬────────────────────────────┘  │
│         │                               │
│         ▼                               │
│  ┌─────────────────┐                   │
│  │  OrganizationDAO│                   │
│  │  ProjectDAO     │                   │
│  └──────┬──────────┘                   │
└─────────┼───────────────────────────────┘
          │
          ▼
    ┌──────────┐
    │PostgreSQL│
    └──────────┘

    [ADMIN reviews and creates proposal]

┌────────┐
│ ADMIN  │
└───┬────┘
    │
    │ 3. Create Proposal
    ▼
┌─────────────────────┐
│  Backend            │
│  - ProposalService  │
│  - Generate PDF     │
│  - Notify CLIENT    │
└──────┬──────────────┘
       │
       ▼
    ┌──────────┐
    │PostgreSQL│
    └──────────┘

    [CLIENT reviews and approves]

┌───────────┐
│  CLIENT   │
└─────┬─────┘
      │
      │ 4. Approve Proposal → Redirect to Stripe Checkout
      ▼
┌─────────────────────┐
│  Backend            │
│  - Create Stripe    │
│    Checkout Session │
│  - Return URL       │
└──────┬──────────────┘
       │
       │ 5. Redirect to Stripe
       ▼
┌──────────────┐
│   Stripe     │
│   Checkout   │
└──────┬───────┘
       │
       │ 6. Payment success → Webhook
       ▼
┌─────────────────────────────┐
│  Backend Webhook Handler    │
│  - Verify signature         │
│  - Create Invoice           │
│  - Update Proposal status   │
│  - Send confirmation email  │
└──────┬──────────────────────┘
       │
       ▼
    ┌──────────┐
    │PostgreSQL│
    └──────────┘
```

### Multi-Tenancy Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                         REQUEST FLOW                          │
└───────────────────────────────────────────────────────────────┘

  CLIENT Request: GET /api/projects
  Authorization: Bearer <JWT_TOKEN>

           │
           ▼
┌──────────────────────────┐
│  Auth Middleware         │
│  - Decode JWT            │
│  - Extract user_id       │
│  - Extract org_id        │
│  - Extract role          │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  RBAC Middleware         │
│  - Verify role           │
│  - Check permissions     │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  ProjectService          │
│  - Get projects          │
│  - Pass org_id from JWT  │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  ProjectDAO                              │
│  - Apply org_id filter automatically     │
│  - SELECT * FROM projects                │
│    WHERE org_id = <from_jwt>             │
│  - NEVER trust client-provided org_id    │
└──────────┬───────────────────────────────┘
           │
           ▼
┌──────────────────────────┐
│  PostgreSQL              │
│  - All multi-tenant      │
│    tables have org_id    │
│  - Indexes on org_id     │
│  - Row-level security    │
│    (future: RLS policies)│
└──────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                      DATA ISOLATION                           │
└───────────────────────────────────────────────────────────────┘

Organization 1 (org_id=1)          Organization 2 (org_id=2)
┌────────────────────┐             ┌────────────────────┐
│ Projects:          │             │ Projects:          │
│  - Project A       │             │  - Project X       │
│  - Project B       │             │  - Project Y       │
│                    │             │                    │
│ Users:             │             │ Users:             │
│  - user@org1.com   │             │  - user@org2.com   │
│                    │             │                    │
│ Invoices:          │             │ Invoices:          │
│  - Invoice #001    │             │  - Invoice #001    │
│  - Invoice #002    │             │  - Invoice #002    │
└────────────────────┘             └────────────────────┘

    ❌ No cross-org access
    ✅ ADMIN can query all orgs (role-based)
    ✅ CLIENT can only query their org
    ✅ Enforced at DAO level (defense in depth)
```

### Security Architecture (OWASP Compliance)

```
┌───────────────────────────────────────────────────────────────────┐
│                   SECURITY LAYERS (Defense in Depth)              │
└───────────────────────────────────────────────────────────────────┘

Layer 1: Network Security
┌─────────────────────────────────────────────────────────────┐
│  Traefik                                                     │
│  ✅ SSL/TLS (Let's Encrypt)                                  │
│  ✅ Rate limiting (5 req/s per IP on auth endpoints)        │
│  ✅ DDoS protection                                          │
└─────────────────────────────────────────────────────────────┘

Layer 2: Application Security
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Middleware                                          │
│  ✅ CORS (allowlist origins)                                 │
│  ✅ Security headers (HSTS, CSP, X-Frame-Options)           │
│  ✅ Request validation (Pydantic schemas)                   │
│  ✅ Input sanitization                                       │
└─────────────────────────────────────────────────────────────┘

Layer 3: Authentication & Authorization
┌─────────────────────────────────────────────────────────────┐
│  Auth System                                                 │
│  ✅ JWT with HS256 (future: RS256)                           │
│  ✅ 24-hour token expiration                                 │
│  ✅ Refresh token rotation                                   │
│  ✅ Token blacklist (logout)                                 │
│  ✅ RBAC (ADMIN/CLIENT roles)                                │
│  ✅ Password hashing (bcrypt, cost factor 12)               │
└─────────────────────────────────────────────────────────────┘

Layer 4: Business Logic Security
┌─────────────────────────────────────────────────────────────┐
│  Services                                                    │
│  ✅ Organization-scoped operations                           │
│  ✅ Authorization checks before operations                   │
│  ✅ Custom exceptions (no sensitive data leaks)             │
└─────────────────────────────────────────────────────────────┘

Layer 5: Data Access Security
┌─────────────────────────────────────────────────────────────┐
│  DAOs                                                        │
│  ✅ Parameterized queries (SQL injection prevention)        │
│  ✅ Automatic org_id filtering                               │
│  ✅ No raw SQL (SQLAlchemy ORM)                             │
└─────────────────────────────────────────────────────────────┘

Layer 6: Data Security
┌─────────────────────────────────────────────────────────────┐
│  Database & Encryption                                       │
│  ✅ Fernet encryption for sensitive data (n8n API keys)     │
│  ✅ Database backups encrypted at rest                      │
│  ✅ SSL connections to PostgreSQL                           │
└─────────────────────────────────────────────────────────────┘

Layer 7: Monitoring & Audit
┌─────────────────────────────────────────────────────────────┐
│  Observability                                               │
│  ✅ Audit logging (all auth/authz events)                   │
│  ✅ Error tracking (Sentry)                                  │
│  ✅ Structured logging (JSON logs)                          │
│  ✅ Security alerts (failed logins, permission denials)     │
└─────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│                    OWASP TOP 10 MAPPING                           │
└───────────────────────────────────────────────────────────────────┘

A01: Broken Access Control
  → RBAC middleware, org-scoping at DAO level, audit logging

A02: Cryptographic Failures
  → Fernet encryption, bcrypt password hashing, HTTPS everywhere

A03: Injection
  → SQLAlchemy ORM, parameterized queries, Pydantic validation

A04: Insecure Design
  → Threat modeling, security reviews, custom exception hierarchy

A05: Security Misconfiguration
  → Security headers, secure defaults, dependency scanning

A06: Vulnerable and Outdated Components
  → Automated scanning (Bandit, npm audit), dependency updates

A07: Identification and Authentication Failures
  → JWT with expiration, bcrypt, rate limiting, token blacklist

A08: Software and Data Integrity Failures
  → Webhook signature verification (Stripe, n8n), CI/CD integrity

A09: Security Logging and Monitoring Failures
  → Comprehensive audit logs, Sentry integration, alerting

A10: Server-Side Request Forgery (SSRF)
  → Allowlist for external APIs, URL validation
```

### Database Schema (Simplified)

```sql
-- Multi-tenant architecture: All tables have org_id for isolation

CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    org_id INTEGER REFERENCES organizations(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('ADMIN', 'CLIENT')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_users_org_id (org_id),
    INDEX idx_users_email (email)
);

CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    org_id INTEGER REFERENCES organizations(id) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_projects_org_id (org_id),
    INDEX idx_projects_status (status)
);

CREATE TABLE proposals (
    id SERIAL PRIMARY KEY,
    org_id INTEGER REFERENCES organizations(id) NOT NULL,
    project_id INTEGER REFERENCES projects(id) NOT NULL,
    title VARCHAR(255) NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    approved_at TIMESTAMP,
    pdf_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_proposals_org_id (org_id),
    INDEX idx_proposals_project_id (project_id)
);

CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    org_id INTEGER REFERENCES organizations(id) NOT NULL,
    proposal_id INTEGER REFERENCES proposals(id),
    stripe_payment_intent_id VARCHAR(255),
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    paid_at TIMESTAMP,
    pdf_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_invoices_org_id (org_id),
    INDEX idx_invoices_stripe_id (stripe_payment_intent_id)
);

CREATE TABLE n8n_environments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    api_url VARCHAR(500) NOT NULL,
    api_key_encrypted TEXT NOT NULL,  -- Fernet encrypted
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE workflow_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    n8n_workflow_id VARCHAR(255),
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE workflow_instances (
    id SERIAL PRIMARY KEY,
    org_id INTEGER REFERENCES organizations(id) NOT NULL,
    project_id INTEGER REFERENCES projects(id) NOT NULL,
    template_id INTEGER REFERENCES workflow_templates(id),
    n8n_environment_id INTEGER REFERENCES n8n_environments(id),
    n8n_workflow_id VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_workflow_instances_org_id (org_id),
    INDEX idx_workflow_instances_project_id (project_id)
);

CREATE TABLE execution_logs (
    id SERIAL PRIMARY KEY,
    org_id INTEGER REFERENCES organizations(id) NOT NULL,
    workflow_instance_id INTEGER REFERENCES workflow_instances(id) NOT NULL,
    n8n_execution_id VARCHAR(255),
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_execution_logs_org_id (org_id),
    INDEX idx_execution_logs_workflow_id (workflow_instance_id)
);

CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    org_id INTEGER REFERENCES organizations(id) NOT NULL,
    project_id INTEGER REFERENCES projects(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    priority VARCHAR(50) NOT NULL DEFAULT 'MEDIUM',
    sla_due_at TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_tickets_org_id (org_id),
    INDEX idx_tickets_project_id (project_id),
    INDEX idx_tickets_status (status)
);

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    org_id INTEGER REFERENCES organizations(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id INTEGER,
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_audit_logs_user_id (user_id),
    INDEX idx_audit_logs_org_id (org_id),
    INDEX idx_audit_logs_action (action),
    INDEX idx_audit_logs_created_at (created_at)
);
```

---

## Technology Stack

### Backend

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Language | Python | 3.11+ | Async/await support, type hints, modern features |
| Framework | FastAPI | 0.109+ | High performance, auto-documentation, Pydantic integration |
| ORM | SQLAlchemy | 2.0+ | Async support, powerful query API, migration support |
| Database | PostgreSQL | 15+ | ACID compliance, JSONB support, mature ecosystem |
| Cache | Redis | 7+ | Fast in-memory store for sessions, queues, rate limiting |
| Migrations | Alembic | 1.13+ | Database migration management |
| Auth | python-jose | 3.3+ | JWT encoding/decoding with cryptography support |
| Password Hashing | bcrypt | 4.1+ | Industry-standard password hashing |
| Encryption | cryptography (Fernet) | 41+ | Symmetric encryption for sensitive data |
| Validation | Pydantic | 2.5+ | Data validation and settings management |
| Background Jobs | Dramatiq | 1.16+ | Distributed task processing with Redis |
| HTTP Client | httpx | 0.26+ | Async HTTP client for external APIs |
| Testing | pytest | 7.4+ | Feature-rich testing framework |
| Linting | ruff | 0.1+ | Fast Python linter |
| Type Checking | mypy | 1.8+ | Static type checking |

### Frontend

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Framework | Next.js | 14+ | App Router, SSR, performance optimizations |
| Language | TypeScript | 5.3+ | Type safety, better developer experience |
| Styling | Tailwind CSS | 3.4+ | Utility-first CSS framework |
| UI Components | shadcn/ui | Latest | Accessible, customizable components (Radix UI) |
| Auth | NextAuth.js | 5+ | Authentication for Next.js |
| Forms | React Hook Form | 7.49+ | Performant form validation |
| Validation | Zod | 3.22+ | TypeScript-first schema validation |
| HTTP Client | Axios | 1.6+ | Promise-based HTTP client |
| Testing | Jest | 29+ | JavaScript testing framework |
| Testing | React Testing Library | 14+ | Component testing |
| Accessibility Testing | axe-core | 4.8+ | Automated accessibility testing |
| Linting | ESLint | 8+ | JavaScript/TypeScript linting |

### Infrastructure

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Containerization | Docker | 24+ | Consistent environments, easy deployment |
| Orchestration | Docker Compose | 2.23+ | Multi-container management (local/production) |
| Reverse Proxy | Traefik | 2.10+ | Automatic SSL, load balancing, service discovery |
| Workflow Automation | n8n | Latest | Self-hosted workflow automation platform |
| Payment Processing | Stripe | Latest | Industry-standard payment platform |
| Email Service | Resend | Latest | Developer-friendly email API |
| Error Tracking | Sentry | Latest | Error monitoring and performance tracking |
| Observability | OpenTelemetry | Latest | Distributed tracing and metrics |

### Future Enhancements (Post-MVP)

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Webhook Gateway | Rust (Axum) | High performance, low latency for webhook processing |
| Secrets Proxy | Rust (Axum) | Secure credential management with minimal attack surface |
| Monitoring | Grafana | Visualization for Prometheus metrics |
| Message Queue | RabbitMQ | More robust queuing for high-volume workflows |

---

## Security & Compliance

### OWASP Top 10 Implementation Checklist

#### A01: Broken Access Control
- [x] JWT-based authentication with role verification
- [x] RBAC middleware (ADMIN vs CLIENT roles)
- [x] Organization-scoped queries at DAO level
- [x] Authorization checks in service layer
- [x] Audit logging for all access control decisions
- [ ] Future: Row-level security (RLS) in PostgreSQL

#### A02: Cryptographic Failures
- [x] HTTPS everywhere (Traefik + Let's Encrypt)
- [x] Bcrypt for password hashing (cost factor 12)
- [x] Fernet encryption for sensitive data (n8n API keys)
- [x] Secure JWT secret (min 32 chars, env variable)
- [x] SSL/TLS for database connections
- [ ] Future: Hardware Security Module (HSM) for key storage

#### A03: Injection
- [x] SQLAlchemy ORM (no raw SQL)
- [x] Parameterized queries
- [x] Pydantic input validation on all endpoints
- [x] Input sanitization
- [x] SAST scanning (Bandit)

#### A04: Insecure Design
- [x] Threat modeling during architecture phase
- [x] Security reviews by specialized agent
- [x] Custom exception hierarchy (no sensitive data leaks)
- [x] Fail-safe defaults (deny by default)
- [x] Defense in depth (multiple security layers)

#### A05: Security Misconfiguration
- [x] Security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)
- [x] Secure defaults in configuration
- [x] Environment variables for secrets (never hardcoded)
- [x] Dependency scanning (Bandit, npm audit)
- [x] Docker image scanning

#### A06: Vulnerable and Outdated Components
- [x] Automated dependency scanning in CI/CD
- [x] Regular dependency updates (Dependabot)
- [x] Pinned versions in requirements files
- [x] Security advisories monitoring

#### A07: Identification and Authentication Failures
- [x] JWT with short expiration (24 hours)
- [x] Token refresh mechanism
- [x] Token blacklist for logout (Redis)
- [x] Rate limiting on login endpoints (5 req/min per IP)
- [x] Bcrypt password hashing
- [ ] Future: Multi-factor authentication (MFA)
- [ ] Future: OAuth 2.0 / OIDC for SSO

#### A08: Software and Data Integrity Failures
- [x] Webhook signature verification (Stripe)
- [x] Webhook signature verification (n8n)
- [x] CI/CD pipeline integrity (GitHub Actions)
- [x] Docker image signing (future)

#### A09: Security Logging and Monitoring Failures
- [x] Comprehensive audit logging (all auth/authz events)
- [x] Structured logging (JSON format)
- [x] Sentry integration for error tracking
- [x] Log retention policy (30 days)
- [x] Alerting on security events

#### A10: Server-Side Request Forgery (SSRF)
- [x] Allowlist for external API calls
- [x] URL validation before requests
- [x] No user-controlled URLs without validation

### WCAG 2.1 Level AA Compliance Checklist

#### Perceivable
- [ ] Alt text for all images (1.1.1)
- [ ] Captions for videos (1.2.2)
- [ ] Color contrast ratio ≥ 4.5:1 for text (1.4.3)
- [ ] Responsive layout (1.4.10)
- [ ] Semantic HTML structure

#### Operable
- [ ] All functionality keyboard-accessible (2.1.1)
- [ ] No keyboard traps (2.1.2)
- [ ] Visible focus indicators (2.4.7)
- [ ] Skip navigation links (2.4.1)
- [ ] Descriptive page titles (2.4.2)

#### Understandable
- [ ] Language attribute on HTML element (3.1.1)
- [ ] Labels for form inputs (3.3.2)
- [ ] Error identification and suggestions (3.3.1, 3.3.3)
- [ ] Consistent navigation (3.2.3)

#### Robust
- [ ] Valid HTML (4.1.1)
- [ ] ARIA labels for dynamic content (4.1.2)
- [ ] Compatible with assistive technologies

---

## Development Methodology

### Agile Framework

**Sprint Structure:**
- Sprint Duration: 2-4 weeks
- Planning Poker: Fibonacci scale (1, 2, 3, 5, 8, 13, 21)
- Daily Standups: Async updates in project channel
- Sprint Review: Demo to stakeholders
- Sprint Retrospective: Continuous improvement

**Kanban Board:**
- Master Board: `docs/kanban/master-board.md`
- Sub-Boards: Feature-specific boards (auth-security, billing-payments, etc.)
- Columns: Todo → In Progress → Done → Blocked
- WIP Limits: Max 3 tasks in progress per developer

### Test-Driven Development (TDD)

**RED → GREEN → REFACTOR Cycle:**

1. **RED**: Write a failing test first
   ```python
   def test_user_login_returns_jwt():
       """Test that valid login returns JWT token"""
       response = client.post("/auth/login", json={
           "email": "user@example.com",
           "password": "password123"
       })
       assert response.status_code == 200
       assert "access_token" in response.json()
   ```

2. **GREEN**: Write minimal code to pass the test
   ```python
   @router.post("/auth/login")
   async def login(credentials: LoginSchema, db: AsyncSession = Depends(get_db)):
       user = await user_dao.get_by_email(credentials.email)
       if not user or not verify_password(credentials.password, user.password_hash):
           raise AuthenticationError("Invalid credentials")

       token = create_access_token({"user_id": user.id, "org_id": user.org_id})
       return {"access_token": token}
   ```

3. **REFACTOR**: Improve code while keeping tests green

**Test Coverage Requirements:**
- Minimum 80% code coverage
- Unit tests: Fast, isolated, mock dependencies
- Integration tests: Real database, test transactions
- E2E tests: Full user flows (register → login → create project)

### Code Standards

**DAO Pattern (Mandatory):**
```python
class UserDAO(BaseDAO[User]):
    """
    Data Access Object for User model.

    WHY: Separating database operations from business logic makes code
    more testable, maintainable, and allows for easier database migrations.
    """

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Retrieve user by email address.

        WHY: Email is the unique identifier for authentication.
        Case-insensitive comparison prevents duplicate accounts.
        """
        result = await self.session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()
```

**Custom Exceptions (Mandatory):**
```python
class AuthenticationError(AppException):
    """
    Raised when authentication fails.

    WHY: Custom exceptions allow consistent error handling and
    prevent leaking sensitive information in error messages.
    """
    status_code = 401
    default_message = "Authentication failed"
```

**Documentation (Mandatory):**
- Every function must have a docstring
- Docstrings must explain **WHY**, not just what
- Include context: Why this approach vs alternatives?

**Quality Gates (Before Merging):**
- [ ] All tests passing
- [ ] Code coverage ≥ 80%
- [ ] No security vulnerabilities
- [ ] No accessibility violations
- [ ] Type checking passes
- [ ] Linting passes
- [ ] DAO pattern used (if database access)
- [ ] Custom exceptions (no base Exception)
- [ ] Comprehensive documentation (WHY included)
- [ ] Code review approved

### Specialized Agent Framework

**5 Specialized Agents:**

1. **Architecture Agent** (`.claude/agents/architecture.md`)
   - System design and architectural decisions
   - Design pattern selection
   - Scalability planning

2. **Test Design Agent** (`.claude/agents/test-design.md`)
   - Test strategy and test plan creation
   - Test case design
   - TDD enforcement

3. **Software Implementation Agent** (`.claude/agents/implementation.md`)
   - Code development following TDD
   - DAO pattern implementation
   - Comprehensive documentation

4. **Cybersecurity Agent** (`.claude/agents/security.md`)
   - OWASP Top 10 compliance
   - Security audits and vulnerability assessment
   - Secure coding practices

5. **DevOps Agent** (`.claude/agents/devops.md`)
   - CI/CD pipeline management
   - Infrastructure as code
   - Monitoring and observability

### Definition of Done

A task is **DONE** when:
- [ ] Tests written FIRST (TDD)
- [ ] All tests passing (unit + integration + e2e)
- [ ] Code coverage ≥ 80%
- [ ] Security review completed (OWASP checklist)
- [ ] Accessibility review (if frontend, WCAG checklist)
- [ ] DAO pattern used (if database access)
- [ ] Custom exceptions (no base Exception)
- [ ] Comprehensive documentation (WHY included)
- [ ] Code review approved by relevant agents
- [ ] Merged to main branch

---

## Glossary

**Terms:**

- **ADMIN**: Service provider role with full system access
- **CLIENT**: Customer role with org-scoped access
- **DAO (Data Access Object)**: Pattern separating database operations from business logic
- **Multi-Tenancy**: Multiple organizations sharing single application instance with data isolation
- **n8n**: Open-source workflow automation platform
- **Org-Scoping**: Automatic filtering of data by organization ID
- **OWASP**: Open Web Application Security Project
- **RBAC (Role-Based Access Control)**: Access control based on user roles
- **SLA (Service Level Agreement)**: Commitment to response/resolution times
- **TDD (Test-Driven Development)**: Write tests before implementation
- **WCAG (Web Content Accessibility Guidelines)**: Accessibility standards

**Acronyms:**

- **API**: Application Programming Interface
- **CI/CD**: Continuous Integration / Continuous Deployment
- **CSP**: Content Security Policy
- **DTO**: Data Transfer Object
- **JWT**: JSON Web Token
- **ORM**: Object-Relational Mapping
- **PDF**: Portable Document Format
- **REST**: Representational State Transfer
- **SaaS**: Software as a Service
- **SQL**: Structured Query Language
- **SSL/TLS**: Secure Sockets Layer / Transport Layer Security
- **UUID**: Universally Unique Identifier

---

## Document Control

**Approval:**

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product Owner | TBD | | |
| Tech Lead | TBD | | |
| Security Lead | TBD | | |

**Change History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-12 | Claude Code | Initial specification document |

---

**End of Software Specification Document**
