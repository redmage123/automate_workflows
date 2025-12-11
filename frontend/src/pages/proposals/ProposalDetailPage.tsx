/**
 * Proposal Detail Page
 *
 * WHAT: Displays full proposal details with workflow actions.
 *
 * WHY: Provides comprehensive proposal view with:
 * - Full proposal info and line items
 * - Workflow actions (send, approve, reject, revise)
 * - Version history link
 * - PDF-ready layout structure
 *
 * HOW: Uses React Query for data fetching and mutations.
 */

import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import {
  getProposal,
  sendProposal,
  markProposalViewed,
  approveProposal,
  rejectProposal,
  deleteProposal,
} from '../../services/proposals';
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

export default function ProposalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');
  const proposalId = parseInt(id || '0', 10);

  const [rejectReason, setRejectReason] = useState('');
  const [showRejectDialog, setShowRejectDialog] = useState(false);

  // Fetch proposal
  const {
    data: proposal,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['proposal', proposalId],
    queryFn: () => getProposal(proposalId),
    enabled: proposalId > 0,
  });

  // Workflow mutations
  const sendMutation = useMutation({
    mutationFn: () => sendProposal(proposalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposal', proposalId] });
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
    },
  });

  const viewMutation = useMutation({
    mutationFn: () => markProposalViewed(proposalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposal', proposalId] });
    },
  });

  const approveMutation = useMutation({
    mutationFn: () => approveProposal(proposalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposal', proposalId] });
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => rejectProposal(proposalId, { reason: rejectReason || undefined }),
    onSuccess: () => {
      setShowRejectDialog(false);
      setRejectReason('');
      queryClient.invalidateQueries({ queryKey: ['proposal', proposalId] });
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteProposal(proposalId),
    onSuccess: () => {
      navigate('/proposals');
    },
  });

  const handleDelete = () => {
    if (proposal && window.confirm(`Are you sure you want to delete "${proposal.title}"?`)) {
      deleteMutation.mutate();
    }
  };

  const handleSend = () => {
    if (window.confirm('Send this proposal to the client?')) {
      sendMutation.mutate();
    }
  };

  const handleApprove = () => {
    if (window.confirm('Approve this proposal?')) {
      approveMutation.mutate();
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading proposal...</div>
      </div>
    );
  }

  if (error || !proposal) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">Proposal not found</h2>
        <p className="mt-2 text-gray-500">The proposal you're looking for doesn't exist.</p>
        <Link to="/proposals" className="mt-4 inline-block text-blue-600 hover:underline">
          Back to proposals
        </Link>
      </div>
    );
  }

  const statusConfig = PROPOSAL_STATUS_CONFIG[proposal.status];
  const lineItems = proposal.line_items || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm">
            <Link to="/proposals" className="text-gray-500 hover:text-gray-700">
              Proposals
            </Link>
            <span className="text-gray-400">/</span>
            <span className="text-gray-900">{proposal.title}</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">{proposal.title}</h1>
          <div className="mt-2 flex items-center gap-4">
            <span className={`px-3 py-1 text-sm font-medium rounded-full ${statusConfig.bgColor} ${statusConfig.color}`}>
              {statusConfig.label}
            </span>
            <span className="text-sm text-gray-500">Version {proposal.version}</span>
            {proposal.is_expired && (
              <span className="px-3 py-1 text-sm font-medium rounded-full bg-orange-100 text-orange-600">
                Expired
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/projects/${proposal.project_id}`}
            className="btn-secondary text-sm"
          >
            View Project
          </Link>
          {isAdmin && proposal.is_editable && (
            <>
              <Link to={`/proposals/${proposal.id}/edit`} className="btn-secondary">
                Edit
              </Link>
              <button
                onClick={handleDelete}
                className="btn-danger"
                disabled={deleteMutation.isPending}
              >
                Delete
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Proposal Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description */}
          {proposal.description && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Scope of Work</h2>
              <p className="text-gray-600 whitespace-pre-wrap">{proposal.description}</p>
            </div>
          )}

          {/* Line Items */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Line Items</h2>
            {lineItems.length === 0 ? (
              <p className="text-gray-500">No line items.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-2 text-sm font-medium text-gray-500">Description</th>
                      <th className="text-right py-2 text-sm font-medium text-gray-500 w-24">Qty</th>
                      <th className="text-right py-2 text-sm font-medium text-gray-500 w-32">Unit Price</th>
                      <th className="text-right py-2 text-sm font-medium text-gray-500 w-32">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lineItems.map((item, index) => (
                      <tr key={index} className="border-b border-gray-100">
                        <td className="py-3 text-gray-900">{item.description}</td>
                        <td className="py-3 text-right text-gray-600">{item.quantity}</td>
                        <td className="py-3 text-right text-gray-600">{formatCurrency(item.unit_price)}</td>
                        <td className="py-3 text-right font-medium text-gray-900">{formatCurrency(item.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Totals */}
            <div className="mt-6 pt-4 border-t border-gray-200">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Subtotal</span>
                  <span className="text-gray-900">{formatCurrency(proposal.subtotal)}</span>
                </div>
                {proposal.discount_percent && proposal.discount_percent > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Discount ({proposal.discount_percent}%)</span>
                    <span className="text-green-600">-{formatCurrency(proposal.discount_amount || 0)}</span>
                  </div>
                )}
                {proposal.tax_percent && proposal.tax_percent > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Tax ({proposal.tax_percent}%)</span>
                    <span className="text-gray-900">{formatCurrency(proposal.tax_amount || 0)}</span>
                  </div>
                )}
                <div className="flex justify-between text-lg font-semibold pt-2 border-t border-gray-200">
                  <span className="text-gray-900">Total</span>
                  <span className="text-gray-900">{formatCurrency(proposal.total)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Client Notes */}
          {proposal.client_notes && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Notes</h2>
              <p className="text-gray-600 whitespace-pre-wrap">{proposal.client_notes}</p>
            </div>
          )}

          {/* Terms */}
          {proposal.terms && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Terms & Conditions</h2>
              <p className="text-gray-600 whitespace-pre-wrap">{proposal.terms}</p>
            </div>
          )}

          {/* Internal Notes (Admin Only) */}
          {isAdmin && proposal.notes && (
            <div className="card bg-yellow-50 border-yellow-200">
              <h2 className="text-lg font-semibold text-yellow-800 mb-4">Internal Notes</h2>
              <p className="text-yellow-700 whitespace-pre-wrap">{proposal.notes}</p>
            </div>
          )}
        </div>

        {/* Right Column - Sidebar */}
        <div className="space-y-6">
          {/* Workflow Actions */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Actions</h3>
            <div className="space-y-2">
              {/* Send - only for draft */}
              {isAdmin && proposal.status === 'draft' && (
                <button
                  onClick={handleSend}
                  disabled={sendMutation.isPending}
                  className="w-full btn-primary"
                >
                  {sendMutation.isPending ? 'Sending...' : 'Send to Client'}
                </button>
              )}

              {/* Mark as Viewed - for sent proposals */}
              {proposal.status === 'sent' && (
                <button
                  onClick={() => viewMutation.mutate()}
                  disabled={viewMutation.isPending}
                  className="w-full btn-secondary"
                >
                  {viewMutation.isPending ? 'Marking...' : 'Mark as Viewed'}
                </button>
              )}

              {/* Approve/Reject - for sent or viewed, not expired */}
              {proposal.can_be_approved && (
                <>
                  <button
                    onClick={handleApprove}
                    disabled={approveMutation.isPending}
                    className="w-full px-4 py-2 text-sm font-medium rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    {approveMutation.isPending ? 'Approving...' : 'Approve Proposal'}
                  </button>
                  <button
                    onClick={() => setShowRejectDialog(true)}
                    className="w-full px-4 py-2 text-sm font-medium rounded-lg bg-red-100 text-red-700 hover:bg-red-200"
                  >
                    Reject Proposal
                  </button>
                </>
              )}

              {/* Revise - for any non-draft */}
              {isAdmin && proposal.status !== 'draft' && (
                <Link
                  to={`/proposals/${proposal.id}/revise`}
                  className="w-full btn-secondary block text-center"
                >
                  Create Revision
                </Link>
              )}
            </div>
          </div>

          {/* Rejection Reason */}
          {proposal.rejection_reason && (
            <div className="card bg-red-50 border-red-200">
              <h3 className="text-sm font-semibold text-red-800 mb-2">Rejection Reason</h3>
              <p className="text-red-700 text-sm">{proposal.rejection_reason}</p>
            </div>
          )}

          {/* Details */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Details</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Proposal ID</dt>
                <dd className="text-gray-900 font-medium">{proposal.id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Project ID</dt>
                <dd>
                  <Link to={`/projects/${proposal.project_id}`} className="text-blue-600 hover:underline">
                    #{proposal.project_id}
                  </Link>
                </dd>
              </div>
              {proposal.previous_version_id && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Previous Version</dt>
                  <dd>
                    <Link to={`/proposals/${proposal.previous_version_id}`} className="text-blue-600 hover:underline">
                      #{proposal.previous_version_id}
                    </Link>
                  </dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-gray-500">Created</dt>
                <dd className="text-gray-900">{formatDateTime(proposal.created_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Valid Until</dt>
                <dd className={proposal.is_expired ? 'text-red-600 font-medium' : 'text-gray-900'}>
                  {formatDate(proposal.valid_until)}
                </dd>
              </div>
            </dl>
          </div>

          {/* Timeline */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Timeline</h3>
            <dl className="space-y-3 text-sm">
              {proposal.sent_at && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Sent</dt>
                  <dd className="text-gray-900">{formatDateTime(proposal.sent_at)}</dd>
                </div>
              )}
              {proposal.viewed_at && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Viewed</dt>
                  <dd className="text-gray-900">{formatDateTime(proposal.viewed_at)}</dd>
                </div>
              )}
              {proposal.approved_at && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Approved</dt>
                  <dd className="text-green-600">{formatDateTime(proposal.approved_at)}</dd>
                </div>
              )}
              {proposal.rejected_at && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Rejected</dt>
                  <dd className="text-red-600">{formatDateTime(proposal.rejected_at)}</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </div>

      {/* Reject Dialog */}
      {showRejectDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Reject Proposal</h3>
            <div className="mb-4">
              <label htmlFor="reject-reason" className="block text-sm font-medium text-gray-700 mb-1">
                Reason (optional)
              </label>
              <textarea
                id="reject-reason"
                className="input w-full min-h-[100px]"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Why is this proposal being rejected?"
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowRejectDialog(false);
                  setRejectReason('');
                }}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={() => rejectMutation.mutate()}
                disabled={rejectMutation.isPending}
                className="btn-danger"
              >
                {rejectMutation.isPending ? 'Rejecting...' : 'Reject Proposal'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
