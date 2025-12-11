/**
 * Proposals List Page
 *
 * WHAT: Main page for viewing and managing proposals.
 *
 * WHY: Provides a filterable list of proposals with:
 * - Status filters
 * - Quick actions (view, approve, reject)
 * - Value totals
 * - Create new proposal button
 *
 * HOW: Uses React Query for data fetching with proper loading states.
 */

import { useState, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import { getProposals, getProposalStats } from '../../services/proposals';
import type { ProposalStatus, ProposalListParams } from '../../types';
import { PROPOSAL_STATUS_CONFIG, formatCurrency } from '../../types/proposal';

/**
 * Status badge component
 */
function StatusBadge({ status }: { status: ProposalStatus }) {
  const config = PROPOSAL_STATUS_CONFIG[status];
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

export default function ProposalsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');

  // Get project_id from URL if present (coming from project page)
  const projectIdFromUrl = searchParams.get('project_id');

  // Filter state
  const [statusFilter, setStatusFilter] = useState<ProposalStatus | ''>('');
  const [pendingOnly, setPendingOnly] = useState(false);
  const [page, setPage] = useState(0);
  const pageSize = 10;

  // Build query params
  const queryParams: ProposalListParams = useMemo(
    () => ({
      skip: page * pageSize,
      limit: pageSize,
      status: statusFilter || undefined,
      project_id: projectIdFromUrl ? parseInt(projectIdFromUrl, 10) : undefined,
      pending_only: pendingOnly,
    }),
    [page, statusFilter, projectIdFromUrl, pendingOnly]
  );

  // Fetch proposals
  const {
    data: proposalsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['proposals', queryParams],
    queryFn: () => getProposals(queryParams),
  });

  // Fetch stats
  const { data: stats } = useQuery({
    queryKey: ['proposal-stats'],
    queryFn: getProposalStats,
  });

  const proposals = proposalsData?.items || [];
  const total = proposalsData?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Proposals</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your client proposals and approval workflow
          </p>
        </div>
        {isAdmin && (
          <Link
            to={projectIdFromUrl ? `/proposals/new?project_id=${projectIdFromUrl}` : '/proposals/new'}
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
            New Proposal
          </Link>
        )}
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Total Proposals</p>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{stats.total}</p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Pending</p>
            <p className="mt-1 text-2xl font-semibold text-yellow-600">{stats.pending_count}</p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Total Value</p>
            <p className="mt-1 text-2xl font-semibold text-gray-900">
              {formatCurrency(stats.total_value)}
            </p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Approved Value</p>
            <p className="mt-1 text-2xl font-semibold text-green-600">
              {formatCurrency(stats.approved_value)}
            </p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card">
        <div className="flex flex-wrap items-center gap-4">
          {/* Status Filter */}
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="status-filter" className="sr-only">
              Filter by status
            </label>
            <select
              id="status-filter"
              className="input w-full"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as ProposalStatus | '');
                setPendingOnly(false);
                setPage(0);
              }}
            >
              <option value="">All Statuses</option>
              {Object.entries(PROPOSAL_STATUS_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>

          {/* Pending Only Toggle */}
          <div className="flex items-center">
            <input
              id="pending-only"
              type="checkbox"
              className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
              checked={pendingOnly}
              onChange={(e) => {
                setPendingOnly(e.target.checked);
                if (e.target.checked) setStatusFilter('');
                setPage(0);
              }}
            />
            <label htmlFor="pending-only" className="ml-2 text-sm text-gray-700">
              Pending only
            </label>
          </div>

          {/* Clear Project Filter */}
          {projectIdFromUrl && (
            <Link
              to="/proposals"
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Clear project filter
            </Link>
          )}
        </div>
      </div>

      {/* Proposals Table */}
      <div className="card overflow-hidden p-0">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading proposals...</div>
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            Error loading proposals. Please try again.
          </div>
        ) : proposals.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p>No proposals found.</p>
            {isAdmin && (
              <Link to="/proposals/new" className="text-blue-600 hover:underline mt-2 inline-block">
                Create your first proposal
              </Link>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Title
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Version
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Valid Until
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {proposals.map((proposal) => (
                  <tr
                    key={proposal.id}
                    className={`hover:bg-gray-50 cursor-pointer ${
                      proposal.is_expired ? 'bg-orange-50' : ''
                    }`}
                    onClick={() => navigate(`/proposals/${proposal.id}`)}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <p className="font-medium text-gray-900">{proposal.title}</p>
                        {proposal.description && (
                          <p className="text-sm text-gray-500 truncate max-w-xs">
                            {proposal.description}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={proposal.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      v{proposal.version}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <span className="font-semibold text-gray-900">
                        {formatCurrency(proposal.total)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <span className={proposal.is_expired ? 'text-red-600 font-medium' : ''}>
                        {formatDate(proposal.valid_until)}
                      </span>
                    </td>
                    <td
                      className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex justify-end gap-2">
                        <Link
                          to={`/proposals/${proposal.id}`}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          View
                        </Link>
                        {isAdmin && proposal.is_editable && (
                          <Link
                            to={`/proposals/${proposal.id}/edit`}
                            className="text-gray-600 hover:text-gray-800"
                          >
                            Edit
                          </Link>
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
              proposals
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
