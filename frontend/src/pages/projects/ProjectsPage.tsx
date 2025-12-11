/**
 * Projects List Page
 *
 * WHAT: Main page for viewing and managing projects.
 *
 * WHY: Provides a filterable, paginated list of projects with:
 * - Status and priority filters
 * - Search functionality
 * - Quick actions (view, edit, status update)
 * - Create new project button
 *
 * HOW: Uses React Query for data fetching with proper loading states.
 */

import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import {
  getProjects,
  getProjectStats,
  deleteProject,
} from '../../services/projects';
import type { ProjectStatus, ProjectPriority, ProjectListParams } from '../../types';
import { PROJECT_STATUS_CONFIG, PROJECT_PRIORITY_CONFIG } from '../../types/project';

/**
 * Status badge component
 *
 * WHAT: Displays project status with appropriate styling.
 */
function StatusBadge({ status }: { status: ProjectStatus }) {
  const config = PROJECT_STATUS_CONFIG[status];
  return (
    <span className={`px-2 py-1 text-xs font-medium rounded-full ${config.bgColor} ${config.color}`}>
      {config.label}
    </span>
  );
}

/**
 * Priority badge component
 *
 * WHAT: Displays project priority with appropriate styling.
 */
function PriorityBadge({ priority }: { priority: ProjectPriority }) {
  const config = PROJECT_PRIORITY_CONFIG[priority];
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
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString();
}

export default function ProjectsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');

  // Filter state
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | ''>('');
  const [priorityFilter, setPriorityFilter] = useState<ProjectPriority | ''>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeOnly, setActiveOnly] = useState(true);
  const [page, setPage] = useState(0);
  const pageSize = 10;

  // Build query params
  const queryParams: ProjectListParams = useMemo(
    () => ({
      skip: page * pageSize,
      limit: pageSize,
      status: statusFilter || undefined,
      priority: priorityFilter || undefined,
      search: searchQuery.length >= 3 ? searchQuery : undefined,
      active_only: activeOnly,
    }),
    [page, statusFilter, priorityFilter, searchQuery, activeOnly]
  );

  // Fetch projects
  const {
    data: projectsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['projects', queryParams],
    queryFn: () => getProjects(queryParams),
  });

  // Fetch stats
  const { data: stats } = useQuery({
    queryKey: ['project-stats'],
    queryFn: getProjectStats,
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['project-stats'] });
    },
  });

  const projects = projectsData?.items || [];
  const total = projectsData?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  const handleDelete = async (id: number, name: string) => {
    if (window.confirm(`Are you sure you want to delete project "${name}"?`)) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your automation projects
          </p>
        </div>
        {isAdmin && (
          <Link
            to="/projects/new"
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
            New Project
          </Link>
        )}
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Total Projects</p>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{stats.total}</p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Active</p>
            <p className="mt-1 text-2xl font-semibold text-green-600">{stats.active}</p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">In Progress</p>
            <p className="mt-1 text-2xl font-semibold text-blue-600">
              {stats.by_status?.in_progress || 0}
            </p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Overdue</p>
            <p className="mt-1 text-2xl font-semibold text-red-600">{stats.overdue}</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {/* Search */}
          <div className="lg:col-span-2">
            <label htmlFor="search" className="sr-only">
              Search projects
            </label>
            <input
              id="search"
              type="text"
              placeholder="Search projects (min 3 chars)..."
              className="input w-full"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(0);
              }}
            />
          </div>

          {/* Status Filter */}
          <div>
            <label htmlFor="status-filter" className="sr-only">
              Filter by status
            </label>
            <select
              id="status-filter"
              className="input w-full"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as ProjectStatus | '');
                setPage(0);
              }}
            >
              <option value="">All Statuses</option>
              {Object.entries(PROJECT_STATUS_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>

          {/* Priority Filter */}
          <div>
            <label htmlFor="priority-filter" className="sr-only">
              Filter by priority
            </label>
            <select
              id="priority-filter"
              className="input w-full"
              value={priorityFilter}
              onChange={(e) => {
                setPriorityFilter(e.target.value as ProjectPriority | '');
                setPage(0);
              }}
            >
              <option value="">All Priorities</option>
              {Object.entries(PROJECT_PRIORITY_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>

          {/* Active Only Toggle */}
          <div className="flex items-center">
            <input
              id="active-only"
              type="checkbox"
              className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
              checked={activeOnly}
              onChange={(e) => {
                setActiveOnly(e.target.checked);
                setPage(0);
              }}
            />
            <label htmlFor="active-only" className="ml-2 text-sm text-gray-700">
              Active only
            </label>
          </div>
        </div>
      </div>

      {/* Projects Table */}
      <div className="card overflow-hidden p-0">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading projects...</div>
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            Error loading projects. Please try again.
          </div>
        ) : projects.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p>No projects found.</p>
            {isAdmin && (
              <Link to="/projects/new" className="text-blue-600 hover:underline mt-2 inline-block">
                Create your first project
              </Link>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
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
                    Priority
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Due Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Hours
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {projects.map((project) => (
                  <tr
                    key={project.id}
                    className={`hover:bg-gray-50 cursor-pointer ${
                      project.is_overdue ? 'bg-red-50' : ''
                    }`}
                    onClick={() => navigate(`/projects/${project.id}`)}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <p className="font-medium text-gray-900">{project.name}</p>
                        {project.description && (
                          <p className="text-sm text-gray-500 truncate max-w-xs">
                            {project.description}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={project.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <PriorityBadge priority={project.priority} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <span className={project.is_overdue ? 'text-red-600 font-medium' : ''}>
                        {formatDate(project.due_date)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {project.actual_hours || 0} / {project.estimated_hours || '-'}
                    </td>
                    <td
                      className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex justify-end gap-2">
                        <Link
                          to={`/projects/${project.id}`}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          View
                        </Link>
                        {isAdmin && (
                          <>
                            <Link
                              to={`/projects/${project.id}/edit`}
                              className="text-gray-600 hover:text-gray-800"
                            >
                              Edit
                            </Link>
                            <button
                              onClick={() => handleDelete(project.id, project.name)}
                              className="text-red-600 hover:text-red-800"
                              disabled={deleteMutation.isPending}
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Showing {page * pageSize + 1} to {Math.min((page + 1) * pageSize, total)} of {total}{' '}
              projects
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="btn-secondary text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="btn-secondary text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
