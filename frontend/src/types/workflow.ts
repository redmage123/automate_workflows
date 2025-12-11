/**
 * Workflow Type Definitions
 *
 * WHAT: TypeScript types for workflow automation entities.
 *
 * WHY: Provides type safety for:
 * - N8n environment configuration
 * - Workflow templates
 * - Workflow instances
 * - Execution logs
 *
 * HOW: Mirrors backend Pydantic schemas for API contract consistency.
 */

/**
 * Workflow status enum
 *
 * WHY: Tracks workflow instance lifecycle.
 */
export type WorkflowStatus = 'draft' | 'active' | 'paused' | 'error' | 'deleted';

/**
 * Execution status enum
 *
 * WHY: Tracks individual execution runs.
 */
export type ExecutionStatus = 'running' | 'success' | 'failed' | 'cancelled';

/**
 * N8n Environment
 *
 * WHAT: Represents an n8n instance configuration.
 *
 * WHY: Organizations may have multiple n8n environments
 * (production, staging) or their own n8n instances.
 */
export interface N8nEnvironment {
  id: number;
  org_id: number;
  name: string;
  base_url: string;
  is_active: boolean;
  webhook_url: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface N8nEnvironmentCreateRequest {
  name: string;
  base_url: string;
  api_key: string;
  webhook_url?: string;
  is_active?: boolean;
}

export interface N8nEnvironmentUpdateRequest {
  name?: string;
  base_url?: string;
  api_key?: string;
  webhook_url?: string;
  is_active?: boolean;
}

export interface N8nEnvironmentListResponse {
  items: N8nEnvironment[];
  total: number;
  skip: number;
  limit: number;
}

export interface N8nHealthCheckResponse {
  environment_id: number;
  is_healthy: boolean;
  checked_at: string;
}

/**
 * Workflow Template
 *
 * WHAT: Reusable workflow blueprint.
 *
 * WHY: Templates provide pre-built automations that can be
 * customized and deployed as instances.
 */
export interface WorkflowTemplate {
  id: number;
  name: string;
  description: string | null;
  category: string;
  n8n_template_id: string | null;
  default_config: Record<string, unknown> | null;
  default_parameters: Record<string, unknown> | null;
  version: string;
  is_public: boolean;
  created_by_org_id: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface WorkflowTemplateCreateRequest {
  name: string;
  description?: string;
  category?: string;
  n8n_template_id?: string;
  default_parameters?: Record<string, unknown>;
  is_public?: boolean;
}

export interface WorkflowTemplateUpdateRequest {
  name?: string;
  description?: string;
  category?: string;
  n8n_template_id?: string;
  default_parameters?: Record<string, unknown>;
  is_public?: boolean;
}

export interface WorkflowTemplateListResponse {
  items: WorkflowTemplate[];
  total: number;
  skip: number;
  limit: number;
  categories: string[];
}

/**
 * Workflow Instance
 *
 * WHAT: A deployed workflow automation.
 *
 * WHY: Instances are active workflows that can be executed.
 * They're linked to projects for billing/tracking.
 */
export interface WorkflowInstance {
  id: number;
  org_id: number;
  name: string;
  description: string | null;
  status: WorkflowStatus;
  template_id: number | null;
  project_id: number | null;
  n8n_environment_id: number | null;
  n8n_workflow_id: string | null;
  config: Record<string, unknown> | null;
  parameters: Record<string, unknown> | null;
  last_execution_at: string | null;
  last_executed_at: string | null;
  execution_count: number;
  success_count: number;
  failure_count: number;
  created_at: string;
  updated_at: string | null;
  is_active: boolean;
  can_execute: boolean;
}

export interface WorkflowInstanceCreateRequest {
  name: string;
  description?: string;
  template_id?: number;
  project_id?: number;
  n8n_environment_id?: number;
  config?: Record<string, unknown>;
  parameters?: Record<string, unknown>;
}

export interface WorkflowInstanceUpdateRequest {
  name?: string;
  description?: string;
  project_id?: number;
  n8n_environment_id?: number;
  config?: Record<string, unknown>;
  parameters?: Record<string, unknown>;
}

// Aliases for page components
export type WorkflowInstanceCreate = WorkflowInstanceCreateRequest;
export type WorkflowInstanceUpdate = WorkflowInstanceUpdateRequest;
export type N8nEnvironmentCreate = N8nEnvironmentCreateRequest;
export type N8nEnvironmentUpdate = N8nEnvironmentUpdateRequest;

export interface WorkflowStatusUpdateRequest {
  status: Exclude<WorkflowStatus, 'deleted'>;
}

export interface WorkflowInstanceListResponse {
  items: WorkflowInstance[];
  total: number;
  skip: number;
  limit: number;
}

export interface WorkflowInstanceListParams {
  skip?: number;
  limit?: number;
  status?: WorkflowStatus;
  project_id?: number;
}

export interface WorkflowStats {
  total: number;
  active: number;
  by_status: Record<string, number>;
  total_executions: number;
  success_rate: number | null;
}

/**
 * Execution Log
 *
 * WHAT: Record of a workflow execution.
 *
 * WHY: Provides audit trail and debugging information.
 */
export interface ExecutionLog {
  id: number;
  workflow_instance_id: number;
  n8n_execution_id: string | null;
  status: ExecutionStatus;
  started_at: string;
  finished_at: string | null;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  error_message: string | null;
  duration_seconds: number | null;
  is_complete: boolean;
}

export interface ExecutionTriggerRequest {
  input_data?: Record<string, unknown>;
}

export interface ExecutionLogListResponse {
  items: ExecutionLog[];
  total: number;
  skip: number;
  limit: number;
}

export interface ExecutionStats {
  total: number;
  success: number;
  failed: number;
  running: number;
  success_rate: number | null;
  average_duration: number | null;
}

/**
 * Status display configuration
 *
 * WHY: Provides consistent status styling across UI components.
 */
export const WORKFLOW_STATUS_CONFIG: Record<
  WorkflowStatus,
  { label: string; color: string; bgColor: string }
> = {
  draft: { label: 'Draft', color: 'text-gray-600', bgColor: 'bg-gray-100' },
  active: { label: 'Active', color: 'text-green-600', bgColor: 'bg-green-100' },
  paused: { label: 'Paused', color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  error: { label: 'Error', color: 'text-red-600', bgColor: 'bg-red-100' },
  deleted: { label: 'Deleted', color: 'text-gray-400', bgColor: 'bg-gray-50' },
};

export const EXECUTION_STATUS_CONFIG: Record<
  ExecutionStatus,
  { label: string; color: string; bgColor: string }
> = {
  running: { label: 'Running', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  success: { label: 'Success', color: 'text-green-600', bgColor: 'bg-green-100' },
  failed: { label: 'Failed', color: 'text-red-600', bgColor: 'bg-red-100' },
  cancelled: { label: 'Cancelled', color: 'text-gray-600', bgColor: 'bg-gray-100' },
};
