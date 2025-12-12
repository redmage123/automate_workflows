"""
Pydantic schemas for AI-powered workflow generation endpoints.

WHAT: Request/response schemas for natural language workflow creation.

WHY: Schemas define API contracts for AI workflow operations:
1. Validate incoming descriptions and feedback
2. Document API for OpenAPI/Swagger
3. Provide type safety for handlers
4. Structure AI service outputs for frontend

HOW: Uses Pydantic v2 with Field validators.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Request Schemas
# ============================================================================


class WorkflowGenerateRequest(BaseModel):
    """
    Request schema for generating workflow from natural language.

    WHAT: Validates user's workflow description input.

    WHY: Ensures description is provided and within limits
    before sending to AI service.
    """

    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Natural language description of the desired workflow",
    )
    context: Dict[str, Any] | None = Field(
        default=None,
        description="Optional context (available_credentials, project_name, etc.)",
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Ensure description has meaningful content."""
        if len(v.strip()) < 10:
            raise ValueError("Description must be at least 10 characters")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "description": "When a new row is added to my Google Sheet, send a Slack notification to the #sales channel with the customer name and email",
                "context": {
                    "available_credentials": ["google_sheets", "slack"],
                    "project_name": "Lead Notifications",
                },
            }
        }


class WorkflowRefineRequest(BaseModel):
    """
    Request schema for refining an existing workflow.

    WHAT: Validates workflow and feedback for refinement.

    WHY: Allows iterative improvement of generated workflows.
    """

    workflow: Dict[str, Any] = Field(
        ...,
        description="Current workflow JSON to refine",
    )
    feedback: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="User feedback describing desired changes",
    )

    @field_validator("workflow")
    @classmethod
    def validate_workflow(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure workflow has basic structure."""
        if "nodes" not in v:
            raise ValueError("Workflow must have 'nodes' array")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "workflow": {
                    "name": "Lead Notification",
                    "nodes": [{"name": "Trigger", "type": "n8n-nodes-base.webhook"}],
                    "connections": {},
                },
                "feedback": "Also add error handling and retry logic if Slack fails",
            }
        }


class WorkflowValidateRequest(BaseModel):
    """
    Request schema for validating workflow structure.

    WHAT: Validates workflow JSON before deployment.

    WHY: Catches errors before sending to n8n.
    """

    workflow: Dict[str, Any] = Field(
        ...,
        description="Workflow JSON to validate",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "workflow": {
                    "name": "My Workflow",
                    "nodes": [
                        {
                            "id": "uuid-here",
                            "name": "Webhook",
                            "type": "n8n-nodes-base.webhook",
                            "position": [250, 300],
                            "parameters": {},
                        }
                    ],
                    "connections": {},
                    "settings": {"executionOrder": "v1"},
                }
            }
        }


# ============================================================================
# Response Schemas
# ============================================================================


class WorkflowGenerationResponse(BaseModel):
    """
    Response schema for generated workflow.

    WHAT: Returns generated workflow with metadata.

    WHY: Provides complete information for frontend:
    - Workflow JSON for preview/editing
    - Explanation for user understanding
    - Confidence score for guidance
    - Suggestions for improvement
    """

    name: str = Field(..., description="Generated workflow name")
    nodes: List[Dict[str, Any]] = Field(..., description="Workflow nodes")
    connections: Dict[str, Any] = Field(..., description="Node connections")
    settings: Dict[str, Any] = Field(..., description="Workflow settings")
    explanation: str = Field(..., description="AI explanation of the workflow")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="AI confidence score (0-1)",
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Suggestions for improvement",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Google Sheets to Slack Notification",
                "nodes": [
                    {
                        "id": "uuid-1",
                        "name": "Google Sheets Trigger",
                        "type": "n8n-nodes-base.googleSheetsTrigger",
                        "position": [250, 300],
                        "parameters": {},
                    },
                    {
                        "id": "uuid-2",
                        "name": "Send Slack Message",
                        "type": "n8n-nodes-base.slack",
                        "position": [450, 300],
                        "parameters": {
                            "channel": "#sales",
                            "text": "New lead: {{ $json.customer_name }}",
                        },
                    },
                ],
                "connections": {
                    "Google Sheets Trigger": {
                        "main": [[{"node": "Send Slack Message", "type": "main", "index": 0}]]
                    }
                },
                "settings": {"executionOrder": "v1"},
                "explanation": "This workflow triggers when a new row is added to your Google Sheet and sends a notification to Slack #sales channel.",
                "confidence": 0.92,
                "suggestions": [
                    "Consider adding error handling for Slack failures",
                    "You may want to filter notifications based on certain conditions",
                ],
            }
        }


class WorkflowValidationResponse(BaseModel):
    """
    Response schema for workflow validation.

    WHAT: Returns validation results.

    WHY: Helps users fix issues before deployment.
    """

    valid: bool = Field(..., description="Whether workflow is valid")
    errors: List[str] = Field(
        default_factory=list,
        description="Validation errors (must fix)",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Validation warnings (optional to fix)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "valid": True,
                "errors": [],
                "warnings": ["Workflow has no trigger node - will only run manually"],
            }
        }


class AIServiceStatusResponse(BaseModel):
    """
    Response schema for AI service status.

    WHAT: Returns whether AI service is available.

    WHY: Frontend can show/hide AI features based on availability.
    """

    available: bool = Field(..., description="Whether AI service is configured and available")
    model: str | None = Field(None, description="AI model being used")
    message: str = Field(..., description="Status message")

    class Config:
        json_schema_extra = {
            "example": {
                "available": True,
                "model": "gpt-4o",
                "message": "AI workflow generation is available",
            }
        }
