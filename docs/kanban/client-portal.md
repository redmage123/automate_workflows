# Client Portal Sub-Board

**Parent**: Master Kanban Board
**Sprint**: 2-3 (Auth & Orgs, Projects & Proposals)
**Focus**: Organization management, projects, proposals, client-facing features

---

## 🔴 Blocked

*None currently*

---

## 🟡 In Progress

*None currently*

---

## ⚪ Todo (Priority Order)

### ORG-001: Create Organization Endpoint (5 points)
**Priority**: P1
**Dependencies**: AUTH-002

**Description**:
Create API endpoint for organization creation (happens during registration or admin creation).

**Acceptance Criteria**:
- [ ] POST /api/orgs creates organization
- [ ] Organization name uniqueness validated
- [ ] Default settings applied
- [ ] Stripe customer ID field prepared
- [ ] Audit log entry created
- [ ] Tests cover success and error cases

---

### ORG-002: Get Organization Details (2 points)
**Priority**: P1
**Dependencies**: AUTH-002

**Description**:
Retrieve organization details for current user.

**Acceptance Criteria**:
- [ ] GET /api/orgs/me returns user's organization
- [ ] ADMIN can GET /api/orgs/{id} for any org
- [ ] CLIENT only sees own organization
- [ ] Settings included in response

---

### ORG-003: Organization Settings Page (5 points)
**Priority**: P2
**Dependencies**: ORG-001

**Description**:
Frontend page for viewing/editing organization settings.

**Acceptance Criteria**:
- [ ] Settings form with validation
- [ ] Logo upload capability
- [ ] Timezone selection
- [ ] Notification preferences
- [ ] Save confirmation toast

---

### PROJ-001: Project Model + DAO (5 points)
**Priority**: P1
**Dependencies**: AUTH-002

**Description**:
Create Project SQLAlchemy model and DAO with org-scoping.

**Fields**:
- id, org_id, code (unique), title, description
- status (enum), created_by, created_at, updated_at

**Acceptance Criteria**:
- [ ] Model with all fields
- [ ] DAO with CRUD operations
- [ ] Org-scoped queries
- [ ] Project code generation (PRJ-YYYY-NNN)
- [ ] Status enum validation
- [ ] Unit tests for DAO

---

### PROJ-002: Create Project Endpoint (5 points)
**Priority**: P1
**Dependencies**: PROJ-001

**Description**:
API endpoint for creating new projects (ADMIN only).

**Acceptance Criteria**:
- [ ] POST /api/projects creates project
- [ ] ADMIN role required
- [ ] Org_id from authenticated user (not request body)
- [ ] Unique code generated
- [ ] Audit log entry
- [ ] Returns created project

---

### PROJ-003: List Projects Endpoint (3 points)
**Priority**: P1
**Dependencies**: PROJ-001

**Description**:
API endpoint for listing projects with filters and pagination.

**Acceptance Criteria**:
- [ ] GET /api/projects returns paginated list
- [ ] Filter by status
- [ ] Filter by org_id (ADMIN only)
- [ ] Search by title
- [ ] Sort by created_at, title
- [ ] CLIENT sees only their org's projects

---

### PROJ-004: Update Project Status (3 points)
**Priority**: P1
**Dependencies**: PROJ-001

**Description**:
API endpoint for updating project status.

**Acceptance Criteria**:
- [ ] PATCH /api/projects/{id}/status
- [ ] Status transition validation
- [ ] ADMIN only
- [ ] Notification triggered on status change
- [ ] Audit log entry

---

### PROJ-005: Project Details Page UI (5 points)
**Priority**: P1
**Dependencies**: PROJ-002

**Description**:
Frontend page showing complete project information.

**Acceptance Criteria**:
- [ ] Project header with status badge
- [ ] Description display
- [ ] Linked proposals section
- [ ] Linked workflows section
- [ ] Activity timeline
- [ ] Edit button (ADMIN)

---

### PROJ-006: Project List/Kanban View (8 points)
**Priority**: P2
**Dependencies**: PROJ-003

**Description**:
Frontend page with list and kanban view options.

**Acceptance Criteria**:
- [ ] Table view with sorting
- [ ] Kanban board by status
- [ ] View toggle persistence
- [ ] Search functionality
- [ ] Filters for status
- [ ] New project button (ADMIN)

---

### PROP-001: Proposal Model + DAO (5 points)
**Priority**: P1
**Dependencies**: PROJ-001

**Description**:
Create Proposal SQLAlchemy model and DAO.

**Fields**:
- id, org_id, project_id, title
- line_items (JSON), subtotal, tax, total
- status (enum), pdf_url
- created_by, created_at, updated_at

**Acceptance Criteria**:
- [ ] Model with all fields
- [ ] DAO with CRUD operations
- [ ] Line items as JSON array
- [ ] Total calculation method
- [ ] Status transitions
- [ ] Unit tests

---

### PROP-002: Create Proposal Endpoint (5 points)
**Priority**: P1
**Dependencies**: PROP-001

**Description**:
API endpoint for creating proposals (ADMIN only).

**Acceptance Criteria**:
- [ ] POST /api/proposals creates proposal
- [ ] ADMIN role required
- [ ] Project must exist
- [ ] Line items validated
- [ ] Totals calculated server-side
- [ ] Audit log entry

---

### PROP-003: Update Proposal Endpoint (3 points)
**Priority**: P1
**Dependencies**: PROP-001

**Description**:
API endpoint for updating proposal details.

**Acceptance Criteria**:
- [ ] PATCH /api/proposals/{id}
- [ ] Only DRAFT proposals editable
- [ ] Recalculate totals on line item change
- [ ] Audit log entry

---

### PROP-004: Approve Proposal Endpoint (5 points)
**Priority**: P1
**Dependencies**: PROP-001

**Description**:
API endpoint for client proposal approval.

**Acceptance Criteria**:
- [ ] POST /api/proposals/{id}/approve
- [ ] CLIENT can approve their org's proposals
- [ ] Status changes to APPROVED
- [ ] Triggers payment flow
- [ ] Project status updated
- [ ] Notification sent

---

### PROP-005: Proposal Detail Page UI (5 points)
**Priority**: P1
**Dependencies**: PROP-002

**Description**:
Frontend page showing proposal details.

**Acceptance Criteria**:
- [ ] Proposal header with status
- [ ] Line items table
- [ ] Totals display
- [ ] Approve/Reject buttons (CLIENT)
- [ ] Edit button (ADMIN, if DRAFT)
- [ ] PDF download link

---

### PROP-006: Proposal Editor UI (8 points)
**Priority**: P2
**Dependencies**: PROP-002

**Description**:
Frontend form for creating/editing proposals.

**Acceptance Criteria**:
- [ ] Add/remove line items
- [ ] Quantity and price inputs
- [ ] Live total calculation
- [ ] Save as draft
- [ ] Send to client
- [ ] Validation feedback

---

### ONBOARD-001: Client Onboarding Form (8 points)
**Priority**: P2
**Dependencies**: ORG-001, PROJ-002

**Description**:
Guided onboarding flow for new clients.

**Acceptance Criteria**:
- [ ] Multi-step form
- [ ] Company information
- [ ] Initial project details
- [ ] Contact preferences
- [ ] Creates org, user, project
- [ ] Welcome email sent

---

### TICKET-001: Ticket Model + DAO (5 points)
**Priority**: P2
**Dependencies**: PROJ-001

**Description**:
Create Ticket SQLAlchemy model and DAO.

**Fields**:
- id, org_id, project_id (optional)
- title, description, status, priority
- sla_response_due, sla_resolution_due
- created_by, assigned_to, created_at

**Acceptance Criteria**:
- [ ] Model with all fields
- [ ] DAO with CRUD operations
- [ ] SLA calculation method
- [ ] Priority to SLA mapping
- [ ] Unit tests

---

### TICKET-002: Create Ticket Endpoint (3 points)
**Priority**: P2
**Dependencies**: TICKET-001

**Description**:
API endpoint for creating support tickets.

**Acceptance Criteria**:
- [ ] POST /api/tickets creates ticket
- [ ] Both ADMIN and CLIENT can create
- [ ] SLA auto-calculated from priority
- [ ] Notification to support team
- [ ] Audit log entry

---

### TICKET-003: Update Ticket Endpoint (3 points)
**Priority**: P2
**Dependencies**: TICKET-001

**Description**:
API endpoint for updating ticket status/details.

**Acceptance Criteria**:
- [ ] PATCH /api/tickets/{id}
- [ ] Status transitions validated
- [ ] ADMIN can update all fields
- [ ] CLIENT can only add comments
- [ ] First response time captured

---

### TICKET-004: List Tickets Endpoint (3 points)
**Priority**: P2
**Dependencies**: TICKET-001

**Description**:
API endpoint for listing tickets.

**Acceptance Criteria**:
- [ ] GET /api/tickets returns paginated list
- [ ] Filter by status, priority, project
- [ ] ADMIN sees all, CLIENT sees org's
- [ ] Sort by SLA due, created_at

---

### TICKET-005: SLA Timer Calculation (5 points)
**Priority**: P2
**Dependencies**: TICKET-001

**Description**:
Calculate SLA due times based on priority.

**SLA Targets**:
- LOW: 24h response, 72h resolution
- MEDIUM: 8h response, 24h resolution
- HIGH: 4h response, 8h resolution
- URGENT: 1h response, 4h resolution

**Acceptance Criteria**:
- [ ] Business hours only (9-5 M-F)
- [ ] Timezone aware
- [ ] Due times calculated on create
- [ ] SLA breach percentage calculated

---

### TICKET-006: SLA Breach Background Job (8 points)
**Priority**: P2
**Dependencies**: TICKET-005

**Description**:
Background job to check for SLA breaches.

**Acceptance Criteria**:
- [ ] Runs every 15 minutes
- [ ] Flags approaching breaches (75%)
- [ ] Flags actual breaches (100%)
- [ ] Sends notifications
- [ ] Records breach in audit log

---

### TICKET-007: Ticket List UI (5 points)
**Priority**: P2
**Dependencies**: TICKET-004

**Description**:
Frontend page listing tickets.

**Acceptance Criteria**:
- [ ] Table with status badges
- [ ] SLA indicator (green/yellow/red)
- [ ] Filter controls
- [ ] Create ticket button
- [ ] Click to view details

---

### TICKET-008: Ticket Detail/Edit UI (5 points)
**Priority**: P2
**Dependencies**: TICKET-002

**Description**:
Frontend page for ticket details and editing.

**Acceptance Criteria**:
- [ ] Ticket header with status
- [ ] Description display
- [ ] Comment thread
- [ ] Add comment form
- [ ] Status change dropdown (ADMIN)
- [ ] SLA timer display

---

## Definition of Done

- [ ] TDD: Tests written FIRST
- [ ] All tests passing
- [ ] Code coverage >= 80%
- [ ] DAO pattern used
- [ ] Custom exceptions only
- [ ] Documentation (WHAT/WHY/HOW)
- [ ] Accessibility tested (frontend)
- [ ] Code review approved
