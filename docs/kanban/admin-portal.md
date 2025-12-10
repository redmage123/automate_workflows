# Admin Portal Sub-Board

**Parent**: Master Kanban Board
**Sprint**: 7 (Admin Portal & Analytics)
**Focus**: User management, organization management, analytics, system health

---

## 🔴 Blocked

*None currently*

---

## 🟡 In Progress

*None currently*

---

## ⚪ Todo (Priority Order)

### ADMIN-001: Admin Dashboard UI (8 points)
**Priority**: P2
**Dependencies**: AUTH-001

**Description**:
Main admin dashboard with system overview.

**Widgets**:
- Active projects count (by status)
- Pending proposals count
- Revenue MTD/YTD
- Open tickets (by priority)
- Recent activity feed
- Workflow executions (last 24h)

**Acceptance Criteria**:
- [ ] Dashboard layout component
- [ ] Stat cards with icons
- [ ] Revenue chart (Chart.js)
- [ ] Activity timeline
- [ ] Quick links to common actions
- [ ] Responsive design

---

### ADMIN-002: User Management CRUD (8 points)
**Priority**: P2
**Dependencies**: AUTH-001

**Description**:
Admin interface for managing users.

**Features**:
- List all users (filterable)
- Create new user
- Edit user details
- Change user role
- Deactivate/reactivate user
- Reset user password
- View user activity

**Acceptance Criteria**:
- [ ] GET /api/admin/users (list)
- [ ] POST /api/admin/users (create)
- [ ] PATCH /api/admin/users/{id}
- [ ] DELETE /api/admin/users/{id} (deactivate)
- [ ] Users table with search
- [ ] User detail/edit modal
- [ ] Bulk actions

---

### ADMIN-003: Organization Management (5 points)
**Priority**: P2
**Dependencies**: ORG-001

**Description**:
Admin interface for managing organizations.

**Features**:
- List all organizations
- View organization details
- Edit organization settings
- View organization users
- View organization projects/invoices
- Billing status

**Acceptance Criteria**:
- [ ] GET /api/admin/orgs (list)
- [ ] Organizations table
- [ ] Organization detail page
- [ ] Linked users list
- [ ] Revenue summary
- [ ] Edit settings modal

---

### ADMIN-004: System Health Dashboard (5 points)
**Priority**: P2
**Dependencies**: DevOps setup

**Description**:
Dashboard showing system health and metrics.

**Widgets**:
- Service status (backend, DB, Redis, n8n)
- Response time (p50, p95, p99)
- Error rate
- Active connections
- Queue depth
- Disk usage

**Acceptance Criteria**:
- [ ] Health check aggregation endpoint
- [ ] Status indicators (green/yellow/red)
- [ ] Response time chart
- [ ] Error rate chart
- [ ] Refresh every 30s
- [ ] Alert configuration

---

### ADMIN-005: Audit Log Viewer (8 points)
**Priority**: P2
**Dependencies**: AUDIT-001

**Description**:
Interface for viewing audit logs.

**Features**:
- Paginated log list
- Filter by user, action, resource
- Date range filter
- Export to CSV
- Log detail view

**Acceptance Criteria**:
- [ ] GET /api/admin/audit-logs
- [ ] Logs table with filters
- [ ] Date range picker
- [ ] Export functionality
- [ ] Log detail expansion
- [ ] Action descriptions

---

### N8N-005: CRUD n8n Environments (5 points)
**Priority**: P1
**Dependencies**: N8N-001

**Description**:
Admin interface for managing n8n connections.

**Acceptance Criteria**:
- [ ] n8n environments list
- [ ] Add new environment form
- [ ] Edit environment
- [ ] Test connection button
- [ ] Deactivate environment
- [ ] API key masked display

---

### ANALYTICS-001: Project Metrics Endpoint (5 points)
**Priority**: P2
**Dependencies**: PROJ-001

**Description**:
API endpoint for project analytics.

**Metrics**:
- Projects by status (pie chart)
- Projects by month (bar chart)
- Average time in each status
- Projects per organization

**Acceptance Criteria**:
- [ ] GET /api/analytics/projects
- [ ] Status breakdown
- [ ] Monthly counts
- [ ] Duration metrics
- [ ] Org breakdown (ADMIN only)

---

### ANALYTICS-002: Revenue Metrics Endpoint (5 points)
**Priority**: P2
**Dependencies**: PAY-001

**Description**:
API endpoint for revenue analytics.

**Metrics**:
- Revenue MTD/QTD/YTD
- Revenue by month (12 months)
- Average invoice value
- Revenue by organization
- Outstanding invoices

**Acceptance Criteria**:
- [ ] GET /api/analytics/revenue
- [ ] Period summaries
- [ ] Monthly breakdown
- [ ] Org breakdown (ADMIN only)
- [ ] Outstanding balance

---

### ANALYTICS-003: User Activity Metrics (5 points)
**Priority**: P2
**Dependencies**: AUTH-001

**Description**:
API endpoint for user activity analytics.

**Metrics**:
- Daily active users
- User signups by month
- Users by role
- Last login distribution
- Most active users

**Acceptance Criteria**:
- [ ] GET /api/analytics/users
- [ ] DAU/MAU counts
- [ ] Signup trend
- [ ] Role distribution
- [ ] Activity leaderboard

---

### ANALYTICS-004: Analytics Dashboard UI (13 points)
**Priority**: P2
**Dependencies**: ANALYTICS-001, ANALYTICS-002, ANALYTICS-003

**Description**:
Comprehensive analytics dashboard with charts.

**Sections**:
- Projects overview
- Revenue trends
- User activity
- Workflow executions
- Ticket metrics

**Acceptance Criteria**:
- [ ] Tab navigation by section
- [ ] Chart.js integration
- [ ] Date range selector
- [ ] Export to PDF/CSV
- [ ] Responsive layout
- [ ] Print-friendly view

---

### POLISH-001: Error Pages (3 points)
**Priority**: P3
**Dependencies**: None

**Description**:
Custom error pages for 404, 403, 500.

**Acceptance Criteria**:
- [ ] 404 Not Found page
- [ ] 403 Forbidden page
- [ ] 500 Server Error page
- [ ] Consistent branding
- [ ] Helpful links
- [ ] Contact support option

---

### POLISH-002: Loading States (5 points)
**Priority**: P3
**Dependencies**: None

**Description**:
Consistent loading indicators throughout app.

**Acceptance Criteria**:
- [ ] Skeleton screens for lists
- [ ] Spinner for buttons
- [ ] Progress bar for uploads
- [ ] Page transition indicator
- [ ] Consistent styling

---

### POLISH-003: Toast Notifications (3 points)
**Priority**: P3
**Dependencies**: None

**Description**:
Toast notification system for user feedback.

**Types**:
- Success (green)
- Error (red)
- Warning (yellow)
- Info (blue)

**Acceptance Criteria**:
- [ ] Toast component
- [ ] Notification context/hook
- [ ] Auto-dismiss (5s default)
- [ ] Dismiss button
- [ ] Stack multiple toasts
- [ ] Accessible announcements

---

## Admin Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                          HEADER                                  │
├──────────────┬──────────────────────────────────────────────────┤
│              │                                                   │
│   SIDEBAR    │                    MAIN CONTENT                   │
│              │                                                   │
│ • Dashboard  │  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│ • Users      │  │  Projects   │  │   Revenue   │  │  Tickets  │ │
│ • Orgs       │  │    12       │  │   $45,000   │  │     5     │ │
│ • Projects   │  │   active    │  │    MTD      │  │   open    │ │
│ • Proposals  │  └─────────────┘  └─────────────┘  └───────────┘ │
│ • Invoices   │                                                   │
│ • Workflows  │  ┌───────────────────────────────────────────────┐│
│ • Tickets    │  │                                               ││
│ ─────────── │  │              REVENUE CHART                    ││
│ • Analytics  │  │                                               ││
│ • Audit Logs │  └───────────────────────────────────────────────┘│
│ • Settings   │                                                   │
│ • n8n Envs   │  ┌───────────────────────────────────────────────┐│
│              │  │           RECENT ACTIVITY                     ││
│              │  │  • User X created project...                  ││
│              │  │  • Payment received for...                    ││
│              │  │  • Workflow executed...                       ││
│              │  └───────────────────────────────────────────────┘│
│              │                                                   │
└──────────────┴──────────────────────────────────────────────────┘
```

## Access Control

| Feature | ADMIN | CLIENT |
|---------|-------|--------|
| Admin Dashboard | ✅ | ❌ |
| User Management | ✅ | ❌ |
| Org Management | ✅ | ❌ |
| Audit Logs | ✅ | ❌ |
| Analytics | ✅ | ❌ |
| n8n Environments | ✅ | ❌ |
| System Health | ✅ | ❌ |

## Definition of Done

- [ ] TDD: Tests written FIRST
- [ ] All tests passing
- [ ] Code coverage >= 80%
- [ ] ADMIN role enforced
- [ ] Responsive design
- [ ] Accessibility tested
- [ ] Documentation (WHAT/WHY/HOW)
- [ ] Code review approved
