# Software Specification Document
# Automation Services Platform

**Version:** 2.0
**Last Updated:** 2025-12-10
**Status:** Foundation Phase
**Document Type:** Complete Software Specification

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Context](#2-business-context)
3. [System Overview](#3-system-overview)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [System Architecture](#6-system-architecture)
7. [Data Model](#7-data-model)
8. [API Specification](#8-api-specification)
9. [Security Specification](#9-security-specification)
10. [Integration Specification](#10-integration-specification)
11. [User Interface Specification](#11-user-interface-specification)
12. [Testing Specification](#12-testing-specification)
13. [Deployment Specification](#13-deployment-specification)
14. [Glossary](#14-glossary)
15. [Appendices](#15-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document provides a complete software specification for the **Automation Services Platform**, a multi-tenant SaaS application that enables automation service providers to manage client workflows using n8n as the workflow execution engine.

### 1.2 Scope

The platform encompasses:
- Client lifecycle management (onboarding, projects, proposals, billing)
- n8n workflow integration and orchestration
- Multi-tenant architecture with organization-based isolation
- Role-based access control (ADMIN/CLIENT)
- Support ticketing with SLA tracking
- Comprehensive audit logging

### 1.3 Target Audience

- **Automation Service Providers**: Businesses offering workflow automation services
- **Clients**: Organizations purchasing automation services
- **Development Team**: Engineers implementing the platform

### 1.4 Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18+, TypeScript, Tailwind CSS |
| Backend | FastAPI (Python 3.11+), SQLAlchemy 2.0 |
| Database | PostgreSQL 15+ |
| Cache/Queue | Redis 7+ |
| Workflow Engine | n8n (self-hosted) |
| Payments | Stripe |
| Infrastructure | Docker Compose, Traefik |

---

## 2. Business Context

### 2.1 Problem Statement

Automation service providers face operational challenges:

1. **Fragmented Tooling**: Client management, workflow automation, and billing exist in separate systems
2. **Manual Processes**: Proposal generation, workflow provisioning, and invoice creation require significant manual effort
3. **Lack of Client Visibility**: Clients cannot self-serve to track project status or view invoices
4. **Security Concerns**: Managing multiple client organizations requires robust access controls
5. **Scalability Issues**: Manual processes become bottlenecks as the business grows

### 2.2 Solution Overview

A unified platform that:
- Manages the complete client lifecycle from onboarding to ongoing support
- Integrates directly with n8n for workflow automation
- Provides self-service portals for both admins and clients
- Enforces multi-tenant data isolation
- Automates billing through Stripe integration

### 2.3 Value Proposition

**For Service Providers:**
- Centralized client and project management
- Automated billing and invoicing
- Workflow template library for rapid deployment
- Analytics and reporting dashboard

**For Clients:**
- Self-service portal for project visibility
- Transparent pricing through proposals
- Easy support ticket creation
- Access to workflow execution logs

### 2.4 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Client Onboarding Time | < 5 minutes | Time from form submission to account creation |
| Proposal Generation | < 10 minutes | Time to create and send proposal |
| Workflow Deployment | < 30 minutes | Time from approval to workflow active |
| Support Response | < 4 hours | Time to first response on tickets |
| System Uptime | 99.9% | Monthly availability |

---

## 3. System Overview

### 3.1 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL ACTORS                            │
├───────────────┬───────────────┬───────────────┬────────────────────┤
│    Admin      │    Client     │    Stripe     │       n8n          │
│   (Browser)   │   (Browser)   │    (API)      │     (API)          │
└───────┬───────┴───────┬───────┴───────┬───────┴────────┬───────────┘
        │               │               │                │
        └───────────────┼───────────────┼────────────────┘
                        │               │
                        ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AUTOMATION SERVICES PLATFORM                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     React Frontend                           │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │   │
│  │  │ Admin Portal │  │ Client Portal│  │  Auth Pages  │       │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │   │
│  └─────────────────────────────┬───────────────────────────────┘   │
│                                │ REST API                           │
│  ┌─────────────────────────────▼───────────────────────────────┐   │
│  │                     FastAPI Backend                          │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │   │
│  │  │  Auth   │ │Projects │ │Billing  │ │Workflows│ │Tickets │ │   │
│  │  │ Service │ │ Service │ │ Service │ │ Service │ │Service │ │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └───┬────┘ │   │
│  │       │           │           │           │          │       │   │
│  │  ┌────▼───────────▼───────────▼───────────▼──────────▼────┐ │   │
│  │  │                    DAO Layer                            │ │   │
│  │  └────────────────────────┬───────────────────────────────┘ │   │
│  └───────────────────────────┼─────────────────────────────────┘   │
│                              │                                      │
│  ┌───────────────────────────▼───────────────────────────────────┐ │
│  │                      PostgreSQL                                │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Key Components

| Component | Description | Technology |
|-----------|-------------|------------|
| React Frontend | Single-page application for Admin and Client portals | React, TypeScript, Tailwind |
| FastAPI Backend | REST API server handling all business logic | Python, FastAPI, SQLAlchemy |
| PostgreSQL | Primary data store for all application data | PostgreSQL 15+ |
| Redis | Session cache, job queue, rate limiting | Redis 7+ |
| n8n | Workflow automation engine | n8n (Docker) |
| Traefik | Reverse proxy, SSL termination, load balancing | Traefik 2.10+ |

### 3.3 User Roles

| Role | Description | Capabilities |
|------|-------------|--------------|
| ADMIN | Service provider staff | Full access: manage all organizations, users, projects, workflows |
| CLIENT | Customer organization member | Limited access: view own org's projects, proposals, invoices, tickets |

---

## 4. Functional Requirements

### 4.1 Authentication & Authorization (FR-AUTH)

#### FR-AUTH-001: User Registration
| Attribute | Value |
|-----------|-------|
| Priority | P0 (Critical) |
| Description | Users can register with email and password |
| Actors | New users |
| Preconditions | Valid email address |
| Postconditions | User account created, verification email sent |
| Business Rules | - Email must be unique<br>- Password minimum 8 characters with complexity<br>- Email verification required before login |

**Acceptance Criteria:**
1. User submits registration form with email, password, and organization name
2. System validates input (email format, password strength)
3. System creates Organization and User records
4. System sends verification email
5. User cannot login until email verified

#### FR-AUTH-002: User Login
| Attribute | Value |
|-----------|-------|
| Priority | P0 (Critical) |
| Description | Authenticated access via email/password |
| Actors | Registered users |
| Preconditions | Email verified, account active |
| Postconditions | JWT token issued, session created |
| Business Rules | - 5 failed attempts triggers 15-minute lockout<br>- JWT expires in 24 hours<br>- Refresh token valid 30 days |

**Acceptance Criteria:**
1. User submits valid credentials
2. System validates credentials against stored hash
3. System issues JWT with user_id, org_id, role
4. System logs successful authentication
5. Failed attempts increment lockout counter

#### FR-AUTH-003: Role-Based Access Control
| Attribute | Value |
|-----------|-------|
| Priority | P0 (Critical) |
| Description | Enforce permissions based on user role |
| Actors | All authenticated users |
| Preconditions | Valid JWT token |
| Postconditions | Access granted or denied based on role |
| Business Rules | - ADMIN: access all organizations<br>- CLIENT: access only own organization<br>- All queries scoped by org_id |

**Acceptance Criteria:**
1. Every API endpoint checks user role
2. CLIENT users only see their organization's data
3. ADMIN users can access all data
4. Cross-organization access attempts logged and blocked
5. 403 returned for unauthorized access attempts

#### FR-AUTH-004: Password Reset
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Self-service password reset via email |
| Actors | Users who forgot password |
| Preconditions | Valid email in system |
| Postconditions | New password set |
| Business Rules | - Reset token expires in 1 hour<br>- Token single-use<br>- Old sessions invalidated on reset |

#### FR-AUTH-005: Session Management
| Attribute | Value |
|-----------|-------|
| Priority | P0 (Critical) |
| Description | Manage user sessions and token lifecycle |
| Actors | Authenticated users |
| Preconditions | Valid authentication |
| Postconditions | Session created/destroyed appropriately |
| Business Rules | - Sessions tracked in Redis<br>- Logout invalidates all sessions<br>- Concurrent session limit: 5 per user |

---

### 4.2 Organization Management (FR-ORG)

#### FR-ORG-001: Create Organization
| Attribute | Value |
|-----------|-------|
| Priority | P0 (Critical) |
| Description | Create new client organization |
| Actors | ADMIN, Registration system |
| Preconditions | Valid organization data |
| Postconditions | Organization record created |
| Business Rules | - Organization name unique<br>- Initial settings with defaults<br>- Audit log entry created |

**Acceptance Criteria:**
1. ADMIN can create organization via API
2. Registration creates organization automatically
3. Default settings applied (timezone, notification preferences)
4. Organization assigned unique ID
5. Creator becomes first user (for registration flow)

#### FR-ORG-002: Update Organization
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Modify organization settings |
| Actors | ADMIN, CLIENT (own org) |
| Preconditions | Organization exists |
| Postconditions | Organization updated |
| Business Rules | - Name change requires ADMIN approval<br>- Settings changes logged<br>- Billing info changes trigger Stripe update |

#### FR-ORG-003: Organization Settings
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Configure organization preferences |
| Actors | ADMIN, CLIENT (own org) |
| Fields | Timezone, notification preferences, billing contact, logo |

---

### 4.3 Project Management (FR-PROJ)

#### FR-PROJ-001: Create Project
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Create new automation project |
| Actors | ADMIN |
| Preconditions | Organization exists |
| Postconditions | Project record created |
| Business Rules | - Project belongs to one organization<br>- Initial status: DRAFT<br>- Unique project code generated |

**Acceptance Criteria:**
1. ADMIN creates project with title, description, organization
2. System generates unique project code (e.g., PRJ-2025-001)
3. Project status set to DRAFT
4. Audit log records creation with creator ID
5. Project appears in organization's project list

#### FR-PROJ-002: List Projects
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | View projects with filtering |
| Actors | ADMIN (all), CLIENT (own org) |
| Filters | Status, organization, date range, search |
| Pagination | 20 items per page, cursor-based |

#### FR-PROJ-003: Update Project Status
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Change project lifecycle status |
| Actors | ADMIN |
| Statuses | DRAFT → PROPOSED → APPROVED → IN_PROGRESS → COMPLETED → ARCHIVED |
| Business Rules | - Status transitions validated<br>- Notifications sent on status change<br>- Cannot skip statuses (except ADMIN override) |

#### FR-PROJ-004: Project Details
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | View complete project information |
| Actors | ADMIN, CLIENT (own org) |
| Includes | Project data, proposals, workflows, invoices, tickets, activity log |

---

### 4.4 Proposal Management (FR-PROP)

#### FR-PROP-001: Create Proposal
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Generate proposal with line items |
| Actors | ADMIN |
| Preconditions | Project exists |
| Postconditions | Proposal created, linked to project |
| Business Rules | - One active proposal per project<br>- Line items with quantity, unit price<br>- Tax calculation configurable |

**Acceptance Criteria:**
1. ADMIN creates proposal linked to project
2. Add line items with description, quantity, price
3. System calculates subtotal, tax, total
4. Proposal status set to DRAFT
5. PDF generation available

#### FR-PROP-002: Proposal Templates
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Reusable proposal templates |
| Actors | ADMIN |
| Features | Pre-defined line items, terms, formatting |

#### FR-PROP-003: Send Proposal
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Send proposal to client |
| Actors | ADMIN |
| Postconditions | Email sent, status updated to SENT |
| Business Rules | - PDF attached to email<br>- Unique viewing link generated<br>- Proposal locked after sending |

#### FR-PROP-004: Client Proposal Actions
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Client approves or requests changes |
| Actors | CLIENT |
| Actions | APPROVE, REQUEST_CHANGES, DECLINE |
| Business Rules | - Approval triggers payment flow<br>- Changes create new proposal version<br>- Decline closes proposal |

#### FR-PROP-005: Proposal PDF Generation
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Generate PDF document from proposal |
| Actors | ADMIN, CLIENT |
| Technology | WeasyPrint |
| Features | Company branding, line items, terms, signature block |

---

### 4.5 Billing & Payments (FR-BILL)

#### FR-BILL-001: Stripe Customer Setup
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Create Stripe customer for organization |
| Actors | System (automatic) |
| Trigger | Organization creation or first payment |
| Postconditions | Stripe customer ID stored |

#### FR-BILL-002: Payment Processing
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Process payment via Stripe Checkout |
| Actors | CLIENT |
| Preconditions | Approved proposal |
| Postconditions | Payment recorded, invoice created |
| Business Rules | - Redirect to Stripe Checkout<br>- Webhook confirms payment<br>- Invoice generated on success |

**Acceptance Criteria:**
1. Client clicks "Pay Now" on approved proposal
2. System creates Stripe Checkout session
3. Client redirected to Stripe
4. On success, webhook received
5. Invoice created and linked to proposal
6. Project status updated to IN_PROGRESS
7. Confirmation email sent

#### FR-BILL-003: Stripe Webhook Handling
| Attribute | Value |
|-----------|-------|
| Priority | P0 (Critical) |
| Description | Process Stripe webhook events |
| Events | checkout.session.completed, payment_intent.succeeded, payment_intent.failed, invoice.paid, customer.subscription.* |
| Security | Signature verification required |

#### FR-BILL-004: Invoice Generation
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Auto-generate invoice on payment |
| Actors | System (automatic) |
| Trigger | Successful payment |
| Features | Invoice number, line items, payment details, PDF generation |

#### FR-BILL-005: Invoice PDF
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Generate invoice PDF document |
| Technology | WeasyPrint |
| Features | Company details, invoice number, items, payment status |

#### FR-BILL-006: Subscription Management
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Recurring billing for ongoing services |
| Features | Monthly/annual billing, usage-based add-ons, cancellation flow |

---

### 4.6 Workflow Management (FR-WF)

#### FR-WF-001: n8n Environment Configuration
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Configure n8n instance connection |
| Actors | ADMIN |
| Fields | Name, API URL, API key (encrypted) |
| Security | API key encrypted with Fernet |

**Acceptance Criteria:**
1. ADMIN provides n8n instance URL and API key
2. System encrypts API key before storage
3. System validates connection to n8n
4. Environment available for workflow deployment

#### FR-WF-002: Workflow Template Library
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Pre-built workflow templates |
| Actors | ADMIN |
| Features | Categories, descriptions, parameter definitions |

#### FR-WF-003: Deploy Workflow Instance
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Create workflow from template for project |
| Actors | ADMIN |
| Preconditions | Template exists, project approved |
| Postconditions | Workflow active in n8n |
| Business Rules | - Workflow linked to project<br>- Client-specific parameters configured<br>- Execution tracked |

**Acceptance Criteria:**
1. ADMIN selects template for project
2. Configure client-specific parameters
3. System calls n8n API to create workflow
4. Workflow ID stored in database
5. Workflow status tracked

#### FR-WF-004: Trigger Workflow
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Manually trigger workflow execution |
| Actors | ADMIN |
| Postconditions | Execution started, logged |

#### FR-WF-005: Workflow Execution Logs
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | View workflow execution history |
| Actors | ADMIN, CLIENT (own org) |
| Data | Execution ID, status, start/end time, error details |

#### FR-WF-006: Webhook Receiver
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Receive callbacks from n8n workflows |
| Endpoint | /api/webhooks/n8n/{workflow_id} |
| Security | Signature verification |
| Actions | Update execution status, trigger notifications |

---

### 4.7 Support Ticketing (FR-TKT)

#### FR-TKT-001: Create Ticket
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Submit support request |
| Actors | ADMIN, CLIENT |
| Fields | Title, description, priority, project (optional) |
| Business Rules | - Auto-assign SLA based on priority<br>- Notification to support team |

**Acceptance Criteria:**
1. User creates ticket with title and description
2. Select priority (LOW, MEDIUM, HIGH, URGENT)
3. Optionally link to project
4. System calculates SLA due time
5. Notification sent to ADMIN

#### FR-TKT-002: Ticket Status Management
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Update ticket lifecycle |
| Statuses | OPEN → IN_PROGRESS → WAITING → RESOLVED → CLOSED |
| Actors | ADMIN |

#### FR-TKT-003: Ticket Comments
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Threaded discussion on tickets |
| Actors | ADMIN, CLIENT (own org tickets) |
| Features | Rich text, attachments, internal notes (ADMIN only) |

#### FR-TKT-004: SLA Tracking
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Track response and resolution times |
| Metrics | First response time, resolution time |
| SLA Targets | LOW: 24h/72h, MEDIUM: 8h/24h, HIGH: 4h/8h, URGENT: 1h/4h |

#### FR-TKT-005: SLA Breach Alerts
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Notify on approaching/breached SLA |
| Triggers | 75% of SLA time, 100% of SLA time |
| Notifications | Email, Slack (if configured) |

---

### 4.8 Notifications (FR-NOTIF)

#### FR-NOTIF-001: Email Notifications
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Send transactional emails |
| Provider | Resend |
| Templates | Registration, proposal sent, payment received, ticket update |

#### FR-NOTIF-002: Slack Integration
| Attribute | Value |
|-----------|-------|
| Priority | P3 (Low) |
| Description | Send notifications to Slack channels |
| Events | New client, payment received, SLA breach |

#### FR-NOTIF-003: Notification Preferences
| Attribute | Value |
|-----------|-------|
| Priority | P3 (Low) |
| Description | User-configurable notification settings |
| Options | Email on/off per event type, Slack channel selection |

---

### 4.9 Admin Portal (FR-ADMIN)

#### FR-ADMIN-001: Dashboard
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Overview of system status |
| Widgets | Active projects, pending proposals, revenue MTD, open tickets, recent activity |

#### FR-ADMIN-002: User Management
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | CRUD operations on users |
| Actors | ADMIN |
| Features | Create, update, deactivate, password reset, role assignment |

#### FR-ADMIN-003: Organization Management
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Manage client organizations |
| Actors | ADMIN |
| Features | View all, edit settings, manage users, view activity |

#### FR-ADMIN-004: Audit Log Viewer
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | View system audit logs |
| Filters | User, action, resource type, date range |
| Export | CSV download |

#### FR-ADMIN-005: Analytics Dashboard
| Attribute | Value |
|-----------|-------|
| Priority | P3 (Low) |
| Description | Business metrics and reporting |
| Metrics | Revenue by period, projects by status, client acquisition, workflow executions |

---

### 4.10 Client Portal (FR-CLIENT)

#### FR-CLIENT-001: Client Dashboard
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | Overview for client users |
| Widgets | Active projects, pending proposals, recent invoices, open tickets |

#### FR-CLIENT-002: Project Tracking
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | View project status and details |
| Features | Status timeline, linked proposals, workflow executions |

#### FR-CLIENT-003: Invoice Access
| Attribute | Value |
|-----------|-------|
| Priority | P1 (High) |
| Description | View and download invoices |
| Features | Invoice list, PDF download, payment history |

#### FR-CLIENT-004: Ticket Management
| Attribute | Value |
|-----------|-------|
| Priority | P2 (Medium) |
| Description | Create and track support tickets |
| Features | Create ticket, view status, add comments |

---

## 5. Non-Functional Requirements

### 5.1 Performance (NFR-PERF)

| ID | Requirement | Target | Measurement |
|----|-------------|--------|-------------|
| NFR-PERF-001 | API Response Time | < 200ms (p95) | Prometheus metrics |
| NFR-PERF-002 | Page Load Time | < 2s (LCP) | Web Vitals |
| NFR-PERF-003 | Database Query Time | < 100ms (p99) | APM tracing |
| NFR-PERF-004 | Concurrent Users | 1,000 initial | Load testing |
| NFR-PERF-005 | Throughput | 10,000 req/min | Load testing |

### 5.2 Scalability (NFR-SCALE)

| ID | Requirement | Specification |
|----|-------------|---------------|
| NFR-SCALE-001 | Horizontal Scaling | Stateless backend, container replicas |
| NFR-SCALE-002 | Database Scaling | Read replicas for reporting queries |
| NFR-SCALE-003 | Cache Layer | Redis for sessions, frequently accessed data |
| NFR-SCALE-004 | Background Jobs | Dramatiq workers scale independently |
| NFR-SCALE-005 | Multi-Tenancy | 10,000+ organizations on single instance |

### 5.3 Reliability (NFR-REL)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-REL-001 | Uptime | 99.9% (< 8.76 hours/year downtime) |
| NFR-REL-002 | Error Rate | < 0.1% |
| NFR-REL-003 | Data Backup | Daily, 30-day retention |
| NFR-REL-004 | Recovery Point Objective | < 24 hours |
| NFR-REL-005 | Recovery Time Objective | < 4 hours |

### 5.4 Security (NFR-SEC)

| ID | Requirement | Implementation |
|----|-------------|----------------|
| NFR-SEC-001 | Authentication | JWT with 24h expiration, bcrypt passwords |
| NFR-SEC-002 | Authorization | RBAC enforced at API and DAO layers |
| NFR-SEC-003 | Data Encryption | TLS 1.3 in transit, Fernet for sensitive data at rest |
| NFR-SEC-004 | Input Validation | Pydantic schemas, SQL injection prevention |
| NFR-SEC-005 | Rate Limiting | 5 req/s per IP on auth endpoints |
| NFR-SEC-006 | Audit Logging | All mutations logged with actor and timestamp |
| NFR-SEC-007 | OWASP Compliance | Full OWASP Top 10 compliance |

### 5.5 Accessibility (NFR-A11Y)

| ID | Requirement | Standard |
|----|-------------|----------|
| NFR-A11Y-001 | WCAG Level | AA compliance |
| NFR-A11Y-002 | Keyboard Navigation | All interactive elements accessible |
| NFR-A11Y-003 | Screen Reader | Full compatibility |
| NFR-A11Y-004 | Color Contrast | 4.5:1 minimum for text |
| NFR-A11Y-005 | Focus Indicators | Visible on all elements |

### 5.6 Maintainability (NFR-MAINT)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-MAINT-001 | Test Coverage | >= 80% |
| NFR-MAINT-002 | Documentation | WHAT/WHY/HOW for all code |
| NFR-MAINT-003 | Code Patterns | DAO, DRY, SRP enforced |
| NFR-MAINT-004 | Type Safety | Full type hints (Python), TypeScript |
| NFR-MAINT-005 | Linting | ruff (Python), ESLint (TypeScript) |

### 5.7 Observability (NFR-OBS)

| ID | Requirement | Implementation |
|----|-------------|----------------|
| NFR-OBS-001 | Logging | Structured JSON logs with request IDs |
| NFR-OBS-002 | Error Tracking | Sentry integration |
| NFR-OBS-003 | Metrics | Prometheus for all services |
| NFR-OBS-004 | Tracing | OpenTelemetry for request flows |
| NFR-OBS-005 | Alerting | Critical error and performance alerts |

---

## 6. System Architecture

### 6.1 Layered Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     React Application                            ││
│  │  Components → Hooks → Services → API Client                      ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP/REST
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          API LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     FastAPI Routers                              ││
│  │  /auth  /orgs  /projects  /proposals  /billing  /workflows      ││
│  └─────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                      Middleware                                  ││
│  │  CORS → Auth → RBAC → Rate Limit → Audit Log                    ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SERVICE LAYER                                 │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Business Logic                                ││
│  │  AuthService  ProjectService  BillingService  WorkflowService   ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA ACCESS LAYER                               │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    DAO Classes                                   ││
│  │  UserDAO  OrgDAO  ProjectDAO  ProposalDAO  InvoiceDAO  ...      ││
│  └─────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                  SQLAlchemy Models                               ││
│  │  User  Organization  Project  Proposal  Invoice  Workflow  ...  ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      INFRASTRUCTURE LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  PostgreSQL  │  │    Redis     │  │     n8n      │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND                                    │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Auth UI    │  │ Admin Portal │  │Client Portal │              │
│  │              │  │              │  │              │              │
│  │ • Login      │  │ • Dashboard  │  │ • Dashboard  │              │
│  │ • Register   │  │ • Users      │  │ • Projects   │              │
│  │ • Reset PW   │  │ • Projects   │  │ • Proposals  │              │
│  │              │  │ • Workflows  │  │ • Invoices   │              │
│  │              │  │ • Billing    │  │ • Tickets    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Shared Components                             ││
│  │  Layout, Navigation, Forms, Tables, Modals, Notifications       ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          BACKEND                                     │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Auth Module  │  │Project Module│  │Billing Module│              │
│  │              │  │              │  │              │              │
│  │ • JWT        │  │ • CRUD       │  │ • Stripe     │              │
│  │ • RBAC       │  │ • Status     │  │ • Invoices   │              │
│  │ • Sessions   │  │ • Search     │  │ • Webhooks   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │Workflow Module│ │Ticket Module │  │ Org Module   │              │
│  │              │  │              │  │              │              │
│  │ • n8n API    │  │ • CRUD       │  │ • CRUD       │              │
│  │ • Templates  │  │ • SLA        │  │ • Settings   │              │
│  │ • Execution  │  │ • Comments   │  │ • Users      │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                       Core Module                                ││
│  │  Config, Exceptions, Security, Database, Logging, Utils         ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DOCKER COMPOSE                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                       Traefik                                 │  │
│  │              (Reverse Proxy, SSL, Load Balancer)              │  │
│  │                     Ports: 80, 443                            │  │
│  └───────────────────┬───────────────────┬──────────────────────┘  │
│                      │                   │                          │
│         ┌────────────▼────────┐    ┌────▼────────────┐             │
│         │     Frontend        │    │    Backend      │             │
│         │   (React/Nginx)     │    │   (FastAPI)     │             │
│         │    Port: 3000       │    │   Port: 8000    │             │
│         └─────────────────────┘    └────────┬────────┘             │
│                                             │                       │
│         ┌───────────────────────────────────┼───────────────┐      │
│         │                   │               │               │      │
│    ┌────▼────────┐   ┌─────▼─────┐   ┌────▼─────┐   ┌─────▼────┐ │
│    │ PostgreSQL  │   │   Redis   │   │   n8n    │   │  Worker  │ │
│    │  Port: 5432 │   │Port: 6379 │   │Port: 5678│   │(Dramatiq)│ │
│    └─────────────┘   └───────────┘   └──────────┘   └──────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Data Model

### 7.1 Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐
│  Organization   │───────│      User       │
│─────────────────│  1:N  │─────────────────│
│ id              │       │ id              │
│ name            │       │ org_id (FK)     │
│ settings (JSON) │       │ email           │
│ stripe_cust_id  │       │ password_hash   │
│ created_at      │       │ role            │
│ updated_at      │       │ is_active       │
└────────┬────────┘       │ created_at      │
         │                └─────────────────┘
         │ 1:N
         │
┌────────▼────────┐       ┌─────────────────┐
│     Project     │───────│    Proposal     │
│─────────────────│  1:N  │─────────────────│
│ id              │       │ id              │
│ org_id (FK)     │       │ project_id (FK) │
│ code            │       │ org_id (FK)     │
│ title           │       │ title           │
│ description     │       │ line_items (JSON)│
│ status          │       │ total_amount    │
│ created_by (FK) │       │ status          │
│ created_at      │       │ pdf_url         │
│ updated_at      │       │ created_at      │
└────────┬────────┘       └────────┬────────┘
         │                         │
         │                         │ 1:N
         │                         ▼
         │                ┌─────────────────┐
         │                │     Invoice     │
         │                │─────────────────│
         │                │ id              │
         │                │ org_id (FK)     │
         │                │ proposal_id (FK)│
         │                │ stripe_id       │
         │                │ amount          │
         │                │ status          │
         │                │ pdf_url         │
         │                │ paid_at         │
         │                └─────────────────┘
         │
         │ 1:N
         │
┌────────▼────────┐       ┌─────────────────┐
│WorkflowInstance │───────│  ExecutionLog   │
│─────────────────│  1:N  │─────────────────│
│ id              │       │ id              │
│ org_id (FK)     │       │ workflow_id (FK)│
│ project_id (FK) │       │ org_id (FK)     │
│ template_id (FK)│       │ n8n_exec_id     │
│ n8n_workflow_id │       │ status          │
│ status          │       │ started_at      │
│ created_at      │       │ finished_at     │
└─────────────────┘       │ error_message   │
                          └─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│     Ticket      │───────│ TicketComment   │
│─────────────────│  1:N  │─────────────────│
│ id              │       │ id              │
│ org_id (FK)     │       │ ticket_id (FK)  │
│ project_id (FK) │       │ user_id (FK)    │
│ title           │       │ content         │
│ description     │       │ is_internal     │
│ status          │       │ created_at      │
│ priority        │       └─────────────────┘
│ sla_due_at      │
│ created_by (FK) │
│ created_at      │
└─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│ N8nEnvironment  │       │WorkflowTemplate │
│─────────────────│       │─────────────────│
│ id              │       │ id              │
│ name            │       │ name            │
│ api_url         │       │ description     │
│ api_key_enc     │       │ n8n_workflow_id │
│ is_active       │       │ category        │
│ created_at      │       │ parameters (JSON)│
└─────────────────┘       │ created_at      │
                          └─────────────────┘

┌─────────────────┐
│    AuditLog     │
│─────────────────│
│ id              │
│ user_id (FK)    │
│ org_id (FK)     │
│ action          │
│ resource_type   │
│ resource_id     │
│ details (JSON)  │
│ ip_address      │
│ created_at      │
└─────────────────┘
```

### 7.2 Table Definitions

See `docs/database/schema.sql` for complete DDL statements.

---

## 8. API Specification

### 8.1 API Overview

| Category | Base Path | Description |
|----------|-----------|-------------|
| Auth | /api/auth | Authentication endpoints |
| Organizations | /api/orgs | Organization management |
| Users | /api/users | User management |
| Projects | /api/projects | Project CRUD |
| Proposals | /api/proposals | Proposal management |
| Billing | /api/billing | Payments and invoices |
| Workflows | /api/workflows | n8n workflow management |
| Tickets | /api/tickets | Support ticketing |
| Webhooks | /api/webhooks | External webhook receivers |

### 8.2 Authentication Endpoints

#### POST /api/auth/register
**Description:** Register new user and organization
**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "organization_name": "Acme Corp"
}
```
**Response:** `201 Created`
```json
{
  "message": "Registration successful. Please verify your email.",
  "user_id": 1,
  "org_id": 1
}
```

#### POST /api/auth/login
**Description:** Authenticate user
**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```
**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

#### POST /api/auth/logout
**Description:** Invalidate current session
**Headers:** `Authorization: Bearer <token>`
**Response:** `200 OK`

#### POST /api/auth/refresh
**Description:** Get new access token
**Request:**
```json
{
  "refresh_token": "eyJ..."
}
```
**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",
  "expires_in": 86400
}
```

### 8.3 Project Endpoints

#### GET /api/projects
**Description:** List projects
**Query Parameters:**
- `status` (optional): Filter by status
- `page` (default: 1): Page number
- `limit` (default: 20): Items per page

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": 1,
      "code": "PRJ-2025-001",
      "title": "Email Automation",
      "status": "IN_PROGRESS",
      "org_id": 1,
      "created_at": "2025-01-15T10:00:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "pages": 3
}
```

#### POST /api/projects
**Description:** Create project (ADMIN only)
**Request:**
```json
{
  "org_id": 1,
  "title": "Email Automation",
  "description": "Automate customer email workflows"
}
```
**Response:** `201 Created`

#### GET /api/projects/{id}
**Description:** Get project details
**Response:** `200 OK`

#### PATCH /api/projects/{id}
**Description:** Update project
**Request:**
```json
{
  "status": "IN_PROGRESS"
}
```
**Response:** `200 OK`

### 8.4 Complete API Reference

See `docs/api/openapi.yaml` for complete OpenAPI 3.0 specification.

---

## 9. Security Specification

### 9.1 Authentication

| Mechanism | Implementation |
|-----------|----------------|
| Password Storage | bcrypt with cost factor 12 |
| Session Token | JWT (HS256), 24-hour expiration |
| Refresh Token | JWT, 30-day expiration, stored in Redis |
| Rate Limiting | 5 requests/second on auth endpoints |

### 9.2 Authorization (RBAC)

| Role | Permissions |
|------|-------------|
| ADMIN | Full access to all resources |
| CLIENT | Read/write own organization resources only |

### 9.3 Data Protection

| Data Type | Protection |
|-----------|------------|
| Passwords | bcrypt hash (never stored plaintext) |
| API Keys | Fernet symmetric encryption |
| PII | Encrypted at rest in database |
| Transport | TLS 1.3 required |

### 9.4 OWASP Top 10 Compliance

| OWASP Category | Mitigation |
|----------------|------------|
| A01 Broken Access Control | RBAC, org-scoping, audit logs |
| A02 Cryptographic Failures | TLS, bcrypt, Fernet |
| A03 Injection | SQLAlchemy ORM, parameterized queries |
| A04 Insecure Design | Threat modeling, security ADRs |
| A05 Security Misconfiguration | Secure defaults, security headers |
| A06 Vulnerable Components | Dependency scanning, updates |
| A07 Authentication Failures | JWT expiration, rate limiting, bcrypt |
| A08 Software Integrity | Webhook signatures, CI/CD integrity |
| A09 Logging Failures | Comprehensive audit logging |
| A10 SSRF | URL allowlisting, validation |

---

## 10. Integration Specification

### 10.1 n8n Integration

#### Connection
- **Protocol:** REST API over HTTPS
- **Authentication:** API key in header
- **Base URL:** Configurable per environment

#### Operations
| Operation | n8n API Endpoint | Platform Action |
|-----------|------------------|-----------------|
| Create Workflow | POST /workflows | Deploy from template |
| Get Workflow | GET /workflows/{id} | Status check |
| Execute Workflow | POST /workflows/{id}/execute | Trigger run |
| Get Executions | GET /executions | Fetch logs |

### 10.2 Stripe Integration

#### Events Handled
| Stripe Event | Platform Action |
|--------------|-----------------|
| checkout.session.completed | Create invoice, update project |
| payment_intent.succeeded | Mark invoice paid |
| payment_intent.failed | Log failure, notify admin |
| customer.subscription.updated | Update subscription status |
| invoice.paid | Record payment |

### 10.3 Email Integration (Resend)

#### Templates
| Template | Trigger |
|----------|---------|
| welcome | User registration |
| verify_email | Email verification |
| proposal_sent | Proposal created |
| payment_received | Payment confirmed |
| ticket_update | Ticket status change |

---

## 11. User Interface Specification

### 11.1 Design System

| Element | Specification |
|---------|---------------|
| Framework | React 18+ with TypeScript |
| Styling | Tailwind CSS |
| Components | Custom component library |
| Icons | Heroicons |
| Typography | Inter font family |

### 11.2 Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                         Header                                   │
│  Logo    Navigation                      User Menu   Notifications│
├─────────────┬───────────────────────────────────────────────────┤
│             │                                                    │
│  Sidebar    │                    Main Content                    │
│             │                                                    │
│  • Dashboard│                                                    │
│  • Projects │                                                    │
│  • Proposals│                                                    │
│  • Invoices │                                                    │
│  • Tickets  │                                                    │
│  • Settings │                                                    │
│             │                                                    │
├─────────────┴───────────────────────────────────────────────────┤
│                         Footer                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 11.3 Page Inventory

| Page | Route | Role Access |
|------|-------|-------------|
| Login | /login | Public |
| Register | /register | Public |
| Dashboard | /dashboard | ADMIN, CLIENT |
| Projects List | /projects | ADMIN, CLIENT |
| Project Detail | /projects/:id | ADMIN, CLIENT |
| Proposals | /proposals | ADMIN, CLIENT |
| Invoices | /invoices | ADMIN, CLIENT |
| Tickets | /tickets | ADMIN, CLIENT |
| Admin Users | /admin/users | ADMIN |
| Admin Orgs | /admin/orgs | ADMIN |
| Settings | /settings | ADMIN, CLIENT |

---

## 12. Testing Specification

### 12.1 Testing Strategy

| Level | Scope | Tools |
|-------|-------|-------|
| Unit | Functions, classes | pytest, Jest |
| Integration | API endpoints, database | pytest, TestClient |
| E2E | Full user flows | Playwright |
| Performance | Load, stress | Locust |
| Security | Vulnerabilities | OWASP ZAP, Bandit |

### 12.2 Coverage Requirements

| Component | Minimum Coverage |
|-----------|------------------|
| Backend | 80% |
| Frontend | 70% |
| Critical Paths | 100% |

### 12.3 Test Environment

| Environment | Purpose |
|-------------|---------|
| Local | Developer testing |
| CI | Automated on PR |
| Staging | Pre-production validation |
| Production | Smoke tests only |

---

## 13. Deployment Specification

### 13.1 Environments

| Environment | Purpose | URL Pattern |
|-------------|---------|-------------|
| Development | Local development | localhost:* |
| Staging | Pre-production testing | staging.* |
| Production | Live system | app.* |

### 13.2 CI/CD Pipeline

```
Push → Lint → Test → Build → Deploy (staging) → Test → Deploy (prod)
```

### 13.3 Infrastructure Requirements

| Component | Specification |
|-----------|---------------|
| Backend | 2 vCPU, 4GB RAM minimum |
| Database | PostgreSQL 15+, 50GB storage |
| Redis | 1GB memory |
| n8n | 2 vCPU, 4GB RAM |

---

## 14. Glossary

| Term | Definition |
|------|------------|
| ADMIN | Service provider role with full system access |
| CLIENT | Customer role with organization-scoped access |
| DAO | Data Access Object - pattern for database abstraction |
| JWT | JSON Web Token - authentication mechanism |
| n8n | Open-source workflow automation platform |
| RBAC | Role-Based Access Control |
| SLA | Service Level Agreement |
| TDD | Test-Driven Development |

---

## 15. Appendices

### 15.1 Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-12 | Initial | First draft |
| 2.0 | 2025-12-10 | Updated | Complete rewrite with all requirements |

### 15.2 Related Documents

- CLAUDE.md - Development guidelines
- docs/adr/ - Architecture Decision Records
- docs/kanban/ - Project tracking boards
- docs/api/openapi.yaml - API specification

### 15.3 References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [React Documentation](https://react.dev/)
- [n8n API Documentation](https://docs.n8n.io/api/)
- [Stripe API Documentation](https://stripe.com/docs/api)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)

---

**End of Software Specification Document**
