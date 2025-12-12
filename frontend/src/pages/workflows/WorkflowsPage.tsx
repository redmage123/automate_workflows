/**
 * Workflows List Page
 *
 * WHAT: Main page for viewing and managing workflow instances.
 *
 * WHY: Provides a filterable, paginated list of workflows with:
 * - Status filters
 * - Quick actions (view, execute, pause/activate)
 * - Create new workflow button
 *
 * HOW: Uses React Query for data fetching with proper loading states.
 */

import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import {
  getInstances,
  updateInstanceStatus,
  deleteInstance,
  triggerExecution,
  getEnvironments,
  getN8nEditorUrl,
} from '../../services/workflows';
import type { WorkflowStatus, WorkflowInstanceListParams } from '../../types';
import { WORKFLOW_STATUS_CONFIG } from '../../types/workflow';

/**
 * Status badge component
 */
function StatusBadge({ status }: { status: WorkflowStatus }) {
  const config = WORKFLOW_STATUS_CONFIG[status];
  return (
    <span className={`px-2 py-1 text-xs font-medium rounded-full ${config.bgColor} ${config.color}`}>
      {config.label}
    </span>
  );
}

/**
 * Format date for display
 */
function formatDate(dateString: string | null): string {
  if (!dateString) return 'Never';
  return new Date(dateString).toLocaleString();
}

export default function WorkflowsPage() {
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');

  // Filter state
  const [statusFilter, setStatusFilter] = useState<WorkflowStatus | ''>('');
  const [page, setPage] = useState(0);
  const pageSize = 10;
  const [isOpeningN8n, setIsOpeningN8n] = useState(false);

  // Fetch n8n environments to enable "Design in n8n" button
  const { data: environmentsData } = useQuery({
    queryKey: ['n8n-environments'],
    queryFn: () => getEnvironments({ active_only: true, limit: 1 }),
  });

  // Build query params
  const queryParams: WorkflowInstanceListParams = useMemo(
    () => ({
      skip: page * pageSize,
      limit: pageSize,
      status: statusFilter || undefined,
    }),
    [page, statusFilter]
  );

  // Fetch workflows
  const {
    data: workflowsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['workflows', queryParams],
    queryFn: () => getInstances(queryParams),
  });

  // Status update mutation
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: 'active' | 'paused' }) =>
      updateInstanceStatus(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  // Execute mutation
  const executeMutation = useMutation({
    mutationFn: (id: number) => triggerExecution(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteInstance,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  const workflows = workflowsData?.items || [];
  const total = workflowsData?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  const handleDelete = async (id: number, name: string) => {
    if (window.confirm(`Are you sure you want to delete workflow "${name}"?`)) {
      deleteMutation.mutate(id);
    }
  };

  const handleToggleStatus = (id: number, currentStatus: WorkflowStatus) => {
    const newStatus = currentStatus === 'active' ? 'paused' : 'active';
    statusMutation.mutate({ id, status: newStatus });
  };

  const handleExecute = (id: number) => {
    executeMutation.mutate(id);
  };

  const handleOpenN8nEditor = async () => {
    const activeEnv = environmentsData?.items?.[0];
    if (!activeEnv) {
      alert('No active n8n environment configured. Please set up an n8n environment first.');
      return;
    }

    setIsOpeningN8n(true);
    try {
      const result = await getN8nEditorUrl(activeEnv.id);
      // Open n8n editor in a new tab
      window.open(result.editor_url, '_blank', 'noopener,noreferrer');
    } catch (error) {
      alert('Failed to get n8n editor URL. Please check your n8n environment configuration.');
    } finally {
      setIsOpeningN8n(false);
    }
  };

  const hasActiveEnvironment = (environmentsData?.items?.length ?? 0) > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your automation workflows
          </p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <Link
              to="/workflows/ai"
              className="btn-secondary inline-flex items-center"
            >
              <svg
                className="w-4 h-4 mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
              Create with AI
            </Link>
            {hasActiveEnvironment && (
              <button
                onClick={handleOpenN8nEditor}
                disabled={isOpeningN8n}
                className="btn-secondary inline-flex items-center"
                title="Open n8n visual workflow editor"
              >
                <svg
                  className="w-4 h-4 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
                  />
                </svg>
                {isOpeningN8n ? 'Opening...' : 'Design in n8n'}
              </button>
            )}
            <Link
              to="/workflows/new"
              className="btn-primary inline-flex items-center"
            >
              <svg
                className="w-4 h-4 mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              New Workflow
            </Link>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg shadow-sm border">
        <div className="flex flex-wrap gap-4">
          <div>
            <label htmlFor="status" className="block text-sm font-medium text-gray-700">
              Status
            </label>
            <select
              id="status"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as WorkflowStatus | '');
                setPage(0);
              }}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            >
              <option value="">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="error">Error</option>
            </select>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          Error loading workflows. Please try again.
        </div>
      )}

      {/* Workflows Table */}
      {!isLoading && !error && (
        <div className="bg-white shadow-sm rounded-lg border overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Execution
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {workflows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                    No workflows found. Create your first workflow to get started.
                  </td>
                </tr>
              ) : (
                workflows.map((workflow) => (
                  <tr key={workflow.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Link
                        to={`/workflows/${workflow.id}`}
                        className="text-blue-600 hover:text-blue-900 font-medium"
                      >
                        {workflow.name}
                      </Link>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={workflow.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(workflow.last_execution_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(workflow.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end space-x-2">
                        {/* Execute Button */}
                        {workflow.can_execute && (
                          <button
                            onClick={() => handleExecute(workflow.id)}
                            disabled={executeMutation.isPending}
                            className="text-green-600 hover:text-green-900 disabled:opacity-50"
                            title="Execute"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          </button>
                        )}

                        {/* Toggle Status Button */}
                        {isAdmin && (workflow.status === 'active' || workflow.status === 'paused') && (
                          <button
                            onClick={() => handleToggleStatus(workflow.id, workflow.status)}
                            disabled={statusMutation.isPending}
                            className={`${
                              workflow.status === 'active'
                                ? 'text-yellow-600 hover:text-yellow-900'
                                : 'text-green-600 hover:text-green-900'
                            } disabled:opacity-50`}
                            title={workflow.status === 'active' ? 'Pause' : 'Activate'}
                          >
                            {workflow.status === 'active' ? (
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            ) : (
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            )}
                          </button>
                        )}

                        {/* View Button */}
                        <Link
                          to={`/workflows/${workflow.id}`}
                          className="text-blue-600 hover:text-blue-900"
                          title="View Details"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        </Link>

                        {/* Delete Button */}
                        {isAdmin && (
                          <button
                            onClick={() => handleDelete(workflow.id, workflow.name)}
                            disabled={deleteMutation.isPending}
                            className="text-red-600 hover:text-red-900 disabled:opacity-50"
                            title="Delete"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200">
              <div className="flex-1 flex justify-between sm:hidden">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="btn-secondary disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="btn-secondary disabled:opacity-50"
                >
                  Next
                </button>
              </div>
              <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm text-gray-700">
                    Showing{' '}
                    <span className="font-medium">{page * pageSize + 1}</span> to{' '}
                    <span className="font-medium">
                      {Math.min((page + 1) * pageSize, total)}
                    </span>{' '}
                    of <span className="font-medium">{total}</span> results
                  </p>
                </div>
                <div>
                  <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                    <button
                      onClick={() => setPage((p) => Math.max(0, p - 1))}
                      disabled={page === 0}
                      className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                      disabled={page >= totalPages - 1}
                      className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                    >
                      Next
                    </button>
                  </nav>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
