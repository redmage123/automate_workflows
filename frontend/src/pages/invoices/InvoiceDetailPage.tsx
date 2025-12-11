/**
 * Invoice Detail Page
 *
 * WHAT: Detailed view of a single invoice with actions.
 *
 * WHY: Provides:
 * - Full invoice details and line items
 * - Workflow actions (send, cancel, record payment)
 * - Payment options (Stripe checkout)
 * - PDF download
 *
 * HOW: Uses React Query for data fetching and mutations.
 */

import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import {
  getInvoice,
  sendInvoice,
  cancelInvoice,
  recordPayment,
  createCheckoutSession,
  saveInvoicePdf,
  openInvoicePdf,
} from '../../services/invoices';
import type { Invoice, InvoiceStatus, PaymentRecordRequest } from '../../types';
import { INVOICE_STATUS_CONFIG, formatCurrency } from '../../types/invoice';

/**
 * Status badge component
 */
function StatusBadge({ status }: { status: InvoiceStatus }) {
  const config = INVOICE_STATUS_CONFIG[status];
  return (
    <span className={`px-3 py-1 text-sm font-medium rounded-full ${config.bgColor} ${config.color}`}>
      {config.label}
    </span>
  );
}

/**
 * Format date for display
 */
function formatDate(dateString: string | null): string {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/**
 * Format datetime for display
 */
function formatDateTime(dateString: string | null): string {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleString();
}

/**
 * Record Payment Modal
 */
function RecordPaymentModal({
  invoice,
  isOpen,
  onClose,
  onSubmit,
  isLoading,
}: {
  invoice: Invoice;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: PaymentRecordRequest) => void;
  isLoading: boolean;
}) {
  const [amount, setAmount] = useState(invoice.balance_due.toString());
  const [paymentMethod, setPaymentMethod] = useState('check');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      amount: parseFloat(amount),
      payment_method: paymentMethod,
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Record Payment</h3>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label htmlFor="amount" className="block text-sm font-medium text-gray-700">
                Amount
              </label>
              <div className="mt-1 relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-gray-500">
                  $
                </span>
                <input
                  type="number"
                  id="amount"
                  step="0.01"
                  min="0.01"
                  max={invoice.balance_due}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="input pl-7 w-full"
                  required
                />
              </div>
              <p className="mt-1 text-sm text-gray-500">
                Balance due: {formatCurrency(invoice.balance_due)}
              </p>
            </div>
            <div>
              <label htmlFor="payment-method" className="block text-sm font-medium text-gray-700">
                Payment Method
              </label>
              <select
                id="payment-method"
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value)}
                className="input w-full mt-1"
              >
                <option value="check">Check</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="cash">Cash</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>
          <div className="mt-6 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="btn-secondary" disabled={isLoading}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isLoading}>
              {isLoading ? 'Recording...' : 'Record Payment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * Cancel Invoice Modal
 */
function CancelModal({
  isOpen,
  onClose,
  onConfirm,
  isLoading,
}: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason?: string) => void;
  isLoading: boolean;
}) {
  const [reason, setReason] = useState('');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Cancel Invoice</h3>
        <p className="text-gray-600 mb-4">
          Are you sure you want to cancel this invoice? This action cannot be undone.
        </p>
        <div className="mb-4">
          <label htmlFor="cancel-reason" className="block text-sm font-medium text-gray-700">
            Reason (optional)
          </label>
          <textarea
            id="cancel-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="input w-full mt-1"
            rows={3}
            placeholder="Enter cancellation reason..."
          />
        </div>
        <div className="flex justify-end gap-3">
          <button type="button" onClick={onClose} className="btn-secondary" disabled={isLoading}>
            Back
          </button>
          <button
            type="button"
            onClick={() => onConfirm(reason || undefined)}
            className="btn-primary bg-red-600 hover:bg-red-700"
            disabled={isLoading}
          >
            {isLoading ? 'Cancelling...' : 'Cancel Invoice'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');

  // Modal states
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);

  // Fetch invoice
  const {
    data: invoice,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => getInvoice(parseInt(id!, 10)),
    enabled: !!id,
  });

  // Mutations
  const sendMutation = useMutation({
    mutationFn: (invoiceId: number) => sendInvoice(invoiceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-stats'] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: ({ invoiceId, reason }: { invoiceId: number; reason?: string }) =>
      cancelInvoice(invoiceId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-stats'] });
      setShowCancelModal(false);
    },
  });

  const paymentMutation = useMutation({
    mutationFn: ({ invoiceId, data }: { invoiceId: number; data: PaymentRecordRequest }) =>
      recordPayment(invoiceId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-stats'] });
      setShowPaymentModal(false);
    },
  });

  const checkoutMutation = useMutation({
    mutationFn: (invoiceId: number) =>
      createCheckoutSession(invoiceId, {
        success_url: `${window.location.origin}/invoices/${invoiceId}?payment=success`,
        cancel_url: `${window.location.origin}/invoices/${invoiceId}?payment=cancelled`,
      }),
    onSuccess: (data) => {
      // Redirect to Stripe Checkout
      window.location.href = data.checkout_url;
    },
  });

  // PDF actions
  const handleDownloadPdf = async () => {
    if (!invoice) return;
    await saveInvoicePdf(invoice.id, invoice.invoice_number);
  };

  const handleViewPdf = async () => {
    if (!invoice) return;
    await openInvoicePdf(invoice.id);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error || !invoice) {
    return (
      <div className="card text-center py-12">
        <p className="text-red-600 mb-4">Invoice not found or an error occurred.</p>
        <Link to="/invoices" className="btn-secondary">
          Back to Invoices
        </Link>
      </div>
    );
  }

  // Determine available actions
  const canSend = isAdmin && invoice.is_editable;
  const canCancel =
    isAdmin &&
    ['draft', 'sent', 'overdue', 'partially_paid'].includes(invoice.status);
  const canRecordPayment =
    isAdmin && ['sent', 'overdue', 'partially_paid'].includes(invoice.status);
  const canPay = ['sent', 'overdue', 'partially_paid'].includes(invoice.status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link to="/invoices" className="text-blue-600 hover:text-blue-800 text-sm mb-2 inline-block">
            &larr; Back to Invoices
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Invoice {invoice.invoice_number}</h1>
          <div className="mt-2">
            <StatusBadge status={invoice.status} />
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <button onClick={handleViewPdf} className="btn-secondary">
            View PDF
          </button>
          <button onClick={handleDownloadPdf} className="btn-secondary">
            Download PDF
          </button>
          {canSend && (
            <button
              onClick={() => sendMutation.mutate(invoice.id)}
              disabled={sendMutation.isPending}
              className="btn-primary"
            >
              {sendMutation.isPending ? 'Sending...' : 'Send Invoice'}
            </button>
          )}
          {canPay && (
            <button
              onClick={() => checkoutMutation.mutate(invoice.id)}
              disabled={checkoutMutation.isPending}
              className="btn-primary bg-green-600 hover:bg-green-700"
            >
              {checkoutMutation.isPending ? 'Processing...' : 'Pay Now'}
            </button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Invoice Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Summary Card */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Invoice Details</h2>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <dt className="text-sm font-medium text-gray-500">Issue Date</dt>
                <dd className="mt-1 text-gray-900">{formatDate(invoice.issue_date)}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Due Date</dt>
                <dd className={`mt-1 ${invoice.status === 'overdue' ? 'text-red-600 font-medium' : 'text-gray-900'}`}>
                  {formatDate(invoice.due_date)}
                </dd>
              </div>
              {invoice.sent_at && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Sent At</dt>
                  <dd className="mt-1 text-gray-900">{formatDateTime(invoice.sent_at)}</dd>
                </div>
              )}
              {invoice.paid_at && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Paid At</dt>
                  <dd className="mt-1 text-green-600">{formatDateTime(invoice.paid_at)}</dd>
                </div>
              )}
              {invoice.payment_method && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Payment Method</dt>
                  <dd className="mt-1 text-gray-900 capitalize">{invoice.payment_method}</dd>
                </div>
              )}
              {invoice.proposal_id && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Related Proposal</dt>
                  <dd className="mt-1">
                    <Link
                      to={`/proposals/${invoice.proposal_id}`}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      View Proposal
                    </Link>
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Financial Summary */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Financial Summary</h2>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Subtotal</span>
                <span className="text-gray-900">{formatCurrency(invoice.subtotal)}</span>
              </div>
              {invoice.discount_amount && invoice.discount_amount > 0 && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Discount</span>
                  <span className="text-green-600">-{formatCurrency(invoice.discount_amount)}</span>
                </div>
              )}
              {invoice.tax_amount && invoice.tax_amount > 0 && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Tax</span>
                  <span className="text-gray-900">{formatCurrency(invoice.tax_amount)}</span>
                </div>
              )}
              <div className="border-t pt-3 flex justify-between font-semibold">
                <span className="text-gray-900">Total</span>
                <span className="text-gray-900">{formatCurrency(invoice.total)}</span>
              </div>
              {invoice.amount_paid > 0 && (
                <div className="flex justify-between text-green-600">
                  <span>Amount Paid</span>
                  <span>-{formatCurrency(invoice.amount_paid)}</span>
                </div>
              )}
              <div className="border-t pt-3 flex justify-between font-bold text-lg">
                <span className={invoice.balance_due > 0 ? 'text-red-600' : 'text-green-600'}>
                  Balance Due
                </span>
                <span className={invoice.balance_due > 0 ? 'text-red-600' : 'text-green-600'}>
                  {formatCurrency(invoice.balance_due)}
                </span>
              </div>
            </div>
          </div>

          {/* Notes */}
          {invoice.notes && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-2">Notes</h2>
              <p className="text-gray-600 whitespace-pre-wrap">{invoice.notes}</p>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Actions</h2>
            <div className="space-y-3">
              {canRecordPayment && (
                <button
                  onClick={() => setShowPaymentModal(true)}
                  className="w-full btn-secondary"
                >
                  Record Payment
                </button>
              )}
              {canCancel && (
                <button
                  onClick={() => setShowCancelModal(true)}
                  className="w-full btn-secondary text-red-600 border-red-300 hover:bg-red-50"
                >
                  Cancel Invoice
                </button>
              )}
              {isAdmin && invoice.is_editable && (
                <Link
                  to={`/invoices/${invoice.id}/edit`}
                  className="w-full btn-secondary inline-block text-center"
                >
                  Edit Invoice
                </Link>
              )}
            </div>
          </div>

          {/* Timeline / History */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Timeline</h2>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 mt-2 rounded-full bg-gray-400"></div>
                <div>
                  <p className="text-sm font-medium text-gray-900">Created</p>
                  <p className="text-xs text-gray-500">{formatDateTime(invoice.created_at)}</p>
                </div>
              </div>
              {invoice.sent_at && (
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 mt-2 rounded-full bg-blue-500"></div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">Sent</p>
                    <p className="text-xs text-gray-500">{formatDateTime(invoice.sent_at)}</p>
                  </div>
                </div>
              )}
              {invoice.paid_at && (
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 mt-2 rounded-full bg-green-500"></div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">Paid</p>
                    <p className="text-xs text-gray-500">{formatDateTime(invoice.paid_at)}</p>
                  </div>
                </div>
              )}
              {invoice.status === 'cancelled' && (
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 mt-2 rounded-full bg-gray-500"></div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">Cancelled</p>
                    <p className="text-xs text-gray-500">{formatDateTime(invoice.updated_at)}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Modals */}
      <RecordPaymentModal
        invoice={invoice}
        isOpen={showPaymentModal}
        onClose={() => setShowPaymentModal(false)}
        onSubmit={(data) => paymentMutation.mutate({ invoiceId: invoice.id, data })}
        isLoading={paymentMutation.isPending}
      />
      <CancelModal
        isOpen={showCancelModal}
        onClose={() => setShowCancelModal(false)}
        onConfirm={(reason) => cancelMutation.mutate({ invoiceId: invoice.id, reason })}
        isLoading={cancelMutation.isPending}
      />
    </div>
  );
}
