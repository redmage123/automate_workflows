# ADR-010: Natural Language Workflow Creation with Visual Designer Options

## Status
Accepted

## Context

The Automation Services Platform currently requires users to define workflows in JSON format, which creates a significant barrier to entry for non-technical users. Users have requested two improvements:

1. **Natural Language Input**: Ability to describe workflows in plain English and have the system convert them to n8n-compatible JSON
2. **Visual Designer Integration**: Option to use a graphical workflow designer instead of JSON

### Requirements
1. **NL-001**: Accept plain text workflow descriptions
2. **NL-002**: Convert natural language to n8n workflow JSON using AI
3. **NL-003**: Validate generated workflows before deployment
4. **NL-004**: Allow users to review/edit generated JSON before saving
5. **VIS-001**: Research and recommend visual workflow designer options

### Design Constraints
- Must integrate with existing n8n infrastructure
- AI model must have access to n8n node type documentation
- Generated workflows must be valid n8n JSON format
- Security: No direct execution of user-provided prompts without validation

## Decision

### 1. Natural Language to Workflow Conversion Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  User Input     │     │  AI Conversion  │     │  n8n API        │
│  (Plain Text)   │────>│  Service        │────>│  (JSON)         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐
                        │  Validation     │
                        │  & Preview      │
                        └─────────────────┘
```

### 2. AI Service Implementation

We'll use Claude API (via Anthropic SDK) for natural language understanding:

```python
class WorkflowAIService:
    """
    AI-powered workflow generation from natural language.

    WHAT: Converts plain text descriptions to n8n workflow JSON.

    WHY: Enables non-technical users to create automations by
    describing what they want in natural language.

    HOW: Uses Claude API with a specialized system prompt containing
    n8n node type documentation and workflow structure rules.
    """

    async def generate_workflow(
        self,
        description: str,
        context: Optional[dict] = None,
    ) -> WorkflowGenerationResult:
        """
        Generate n8n workflow from natural language description.

        Args:
            description: Plain text description of desired workflow
            context: Optional context (available integrations, credentials, etc.)

        Returns:
            Generated workflow with name, nodes, connections, and confidence score
        """
        pass

    async def refine_workflow(
        self,
        workflow: dict,
        feedback: str,
    ) -> WorkflowGenerationResult:
        """
        Refine an existing workflow based on user feedback.

        Args:
            workflow: Current workflow JSON
            feedback: User's refinement request

        Returns:
            Updated workflow
        """
        pass
```

### 3. System Prompt for Workflow Generation

The AI service will use a detailed system prompt with:
- n8n workflow JSON structure documentation
- Common n8n node types and their parameters
- Best practices for workflow design
- Output format requirements

```python
N8N_WORKFLOW_SYSTEM_PROMPT = '''
You are an expert at creating n8n workflows. Convert the user's description
into a valid n8n workflow JSON structure.

## n8n Workflow Structure
A workflow consists of:
- nodes: Array of node objects
- connections: Object mapping node outputs to inputs
- settings: Workflow settings

## Node Structure
Each node must have:
- id: Unique identifier (uuid)
- name: Display name
- type: n8n node type (e.g., "n8n-nodes-base.webhook")
- position: [x, y] coordinates for visual layout
- parameters: Node-specific configuration

## Common Node Types
- n8n-nodes-base.webhook: HTTP webhook trigger
- n8n-nodes-base.httpRequest: Make HTTP requests
- n8n-nodes-base.if: Conditional branching
- n8n-nodes-base.set: Set/transform data
- n8n-nodes-base.function: JavaScript code execution
- n8n-nodes-base.slack: Slack integration
- n8n-nodes-base.email: Send emails (via SMTP)
- n8n-nodes-base.googleSheets: Google Sheets operations
- n8n-nodes-base.postgres: PostgreSQL database
- n8n-nodes-base.mysql: MySQL database

## Output Format
Return a JSON object with:
{
  "name": "Workflow Name",
  "nodes": [...],
  "connections": {...},
  "settings": {
    "executionOrder": "v1"
  },
  "explanation": "Brief explanation of what the workflow does",
  "confidence": 0.95  // How confident you are in the generation (0-1)
}
'''
```

### 4. API Endpoints

```
POST /api/workflows/generate-from-text
    Request: { "description": "When a new row is added to Google Sheet, send Slack notification" }
    Response: {
        "workflow": {...},
        "explanation": "...",
        "confidence": 0.95,
        "suggestions": ["You may want to add error handling", ...]
    }

POST /api/workflows/refine
    Request: { "workflow": {...}, "feedback": "Also add the row data to the Slack message" }
    Response: { "workflow": {...}, "explanation": "...", "changes": [...] }

POST /api/workflows/validate
    Request: { "workflow": {...} }
    Response: { "valid": true, "errors": [], "warnings": [...] }
```

### 5. Frontend Flow

1. User enters natural language description in a text area
2. System calls AI service to generate workflow
3. User sees generated workflow with:
   - Visual preview (node diagram)
   - JSON editor (collapsible)
   - AI explanation
   - Confidence score
4. User can:
   - Accept and save workflow
   - Provide feedback to refine
   - Manually edit JSON
   - Start over

### 6. Visual Designer Integration: n8n's Built-in Editor

**Decision**: Use n8n's native visual workflow editor directly.

n8n includes a powerful, full-featured graphical workflow designer. Instead of building our own or embedding a third-party tool, we leverage n8n's editor by:

1. **Direct Link**: "Design in n8n" button opens n8n's editor in a new tab
2. **Deep Linking**: Can link directly to specific workflows for editing
3. **Full Feature Access**: Users get all n8n capabilities (500+ nodes, testing, etc.)

#### Implementation
```python
# Backend endpoint returns n8n editor URL
@router.get("/environments/{id}/editor-url")
async def get_editor_url(id: int, workflow_id: str = None):
    env = await get_environment(id)
    if workflow_id:
        return {"editor_url": f"{env.base_url}/workflow/{workflow_id}"}
    return {"editor_url": f"{env.base_url}/workflow/new"}
```

#### User Flow
1. User clicks "Design in n8n" button
2. n8n editor opens in new tab
3. User designs workflow visually with full n8n features
4. User saves workflow in n8n (gets workflow ID)
5. User links workflow to project in our platform

#### Alternatives Considered (Not Chosen)
- **Langflow**: Focused on LLM pipelines, not general automation
- **React Flow Custom**: Significant development effort to match n8n features
- **n8n Embed/iframe**: Added complexity without clear benefit over direct link

### 7. Security Considerations

1. **Prompt Injection Prevention**:
   - Sanitize user input before sending to AI
   - Never execute generated code without validation
   - Use structured output parsing

2. **API Key Security**:
   - Anthropic API key stored encrypted (like n8n keys)
   - Rate limiting on generation endpoint
   - Audit logging for all generations

3. **Generated Workflow Validation**:
   - Validate all node types are known n8n nodes
   - Check for potentially dangerous operations
   - Require user confirmation before deployment

### 8. Database Schema

```python
# New table for tracking AI-generated workflows
class WorkflowGenerationLog(Base):
    """
    Tracks AI workflow generation attempts.

    WHY: Audit trail, improvement training data, debugging.
    """
    __tablename__ = "workflow_generation_logs"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    input_description = Column(Text, nullable=False)
    generated_workflow = Column(JSON)
    confidence_score = Column(Float)
    was_accepted = Column(Boolean, default=False)
    feedback = Column(Text)  # User feedback if they rejected/refined
    created_at = Column(DateTime, server_default=func.now())
```

## Consequences

### Positive
- **Lower Barrier to Entry**: Non-technical users can create workflows
- **Faster Prototyping**: Quick workflow generation from descriptions
- **Iterative Refinement**: AI can improve workflows based on feedback
- **Audit Trail**: All generations logged for improvement

### Negative
- **AI Dependency**: Requires Anthropic API (cost, availability)
- **Generation Accuracy**: AI may not perfectly understand complex requirements
- **Learning Curve**: Users need to learn effective prompting

### Risks
- **Cost Management**: AI API calls add operational cost
- **Prompt Injection**: Malicious inputs could attempt to exploit AI
- **Workflow Validity**: Generated workflows may have subtle issues

## Implementation Guide

### Phase 1: Backend AI Service
1. Create WorkflowAIService with Claude integration
2. Define comprehensive system prompt with n8n documentation
3. Create generation and refinement endpoints
4. Add validation service for generated workflows

### Phase 2: Frontend Natural Language UI
1. Add "Create from Description" option to workflow creation
2. Implement description input with suggestions
3. Build workflow preview component
4. Add refinement/feedback flow

### Phase 3: Visual Designer (Future)
1. Evaluate n8n embed mode for complex editing
2. Consider React Flow for simplified custom view
3. Implement if user demand warrants

## References
- [n8n Workflow JSON Structure](https://docs.n8n.io/workflows/)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [React Flow](https://reactflow.dev/)
- [Langflow](https://github.com/langflow-ai/langflow) (for reference only)
