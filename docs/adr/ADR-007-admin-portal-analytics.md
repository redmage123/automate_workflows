# ADR-007: Admin Portal & Analytics Dashboard

## Status
Accepted

## Context

The Automation Services Platform needs administrative tools for:
1. Managing users across organizations
2. Managing organizations
3. Viewing audit logs for security compliance
4. Business analytics and metrics dashboards

Administrators need visibility into platform operations, user activity, revenue metrics,
and project performance to make informed business decisions.

## Decision

We will implement an Admin Portal with the following components:

### 1. User Management (ADMIN-002)

**API Endpoints**:
- `GET /api/admin/users` - List all users (with pagination, filters)
- `GET /api/admin/users/{id}` - Get user details
- `POST /api/admin/users` - Create user (admin-initiated)
- `PUT /api/admin/users/{id}` - Update user
- `DELETE /api/admin/users/{id}` - Deactivate user (soft delete)
- `POST /api/admin/users/{id}/reset-password` - Force password reset

**Features**:
- Filter by organization, role, status
- Search by email, name
- Bulk operations (export, status change)
- Activity summary per user

### 2. Organization Management (ADMIN-003)

**API Endpoints**:
- `GET /api/admin/organizations` - List all organizations
- `GET /api/admin/organizations/{id}` - Get organization details with stats
- `PUT /api/admin/organizations/{id}` - Update organization
- `POST /api/admin/organizations/{id}/suspend` - Suspend organization
- `POST /api/admin/organizations/{id}/activate` - Reactivate organization

**Features**:
- Organization health metrics (active users, projects, revenue)
- Subscription status
- Usage quotas and limits

### 3. Audit Log Viewer (ADMIN-005)

**API Endpoints**:
- `GET /api/admin/audit-logs` - List audit logs (paginated)
- `GET /api/admin/audit-logs/export` - Export logs (CSV/JSON)

**Filters**:
- Date range
- User
- Organization
- Resource type
- Action type
- IP address

**Features**:
- Real-time log streaming (WebSocket future enhancement)
- Searchable by resource ID
- Immutable records (no delete/update)

### 4. Analytics Endpoints

#### Project Metrics (ANALYTICS-001)
```
GET /api/admin/analytics/projects
```
Returns:
- Total projects by status
- Projects created over time
- Average project duration
- Projects by organization

#### Revenue Metrics (ANALYTICS-002)
```
GET /api/admin/analytics/revenue
```
Returns:
- Total revenue (MTD, YTD, all-time)
- Revenue by organization
- Revenue trend over time
- Average deal size
- Payment method breakdown

#### User Activity Metrics (ANALYTICS-003)
```
GET /api/admin/analytics/users
```
Returns:
- Active users (DAU, WAU, MAU)
- New user registrations over time
- User retention metrics
- Most active users
- Login frequency

### 5. Dashboard Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Admin Dashboard                           │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│   Users     │    Orgs     │   Revenue   │    Activity      │
│   Count     │   Count     │    MTD      │     DAU          │
│    42       │     12      │   $45,230   │      28          │
├─────────────┴─────────────┴─────────────┴──────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Revenue Trend Chart                     │   │
│  │  $50k ─────────────────────────────────────────     │   │
│  │  $40k ──────────────────────/─────────────────     │   │
│  │  $30k ─────────────────/────────────────────     │   │
│  │  $20k ────────────/───────────────────────     │   │
│  │       Jan  Feb  Mar  Apr  May  Jun  Jul  Aug       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────────┐   │
│  │  Projects by Status  │  │    Recent Activity       │   │
│  │  ● Active    45%     │  │  • User login 2m ago     │   │
│  │  ● Complete  35%     │  │  • Project created 5m    │   │
│  │  ● On Hold   20%     │  │  • Payment received 10m  │   │
│  └──────────────────────┘  └──────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6. UI Components

**Admin Dashboard (ADMIN-001)**:
- Summary cards (KPIs)
- Quick actions (create user, view alerts)
- Recent activity feed
- System health indicators

**User Management UI**:
- Data table with sorting/filtering
- User detail modal/page
- Inline editing
- Role management

**Organization Management UI**:
- Organization cards with metrics
- Detail page with usage stats
- Subscription management

**Audit Log Viewer UI**:
- Filterable log table
- Log detail expandable rows
- Export functionality
- Date range picker

**Analytics Dashboard (ANALYTICS-004)**:
- Chart.js or Recharts for visualizations
- Date range selector
- Comparison periods
- Exportable reports

### 7. UI Polish Items

**Error Pages (POLISH-001)**:
- 404 Not Found - Friendly message with navigation
- 500 Server Error - Generic error with support contact
- 403 Forbidden - Access denied message

**Loading States (POLISH-002)**:
- Skeleton loaders for tables
- Spinner for async actions
- Progress bars for uploads
- Optimistic updates

**Toast Notifications (POLISH-003)**:
- Success (green) - Action completed
- Error (red) - Action failed
- Warning (yellow) - Attention needed
- Info (blue) - Informational
- Auto-dismiss with configurable duration
- Action buttons (Undo, Retry)

## Implementation Guide

### Phase 1: Backend API (ADMIN-002, ADMIN-003, ADMIN-005)

1. Create `app/api/admin.py` router:
   - User CRUD endpoints
   - Organization management endpoints
   - Audit log endpoints
   - All require ADMIN role

2. Extend existing DAOs:
   - `UserDAO.list_all()` - Cross-org user listing
   - `OrganizationDAO.get_with_stats()` - Org with metrics
   - `AuditLogDAO.search()` - Advanced filtering

3. Write tests:
   - Unit tests for DAO methods
   - Integration tests for API endpoints

### Phase 2: Analytics API (ANALYTICS-001, 002, 003)

1. Create `app/api/analytics.py` router:
   - Project metrics endpoint
   - Revenue metrics endpoint
   - User activity endpoint

2. Create `app/services/analytics_service.py`:
   - Aggregate queries with date ranges
   - Caching for expensive queries (Redis)
   - Time series data formatting

3. Write tests:
   - Unit tests with mock data
   - Integration tests with test database

### Phase 3: Frontend Dashboard (ADMIN-001, ANALYTICS-004)

1. Create admin pages:
   - `src/pages/admin/AdminDashboard.tsx`
   - `src/pages/admin/UsersPage.tsx`
   - `src/pages/admin/OrganizationsPage.tsx`
   - `src/pages/admin/AuditLogsPage.tsx`
   - `src/pages/admin/AnalyticsPage.tsx`

2. Create chart components:
   - `src/components/charts/LineChart.tsx`
   - `src/components/charts/PieChart.tsx`
   - `src/components/charts/BarChart.tsx`

3. Create shared components:
   - `src/components/DataTable.tsx`
   - `src/components/StatCard.tsx`
   - `src/components/DateRangePicker.tsx`

### Phase 4: UI Polish (POLISH-001, 002, 003)

1. Error pages:
   - `src/pages/errors/NotFoundPage.tsx`
   - `src/pages/errors/ServerErrorPage.tsx`
   - `src/pages/errors/ForbiddenPage.tsx`

2. Loading components:
   - `src/components/Skeleton.tsx`
   - `src/components/Spinner.tsx`
   - `src/components/ProgressBar.tsx`

3. Toast system:
   - `src/components/Toast.tsx`
   - `src/hooks/useToast.ts`
   - `src/store/toastStore.ts`

## Security Considerations

1. **Access Control**:
   - All admin endpoints require ADMIN role
   - Rate limiting on sensitive operations
   - IP allowlisting option for admin routes

2. **Audit Logging**:
   - Log all admin actions
   - Include IP address and user agent
   - Immutable audit trail

3. **Data Protection**:
   - Mask sensitive data in logs (passwords, tokens)
   - PII handling compliance
   - Export restrictions

4. **OWASP Compliance**:
   - A01: Admin-only access enforcement
   - A09: Comprehensive audit logging
   - A04: Secure by default settings

## Consequences

### Positive
- Complete visibility into platform operations
- Data-driven business decisions
- Compliance-ready audit trail
- Professional admin experience

### Negative
- Additional complexity in permission model
- Performance considerations for analytics queries
- Maintenance of dashboard components

### Mitigation
- Cache expensive analytics queries
- Paginate all list endpoints
- Use database indexes for audit log queries
- Implement lazy loading for dashboard widgets
