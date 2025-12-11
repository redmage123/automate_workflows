# ADR-002: Projects and Proposals API

## Status
Accepted

## Context

Sprint 3 requires implementing the Projects and Proposals API endpoints. The models, DAOs, and migrations already exist. We need to:

1. Create Pydantic schemas for request/response validation
2. Implement API routers with proper RBAC and org-scoping
3. Support the full lifecycle for both entities

### Business Requirements

**Projects**:
- Central business entity connecting clients to automation work
- Track status through lifecycle: draft -> proposal_sent -> approved -> in_progress -> completed
- Support priority levels for resource allocation
- Track estimated vs actual hours

**Proposals**:
- Formalize pricing and scope agreements
- Support line items with automatic total calculation
- Track approval workflow: draft -> sent -> viewed -> approved/rejected
- Support versioning for revisions

### Security Requirements (OWASP A01: Broken Access Control)

- All endpoints must enforce org-scoping
- ADMINs can create/update/delete projects and proposals
- CLIENTs can view their org's projects and proposals
- CLIENTs can approve/reject proposals for their projects

## Decision

### API Design

#### Project Endpoints

| Method | Path | Description | RBAC |
|--------|------|-------------|------|
| POST | /projects | Create project | ADMIN |
| GET | /projects | List projects (paginated) | AUTH |
| GET | /projects/{id} | Get project details | AUTH (org-scoped) |
| PUT | /projects/{id} | Update project | ADMIN (org-scoped) |
| DELETE | /projects/{id} | Delete project | ADMIN (org-scoped) |
| PATCH | /projects/{id}/status | Update project status | ADMIN (org-scoped) |
| GET | /projects/{id}/proposals | Get project's proposals | AUTH (org-scoped) |

#### Proposal Endpoints

| Method | Path | Description | RBAC |
|--------|------|-------------|------|
| POST | /proposals | Create proposal | ADMIN |
| GET | /proposals | List proposals (paginated) | AUTH |
| GET | /proposals/{id} | Get proposal details | AUTH (org-scoped) |
| PUT | /proposals/{id} | Update proposal | ADMIN (org-scoped, draft only) |
| DELETE | /proposals/{id} | Delete proposal | ADMIN (org-scoped, draft only) |
| POST | /proposals/{id}/send | Send proposal to client | ADMIN (org-scoped) |
| POST | /proposals/{id}/approve | Approve proposal | AUTH (org-scoped) |
| POST | /proposals/{id}/reject | Reject proposal | AUTH (org-scoped) |
| POST | /proposals/{id}/revise | Create revision | ADMIN (org-scoped) |

### Schema Design

#### Project Schemas

```python
# Create
ProjectCreate:
    name: str (required, max 255)
    description: str | None
    priority: ProjectPriority = MEDIUM
    estimated_hours: float | None
    start_date: datetime | None
    due_date: datetime | None

# Update (partial)
ProjectUpdate:
    name: str | None
    description: str | None
    priority: ProjectPriority | None
    estimated_hours: float | None
    actual_hours: float | None
    start_date: datetime | None
    due_date: datetime | None

# Response
ProjectResponse:
    id: int
    name: str
    description: str | None
    status: ProjectStatus
    priority: ProjectPriority
    org_id: int
    estimated_hours: float | None
    actual_hours: float | None
    start_date: datetime | None
    due_date: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_active: bool (computed)
    is_overdue: bool (computed)

# List Response
ProjectListResponse:
    items: list[ProjectResponse]
    total: int
    skip: int
    limit: int
```

#### Proposal Schemas

```python
# Line Item
LineItem:
    description: str
    quantity: float
    unit_price: float
    amount: float  # computed: quantity * unit_price

# Create
ProposalCreate:
    title: str (required, max 255)
    description: str | None
    project_id: int (required)
    line_items: list[LineItem] | None
    discount_percent: float | None = 0
    tax_percent: float | None = 0
    valid_until: datetime | None
    notes: str | None
    client_notes: str | None
    terms: str | None

# Update (partial, draft only)
ProposalUpdate:
    title: str | None
    description: str | None
    line_items: list[LineItem] | None
    discount_percent: float | None
    tax_percent: float | None
    valid_until: datetime | None
    notes: str | None
    client_notes: str | None
    terms: str | None

# Response
ProposalResponse:
    id: int
    title: str
    description: str | None
    status: ProposalStatus
    project_id: int
    org_id: int
    version: int
    previous_version_id: int | None
    line_items: list[LineItem] | None
    subtotal: float
    discount_percent: float | None
    discount_amount: float | None
    tax_percent: float | None
    tax_amount: float | None
    total: float
    valid_until: datetime | None
    sent_at: datetime | None
    viewed_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    notes: str | None  # Only for ADMIN
    client_notes: str | None
    terms: str | None
    created_at: datetime
    updated_at: datetime
    is_editable: bool (computed)
    is_expired: bool (computed)
    can_be_approved: bool (computed)
```

### Business Logic

1. **Project Creation**: Projects start in DRAFT status
2. **Proposal Approval**: When approved, project status updates to APPROVED
3. **Line Item Calculation**: Totals auto-calculated when line items change
4. **Versioning**: Revisions create new proposal with incremented version
5. **Expiration**: Expired proposals cannot be approved

### Error Handling

All errors use custom exceptions:
- `ResourceNotFoundError` (404): Project/Proposal not found
- `ValidationError` (400): Invalid input data
- `AuthorizationError` (403): RBAC violation
- `OrganizationAccessDenied` (403): Cross-org access attempt
- `InvalidStateTransitionError` (400): Invalid status change

## Consequences

### Positive
- Consistent API design following existing patterns
- Strong org-scoping for multi-tenancy security
- Clear separation of ADMIN vs CLIENT permissions
- Computed fields reduce client-side logic

### Negative
- Denormalized org_id on proposals adds some redundancy
- Line items in JSONB less queryable than separate table

### Risks
- Large proposal lists could be slow (mitigated by pagination)
- Concurrent proposal approvals could conflict (future: locking)

## Implementation Guide

1. Create `backend/app/schemas/project.py`
2. Create `backend/app/schemas/proposal.py`
3. Create `backend/app/api/projects.py`
4. Create `backend/app/api/proposals.py`
5. Register routers in `backend/app/main.py`
6. Write unit tests for DAOs
7. Write integration tests for API endpoints
8. Update Kanban board

## References

- [ADR-001: Project Structure](./ADR-001-project-structure.md)
- [OWASP A01: Broken Access Control](https://owasp.org/Top10/A01_2021-Broken_Access_Control/)
