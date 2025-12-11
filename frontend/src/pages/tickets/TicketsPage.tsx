/**
 * Tickets List Page
 *
 * WHAT: Main page for viewing and managing support tickets.
 *
 * WHY: Provides a filterable, paginated list of tickets with:
 * - Status, priority, and category filters
 * - SLA status indicators
 * - Quick actions (view, assign, status change)
 * - Create new ticket button
 *
 * HOW: Uses React Query for data fetching with proper loading states.
 */

import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import { getTickets, getTicketStats, deleteTicket } from '../../services/tickets';
import type {
  TicketStatus,
  TicketPriority,
  TicketCategory,
  TicketListParams,
} from '../../types';
import {
  TICKET_STATUS_CONFIG,
  TICKET_PRIORITY_CONFIG,
  TICKET_CATEGORY_CONFIG,
  formatUserName,
} from '../../types/ticket';

/**
 * Status badge component
 */
function StatusBadge({ status }: { status: TicketStatus }) {
  const config = TICKET_STATUS_CONFIG[status];
  return (
    <span
      className={`px-2 py-1 text-xs font-medium rounded-full ${config.bgColor} ${config.color}`}
    >
      {config.label}
    </span>
  );
}

/**
 * Priority badge component
 */
function PriorityBadge({ priority }: { priority: TicketPriority }) {
  const config = TICKET_PRIORITY_CONFIG[priority];
  return (
    <span
      className={`px-2 py-1 text-xs font-medium rounded-full ${config.bgColor} ${config.color}`}
    >
      {config.label}
    </span>
  );
}

/**
 * SLA indicator component
 */
function SLAIndicator({
  isBreached,
  dueAt,
}: {
  isBreached: boolean;
  dueAt: string | null;
}) {
  if (!dueAt) return <span className="text-gray-400">-</span>;

  const dueDate = new Date(dueAt);
  const now = new Date();
  const remaining = dueDate.getTime() - now.getTime();
  const hoursRemaining = Math.floor(remaining / (1000 * 60 * 60));

  if (isBreached) {
    return (
      <span className="text-red-600 font-medium flex items-center">
        <svg
          className="w-4 h-4 mr-1"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
            clipRule="evenodd"
          />
        </svg>
        Breached
      </span>
    );
  }

  if (hoursRemaining < 2) {
    return (
      <span className="text-orange-600 font-medium">
        {hoursRemaining}h remaining
      </span>
    );
  }

  if (hoursRemaining < 24) {
    return <span className="text-yellow-600">{hoursRemaining}h remaining</span>;
  }

  return <span className="text-green-600">{Math.floor(hoursRemaining / 24)}d remaining</span>;
}

/**
 * Format date for display
 */
function formatDate(dateString: string | null): string {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString();
}

export default function TicketsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');

  // Filter state
  const [statusFilter, setStatusFilter] = useState<TicketStatus | ''>('');
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | ''>('');
  const [categoryFilter, setCategoryFilter] = useState<TicketCategory | ''>('');
  const [myTicketsOnly, setMyTicketsOnly] = useState(false);
  const [assignedToMe, setAssignedToMe] = useState(false);
  const [page, setPage] = useState(0);
  const pageSize = 10;

  // Build query params
  const queryParams: TicketListParams = useMemo(
    () => ({
      skip: page * pageSize,
      limit: pageSize,
      status: statusFilter || undefined,
      priority: priorityFilter || undefined,
      category: categoryFilter || undefined,
      created_by_me: myTicketsOnly || undefined,
      assigned_to_me: assignedToMe || undefined,
    }),
    [page, statusFilter, priorityFilter, categoryFilter, myTicketsOnly, assignedToMe]
  );

  // Fetch tickets
  const {
    data: ticketsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['tickets', queryParams],
    queryFn: () => getTickets(queryParams),
  });

  // Fetch stats
  const { data: stats } = useQuery({
    queryKey: ['ticket-stats'],
    queryFn: getTicketStats,
  });

  // Delete mutation (admin only)
  const deleteMutation = useMutation({
    mutationFn: deleteTicket,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tickets'] });
      queryClient.invalidateQueries({ queryKey: ['ticket-stats'] });
    },
  });

  const tickets = ticketsData?.items || [];
  const total = ticketsData?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  const handleDelete = async (id: number, subject: string) => {
    if (window.confirm(`Are you sure you want to delete ticket "${subject}"?`)) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Support Tickets</h1>
          <p className="mt-1 text-sm text-gray-500">
            View and manage support requests
          </p>
        </div>
        <Link
          to="/tickets/new"
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
          New Ticket
        </Link>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Total Tickets</p>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{stats.total}</p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Open</p>
            <p className="mt-1 text-2xl font-semibold text-blue-600">
              {stats.by_status?.open || 0}
            </p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">In Progress</p>
            <p className="mt-1 text-2xl font-semibold text-yellow-600">
              {stats.by_status?.in_progress || 0}
            </p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">SLA Breached</p>
            <p className="mt-1 text-2xl font-semibold text-red-600">
              {stats.sla_breached_count}
            </p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Avg Resolution</p>
            <p className="mt-1 text-2xl font-semibold text-green-600">
              {stats.avg_resolution_hours
                ? `${Math.round(stats.avg_resolution_hours)}h`
                : '-'}
            </p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
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
                setStatusFilter(e.target.value as TicketStatus | '');
                setPage(0);
              }}
            >
              <option value="">All Statuses</option>
              {Object.entries(TICKET_STATUS_CONFIG).map(([value, config]) => (
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
                setPriorityFilter(e.target.value as TicketPriority | '');
                setPage(0);
              }}
            >
              <option value="">All Priorities</option>
              {Object.entries(TICKET_PRIORITY_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>

          {/* Category Filter */}
          <div>
            <label htmlFor="category-filter" className="sr-only">
              Filter by category
            </label>
            <select
              id="category-filter"
              className="input w-full"
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value as TicketCategory | '');
                setPage(0);
              }}
            >
              <option value="">All Categories</option>
              {Object.entries(TICKET_CATEGORY_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>

          {/* My Tickets Toggle */}
          <div className="flex items-center">
            <input
              id="my-tickets"
              type="checkbox"
              className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
              checked={myTicketsOnly}
              onChange={(e) => {
                setMyTicketsOnly(e.target.checked);
                setPage(0);
              }}
            />
            <label htmlFor="my-tickets" className="ml-2 text-sm text-gray-700">
              My Tickets
            </label>
          </div>

          {/* Assigned to Me Toggle */}
          {isAdmin && (
            <div className="flex items-center">
              <input
                id="assigned-to-me"
                type="checkbox"
                className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                checked={assignedToMe}
                onChange={(e) => {
                  setAssignedToMe(e.target.checked);
                  setPage(0);
                }}
              />
              <label htmlFor="assigned-to-me" className="ml-2 text-sm text-gray-700">
                Assigned to Me
              </label>
            </div>
          )}
        </div>
      </div>

      {/* Tickets Table */}
      <div className="card overflow-hidden p-0">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading tickets...</div>
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            Error loading tickets. Please try again.
          </div>
        ) : tickets.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p>No tickets found.</p>
            <Link to="/tickets/new" className="text-blue-600 hover:underline mt-2 inline-block">
              Create a new ticket
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Subject
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Priority
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Assignee
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    SLA
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
                {tickets.map((ticket) => (
                  <tr
                    key={ticket.id}
                    className={`hover:bg-gray-50 cursor-pointer ${
                      ticket.is_sla_response_breached || ticket.is_sla_resolution_breached
                        ? 'bg-red-50'
                        : ''
                    }`}
                    onClick={() => navigate(`/tickets/${ticket.id}`)}
                  >
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-gray-900 truncate max-w-md">
                          {ticket.subject}
                        </p>
                        <p className="text-sm text-gray-500 flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 text-xs rounded ${TICKET_CATEGORY_CONFIG[ticket.category].bgColor} ${TICKET_CATEGORY_CONFIG[ticket.category].color}`}>
                            {TICKET_CATEGORY_CONFIG[ticket.category].label}
                          </span>
                          {ticket.comment_count > 0 && (
                            <span className="text-gray-400">
                              {ticket.comment_count} comments
                            </span>
                          )}
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={ticket.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <PriorityBadge priority={ticket.priority} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatUserName(ticket.assigned_to)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <SLAIndicator
                        isBreached={ticket.is_sla_response_breached || ticket.is_sla_resolution_breached}
                        dueAt={ticket.first_response_at ? ticket.sla_resolution_due_at : ticket.sla_response_due_at}
                      />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(ticket.created_at)}
                    </td>
                    <td
                      className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex justify-end gap-2">
                        <Link
                          to={`/tickets/${ticket.id}`}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          View
                        </Link>
                        {isAdmin && (
                          <button
                            onClick={() => handleDelete(ticket.id, ticket.subject)}
                            className="text-red-600 hover:text-red-800"
                            disabled={deleteMutation.isPending}
                          >
                            Delete
                          </button>
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
              Showing {page * pageSize + 1} to {Math.min((page + 1) * pageSize, total)} of{' '}
              {total} tickets
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
