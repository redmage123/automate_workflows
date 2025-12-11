# ADR-004: Workflow Automation with n8n Integration

## Status
Accepted

## Context

The Automation Services Platform needs to provide workflow automation capabilities to clients. n8n is an open-source workflow automation tool that can be self-hosted and provides a visual workflow builder with hundreds of integrations.

### Requirements
1. **N8N-001**: Manage multiple n8n environments per organization
2. **N8N-002**: API client for n8n operations
3. **N8N-003/004**: Secure storage of API keys with encryption
4. **WF-001/002/003**: Workflow templates, instances, and execution logging
5. **WF-005/006/007**: Create, trigger, and monitor workflows
6. **OWASP A02**: Sensitive data (API keys) must be encrypted at rest

### Design Constraints
- n8n instances are external services, not managed by our platform
- API keys must be encrypted using Fernet (symmetric encryption)
- Workflows are linked to projects for client billing and tracking
- Execution logs enable debugging and audit compliance

## Decision

### 1. Data Model Architecture

```
N8nEnvironment (1:1 with Organization)
├── id, org_id (FK)
├── name (e.g., "Production n8n")
├── base_url (https://n8n.example.com)
├── api_key_encrypted (Fernet-encrypted API key)
├── is_active, webhook_url
└── created_at, updated_at

WorkflowTemplate (Global library)
├── id
├── name, description, category
├── n8n_template_id (template workflow in n8n)
├── default_parameters (JSONB)
├── is_public (available to all orgs)
├── created_by_org_id (null = system template)
└── created_at, updated_at

WorkflowInstance (Per org/project)
├── id, org_id (FK), project_id (FK)
├── template_id (FK to WorkflowTemplate)
├── n8n_environment_id (FK)
├── n8n_workflow_id (created workflow ID in n8n)
├── name, status (DRAFT/ACTIVE/PAUSED/ERROR/DELETED)
├── parameters (JSONB, merged with template defaults)
├── last_execution_at
└── created_at, updated_at

ExecutionLog (Per workflow instance)
├── id, workflow_instance_id (FK)
├── n8n_execution_id (from n8n API)
├── status (RUNNING/SUCCESS/FAILED/CANCELLED)
├── started_at, finished_at
├── input_data, output_data (JSONB)
├── error_message (if failed)
└── created_at
```

### 2. Encryption Service (OWASP A02)

API keys are encrypted at rest using Fernet symmetric encryption:

```python
from cryptography.fernet import Fernet

class EncryptionService:
    """
    Encrypts/decrypts sensitive data using Fernet.

    WHY: OWASP A02 requires protecting sensitive data at rest.
    Fernet provides authenticated encryption (AES-128-CBC + HMAC).
    """

    def __init__(self, key: bytes):
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt string, return base64-encoded ciphertext."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt base64-encoded ciphertext to string."""
        return self._fernet.decrypt(ciphertext.encode()).decode()
```

Key management:
- Encryption key stored in environment variable (`ENCRYPTION_KEY`)
- Key generated with `Fernet.generate_key()`
- 32-byte URL-safe base64-encoded key

### 3. n8n API Client

```python
class N8nClient:
    """
    HTTP client for n8n REST API.

    WHAT: Manages workflows, executions, and webhooks.

    WHY: Abstracts n8n API complexity and handles:
    - Authentication (API key header)
    - Error handling and retries
    - Response parsing
    """

    async def create_workflow(self, workflow_data: dict) -> dict:
        """Create new workflow in n8n."""

    async def get_workflow(self, workflow_id: str) -> dict:
        """Get workflow by ID."""

    async def activate_workflow(self, workflow_id: str) -> dict:
        """Activate/enable workflow."""

    async def deactivate_workflow(self, workflow_id: str) -> dict:
        """Deactivate/pause workflow."""

    async def delete_workflow(self, workflow_id: str) -> None:
        """Delete workflow."""

    async def execute_workflow(self, workflow_id: str, data: dict = None) -> dict:
        """Trigger workflow execution."""

    async def get_execution(self, execution_id: str) -> dict:
        """Get execution status and data."""

    async def list_executions(self, workflow_id: str, limit: int = 20) -> list:
        """List recent executions for workflow."""
```

### 4. Workflow Status State Machine

```
WorkflowInstance Status:
  DRAFT ──────────────► ACTIVE
    │                     │
    │                     ▼
    │                   PAUSED ◄──► ACTIVE
    │                     │
    ▼                     ▼
  DELETED ◄──────────── ERROR
                          │
                          ▼
                       ACTIVE (after fix)
```

```
ExecutionLog Status:
  RUNNING ──► SUCCESS
     │
     └──────► FAILED
     │
     └──────► CANCELLED
```

### 5. API Endpoints

**N8N Environment Management (Admin only)**:
```
POST   /api/n8n-environments          Create environment
GET    /api/n8n-environments          List environments
GET    /api/n8n-environments/{id}     Get environment
PATCH  /api/n8n-environments/{id}     Update environment
DELETE /api/n8n-environments/{id}     Delete environment
POST   /api/n8n-environments/{id}/test  Test connection
```

**Workflow Templates**:
```
GET    /api/workflow-templates        List templates (public + org)
GET    /api/workflow-templates/{id}   Get template details
POST   /api/workflow-templates        Create org template (Admin)
PATCH  /api/workflow-templates/{id}   Update template (Admin)
DELETE /api/workflow-templates/{id}   Delete template (Admin)
```

**Workflow Instances**:
```
POST   /api/workflows                 Create from template
GET    /api/workflows                 List instances
GET    /api/workflows/{id}            Get instance details
PATCH  /api/workflows/{id}            Update instance
DELETE /api/workflows/{id}            Delete (marks as DELETED)
POST   /api/workflows/{id}/activate   Activate in n8n
POST   /api/workflows/{id}/pause      Pause in n8n
POST   /api/workflows/{id}/execute    Trigger execution
GET    /api/workflows/{id}/executions List executions
```

**Webhook Receiver**:
```
POST   /api/webhooks/n8n/{instance_id}  Receive n8n webhook callbacks
```

### 6. Security Considerations

1. **Encryption at Rest (OWASP A02)**:
   - API keys encrypted with Fernet before storage
   - Encryption key managed via environment variable
   - Never log decrypted keys

2. **Access Control (OWASP A01)**:
   - N8n environments: ADMIN only
   - Templates: Public readable, ADMIN writable
   - Instances: Org-scoped, all roles can view/execute
   - Webhook endpoint validates instance ownership

3. **Input Validation (OWASP A03)**:
   - Validate n8n base URLs (https only in production)
   - Sanitize workflow parameters
   - Validate webhook payloads

4. **Webhook Security**:
   - Instance-specific webhook URLs (contains instance_id)
   - Validate caller (optional n8n signature header)
   - Rate limiting on webhook endpoint

### 7. Database Migration

```python
# 007_add_workflow_tables.py

def upgrade():
    # Create workflow status enum
    workflow_status = sa.Enum(
        'draft', 'active', 'paused', 'error', 'deleted',
        name='workflowstatus'
    )
    workflow_status.create(op.get_bind())

    # Create execution status enum
    execution_status = sa.Enum(
        'running', 'success', 'failed', 'cancelled',
        name='executionstatus'
    )
    execution_status.create(op.get_bind())

    # N8n environments table
    op.create_table(
        'n8n_environments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('org_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('webhook_url', sa.String(500)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
        sa.UniqueConstraint('org_id', 'name', name='uq_n8n_env_org_name'),
    )

    # Workflow templates table
    op.create_table(
        'workflow_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('category', sa.String(100)),
        sa.Column('n8n_template_id', sa.String(100)),
        sa.Column('default_parameters', sa.JSON()),
        sa.Column('is_public', sa.Boolean(), default=True),
        sa.Column('created_by_org_id', sa.Integer(), sa.ForeignKey('organizations.id')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )

    # Workflow instances table
    op.create_table(
        'workflow_instances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('org_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id')),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('workflow_templates.id')),
        sa.Column('n8n_environment_id', sa.Integer(), sa.ForeignKey('n8n_environments.id')),
        sa.Column('n8n_workflow_id', sa.String(100)),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', workflow_status, default='draft'),
        sa.Column('parameters', sa.JSON()),
        sa.Column('last_execution_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )

    # Execution logs table
    op.create_table(
        'execution_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workflow_instance_id', sa.Integer(),
                  sa.ForeignKey('workflow_instances.id'), nullable=False),
        sa.Column('n8n_execution_id', sa.String(100)),
        sa.Column('status', execution_status, default='running'),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime()),
        sa.Column('input_data', sa.JSON()),
        sa.Column('output_data', sa.JSON()),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Indexes
    op.create_index('ix_workflow_instances_org_id', 'workflow_instances', ['org_id'])
    op.create_index('ix_workflow_instances_project_id', 'workflow_instances', ['project_id'])
    op.create_index('ix_execution_logs_instance_id', 'execution_logs', ['workflow_instance_id'])
    op.create_index('ix_execution_logs_status', 'execution_logs', ['status'])
```

## Consequences

### Positive
- **Flexible n8n Integration**: Support multiple n8n instances per org
- **Secure API Keys**: Fernet encryption meets OWASP A02
- **Audit Trail**: Execution logs for debugging and compliance
- **Template Library**: Reusable workflow templates speed up deployment
- **Project Linking**: Workflows tied to projects for billing/tracking

### Negative
- **External Dependency**: n8n availability affects workflow execution
- **Key Management**: Encryption key must be securely managed
- **Webhook Complexity**: Need to handle n8n callbacks reliably

### Risks
- **n8n API Changes**: Version lock n8n or handle API evolution
- **Execution Timeouts**: Long-running workflows may timeout
- **Data Volume**: Execution logs may grow large (consider retention policy)

## Implementation Guide

### Phase 1: Core Infrastructure (N8N-001 to N8N-004)
1. Create encryption service with Fernet
2. Create N8nEnvironment model and DAO
3. Create n8n API client service
4. Create N8nEnvironment API endpoints

### Phase 2: Workflow Models (WF-001 to WF-003)
1. Create WorkflowTemplate model and DAO
2. Create WorkflowInstance model and DAO
3. Create ExecutionLog model and DAO
4. Seed template library data

### Phase 3: Workflow Operations (WF-005 to WF-008)
1. Implement create workflow from template
2. Implement activate/pause/execute endpoints
3. Implement webhook receiver for callbacks
4. Implement execution log storage

### Phase 4: Frontend UI (WF-009 to WF-010)
1. Template library browser
2. Workflow instance management UI
3. Execution history viewer

## References
- [n8n API Documentation](https://docs.n8n.io/api/)
- [Fernet Encryption](https://cryptography.io/en/latest/fernet/)
- [OWASP A02: Cryptographic Failures](https://owasp.org/Top10/A02_2021-Cryptographic_Failures/)
