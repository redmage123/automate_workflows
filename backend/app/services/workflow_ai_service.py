"""
AI-powered workflow generation service using OpenAI GPT.

WHAT: Converts natural language descriptions into n8n workflow JSON.

WHY: Enables non-technical users to create automations by describing
what they want in plain English, lowering the barrier to workflow creation.

Security Considerations (OWASP):
- A03 Injection: Sanitize user input before AI processing
- A04 Insecure Design: Validate all generated output before use
- Never execute generated code without validation

HOW: Uses OpenAI GPT API with a specialized system prompt containing
n8n workflow structure documentation to generate valid workflow JSON.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError

from app.core.config import settings
from app.core.exceptions import (
    AIServiceError,
    AIGenerationError,
    AIRateLimitError,
    ValidationError,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================


# System prompt for workflow generation
N8N_WORKFLOW_SYSTEM_PROMPT = '''You are an expert at creating n8n workflows. Convert the user's description into a valid n8n workflow JSON structure.

## n8n Workflow Structure
A workflow consists of:
- nodes: Array of node objects defining workflow steps
- connections: Object mapping node outputs to subsequent node inputs
- settings: Workflow configuration

## Node Structure
Each node MUST have:
- id: Unique UUID string (e.g., "550e8400-e29b-41d4-a716-446655440000")
- name: Display name for the node
- type: n8n node type (e.g., "n8n-nodes-base.webhook")
- position: [x, y] coordinates for visual layout (start at [250, 300], space nodes ~200px apart horizontally)
- parameters: Node-specific configuration object
- typeVersion: Version number (usually 1 or 2)

## Common Node Types and Their Parameters

### Triggers (Start nodes)
- n8n-nodes-base.webhook: HTTP webhook trigger
  - parameters: { httpMethod: "POST", path: "webhook-path", responseMode: "onReceived" }

- n8n-nodes-base.scheduleTrigger: Cron-based trigger
  - parameters: { rule: { interval: [{ field: "hours", value: 1 }] } }

- n8n-nodes-base.manualTrigger: Manual execution trigger
  - parameters: {}

### Data Processing
- n8n-nodes-base.set: Set/transform data
  - parameters: { mode: "manual", assignments: { assignments: [{ id: "uuid", name: "fieldName", value: "={{ $json.data }}", type: "string" }] } }

- n8n-nodes-base.if: Conditional branching
  - parameters: { conditions: { options: { caseSensitive: true }, conditions: [{ leftValue: "={{ $json.field }}", rightValue: "value", operator: { type: "string", operation: "equals" } }] } }

- n8n-nodes-base.code: JavaScript/Python code execution
  - parameters: { language: "javaScript", jsCode: "return items.map(item => ({ json: { ...item.json, processed: true } }));" }

- n8n-nodes-base.merge: Merge multiple inputs
  - parameters: { mode: "combine", combinationMode: "multiplex" }

### HTTP & APIs
- n8n-nodes-base.httpRequest: Make HTTP requests
  - parameters: { method: "POST", url: "https://api.example.com/endpoint", sendBody: true, bodyParameters: { parameters: [{ name: "key", value: "value" }] } }

### Communication
- n8n-nodes-base.slack: Send Slack messages
  - parameters: { resource: "message", operation: "post", channel: "#channel-name", text: "Message text" }

- n8n-nodes-base.emailSend: Send emails via SMTP
  - parameters: { fromEmail: "from@example.com", toEmail: "to@example.com", subject: "Subject", text: "Body" }

- n8n-nodes-base.telegram: Send Telegram messages
  - parameters: { resource: "message", operation: "sendMessage", chatId: "chat_id", text: "Message" }

### Data Storage
- n8n-nodes-base.googleSheets: Google Sheets operations
  - parameters: { resource: "sheet", operation: "append", documentId: "sheet_id", sheetName: "Sheet1" }

- n8n-nodes-base.postgres: PostgreSQL database
  - parameters: { operation: "executeQuery", query: "SELECT * FROM table" }

- n8n-nodes-base.redis: Redis operations
  - parameters: { operation: "set", key: "key", value: "value" }

## Connection Structure
Connections define data flow between nodes:
```json
{
  "Node Name": {
    "main": [
      [
        { "node": "Next Node Name", "type": "main", "index": 0 }
      ]
    ]
  }
}
```

For IF nodes, use multiple arrays for true/false branches:
```json
{
  "IF Node": {
    "main": [
      [{ "node": "True Branch Node", "type": "main", "index": 0 }],
      [{ "node": "False Branch Node", "type": "main", "index": 0 }]
    ]
  }
}
```

## Output Format
Return ONLY valid JSON (no markdown, no code blocks) with this structure:
{
  "name": "Descriptive Workflow Name",
  "nodes": [...],
  "connections": {...},
  "settings": {
    "executionOrder": "v1"
  },
  "explanation": "2-3 sentence explanation of what the workflow does and how it works",
  "confidence": 0.95,
  "suggestions": ["Optional improvement suggestion 1", "Optional suggestion 2"]
}

## Important Rules
1. Always start with a trigger node (webhook, schedule, or manual)
2. Use realistic node positions for visual layout
3. Ensure all node names referenced in connections exist
4. Generate unique UUIDs for all node IDs
5. Set confidence between 0.0 and 1.0 based on clarity of request
6. Include helpful suggestions if the workflow could be improved
'''


# Maximum description length to prevent abuse
MAX_DESCRIPTION_LENGTH = 5000

# Maximum refinement feedback length
MAX_FEEDBACK_LENGTH = 2000


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class WorkflowGenerationResult:
    """
    Result of AI workflow generation.

    WHAT: Contains generated workflow and metadata.

    WHY: Provides structured output for frontend consumption,
    including confidence score and suggestions for improvement.
    """

    name: str
    nodes: List[Dict[str, Any]]
    connections: Dict[str, Any]
    settings: Dict[str, Any]
    explanation: str
    confidence: float
    suggestions: List[str] = field(default_factory=list)
    raw_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "nodes": self.nodes,
            "connections": self.connections,
            "settings": self.settings,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "suggestions": self.suggestions,
        }

    def to_n8n_workflow(self) -> Dict[str, Any]:
        """
        Convert to n8n-compatible workflow format.

        WHAT: Returns just the workflow structure needed by n8n API.

        WHY: n8n API expects specific fields, not our metadata.
        """
        return {
            "name": self.name,
            "nodes": self.nodes,
            "connections": self.connections,
            "settings": self.settings,
        }


@dataclass
class WorkflowValidationResult:
    """
    Result of workflow validation.

    WHAT: Contains validation status and any errors/warnings.

    WHY: Allows users to see issues before deploying workflows.
    """

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ============================================================================
# Service Class
# ============================================================================


class WorkflowAIService:
    """
    AI-powered workflow generation using OpenAI GPT.

    WHAT: Converts natural language to n8n workflow JSON.

    WHY: Enables non-technical users to create automations by
    describing what they want, lowering the barrier to entry.

    HOW: Uses GPT with specialized system prompt containing
    n8n documentation to generate valid workflow structures.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize workflow AI service.

        WHAT: Sets up OpenAI client with configuration.

        WHY: Allows dependency injection for testing and
        configuration override.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Model name (defaults to settings)
        """
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = model or settings.OPENAI_MODEL

        if not self._api_key:
            logger.warning("OpenAI API key not configured - AI workflow generation disabled")
            self._client = None
        else:
            self._client = AsyncOpenAI(api_key=self._api_key)

    def _sanitize_input(self, text: str, max_length: int) -> str:
        """
        Sanitize user input for AI processing.

        WHAT: Cleans and validates user-provided text.

        WHY: OWASP A03 Injection prevention - ensures input
        doesn't contain malicious content or prompt injections.

        Args:
            text: User-provided text
            max_length: Maximum allowed length

        Returns:
            Sanitized text

        Raises:
            ValidationError: If input is invalid
        """
        if not text or not text.strip():
            raise ValidationError(
                message="Description cannot be empty",
                field="description",
            )

        # Trim whitespace
        text = text.strip()

        # Check length
        if len(text) > max_length:
            raise ValidationError(
                message=f"Description too long (max {max_length} characters)",
                field="description",
                length=len(text),
                max_length=max_length,
            )

        # Remove potential prompt injection attempts
        # WHY: Users might try to override system prompt with instructions
        injection_patterns = [
            r"ignore\s+(previous|all|above)\s+instructions",
            r"disregard\s+(previous|all|above)\s+instructions",
            r"forget\s+(previous|all|above)\s+instructions",
            r"system\s*:\s*",
            r"assistant\s*:\s*",
            r"<\|.*?\|>",  # Special tokens
        ]

        for pattern in injection_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Potential prompt injection detected: {pattern}")
                raise ValidationError(
                    message="Invalid characters in description",
                    field="description",
                )

        return text

    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse AI response JSON.

        WHAT: Extracts JSON from AI response.

        WHY: AI may include markdown formatting or extra text.
        We need to extract just the JSON structure.

        Args:
            response_text: Raw AI response

        Returns:
            Parsed JSON dictionary

        Raises:
            AIGenerationError: If JSON parsing fails
        """
        # Try direct JSON parse first
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        json_patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
            r"\{[\s\S]*\}",
        ]

        for pattern in json_patterns:
            match = re.search(pattern, response_text)
            if match:
                try:
                    json_str = match.group(1) if "```" in pattern else match.group(0)
                    return json.loads(json_str)
                except (json.JSONDecodeError, IndexError):
                    continue

        raise AIGenerationError(
            message="Failed to parse AI response as JSON",
            raw_response=response_text[:500],
        )

    async def generate_workflow(
        self,
        description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowGenerationResult:
        """
        Generate n8n workflow from natural language description.

        WHAT: Converts plain text to workflow JSON.

        WHY: Main entry point for natural language workflow creation.
        Users describe what they want, AI generates the structure.

        HOW:
        1. Sanitize input
        2. Build prompt with context
        3. Call OpenAI API
        4. Parse and validate response
        5. Return structured result

        Args:
            description: Plain text workflow description
            context: Optional context (available integrations, etc.)

        Returns:
            WorkflowGenerationResult with workflow and metadata

        Raises:
            ValidationError: If input is invalid
            AIServiceError: If AI service fails
            AIGenerationError: If generation fails
        """
        if not self._client:
            raise AIServiceError(
                message="AI service not configured - please set OPENAI_API_KEY"
            )

        # Sanitize input
        description = self._sanitize_input(description, MAX_DESCRIPTION_LENGTH)

        # Build user message with optional context
        user_message = f"Create an n8n workflow for: {description}"

        if context:
            if context.get("available_credentials"):
                user_message += f"\n\nAvailable credentials/integrations: {', '.join(context['available_credentials'])}"
            if context.get("project_name"):
                user_message += f"\n\nThis is for project: {context['project_name']}"

        try:
            logger.info(f"Generating workflow from description: {description[:100]}...")

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": N8N_WORKFLOW_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,  # Balance creativity and consistency
                max_tokens=4000,
            )

            response_text = response.choices[0].message.content
            logger.debug(f"AI response: {response_text[:500]}...")

            # Parse response
            parsed = self._parse_ai_response(response_text)

            # Extract fields with defaults
            result = WorkflowGenerationResult(
                name=parsed.get("name", "Generated Workflow"),
                nodes=parsed.get("nodes", []),
                connections=parsed.get("connections", {}),
                settings=parsed.get("settings", {"executionOrder": "v1"}),
                explanation=parsed.get("explanation", ""),
                confidence=float(parsed.get("confidence", 0.5)),
                suggestions=parsed.get("suggestions", []),
                raw_response=response_text,
            )

            # Ensure nodes have valid UUIDs
            for node in result.nodes:
                if "id" not in node or not node["id"]:
                    node["id"] = str(uuid.uuid4())

            logger.info(
                f"Generated workflow '{result.name}' with {len(result.nodes)} nodes, "
                f"confidence: {result.confidence}"
            )

            return result

        except RateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded: {e}")
            raise AIRateLimitError(
                message="AI service rate limit exceeded - please try again in a few minutes"
            )
        except APIConnectionError as e:
            logger.error(f"OpenAI connection error: {e}")
            raise AIServiceError(
                message="Failed to connect to AI service - please try again"
            )
        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise AIServiceError(
                message="AI service error",
                error_code=getattr(e, "code", None),
            )

    async def refine_workflow(
        self,
        workflow: Dict[str, Any],
        feedback: str,
    ) -> WorkflowGenerationResult:
        """
        Refine an existing workflow based on user feedback.

        WHAT: Modifies a workflow according to user instructions.

        WHY: Allows iterative improvement of generated workflows
        without starting from scratch.

        HOW:
        1. Take existing workflow and feedback
        2. Ask AI to modify based on feedback
        3. Return updated workflow

        Args:
            workflow: Current workflow JSON
            feedback: User's refinement request

        Returns:
            Updated WorkflowGenerationResult

        Raises:
            ValidationError: If input is invalid
            AIServiceError: If AI service fails
        """
        if not self._client:
            raise AIServiceError(
                message="AI service not configured - please set OPENAI_API_KEY"
            )

        # Sanitize feedback
        feedback = self._sanitize_input(feedback, MAX_FEEDBACK_LENGTH)

        # Build refinement prompt
        user_message = f"""Here is an existing n8n workflow:

```json
{json.dumps(workflow, indent=2)}
```

Please modify this workflow based on the following feedback:
{feedback}

Return the complete updated workflow in the same JSON format."""

        try:
            logger.info(f"Refining workflow based on feedback: {feedback[:100]}...")

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": N8N_WORKFLOW_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,
                max_tokens=4000,
            )

            response_text = response.choices[0].message.content
            parsed = self._parse_ai_response(response_text)

            result = WorkflowGenerationResult(
                name=parsed.get("name", workflow.get("name", "Refined Workflow")),
                nodes=parsed.get("nodes", []),
                connections=parsed.get("connections", {}),
                settings=parsed.get("settings", {"executionOrder": "v1"}),
                explanation=parsed.get("explanation", f"Refined based on: {feedback}"),
                confidence=float(parsed.get("confidence", 0.7)),
                suggestions=parsed.get("suggestions", []),
                raw_response=response_text,
            )

            # Ensure nodes have valid UUIDs
            for node in result.nodes:
                if "id" not in node or not node["id"]:
                    node["id"] = str(uuid.uuid4())

            logger.info(f"Refined workflow '{result.name}' with {len(result.nodes)} nodes")

            return result

        except RateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded: {e}")
            raise AIRateLimitError(
                message="AI service rate limit exceeded - please try again in a few minutes"
            )
        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise AIServiceError(
                message="AI service error",
                error_code=getattr(e, "code", None),
            )

    def validate_workflow(self, workflow: Dict[str, Any]) -> WorkflowValidationResult:
        """
        Validate a workflow structure.

        WHAT: Checks workflow JSON for common issues.

        WHY: Catches problems before attempting to deploy to n8n,
        providing helpful error messages to users.

        HOW: Performs structural validation:
        1. Required fields present
        2. Node structure valid
        3. Connections reference existing nodes
        4. Has at least one trigger node

        Args:
            workflow: Workflow JSON to validate

        Returns:
            WorkflowValidationResult with errors and warnings
        """
        errors = []
        warnings = []

        # Check required top-level fields
        if "nodes" not in workflow:
            errors.append("Workflow missing 'nodes' array")
        elif not isinstance(workflow["nodes"], list):
            errors.append("'nodes' must be an array")
        elif len(workflow["nodes"]) == 0:
            errors.append("Workflow must have at least one node")

        if "connections" not in workflow:
            warnings.append("Workflow missing 'connections' - nodes are not connected")

        if "name" not in workflow:
            warnings.append("Workflow missing 'name' - using default")

        # Validate nodes
        if "nodes" in workflow and isinstance(workflow["nodes"], list):
            node_names = set()
            has_trigger = False
            trigger_types = [
                "n8n-nodes-base.webhook",
                "n8n-nodes-base.scheduleTrigger",
                "n8n-nodes-base.manualTrigger",
                "n8n-nodes-base.cron",
                "n8n-nodes-base.start",
            ]

            for i, node in enumerate(workflow["nodes"]):
                if not isinstance(node, dict):
                    errors.append(f"Node {i} is not an object")
                    continue

                # Check required node fields
                if "name" not in node:
                    errors.append(f"Node {i} missing 'name'")
                else:
                    if node["name"] in node_names:
                        errors.append(f"Duplicate node name: {node['name']}")
                    node_names.add(node["name"])

                if "type" not in node:
                    errors.append(f"Node {i} missing 'type'")
                else:
                    # Check for trigger
                    if any(t in node["type"] for t in trigger_types):
                        has_trigger = True

                if "position" not in node:
                    warnings.append(f"Node '{node.get('name', i)}' missing 'position'")

                if "parameters" not in node:
                    warnings.append(f"Node '{node.get('name', i)}' missing 'parameters'")

            if not has_trigger:
                warnings.append(
                    "Workflow has no trigger node - will only run manually or via API"
                )

            # Validate connections reference existing nodes
            if "connections" in workflow and isinstance(workflow["connections"], dict):
                for source_node, outputs in workflow["connections"].items():
                    if source_node not in node_names:
                        errors.append(
                            f"Connection references non-existent source node: {source_node}"
                        )

                    if isinstance(outputs, dict) and "main" in outputs:
                        for output_index, targets in enumerate(outputs.get("main", [])):
                            if isinstance(targets, list):
                                for target in targets:
                                    if isinstance(target, dict):
                                        target_node = target.get("node")
                                        if target_node and target_node not in node_names:
                                            errors.append(
                                                f"Connection references non-existent target node: {target_node}"
                                            )

        return WorkflowValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )


# ============================================================================
# Factory Function
# ============================================================================


def get_workflow_ai_service() -> WorkflowAIService:
    """
    Get workflow AI service instance.

    WHAT: Factory function for WorkflowAIService.

    WHY: Provides clean interface for dependency injection.

    Returns:
        Configured WorkflowAIService instance
    """
    return WorkflowAIService()
