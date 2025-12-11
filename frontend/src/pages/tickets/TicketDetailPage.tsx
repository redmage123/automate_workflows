/**
 * Ticket Detail Page
 *
 * WHAT: View and manage a single support ticket.
 *
 * WHY: Provides full ticket details with:
 * - SLA countdown display
 * - Status and assignment management
 * - Comment thread with internal notes
 * - File attachments
 *
 * HOW: Uses React Query for data fetching and mutations.
 */

import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import {
  getTicket,
  getTicketSLA,
  changeTicketStatus,
  assignTicket,
  addComment,
  deleteComment,
} from '../../services/tickets';
import type { TicketStatus, TicketPriority } from '../../types';
import {
  TICKET_STATUS_CONFIG,
  TICKET_PRIORITY_CONFIG,
  TICKET_CATEGORY_CONFIG,
  formatUserName,
  formatFileSize,
} from '../../types/ticket';

/**
 * Format datetime for display
 */
function formatDateTime(dateString: string | null): string {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleString();
}

/**
 * SLA Card component
 */
function SLACard({
  title,
  isBreached,
  isMet,
  dueAt,
  metAt,
}: {
  title: string;
  isBreached: boolean;
  isMet: boolean;
  dueAt: string | null;
  metAt: string | null;
}) {
  let statusColor = 'bg-gray-100 text-gray-600';
  let statusText = 'Pending';

  if (isMet) {
    statusColor = 'bg-green-100 text-green-700';
    statusText = 'Met';
  } else if (isBreached) {
    statusColor = 'bg-red-100 text-red-700';
    statusText = 'Breached';
  } else if (dueAt) {
    const remaining = new Date(dueAt).getTime() - Date.now();
    const hoursRemaining = remaining / (1000 * 60 * 60);

    if (hoursRemaining < 2) {
      statusColor = 'bg-orange-100 text-orange-700';
      statusText = `${Math.max(0, Math.floor(hoursRemaining))}h remaining`;
    } else if (hoursRemaining < 24) {
      statusColor = 'bg-yellow-100 text-yellow-700';
      statusText = `${Math.floor(hoursRemaining)}h remaining`;
    } else {
      statusColor = 'bg-blue-100 text-blue-700';
      statusText = `${Math.floor(hoursRemaining / 24)}d remaining`;
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm font-medium text-gray-500">{title}</p>
      <div className="mt-2 flex items-center justify-between">
        <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColor}`}>
          {statusText}
        </span>
        <p className="text-sm text-gray-500">
          {isMet ? `Met: ${formatDateTime(metAt)}` : dueAt ? `Due: ${formatDateTime(dueAt)}` : 'No SLA'}
        </p>
      </div>
    </div>
  );
}

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === 'ADMIN';

  const [newComment, setNewComment] = useState('');
  const [isInternalNote, setIsInternalNote] = useState(false);

  // Fetch ticket details
  const {
    data: ticket,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['ticket', id],
    queryFn: () => getTicket(Number(id)),
    enabled: !!id,
  });

  // Fetch SLA status
  const { data: slaStatus } = useQuery({
    queryKey: ['ticket-sla', id],
    queryFn: () => getTicketSLA(Number(id)),
    enabled: !!id,
    refetchInterval: 60000, // Refresh every minute
  });

  // Change status mutation
  const statusMutation = useMutation({
    mutationFn: ({ status }: { status: TicketStatus }) =>
      changeTicketStatus(Number(id), { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ticket', id] });
      queryClient.invalidateQueries({ queryKey: ['ticket-sla', id] });
    },
  });

  // Add comment mutation
  const commentMutation = useMutation({
    mutationFn: (content: string) =>
      addComment(Number(id), { content, is_internal: isInternalNote }),
    onSuccess: () => {
      setNewComment('');
      setIsInternalNote(false);
      queryClient.invalidateQueries({ queryKey: ['ticket', id] });
    },
  });

  // Delete comment mutation
  const deleteCommentMutation = useMutation({
    mutationFn: (commentId: number) => deleteComment(Number(id), commentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ticket', id] });
    },
  });

  const handleSubmitComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (newComment.trim()) {
      commentMutation.mutate(newComment);
    }
  };

  const handleDeleteComment = (commentId: number) => {
    if (window.confirm('Are you sure you want to delete this comment?')) {
      deleteCommentMutation.mutate(commentId);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading ticket...</div>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-red-600">Error loading ticket</p>
          <button
            onClick={() => navigate('/tickets')}
            className="mt-4 btn-secondary"
          >
            Back to Tickets
          </button>
        </div>
      </div>
    );
  }

  const statusConfig = TICKET_STATUS_CONFIG[ticket.status];
  const priorityConfig = TICKET_PRIORITY_CONFIG[ticket.priority];
  const categoryConfig = TICKET_CATEGORY_CONFIG[ticket.category];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
            <Link to="/tickets" className="hover:text-gray-700">
              Tickets
            </Link>
            <span>/</span>
            <span>#{ticket.id}</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{ticket.subject}</h1>
          <div className="mt-2 flex items-center gap-3">
            <span className={`px-2 py-1 text-sm font-medium rounded-full ${statusConfig.bgColor} ${statusConfig.color}`}>
              {statusConfig.label}
            </span>
            <span className={`px-2 py-1 text-sm font-medium rounded-full ${priorityConfig.bgColor} ${priorityConfig.color}`}>
              {priorityConfig.label}
            </span>
            <span className={`px-2 py-1 text-sm font-medium rounded-full ${categoryConfig.bgColor} ${categoryConfig.color}`}>
              {categoryConfig.label}
            </span>
          </div>
        </div>

        {isAdmin && (
          <div className="flex gap-2">
            <select
              value={ticket.status}
              onChange={(e) =>
                statusMutation.mutate({ status: e.target.value as TicketStatus })
              }
              className="input"
              disabled={statusMutation.isPending}
            >
              {Object.entries(TICKET_STATUS_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description */}
          <div className="card">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Description</h2>
            <p className="text-gray-700 whitespace-pre-wrap">{ticket.description}</p>
          </div>

          {/* Comments */}
          <div className="card">
            <h2 className="text-lg font-medium text-gray-900 mb-4">
              Comments ({ticket.comments.length})
            </h2>

            <div className="space-y-4">
              {ticket.comments.map((comment) => (
                <div
                  key={comment.id}
                  className={`p-4 rounded-lg ${
                    comment.is_internal
                      ? 'bg-yellow-50 border border-yellow-200'
                      : 'bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">
                        {formatUserName(comment.user)}
                      </span>
                      {comment.is_internal && (
                        <span className="px-2 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">
                          Internal Note
                        </span>
                      )}
                      {comment.is_edited && (
                        <span className="text-xs text-gray-400">(edited)</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500">
                        {formatDateTime(comment.created_at)}
                      </span>
                      {(comment.user?.id === user?.id || isAdmin) && (
                        <button
                          onClick={() => handleDeleteComment(comment.id)}
                          className="text-red-500 hover:text-red-700 text-sm"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="text-gray-700 whitespace-pre-wrap">{comment.content}</p>

                  {/* Comment attachments */}
                  {comment.attachments.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {comment.attachments.map((att) => (
                        <a
                          key={att.id}
                          href={att.download_url || '#'}
                          className="inline-flex items-center px-2 py-1 bg-white border border-gray-200 rounded text-sm text-gray-600 hover:bg-gray-50"
                        >
                          <svg
                            className="w-4 h-4 mr-1"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                            />
                          </svg>
                          {att.filename} ({formatFileSize(att.file_size)})
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {ticket.comments.length === 0 && (
                <p className="text-gray-500 text-center py-4">No comments yet</p>
              )}
            </div>

            {/* Add Comment Form */}
            <form onSubmit={handleSubmitComment} className="mt-6">
              <textarea
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Add a comment..."
                className="input w-full min-h-[100px]"
                required
              />
              <div className="mt-3 flex items-center justify-between">
                {isAdmin && (
                  <label className="flex items-center text-sm text-gray-600">
                    <input
                      type="checkbox"
                      checked={isInternalNote}
                      onChange={(e) => setIsInternalNote(e.target.checked)}
                      className="mr-2 h-4 w-4 text-yellow-600 rounded border-gray-300"
                    />
                    Internal note (hidden from client)
                  </label>
                )}
                <button
                  type="submit"
                  disabled={commentMutation.isPending || !newComment.trim()}
                  className="btn-primary disabled:opacity-50"
                >
                  {commentMutation.isPending ? 'Posting...' : 'Post Comment'}
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* SLA Status */}
          <div className="card">
            <h2 className="text-lg font-medium text-gray-900 mb-4">SLA Status</h2>
            <div className="space-y-3">
              <SLACard
                title="First Response"
                isBreached={ticket.is_sla_response_breached}
                isMet={!!ticket.first_response_at}
                dueAt={ticket.sla_response_due_at}
                metAt={ticket.first_response_at}
              />
              <SLACard
                title="Resolution"
                isBreached={ticket.is_sla_resolution_breached}
                isMet={ticket.status === 'resolved' || ticket.status === 'closed'}
                dueAt={ticket.sla_resolution_due_at}
                metAt={ticket.resolved_at}
              />
            </div>
          </div>

          {/* Details */}
          <div className="card">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Details</h2>
            <dl className="space-y-3">
              <div>
                <dt className="text-sm font-medium text-gray-500">Created By</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatUserName(ticket.created_by)}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Assigned To</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatUserName(ticket.assigned_to)}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Created</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDateTime(ticket.created_at)}
                </dd>
              </div>
              {ticket.project_name && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Project</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    <Link
                      to={`/projects/${ticket.project_id}`}
                      className="text-blue-600 hover:underline"
                    >
                      {ticket.project_name}
                    </Link>
                  </dd>
                </div>
              )}
              {ticket.resolved_at && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Resolved</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {formatDateTime(ticket.resolved_at)}
                  </dd>
                </div>
              )}
              {ticket.closed_at && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Closed</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {formatDateTime(ticket.closed_at)}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Attachments */}
          {ticket.attachments.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-medium text-gray-900 mb-4">
                Attachments ({ticket.attachments.length})
              </h2>
              <ul className="space-y-2">
                {ticket.attachments.map((att) => (
                  <li key={att.id}>
                    <a
                      href={att.download_url || '#'}
                      className="flex items-center p-2 rounded hover:bg-gray-50"
                    >
                      <svg
                        className="w-5 h-5 text-gray-400 mr-2"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                        />
                      </svg>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {att.filename}
                        </p>
                        <p className="text-xs text-gray-500">
                          {formatFileSize(att.file_size)}
                        </p>
                      </div>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
