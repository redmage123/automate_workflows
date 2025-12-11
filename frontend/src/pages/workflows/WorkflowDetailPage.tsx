/**
 * Workflow Detail Page
 *
 * WHAT: Displays full workflow instance details with execution history.
 *
 * WHY: Provides comprehensive workflow view with:
 * - Workflow configuration and status
 * - Execution history with logs
 * - Status control actions (activate/pause/delete)
 * - Manual trigger capability
 *
 * HOW: Uses React Query for data fetching and mutations.
 */

import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import {
  getWorkflowInstance,
  activateWorkflow,
  pauseWorkflow,
  deleteWorkflow,
  executeWorkflow,
  getWorkflowExecutions,
} from '../../services/workflows';
import { WORKFLOW_STATUS_CONFIG, EXECUTION_STATUS_CONFIG } from '../../types/workflow';

/**
 * Format datetime for display
 *
 * WHAT: Converts ISO date string to localized datetime string.
 *
 * WHY: Provides user-friendly datetime display.
 *
 * HOW: Uses browser's toLocaleString for localization.
 */
function formatDateTime(dateString: string | null): string {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleString();
}

/**
 * Format duration in seconds to human-readable string
 *
 * WHAT: Converts seconds to readable duration.
 *
 * WHY: Execution times need to be easily understood.
 *
 * HOW: Calculates hours, minutes, seconds from total seconds.
 */
function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '-';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

export default function WorkflowDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');
  const workflowId = parseInt(id || '0', 10);
  const [executionsPage, setExecutionsPage] = useState(1);

  /**
   * Fetch workflow instance
   *
   * WHY: Load workflow details for display.
   */
  const {
    data: workflow,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => getWorkflowInstance(workflowId),
    enabled: workflowId > 0,
  });

  /**
   * Fetch execution history
   *
   * WHY: Show past executions with their status and duration.
   */
  const { data: executionsData } = useQuery({
    queryKey: ['workflow-executions', workflowId, executionsPage],
    queryFn: () => getWorkflowExecutions(workflowId, executionsPage, 10),
    enabled: workflowId > 0,
  });

  /**
   * Execute workflow mutation
   *
   * WHY: Allow manual triggering of workflow execution.
   */
  const executeMutation = useMutation({
    mutationFn: () => executeWorkflow(workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] });
      queryClient.invalidateQueries({ queryKey: ['workflow-executions', workflowId] });
    },
  });

  /**
   * Activate workflow mutation
   *
   * WHY: Enable workflow for scheduled/triggered execution.
   */
  const activateMutation = useMutation({
    mutationFn: () => activateWorkflow(workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] });
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  /**
   * Pause workflow mutation
   *
   * WHY: Temporarily disable workflow without deleting.
   */
  const pauseMutation = useMutation({
    mutationFn: () => pauseWorkflow(workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] });
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  /**
   * Delete workflow mutation
   *
   * WHY: Allow removal of workflows no longer needed.
   */
  const deleteMutation = useMutation({
    mutationFn: () => deleteWorkflow(workflowId),
    onSuccess: () => {
      navigate('/workflows');
    },
  });

  const handleExecute = () => {
    if (window.confirm('Execute this workflow now?')) {
      executeMutation.mutate();
    }
  };

  const handleActivate = () => {
    if (window.confirm('Activate this workflow?')) {
      activateMutation.mutate();
    }
  };

  const handlePause = () => {
    if (window.confirm('Pause this workflow?')) {
      pauseMutation.mutate();
    }
  };

  const handleDelete = () => {
    if (workflow && window.confirm(`Are you sure you want to delete "${workflow.name}"?`)) {
      deleteMutation.mutate();
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading workflow...</div>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">Workflow not found</h2>
        <p className="mt-2 text-gray-500">The workflow you're looking for doesn't exist.</p>
        <Link to="/workflows" className="mt-4 inline-block text-blue-600 hover:underline">
          Back to workflows
        </Link>
      </div>
    );
  }

  const statusConfig = WORKFLOW_STATUS_CONFIG[workflow.status];
  const executions = executionsData?.items || [];
  const totalExecutions = executionsData?.total || 0;
  const totalPages = Math.ceil(totalExecutions / 10);

  /**
   * Determine if workflow can be executed
   *
   * WHY: Only active workflows should be manually executable.
   */
  const canExecute = workflow.status === 'active';
  const canActivate = workflow.status === 'draft' || workflow.status === 'paused';
  const canPause = workflow.status === 'active';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/workflows" className="text-gray-500 hover:text-gray-700">
              Workflows
            </Link>
            <span className="text-gray-400">/</span>
            <span className="text-gray-900">{workflow.name}</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">{workflow.name}</h1>
          <div className="mt-2 flex items-center gap-4">
            <span
              className={`px-3 py-1 text-sm font-medium rounded-full ${statusConfig.bgColor} ${statusConfig.color}`}
            >
              {statusConfig.label}
            </span>
            {workflow.n8n_workflow_id && (
              <span className="text-sm text-gray-500">
                n8n ID: {workflow.n8n_workflow_id}
              </span>
            )}
          </div>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            {canExecute && (
              <button
                onClick={handleExecute}
                className="btn-primary"
                disabled={executeMutation.isPending}
              >
                {executeMutation.isPending ? 'Executing...' : 'Execute Now'}
              </button>
            )}
            <Link to={`/workflows/${workflow.id}/edit`} className="btn-secondary">
              Edit
            </Link>
            <button
              onClick={handleDelete}
              className="btn-danger"
              disabled={deleteMutation.isPending}
            >
              Delete
            </button>
          </div>
        )}
      </div>

      {/* Error Display */}
      {(executeMutation.isError || activateMutation.isError || pauseMutation.isError) && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">
            {(executeMutation.error as Error)?.message ||
              (activateMutation.error as Error)?.message ||
              (pauseMutation.error as Error)?.message ||
              'An error occurred'}
          </p>
        </div>
      )}

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Details & Executions */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Description</h2>
            <p className="text-gray-600 whitespace-pre-wrap">
              {workflow.description || 'No description provided.'}
            </p>
          </div>

          {/* Configuration */}
          {workflow.config && Object.keys(workflow.config).length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Configuration</h2>
              <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-auto">
                {JSON.stringify(workflow.config, null, 2)}
              </pre>
            </div>
          )}

          {/* Execution History */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Execution History</h2>
              <span className="text-sm text-gray-500">{totalExecutions} executions</span>
            </div>
            {executions.length === 0 ? (
              <p className="text-gray-500 text-sm">No executions yet.</p>
            ) : (
              <>
                <div className="space-y-3">
                  {executions.map((execution) => {
                    const execStatusConfig = EXECUTION_STATUS_CONFIG[execution.status];
                    return (
                      <div
                        key={execution.id}
                        className="p-4 border border-gray-200 rounded-lg"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span
                              className={`px-2 py-1 text-xs font-medium rounded-full ${execStatusConfig.bgColor} ${execStatusConfig.color}`}
                            >
                              {execStatusConfig.label}
                            </span>
                            <span className="text-sm text-gray-500">
                              {formatDateTime(execution.started_at)}
                            </span>
                          </div>
                          <div className="text-right text-sm">
                            <span className="text-gray-900 font-medium">
                              {formatDuration(execution.duration_seconds)}
                            </span>
                          </div>
                        </div>
                        {execution.error_message && (
                          <div className="mt-2 p-2 bg-red-50 rounded text-sm text-red-700">
                            {execution.error_message}
                          </div>
                        )}
                        {execution.output_data && Object.keys(execution.output_data).length > 0 && (
                          <details className="mt-2">
                            <summary className="text-sm text-blue-600 cursor-pointer hover:underline">
                              View Output
                            </summary>
                            <pre className="mt-2 p-2 bg-gray-50 rounded text-xs overflow-auto">
                              {JSON.stringify(execution.output_data, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    );
                  })}
                </div>
                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-2 mt-4">
                    <button
                      onClick={() => setExecutionsPage((p) => Math.max(1, p - 1))}
                      disabled={executionsPage === 1}
                      className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <span className="text-sm text-gray-500">
                      Page {executionsPage} of {totalPages}
                    </span>
                    <button
                      onClick={() => setExecutionsPage((p) => Math.min(totalPages, p + 1))}
                      disabled={executionsPage === totalPages}
                      className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Right Column - Sidebar */}
        <div className="space-y-6">
          {/* Status Actions */}
          {isAdmin && (canActivate || canPause) && (
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Workflow Control</h3>
              <div className="space-y-2">
                {canActivate && (
                  <button
                    onClick={handleActivate}
                    disabled={activateMutation.isPending}
                    className="w-full px-4 py-2 text-sm font-medium rounded-lg bg-green-100 text-green-700 border border-green-300 hover:bg-green-200 disabled:opacity-50"
                  >
                    {activateMutation.isPending ? 'Activating...' : 'Activate Workflow'}
                  </button>
                )}
                {canPause && (
                  <button
                    onClick={handlePause}
                    disabled={pauseMutation.isPending}
                    className="w-full px-4 py-2 text-sm font-medium rounded-lg bg-yellow-100 text-yellow-700 border border-yellow-300 hover:bg-yellow-200 disabled:opacity-50"
                  >
                    {pauseMutation.isPending ? 'Pausing...' : 'Pause Workflow'}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Workflow Info */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Details</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Workflow ID</dt>
                <dd className="text-gray-900 font-medium">{workflow.id}</dd>
              </div>
              {workflow.project_id && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Project</dt>
                  <dd>
                    <Link
                      to={`/projects/${workflow.project_id}`}
                      className="text-blue-600 hover:underline"
                    >
                      #{workflow.project_id}
                    </Link>
                  </dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-gray-500">Created</dt>
                <dd className="text-gray-900">{formatDateTime(workflow.created_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Updated</dt>
                <dd className="text-gray-900">{formatDateTime(workflow.updated_at)}</dd>
              </div>
              {workflow.last_executed_at && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Last Executed</dt>
                  <dd className="text-gray-900">{formatDateTime(workflow.last_executed_at)}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Execution Stats */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Statistics</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Total Executions</dt>
                <dd className="text-gray-900 font-medium">{workflow.execution_count}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Success Count</dt>
                <dd className="text-green-600 font-medium">{workflow.success_count}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Failure Count</dt>
                <dd className="text-red-600 font-medium">{workflow.failure_count}</dd>
              </div>
              {workflow.execution_count > 0 && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Success Rate</dt>
                  <dd className="text-gray-900 font-medium">
                    {((workflow.success_count / workflow.execution_count) * 100).toFixed(1)}%
                  </dd>
                </div>
              )}
            </dl>
            {workflow.execution_count > 0 && (
              <div className="mt-4">
                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-green-500 rounded-full"
                    style={{
                      width: `${(workflow.success_count / workflow.execution_count) * 100}%`,
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
