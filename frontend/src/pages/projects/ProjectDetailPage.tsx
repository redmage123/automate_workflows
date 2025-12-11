/**
 * Project Detail Page
 *
 * WHAT: Displays full project details with related proposals.
 *
 * WHY: Provides comprehensive project view with:
 * - Project info and status
 * - Hours tracking
 * - Related proposals list
 * - Status change workflow
 *
 * HOW: Uses React Query for data fetching and mutations.
 */

import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import { getProject, updateProjectStatus, deleteProject, getProjectProposals } from '../../services/projects';
import { ProjectStatus } from '../../types';
import { PROJECT_STATUS_CONFIG, PROJECT_PRIORITY_CONFIG } from '../../types/project';
import { PROPOSAL_STATUS_CONFIG, formatCurrency } from '../../types/proposal';

/**
 * Format date for display
 */
function formatDate(dateString: string | null): string {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString();
}

/**
 * Format datetime for display
 */
function formatDateTime(dateString: string | null): string {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleString();
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');
  const projectId = parseInt(id || '0', 10);

  // Fetch project
  const {
    data: project,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: projectId > 0,
  });

  // Fetch proposals
  const { data: proposalsData } = useQuery({
    queryKey: ['project-proposals', projectId],
    queryFn: () => getProjectProposals(projectId),
    enabled: projectId > 0,
  });

  // Status update mutation
  const statusMutation = useMutation({
    mutationFn: (status: ProjectStatus) => updateProjectStatus(projectId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: () => deleteProject(projectId),
    onSuccess: () => {
      navigate('/projects');
    },
  });

  const handleDelete = () => {
    if (project && window.confirm(`Are you sure you want to delete "${project.name}"?`)) {
      deleteMutation.mutate();
    }
  };

  const handleStatusChange = (status: ProjectStatus) => {
    if (window.confirm(`Change status to "${PROJECT_STATUS_CONFIG[status].label}"?`)) {
      statusMutation.mutate(status);
    }
  };

  // Available status transitions based on current status
  const getAvailableStatuses = (current: ProjectStatus): ProjectStatus[] => {
    const transitions: Record<ProjectStatus, ProjectStatus[]> = {
      draft: ['proposal_sent', 'cancelled'],
      proposal_sent: ['approved', 'draft', 'cancelled'],
      approved: ['in_progress', 'on_hold', 'cancelled'],
      in_progress: ['completed', 'on_hold', 'cancelled'],
      on_hold: ['in_progress', 'cancelled'],
      completed: [],
      cancelled: ['draft'],
    };
    return transitions[current] || [];
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading project...</div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">Project not found</h2>
        <p className="mt-2 text-gray-500">The project you're looking for doesn't exist.</p>
        <Link to="/projects" className="mt-4 inline-block text-blue-600 hover:underline">
          Back to projects
        </Link>
      </div>
    );
  }

  const statusConfig = PROJECT_STATUS_CONFIG[project.status];
  const priorityConfig = PROJECT_PRIORITY_CONFIG[project.priority];
  const availableStatuses = getAvailableStatuses(project.status);
  const proposals = proposalsData?.items || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/projects" className="text-gray-500 hover:text-gray-700">
              Projects
            </Link>
            <span className="text-gray-400">/</span>
            <span className="text-gray-900">{project.name}</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">{project.name}</h1>
          <div className="mt-2 flex items-center gap-4">
            <span className={`px-3 py-1 text-sm font-medium rounded-full ${statusConfig.bgColor} ${statusConfig.color}`}>
              {statusConfig.label}
            </span>
            <span className={`px-3 py-1 text-sm font-medium rounded-full ${priorityConfig.bgColor} ${priorityConfig.color}`}>
              {priorityConfig.label} Priority
            </span>
            {project.is_overdue && (
              <span className="px-3 py-1 text-sm font-medium rounded-full bg-red-100 text-red-600">
                Overdue
              </span>
            )}
          </div>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <Link to={`/projects/${project.id}/edit`} className="btn-secondary">
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

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Description</h2>
            <p className="text-gray-600 whitespace-pre-wrap">
              {project.description || 'No description provided.'}
            </p>
          </div>

          {/* Proposals */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Proposals</h2>
              {isAdmin && (
                <Link
                  to={`/proposals/new?project_id=${project.id}`}
                  className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                >
                  + Create Proposal
                </Link>
              )}
            </div>
            {proposals.length === 0 ? (
              <p className="text-gray-500 text-sm">No proposals yet.</p>
            ) : (
              <div className="space-y-3">
                {proposals.map((proposal) => {
                  const pStatusConfig = PROPOSAL_STATUS_CONFIG[proposal.status];
                  return (
                    <Link
                      key={proposal.id}
                      to={`/proposals/${proposal.id}`}
                      className="block p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-gray-900">{proposal.title}</p>
                          <p className="text-sm text-gray-500">Version {proposal.version}</p>
                        </div>
                        <div className="text-right">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${pStatusConfig.bgColor} ${pStatusConfig.color}`}>
                            {pStatusConfig.label}
                          </span>
                          <p className="mt-1 font-semibold text-gray-900">
                            {formatCurrency(proposal.total)}
                          </p>
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column - Sidebar */}
        <div className="space-y-6">
          {/* Status Actions */}
          {isAdmin && availableStatuses.length > 0 && (
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Change Status</h3>
              <div className="space-y-2">
                {availableStatuses.map((status) => {
                  const config = PROJECT_STATUS_CONFIG[status];
                  return (
                    <button
                      key={status}
                      onClick={() => handleStatusChange(status)}
                      disabled={statusMutation.isPending}
                      className={`w-full px-4 py-2 text-sm font-medium rounded-lg border transition-colors ${config.bgColor} ${config.color} border-current hover:opacity-80 disabled:opacity-50`}
                    >
                      Mark as {config.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Project Info */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Details</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Project ID</dt>
                <dd className="text-gray-900 font-medium">{project.id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Created</dt>
                <dd className="text-gray-900">{formatDateTime(project.created_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Updated</dt>
                <dd className="text-gray-900">{formatDateTime(project.updated_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Start Date</dt>
                <dd className="text-gray-900">{formatDate(project.start_date)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Due Date</dt>
                <dd className={project.is_overdue ? 'text-red-600 font-medium' : 'text-gray-900'}>
                  {formatDate(project.due_date)}
                </dd>
              </div>
              {project.completed_at && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Completed</dt>
                  <dd className="text-green-600">{formatDateTime(project.completed_at)}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Hours Tracking */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Hours</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Estimated</dt>
                <dd className="text-gray-900 font-medium">
                  {project.estimated_hours ? `${project.estimated_hours}h` : '-'}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Actual</dt>
                <dd className="text-gray-900 font-medium">
                  {project.actual_hours ? `${project.actual_hours}h` : '0h'}
                </dd>
              </div>
              {project.hours_remaining !== null && project.hours_remaining !== undefined && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Remaining</dt>
                  <dd className={project.hours_remaining < 0 ? 'text-red-600 font-medium' : 'text-gray-900'}>
                    {project.hours_remaining}h
                  </dd>
                </div>
              )}
            </dl>
            {project.estimated_hours && project.actual_hours !== null && (
              <div className="mt-4">
                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      (project.actual_hours || 0) > project.estimated_hours
                        ? 'bg-red-500'
                        : 'bg-blue-500'
                    }`}
                    style={{
                      width: `${Math.min(100, ((project.actual_hours || 0) / project.estimated_hours) * 100)}%`,
                    }}
                  />
                </div>
                <p className="text-xs text-gray-500 mt-1 text-center">
                  {Math.round(((project.actual_hours || 0) / project.estimated_hours) * 100)}% of estimate
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
