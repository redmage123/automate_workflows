# Workflows Sub-Board

**Parent**: Master Kanban Board
**Sprint**: 5 (Workflow Automation)
**Focus**: n8n integration, workflow templates, execution tracking

---

## 🔴 Blocked

*None currently*

---

## 🟡 In Progress

*None currently*

---

## ⚪ Todo (Priority Order)

### N8N-001: N8nEnvironment Model + DAO (3 points)
**Priority**: P1
**Dependencies**: None

**Description**:
Create model for storing n8n instance configurations.

**Fields**:
- id, name, api_url
- api_key_encrypted (Fernet)
- is_active, created_at, updated_at

**Acceptance Criteria**:
- [ ] Model with all fields
- [ ] DAO with CRUD operations
- [ ] API key never stored in plaintext
- [ ] Connection test method
- [ ] Unit tests

---

### N8N-002: n8n API Client Service (8 points)
**Priority**: P1
**Dependencies**: None

**Description**:
Service for interacting with n8n REST API.

**Operations**:
- List workflows
- Get workflow by ID
- Create workflow
- Update workflow
- Execute workflow
- Get executions

**Acceptance Criteria**:
- [ ] N8nClient class
- [ ] API key decryption on use
- [ ] Error handling (N8nError)
- [ ] Retry logic for transient failures
- [ ] Rate limiting respect
- [ ] Unit tests with mocked API

---

### N8N-003: Encryption Service (Fernet) (5 points)
**Priority**: P1
**Dependencies**: None

**Description**:
Service for encrypting sensitive data at rest.

**Acceptance Criteria**:
- [ ] Fernet key from env variable
- [ ] encrypt(plaintext) -> ciphertext
- [ ] decrypt(ciphertext) -> plaintext
- [ ] Key rotation support
- [ ] Tests for encrypt/decrypt round-trip

---

### N8N-004: API Key Encryption/Decryption (3 points)
**Priority**: P1
**Dependencies**: N8N-003

**Description**:
Integrate encryption with n8n environment storage.

**Acceptance Criteria**:
- [ ] API key encrypted before DB storage
- [ ] API key decrypted when needed for API calls
- [ ] Key masking in logs and API responses
- [ ] Migration to encrypt existing keys

---

### N8N-005: CRUD n8n Environments (Admin) (5 points)
**Priority**: P1
**Dependencies**: N8N-001

**Description**:
API endpoints for managing n8n environments.

**Acceptance Criteria**:
- [ ] POST /api/admin/n8n-environments
- [ ] GET /api/admin/n8n-environments
- [ ] PUT /api/admin/n8n-environments/{id}
- [ ] DELETE /api/admin/n8n-environments/{id}
- [ ] Connection test endpoint
- [ ] ADMIN only

---

### WF-001: WorkflowTemplate Model + DAO (3 points)
**Priority**: P1
**Dependencies**: None

**Description**:
Create model for workflow templates.

**Fields**:
- id, name, description, category
- n8n_workflow_json (the template)
- parameters (JSON schema for inputs)
- is_active, created_at, updated_at

**Acceptance Criteria**:
- [ ] Model with all fields
- [ ] DAO with CRUD operations
- [ ] Category filtering
- [ ] Parameter schema validation
- [ ] Unit tests

---

### WF-002: WorkflowInstance Model + DAO (5 points)
**Priority**: P1
**Dependencies**: PROJ-001, WF-001

**Description**:
Create model for deployed workflow instances.

**Fields**:
- id, org_id, project_id
- template_id, environment_id
- n8n_workflow_id (ID in n8n)
- parameters (configured values)
- status (ACTIVE, PAUSED, ERROR)
- created_at, updated_at

**Acceptance Criteria**:
- [ ] Model with all fields
- [ ] DAO with CRUD operations
- [ ] Org-scoped queries
- [ ] Link to project
- [ ] Unit tests

---

### WF-003: ExecutionLog Model + DAO (3 points)
**Priority**: P1
**Dependencies**: WF-002

**Description**:
Create model for workflow execution history.

**Fields**:
- id, workflow_instance_id, org_id
- n8n_execution_id
- status (SUCCESS, FAILED, RUNNING)
- started_at, finished_at
- error_message, execution_data (JSON)

**Acceptance Criteria**:
- [ ] Model with all fields
- [ ] DAO with CRUD operations
- [ ] Org-scoped queries
- [ ] Pagination for large histories
- [ ] Unit tests

---

### WF-004: Template Library Seed Data (5 points)
**Priority**: P2
**Dependencies**: WF-001

**Description**:
Pre-populate workflow template library.

**Templates**:
- Email automation (send on trigger)
- Data sync (CRM to spreadsheet)
- Form processing (submission to database)
- Notification bot (Slack/Email)
- Scheduled report generation

**Acceptance Criteria**:
- [ ] 5+ templates created
- [ ] Categories assigned
- [ ] Parameters documented
- [ ] Alembic seed migration
- [ ] Templates work in n8n

---

### WF-005: Create Workflow from Template (8 points)
**Priority**: P1
**Dependencies**: WF-002, N8N-002

**Description**:
Deploy workflow instance from template to n8n.

**Acceptance Criteria**:
- [ ] POST /api/workflows (ADMIN)
- [ ] Select template and project
- [ ] Configure parameters
- [ ] Template variables replaced
- [ ] Workflow created in n8n
- [ ] n8n_workflow_id stored
- [ ] Audit log entry

---

### WF-006: Trigger Workflow Execution (8 points)
**Priority**: P1
**Dependencies**: WF-002, N8N-002

**Description**:
Manually trigger workflow execution.

**Acceptance Criteria**:
- [ ] POST /api/workflows/{id}/execute
- [ ] ADMIN only
- [ ] Call n8n execute API
- [ ] Create execution log entry
- [ ] Return execution ID
- [ ] Async (don't wait for completion)

---

### WF-007: n8n Webhook Receiver (8 points)
**Priority**: P1
**Dependencies**: WF-003

**Description**:
Receive callbacks from n8n workflows.

**Acceptance Criteria**:
- [ ] POST /api/webhooks/n8n/{workflow_id}
- [ ] Signature verification
- [ ] Update execution status
- [ ] Store execution data
- [ ] Trigger notifications if needed
- [ ] 200 response for n8n

---

### WF-008: Execution Log Storage (3 points)
**Priority**: P1
**Dependencies**: WF-007

**Description**:
Store and index execution history.

**Acceptance Criteria**:
- [ ] Execution data stored in DB
- [ ] Large payloads in S3 (link in DB)
- [ ] Retention policy (30 days default)
- [ ] Searchable by date, status

---

### WF-009: Template Library UI (8 points)
**Priority**: P2
**Dependencies**: WF-001

**Description**:
Frontend page for browsing workflow templates.

**Acceptance Criteria**:
- [ ] Grid/list view of templates
- [ ] Category filtering
- [ ] Search by name/description
- [ ] Template detail modal
- [ ] "Deploy" button (ADMIN)

---

### WF-010: Workflow Instance List UI (5 points)
**Priority**: P2
**Dependencies**: WF-002

**Description**:
Frontend page listing deployed workflows.

**Acceptance Criteria**:
- [ ] Table with status indicators
- [ ] Link to project
- [ ] Last execution status
- [ ] Execute button
- [ ] View logs button

---

### WF-011: Execution Logs Viewer UI (5 points)
**Priority**: P2
**Dependencies**: WF-003

**Description**:
Frontend page for viewing execution history.

**Acceptance Criteria**:
- [ ] Timeline of executions
- [ ] Status badges (success/fail)
- [ ] Duration display
- [ ] Expandable details
- [ ] Error message display

---

## n8n Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AUTOMATION PLATFORM                          │
│                                                                  │
│  ┌────────────────┐    ┌────────────────┐    ┌───────────────┐ │
│  │ Template       │───▶│ N8nClient      │───▶│ n8n API       │ │
│  │ Library        │    │ Service        │    │               │ │
│  └────────────────┘    └────────────────┘    └───────────────┘ │
│          │                     │                     │          │
│          │                     │                     │          │
│          ▼                     ▼                     ▼          │
│  ┌────────────────┐    ┌────────────────┐    ┌───────────────┐ │
│  │ Workflow       │───▶│ Execute        │───▶│ n8n Workflow  │ │
│  │ Instance       │    │ Workflow       │    │ Execution     │ │
│  └────────────────┘    └────────────────┘    └───────┬───────┘ │
│          │                                           │          │
│          │                                           │ Webhook  │
│          │                     ┌─────────────────────┘          │
│          ▼                     ▼                                │
│  ┌────────────────┐    ┌────────────────┐                      │
│  │ Execution      │◀───│ Webhook        │                      │
│  │ Log            │    │ Handler        │                      │
│  └────────────────┘    └────────────────┘                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Security Considerations

### API Key Storage
- Keys encrypted with Fernet (AES-128)
- Encryption key from environment variable
- Keys decrypted only when needed
- Never logged or returned in API responses

### n8n Webhook Security
- Per-workflow secret tokens
- Signature verification
- IP allowlisting (optional)
- Rate limiting

## Definition of Done

- [ ] TDD: Tests written FIRST
- [ ] All tests passing
- [ ] Code coverage >= 80%
- [ ] API keys encrypted
- [ ] Webhook signatures verified
- [ ] DAO pattern used
- [ ] Documentation (WHAT/WHY/HOW)
- [ ] Code review approved
