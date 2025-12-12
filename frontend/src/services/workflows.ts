/**
 * Workflow API Service
 *
 * WHAT: API client functions for workflow automation operations.
 *
 * WHY: Encapsulates all workflow-related API calls with proper typing,
 * error handling, and query parameter building.
 *
 * HOW: Uses the base API client with typed request/response functions.
 */

import { apiGet, apiPost, apiPatch, apiDelete } from './api';
import type {
  // N8n Environment
  N8nEnvironment,
  N8nEnvironmentCreateRequest,
  N8nEnvironmentUpdateRequest,
  N8nEnvironmentListResponse,
  N8nHealthCheckResponse,
  // Workflow Template
  WorkflowTemplate,
  WorkflowTemplateCreateRequest,
  WorkflowTemplateUpdateRequest,
  WorkflowTemplateListResponse,
  // Workflow Instance
  WorkflowInstance,
  WorkflowInstanceCreateRequest,
  WorkflowInstanceUpdateRequest,
  WorkflowStatusUpdateRequest,
  WorkflowInstanceListResponse,
  WorkflowInstanceListParams,
  WorkflowStats,
  // Execution Log
  ExecutionLog,
  ExecutionTriggerRequest,
  ExecutionLogListResponse,
  ExecutionStats,
} from '../types';

/**
 * Build query string from params object
 *
 * WHAT: Converts params object to URL query string.
 *
 * WHY: Filters out undefined values and properly encodes params.
 */
function buildQueryString(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value));
    }
  });
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}

// ============================================================================
// N8n Environment API
// ============================================================================

/**
 * Get paginated list of n8n environments
 *
 * @param params - Filter and pagination options
 * @returns Paginated environment list
 */
export async function getEnvironments(params: {
  skip?: number;
  limit?: number;
  active_only?: boolean;
} = {}): Promise<N8nEnvironmentListResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiGet<N8nEnvironmentListResponse>(`/api/workflows/environments${queryString}`);
}

/**
 * Get single n8n environment by ID
 *
 * @param id - Environment ID
 * @returns Environment data
 */
export async function getEnvironment(id: number): Promise<N8nEnvironment> {
  return apiGet<N8nEnvironment>(`/api/workflows/environments/${id}`);
}

/**
 * Create new n8n environment
 *
 * @param data - Environment creation data
 * @returns Created environment
 */
export async function createEnvironment(
  data: N8nEnvironmentCreateRequest
): Promise<N8nEnvironment> {
  return apiPost<N8nEnvironment>('/api/workflows/environments', data);
}

/**
 * Update n8n environment
 *
 * @param id - Environment ID
 * @param data - Update data
 * @returns Updated environment
 */
export async function updateEnvironment(
  id: number,
  data: N8nEnvironmentUpdateRequest
): Promise<N8nEnvironment> {
  return apiPatch<N8nEnvironment>(`/api/workflows/environments/${id}`, data);
}

/**
 * Delete n8n environment
 *
 * @param id - Environment ID
 */
export async function deleteEnvironment(id: number): Promise<void> {
  return apiDelete(`/api/workflows/environments/${id}`);
}

/**
 * Check n8n environment health
 *
 * @param id - Environment ID
 * @returns Health check result
 */
export async function checkEnvironmentHealth(id: number): Promise<N8nHealthCheckResponse> {
  return apiGet<N8nHealthCheckResponse>(`/api/workflows/environments/${id}/health`);
}

/**
 * N8n editor URL response
 */
export interface N8nEditorUrlResponse {
  editor_url: string;
  base_url: string;
  environment_name: string;
  workflow_id: string | null;
  instructions: string;
}

/**
 * Get n8n visual editor URL
 *
 * WHY: n8n has a powerful built-in graphical workflow designer.
 * This returns the URL to access it directly.
 *
 * @param environmentId - Environment ID
 * @param workflowId - Optional workflow ID to edit
 * @returns Editor URL and instructions
 */
export async function getN8nEditorUrl(
  environmentId: number,
  workflowId?: string
): Promise<N8nEditorUrlResponse> {
  const queryString = workflowId ? `?workflow_id=${workflowId}` : '';
  return apiGet<N8nEditorUrlResponse>(
    `/api/workflows/environments/${environmentId}/editor-url${queryString}`
  );
}

// ============================================================================
// Workflow Template API
// ============================================================================

/**
 * Get paginated list of workflow templates
 *
 * @param params - Filter and pagination options
 * @returns Paginated template list with categories
 */
export async function getTemplates(params: {
  skip?: number;
  limit?: number;
  category?: string;
} = {}): Promise<WorkflowTemplateListResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiGet<WorkflowTemplateListResponse>(`/api/workflows/templates${queryString}`);
}

/**
 * Get single workflow template by ID
 *
 * @param id - Template ID
 * @returns Template data
 */
export async function getTemplate(id: number): Promise<WorkflowTemplate> {
  return apiGet<WorkflowTemplate>(`/api/workflows/templates/${id}`);
}

/**
 * Create new workflow template
 *
 * @param data - Template creation data
 * @returns Created template
 */
export async function createTemplate(
  data: WorkflowTemplateCreateRequest
): Promise<WorkflowTemplate> {
  return apiPost<WorkflowTemplate>('/api/workflows/templates', data);
}

/**
 * Update workflow template
 *
 * @param id - Template ID
 * @param data - Update data
 * @returns Updated template
 */
export async function updateTemplate(
  id: number,
  data: WorkflowTemplateUpdateRequest
): Promise<WorkflowTemplate> {
  return apiPatch<WorkflowTemplate>(`/api/workflows/templates/${id}`, data);
}

// ============================================================================
// Workflow Instance API
// ============================================================================

/**
 * Get paginated list of workflow instances
 *
 * @param params - Filter and pagination options
 * @returns Paginated instance list
 */
export async function getInstances(
  params: WorkflowInstanceListParams = {}
): Promise<WorkflowInstanceListResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiGet<WorkflowInstanceListResponse>(`/api/workflows/instances${queryString}`);
}

/**
 * Get single workflow instance by ID
 *
 * @param id - Instance ID
 * @returns Instance data
 */
export async function getInstance(id: number): Promise<WorkflowInstance> {
  return apiGet<WorkflowInstance>(`/api/workflows/instances/${id}`);
}

/**
 * Create new workflow instance
 *
 * @param data - Instance creation data
 * @returns Created instance
 */
export async function createInstance(
  data: WorkflowInstanceCreateRequest
): Promise<WorkflowInstance> {
  return apiPost<WorkflowInstance>('/api/workflows/instances', data);
}

/**
 * Update workflow instance
 *
 * @param id - Instance ID
 * @param data - Update data
 * @returns Updated instance
 */
export async function updateInstance(
  id: number,
  data: WorkflowInstanceUpdateRequest
): Promise<WorkflowInstance> {
  return apiPatch<WorkflowInstance>(`/api/workflows/instances/${id}`, data);
}

/**
 * Update workflow instance status
 *
 * @param id - Instance ID
 * @param data - New status
 * @returns Updated instance
 */
export async function updateInstanceStatus(
  id: number,
  data: WorkflowStatusUpdateRequest
): Promise<WorkflowInstance> {
  return apiPost<WorkflowInstance>(`/api/workflows/instances/${id}/status`, data);
}

/**
 * Delete (soft-delete) workflow instance
 *
 * @param id - Instance ID
 */
export async function deleteInstance(id: number): Promise<void> {
  return apiDelete(`/api/workflows/instances/${id}`);
}

/**
 * Get workflow instance statistics
 *
 * @param id - Instance ID
 * @returns Workflow statistics
 */
export async function getInstanceStats(id: number): Promise<WorkflowStats> {
  return apiGet<WorkflowStats>(`/api/workflows/instances/${id}/stats`);
}

// ============================================================================
// Execution API
// ============================================================================

/**
 * Trigger workflow execution
 *
 * @param instanceId - Workflow instance ID
 * @param data - Optional input data
 * @returns Execution log
 */
export async function triggerExecution(
  instanceId: number,
  data: ExecutionTriggerRequest = {}
): Promise<ExecutionLog> {
  return apiPost<ExecutionLog>(`/api/workflows/instances/${instanceId}/execute`, data);
}

/**
 * Get paginated list of executions for a workflow
 *
 * @param instanceId - Workflow instance ID
 * @param params - Pagination options
 * @returns Paginated execution list
 */
export async function getExecutions(
  instanceId: number,
  params: { skip?: number; limit?: number } = {}
): Promise<ExecutionLogListResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiGet<ExecutionLogListResponse>(
    `/api/workflows/instances/${instanceId}/executions${queryString}`
  );
}

/**
 * Get single execution by ID
 *
 * @param instanceId - Workflow instance ID
 * @param executionId - Execution ID
 * @returns Execution data
 */
export async function getExecution(
  instanceId: number,
  executionId: number
): Promise<ExecutionLog> {
  return apiGet<ExecutionLog>(
    `/api/workflows/instances/${instanceId}/executions/${executionId}`
  );
}

/**
 * Get execution statistics for a workflow
 *
 * @param instanceId - Workflow instance ID
 * @returns Execution statistics
 */
export async function getExecutionStats(instanceId: number): Promise<ExecutionStats> {
  return apiGet<ExecutionStats>(`/api/workflows/instances/${instanceId}/executions/stats`);
}

// ============================================================================
// Convenience Aliases for UI Components
// ============================================================================

/**
 * Get workflow instance by ID (alias for getInstance)
 */
export const getWorkflowInstance = getInstance;

/**
 * Create workflow instance (alias for createInstance)
 */
export const createWorkflowInstance = createInstance;

/**
 * Update workflow instance (alias for updateInstance)
 */
export const updateWorkflowInstance = updateInstance;

/**
 * Delete workflow instance (alias for deleteInstance)
 */
export const deleteWorkflow = deleteInstance;

/**
 * Execute workflow (alias for triggerExecution)
 */
export async function executeWorkflow(instanceId: number): Promise<ExecutionLog> {
  return triggerExecution(instanceId);
}

/**
 * Get workflow executions (alias for getExecutions)
 */
export async function getWorkflowExecutions(
  instanceId: number,
  page: number = 1,
  limit: number = 10
): Promise<ExecutionLogListResponse> {
  return getExecutions(instanceId, { skip: (page - 1) * limit, limit });
}

/**
 * Activate workflow by setting status to active
 */
export async function activateWorkflow(instanceId: number): Promise<WorkflowInstance> {
  return updateInstanceStatus(instanceId, { status: 'active' });
}

/**
 * Pause workflow by setting status to paused
 */
export async function pauseWorkflow(instanceId: number): Promise<WorkflowInstance> {
  return updateInstanceStatus(instanceId, { status: 'paused' });
}

/**
 * Test n8n environment connection
 *
 * @param id - Environment ID (optional, tests first active if not provided)
 * @returns Health check result
 */
export async function testEnvironmentConnection(id?: number): Promise<N8nHealthCheckResponse> {
  if (id) {
    return checkEnvironmentHealth(id);
  }
  // If no ID provided, get the first environment and test it
  const envs = await getEnvironments({ active_only: true, limit: 1 });
  if (envs.items.length === 0) {
    throw new Error('No active n8n environment configured');
  }
  return checkEnvironmentHealth(envs.items[0].id);
}

// ============================================================================
// Workflow AI API (Natural Language Generation)
// ============================================================================

/**
 * AI-generated workflow response
 *
 * WHY: Defines the structure returned by AI generation endpoints.
 */
export interface WorkflowGenerationResponse {
  name: string;
  nodes: Record<string, unknown>[];
  connections: Record<string, unknown>;
  settings: Record<string, unknown>;
  explanation: string;
  confidence: number;
  suggestions: string[];
}

/**
 * AI service status response
 */
export interface AIServiceStatusResponse {
  available: boolean;
  model: string | null;
  message: string;
}

/**
 * Workflow validation response
 */
export interface WorkflowValidationResponse {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

/**
 * Check AI service availability
 *
 * WHY: Frontend should know if AI features are available to show/hide UI.
 */
export async function getAIServiceStatus(): Promise<AIServiceStatusResponse> {
  return apiGet<AIServiceStatusResponse>('/api/workflow-ai/status');
}

/**
 * Generate workflow from natural language description
 *
 * @param description - Plain text description of desired workflow
 * @param context - Optional context (available_credentials, project_name, etc.)
 * @returns Generated workflow with metadata
 */
export async function generateWorkflowFromDescription(
  description: string,
  context?: Record<string, unknown>
): Promise<WorkflowGenerationResponse> {
  return apiPost<WorkflowGenerationResponse>('/api/workflow-ai/generate', {
    description,
    context,
  });
}

/**
 * Refine existing workflow based on feedback
 *
 * @param workflow - Current workflow JSON
 * @param feedback - User's refinement request
 * @returns Updated workflow with metadata
 */
export async function refineWorkflow(
  workflow: Record<string, unknown>,
  feedback: string
): Promise<WorkflowGenerationResponse> {
  return apiPost<WorkflowGenerationResponse>('/api/workflow-ai/refine', {
    workflow,
    feedback,
  });
}

/**
 * Validate workflow structure
 *
 * @param workflow - Workflow JSON to validate
 * @returns Validation result with errors and warnings
 */
export async function validateWorkflow(
  workflow: Record<string, unknown>
): Promise<WorkflowValidationResponse> {
  return apiPost<WorkflowValidationResponse>('/api/workflow-ai/validate', {
    workflow,
  });
}
