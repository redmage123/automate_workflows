"""
Integration Pydantic Schemas.

WHAT: Request/response schemas for external integrations.

WHY: Pydantic schemas provide:
1. Input validation for API requests
2. Response serialization for API responses
3. Type safety and documentation
4. Security by controlling exposed fields

HOW: Defines schemas for:
- Calendar integration configuration
- Webhook endpoint management
- Webhook delivery tracking
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator
import re

from app.models.integration import CalendarProvider, WebhookEventType


# ============================================================================
# Calendar Integration Schemas
# ============================================================================


class CalendarIntegrationBase(BaseModel):
    """Base schema for calendar integration."""

    provider: str = Field(
        ...,
        description="Calendar provider (google, outlook, apple, caldav)",
        examples=["google"],
    )
    calendar_id: Optional[str] = Field(
        None,
        description="Specific calendar ID to sync (default: primary)",
    )
    calendar_name: Optional[str] = Field(
        None,
        description="Display name for the calendar",
    )
    sync_projects: bool = Field(
        True,
        description="Sync project milestones to calendar",
    )
    sync_tickets: bool = Field(
        False,
        description="Sync ticket due dates to calendar",
    )
    sync_invoices: bool = Field(
        False,
        description="Sync invoice due dates to calendar",
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """
        Validate calendar provider.

        WHAT: Ensures provider is a valid CalendarProvider enum value.

        WHY: Prevents invalid provider types from being stored,
        which would cause issues during calendar sync operations.
        """
        valid_providers = [p.value for p in CalendarProvider]
        if v.lower() not in valid_providers:
            raise ValueError(
                f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
            )
        return v.lower()


class CalendarIntegrationCreate(BaseModel):
    """
    Schema for initiating calendar integration OAuth flow.

    WHAT: Minimal data needed to start OAuth.

    WHY: OAuth flow provides tokens, so we only need
    the provider and optional settings upfront.
    """

    provider: str = Field(
        ...,
        description="Calendar provider to connect",
        examples=["google"],
    )
    sync_projects: bool = Field(True)
    sync_tickets: bool = Field(False)
    sync_invoices: bool = Field(False)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        valid_providers = [p.value for p in CalendarProvider]
        if v.lower() not in valid_providers:
            raise ValueError(
                f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
            )
        return v.lower()


class CalendarIntegrationUpdate(BaseModel):
    """
    Schema for updating calendar integration settings.

    WHAT: Fields that can be updated after initial connection.

    WHY: Users may want to change sync preferences or
    select a different calendar without re-authenticating.
    """

    calendar_id: Optional[str] = None
    calendar_name: Optional[str] = None
    sync_enabled: Optional[bool] = None
    sync_projects: Optional[bool] = None
    sync_tickets: Optional[bool] = None
    sync_invoices: Optional[bool] = None


class CalendarIntegrationResponse(BaseModel):
    """
    Schema for calendar integration response.

    WHAT: Full integration details (excluding sensitive tokens).

    WHY: Response includes status and settings needed
    for UI display, but excludes OAuth tokens for security.
    """

    id: int
    user_id: int
    org_id: int
    provider: str
    provider_email: Optional[str] = None
    calendar_id: Optional[str] = None
    calendar_name: Optional[str] = None
    sync_enabled: bool
    sync_projects: bool
    sync_tickets: bool
    sync_invoices: bool
    last_sync_at: Optional[datetime] = None
    is_active: bool
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CalendarOAuthCallback(BaseModel):
    """
    Schema for OAuth callback data.

    WHAT: Data received from OAuth provider after authorization.

    WHY: OAuth callback includes authorization code needed
    to exchange for access/refresh tokens.
    """

    code: str = Field(..., description="Authorization code from OAuth provider")
    state: str = Field(..., description="State parameter for CSRF protection")


class CalendarSyncRequest(BaseModel):
    """
    Schema for manual sync request.

    WHAT: Options for triggering manual calendar sync.

    WHY: Users may want to force a sync outside the
    scheduled interval to see immediate updates.
    """

    full_sync: bool = Field(
        False,
        description="Perform full sync instead of incremental",
    )


# ============================================================================
# Webhook Endpoint Schemas
# ============================================================================


class WebhookEndpointBase(BaseModel):
    """Base schema for webhook endpoint."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable name for the webhook",
        examples=["Slack Notifications"],
    )
    description: Optional[str] = Field(
        None,
        description="Description of what this webhook does",
    )
    url: str = Field(
        ...,
        description="Webhook URL to deliver events to",
        examples=["https://example.com/webhook"],
    )
    events: List[str] = Field(
        ...,
        min_length=1,
        description="Event types to subscribe to (supports wildcards like 'ticket.*')",
        examples=[["ticket.created", "ticket.updated"]],
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        description="Custom headers to include in webhook requests",
    )
    retry_enabled: bool = Field(
        True,
        description="Enable automatic retries for failed deliveries",
    )
    max_retries: int = Field(
        3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed deliveries",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """
        Validate webhook URL.

        WHAT: Ensures URL is valid and uses HTTPS.

        WHY: Webhooks contain sensitive data; HTTPS is required
        to prevent interception. URL validation prevents SSRF.
        """
        if not v.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
        # Basic URL validation
        url_pattern = re.compile(
            r"^https://[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?"
            r"(\.[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9])*"
            r"(:\d+)?(/.*)?$"
        )
        if not url_pattern.match(v):
            raise ValueError("Invalid webhook URL format")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: List[str]) -> List[str]:
        """
        Validate event types.

        WHAT: Ensures event types are valid or valid wildcards.

        WHY: Invalid event types would never trigger,
        leading to confusion. Validation catches typos early.
        """
        valid_events = {e.value for e in WebhookEventType}
        valid_prefixes = {"ticket", "project", "proposal", "invoice", "user", "workflow"}

        for event in v:
            if event == "*":
                continue
            if event.endswith(".*"):
                prefix = event[:-2]
                if prefix not in valid_prefixes:
                    raise ValueError(
                        f"Invalid event wildcard '{event}'. "
                        f"Valid prefixes: {', '.join(sorted(valid_prefixes))}"
                    )
            elif event not in valid_events:
                raise ValueError(
                    f"Invalid event type '{event}'. "
                    f"Use valid events or wildcards (e.g., 'ticket.*')"
                )
        return v


class WebhookEndpointCreate(WebhookEndpointBase):
    """
    Schema for creating a webhook endpoint.

    WHAT: All fields needed to create a webhook.

    WHY: Creates inherit from base to get validation,
    and may add create-specific fields in the future.
    """

    pass


class WebhookEndpointUpdate(BaseModel):
    """
    Schema for updating a webhook endpoint.

    WHAT: Optional fields for partial updates.

    WHY: Partial updates allow changing specific settings
    without providing all fields again.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    headers: Optional[Dict[str, str]] = None
    retry_enabled: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    is_active: Optional[bool] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        if len(v) == 0:
            raise ValueError("At least one event type is required")
        return v


class WebhookEndpointResponse(BaseModel):
    """
    Schema for webhook endpoint response.

    WHAT: Full endpoint details including statistics.

    WHY: Response includes delivery stats to help users
    monitor webhook health and identify issues.
    """

    id: int
    org_id: int
    name: str
    description: Optional[str] = None
    url: str
    events: List[str]
    headers: Optional[Dict[str, str]] = None
    is_active: bool
    retry_enabled: bool
    max_retries: int
    delivery_count: int
    success_count: int
    failure_count: int
    last_triggered_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WebhookEndpointWithSecret(WebhookEndpointResponse):
    """
    Schema for webhook endpoint response with secret.

    WHAT: Full endpoint details including signing secret.

    WHY: Secret is shown only when creating or explicitly
    requesting it, to minimize exposure.
    """

    secret: str


class WebhookTestRequest(BaseModel):
    """
    Schema for testing a webhook endpoint.

    WHAT: Options for sending a test event.

    WHY: Users need to verify their webhook URL works
    before relying on it for production events.
    """

    event_type: str = Field(
        "test.ping",
        description="Event type for the test payload",
    )
    payload: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom payload for the test (default: sample payload)",
    )


# ============================================================================
# Webhook Delivery Schemas
# ============================================================================


class WebhookDeliveryResponse(BaseModel):
    """
    Schema for webhook delivery response.

    WHAT: Details of a webhook delivery attempt.

    WHY: Delivery details help users debug failed webhooks
    by showing request/response information.
    """

    id: int
    endpoint_id: int
    event_type: str
    event_id: str
    request_url: str
    request_headers: Optional[Dict[str, str]] = None
    request_body: Optional[Dict[str, Any]] = None
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    response_body: Optional[str] = None
    delivered: bool
    attempt_count: int
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    triggered_at: datetime
    delivered_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WebhookDeliveryStats(BaseModel):
    """
    Schema for webhook delivery statistics.

    WHAT: Aggregated delivery metrics for an endpoint.

    WHY: Statistics help users monitor webhook reliability
    without reviewing individual deliveries.
    """

    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    success_rate: float
    average_duration_ms: Optional[int] = None
    period_start: datetime
    period_end: datetime


class WebhookPayload(BaseModel):
    """
    Schema for outgoing webhook payload.

    WHAT: Standard webhook payload structure.

    WHY: Consistent payload format makes it easier
    for consumers to parse webhook events.
    """

    event_type: str = Field(..., description="Type of event")
    event_id: str = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(..., description="When the event occurred")
    org_id: int = Field(..., description="Organization ID")
    data: Dict[str, Any] = Field(..., description="Event-specific data")
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata",
    )


# ============================================================================
# List Response Schemas
# ============================================================================


class CalendarIntegrationList(BaseModel):
    """List response for calendar integrations."""

    items: List[CalendarIntegrationResponse]
    total: int


class WebhookEndpointList(BaseModel):
    """List response for webhook endpoints."""

    items: List[WebhookEndpointResponse]
    total: int


class WebhookDeliveryList(BaseModel):
    """List response for webhook deliveries."""

    items: List[WebhookDeliveryResponse]
    total: int
    has_more: bool
