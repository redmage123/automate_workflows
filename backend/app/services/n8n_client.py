"""
N8n API client service for workflow automation.

WHAT: HTTP client for interacting with n8n REST API.

WHY: Provides a clean interface for:
1. Creating and managing workflows in n8n
2. Triggering workflow executions
3. Monitoring execution status
4. Managing credentials and settings

Security Considerations (OWASP):
- A02: API keys encrypted at rest, decrypted only for API calls
- A10: SSRF prevention via URL validation
- A08: Webhook signature validation for incoming requests

HOW: Uses httpx for async HTTP with proper timeout handling.
All API errors wrapped in N8nError for consistent handling.
"""

import hashlib
import hmac
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings
from app.core.exceptions import N8nError, ValidationError
from app.services.encryption_service import get_encryption_service


# ============================================================================
# Constants
# ============================================================================

# Default timeout for n8n API calls (seconds)
DEFAULT_TIMEOUT = 30.0

# Maximum timeout for execution triggers (may take longer)
EXECUTION_TIMEOUT = 60.0

# Allowed URL schemes for SSRF prevention
ALLOWED_SCHEMES = {"http", "https"}

# Allowed ports for n8n connections
ALLOWED_PORTS = {80, 443, 5678}  # 5678 is default n8n port


# ============================================================================
# N8n API Client
# ============================================================================


class N8nClient:
    """
    Async HTTP client for n8n API.

    WHAT: Handles all communication with n8n instances.

    WHY: Centralizes n8n API logic for:
    - Consistent error handling
    - Proper authentication
    - URL construction
    - Response parsing

    HOW: Uses httpx async client with:
    - Bearer token authentication
    - Proper timeout handling
    - Error wrapping in N8nError
    """

    def __init__(
        self,
        base_url: str,
        api_key_encrypted: str,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        Initialize n8n client.

        WHAT: Sets up HTTP client with authentication.

        WHY: Each organization may have their own n8n instance,
        so client is configured per-environment.

        Args:
            base_url: Base URL of n8n instance (e.g., https://n8n.example.com)
            api_key_encrypted: Encrypted API key (decrypted on demand)
            timeout: Request timeout in seconds

        Raises:
            ValidationError: If base_url is invalid or poses SSRF risk
        """
        self._validate_base_url(base_url)
        self._base_url = base_url.rstrip("/")
        self._api_key_encrypted = api_key_encrypted
        self._timeout = timeout
        self._encryption_service = get_encryption_service()

    def _validate_base_url(self, url: str) -> None:
        """
        Validate base URL to prevent SSRF attacks.

        WHAT: Checks URL is safe to connect to.

        WHY: SSRF prevention (OWASP A10) - prevents attackers from:
        - Accessing internal services
        - Scanning internal networks
        - Accessing cloud metadata endpoints

        HOW: Validates scheme, host, and port against allowlists.

        Args:
            url: URL to validate

        Raises:
            ValidationError: If URL is invalid or poses SSRF risk
        """
        try:
            parsed = urlparse(url)
        except ValueError as e:
            raise ValidationError(
                message="Invalid n8n URL format",
                url=url,
                error=str(e),
            )

        # Check scheme
        if parsed.scheme not in ALLOWED_SCHEMES:
            raise ValidationError(
                message=f"Invalid URL scheme. Must be one of: {ALLOWED_SCHEMES}",
                url=url,
                scheme=parsed.scheme,
            )

        # Check for localhost/internal IPs in production
        if not settings.DEBUG:
            blocked_hosts = {
                "localhost",
                "127.0.0.1",
                "0.0.0.0",
                "::1",
                "169.254.169.254",  # AWS metadata
                "metadata.google.internal",  # GCP metadata
            }
            if parsed.hostname and parsed.hostname.lower() in blocked_hosts:
                raise ValidationError(
                    message="Cannot connect to internal or metadata endpoints",
                    url=url,
                )

        # Check port if specified
        if parsed.port and parsed.port not in ALLOWED_PORTS:
            raise ValidationError(
                message=f"Invalid port. Must be one of: {ALLOWED_PORTS}",
                url=url,
                port=parsed.port,
            )

    def _get_api_key(self) -> str:
        """
        Decrypt API key for use in requests.

        WHAT: Decrypts the stored API key.

        WHY: API keys stored encrypted (OWASP A02), decrypted only
        when needed for API calls to minimize exposure window.

        Returns:
            Decrypted API key
        """
        return self._encryption_service.decrypt(self._api_key_encrypted)

    def _get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for API requests.

        WHAT: Constructs authentication headers.

        WHY: n8n uses Bearer token authentication.

        Returns:
            Dictionary of HTTP headers
        """
        return {
            "Authorization": f"Bearer {self._get_api_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated request to n8n API.

        WHAT: Executes HTTP request with proper error handling.

        WHY: Centralizes request logic for consistent:
        - Authentication
        - Error handling
        - Timeout management
        - Response parsing

        HOW:
        1. Constructs full URL from base and endpoint
        2. Adds authentication headers
        3. Makes request with timeout
        4. Wraps errors in N8nError
        5. Parses and returns JSON response

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint path (e.g., /workflows)
            data: Request body (for POST, PUT, PATCH)
            timeout: Override default timeout

        Returns:
            Parsed JSON response

        Raises:
            N8nError: If request fails or returns error status
        """
        url = urljoin(self._base_url + "/", endpoint.lstrip("/"))
        request_timeout = timeout or self._timeout

        try:
            async with httpx.AsyncClient(
                timeout=request_timeout,
                follow_redirects=False,  # Prevent redirect-based SSRF
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    json=data,
                )

                # Check for error status codes
                if response.status_code >= 400:
                    error_detail = self._parse_error_response(response)
                    raise N8nError(
                        message=f"n8n API error: {error_detail}",
                        status_code=response.status_code,
                        endpoint=endpoint,
                        method=method,
                    )

                # Return empty dict for 204 No Content
                if response.status_code == 204:
                    return {}

                return response.json()

        except httpx.TimeoutException:
            raise N8nError(
                message="n8n API request timed out",
                endpoint=endpoint,
                timeout=request_timeout,
            )
        except httpx.RequestError as e:
            raise N8nError(
                message=f"n8n API connection error: {str(e)}",
                endpoint=endpoint,
            )

    def _parse_error_response(self, response: httpx.Response) -> str:
        """
        Extract error message from n8n error response.

        WHAT: Parses n8n error response body.

        WHY: n8n returns structured error responses that we can
        use for more helpful error messages.

        Args:
            response: HTTP response with error status

        Returns:
            Error message string
        """
        try:
            data = response.json()
            if "message" in data:
                return data["message"]
            if "error" in data:
                return data["error"]
            return str(data)
        except Exception:
            return response.text or f"HTTP {response.status_code}"

    # =========================================================================
    # Workflow Management
    # =========================================================================

    async def get_workflows(self) -> List[Dict[str, Any]]:
        """
        List all workflows in n8n instance.

        WHAT: Retrieves all workflow definitions.

        WHY: Needed for syncing workflow list and status.

        Returns:
            List of workflow objects from n8n
        """
        response = await self._request("GET", "/api/v1/workflows")
        return response.get("data", [])

    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get a specific workflow by ID.

        WHAT: Retrieves workflow definition and status.

        WHY: Needed for workflow detail view and editing.

        Args:
            workflow_id: n8n workflow ID

        Returns:
            Workflow object from n8n
        """
        return await self._request("GET", f"/api/v1/workflows/{workflow_id}")

    async def create_workflow(
        self,
        name: str,
        nodes: List[Dict[str, Any]],
        connections: Dict[str, Any],
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new workflow in n8n.

        WHAT: Creates a new workflow definition.

        WHY: Enables creating workflows from templates or custom definitions.

        HOW: Sends workflow structure to n8n API.

        Args:
            name: Workflow name
            nodes: List of workflow nodes
            connections: Node connection definitions
            settings: Optional workflow settings

        Returns:
            Created workflow object from n8n
        """
        data = {
            "name": name,
            "nodes": nodes,
            "connections": connections,
            "settings": settings or {},
        }
        return await self._request("POST", "/api/v1/workflows", data=data)

    async def update_workflow(
        self,
        workflow_id: str,
        name: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        connections: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing workflow.

        WHAT: Modifies workflow definition or status.

        WHY: Enables editing workflows and activating/deactivating them.

        Args:
            workflow_id: n8n workflow ID
            name: New workflow name (if changing)
            nodes: Updated node list (if changing)
            connections: Updated connections (if changing)
            settings: Updated settings (if changing)
            active: Activate/deactivate workflow (if changing)

        Returns:
            Updated workflow object from n8n
        """
        data: Dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if nodes is not None:
            data["nodes"] = nodes
        if connections is not None:
            data["connections"] = connections
        if settings is not None:
            data["settings"] = settings
        if active is not None:
            data["active"] = active

        return await self._request(
            "PATCH",
            f"/api/v1/workflows/{workflow_id}",
            data=data,
        )

    async def delete_workflow(self, workflow_id: str) -> None:
        """
        Delete a workflow from n8n.

        WHAT: Removes workflow definition.

        WHY: Cleanup when workflow instance is deleted.

        Args:
            workflow_id: n8n workflow ID
        """
        await self._request("DELETE", f"/api/v1/workflows/{workflow_id}")

    async def activate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Activate a workflow in n8n.

        WHAT: Enables workflow for trigger-based execution.

        WHY: Workflows must be active to respond to triggers.

        Args:
            workflow_id: n8n workflow ID

        Returns:
            Updated workflow object
        """
        return await self.update_workflow(workflow_id, active=True)

    async def deactivate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Deactivate a workflow in n8n.

        WHAT: Disables workflow execution.

        WHY: Needed for pausing workflows without deleting them.

        Args:
            workflow_id: n8n workflow ID

        Returns:
            Updated workflow object
        """
        return await self.update_workflow(workflow_id, active=False)

    # =========================================================================
    # Workflow Execution
    # =========================================================================

    async def trigger_workflow(
        self,
        workflow_id: str,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Trigger immediate workflow execution.

        WHAT: Starts a workflow execution with optional input data.

        WHY: Enables on-demand workflow runs (vs trigger-based).

        HOW: Uses n8n webhook or execution API to trigger run.

        Args:
            workflow_id: n8n workflow ID
            input_data: Optional input data for the workflow

        Returns:
            Execution response from n8n
        """
        data = {"data": input_data or {}}
        return await self._request(
            "POST",
            f"/api/v1/workflows/{workflow_id}/execute",
            data=data,
            timeout=EXECUTION_TIMEOUT,
        )

    async def get_executions(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List workflow executions.

        WHAT: Retrieves execution history.

        WHY: Needed for execution log display and monitoring.

        Args:
            workflow_id: Filter by specific workflow (optional)
            limit: Maximum number of results
            cursor: Pagination cursor

        Returns:
            List of executions with pagination info
        """
        endpoint = "/api/v1/executions"
        params = []
        if workflow_id:
            params.append(f"workflowId={workflow_id}")
        if limit:
            params.append(f"limit={limit}")
        if cursor:
            params.append(f"cursor={cursor}")

        if params:
            endpoint += "?" + "&".join(params)

        return await self._request("GET", endpoint)

    async def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Get details of a specific execution.

        WHAT: Retrieves full execution data including results.

        WHY: Needed for execution detail view and debugging.

        Args:
            execution_id: n8n execution ID

        Returns:
            Execution object with full data
        """
        return await self._request("GET", f"/api/v1/executions/{execution_id}")

    async def stop_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Stop a running execution.

        WHAT: Cancels an in-progress execution.

        WHY: Enables cancelling stuck or erroneous executions.

        Args:
            execution_id: n8n execution ID

        Returns:
            Updated execution object
        """
        return await self._request("POST", f"/api/v1/executions/{execution_id}/stop")

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> bool:
        """
        Check if n8n instance is accessible.

        WHAT: Verifies connection to n8n.

        WHY: Needed for environment validation and monitoring.

        Returns:
            True if n8n is accessible, False otherwise
        """
        try:
            await self._request("GET", "/api/v1/workflows", timeout=10.0)
            return True
        except N8nError:
            return False


# ============================================================================
# Webhook Signature Validation
# ============================================================================


def validate_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """
    Validate n8n webhook signature.

    WHAT: Verifies webhook request authenticity.

    WHY: Security (OWASP A08) - prevents attackers from spoofing
    webhook calls and triggering unauthorized actions.

    HOW: Computes HMAC-SHA256 of payload and compares to signature.

    Args:
        payload: Raw request body
        signature: Signature from X-N8n-Signature header
        secret: Shared secret for HMAC

    Returns:
        True if signature is valid
    """
    if not signature or not secret:
        return False

    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


# ============================================================================
# Factory Function
# ============================================================================


def create_n8n_client(
    base_url: str,
    api_key_encrypted: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> N8nClient:
    """
    Create an n8n client instance.

    WHAT: Factory function for N8nClient.

    WHY: Provides clean interface for client creation.

    Args:
        base_url: n8n instance URL
        api_key_encrypted: Encrypted API key
        timeout: Request timeout

    Returns:
        Configured N8nClient instance
    """
    return N8nClient(
        base_url=base_url,
        api_key_encrypted=api_key_encrypted,
        timeout=timeout,
    )
