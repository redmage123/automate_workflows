/**
 * Invoices List Page
 *
 * WHAT: Main page for viewing and managing invoices.
 *
 * WHY: Provides a filterable list of invoices with:
 * - Status filters
 * - Quick actions (view, send, cancel, pay)
 * - Financial totals (outstanding, paid)
 * - Create new invoice button (ADMIN only)
 *
 * HOW: Uses React Query for data fetching with proper loading states.
 */

import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import { getInvoices, getInvoiceStats } from '../../services/invoices';
import type { InvoiceStatus, InvoiceListParams } from '../../types';
import { INVOICE_STATUS_CONFIG, formatCurrency } from '../../types/invoice';

/**
 * Status badge component
 *
 * WHAT: Renders colored badge for invoice status.
 *
 * WHY: Visual indicator of invoice state.
 */
function StatusBadge({ status }: { status: InvoiceStatus }) {
  const config = INVOICE_STATUS_CONFIG[status];
  return (
    <span className={`px-2 py-1 text-xs font-medium rounded-full ${config.bgColor} ${config.color}`}>
      {config.label}
    </span>
  );
}

/**
 * Format date for display
 *
 * WHAT: Converts ISO date string to localized format.
 *
 * WHY: Consistent date display across the page.
 */
function formatDate(dateString: string | null): string {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString();
}

export default function InvoicesPage() {
  const navigate = useNavigate();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');

  // Filter state
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | ''>('');
  const [unpaidOnly, setUnpaidOnly] = useState(false);
  const [page, setPage] = useState(0);
  const pageSize = 10;

  // Build query params
  const queryParams: InvoiceListParams = useMemo(
    () => ({
      skip: page * pageSize,
      limit: pageSize,
      status: statusFilter || undefined,
      unpaid_only: unpaidOnly,
    }),
    [page, statusFilter, unpaidOnly]
  );

  // Fetch invoices
  const {
    data: invoicesData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['invoices', queryParams],
    queryFn: () => getInvoices(queryParams),
  });

  // Fetch stats
  const { data: stats } = useQuery({
    queryKey: ['invoice-stats'],
    queryFn: getInvoiceStats,
  });

  const invoices = invoicesData?.items || [];
  const total = invoicesData?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Invoices</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage invoices and track payments
          </p>
        </div>
        {isAdmin && (
          <Link
            to="/invoices/new"
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
            New Invoice
          </Link>
        )}
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Total Invoices</p>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{stats.total}</p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Outstanding</p>
            <p className="mt-1 text-2xl font-semibold text-red-600">
              {formatCurrency(stats.total_outstanding)}
            </p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Paid</p>
            <p className="mt-1 text-2xl font-semibold text-green-600">
              {formatCurrency(stats.total_paid)}
            </p>
          </div>
          <div className="card">
            <p className="text-sm font-medium text-gray-500">Overdue</p>
            <p className="mt-1 text-2xl font-semibold text-orange-600">
              {stats.by_status?.overdue || 0}
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
                setStatusFilter(e.target.value as InvoiceStatus | '');
                setUnpaidOnly(false);
                setPage(0);
              }}
            >
              <option value="">All Statuses</option>
              {Object.entries(INVOICE_STATUS_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>

          {/* Unpaid Only Toggle */}
          <div className="flex items-center">
            <input
              id="unpaid-only"
              type="checkbox"
              className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
              checked={unpaidOnly}
              onChange={(e) => {
                setUnpaidOnly(e.target.checked);
                if (e.target.checked) setStatusFilter('');
                setPage(0);
              }}
            />
            <label htmlFor="unpaid-only" className="ml-2 text-sm text-gray-700">
              Unpaid only
            </label>
          </div>
        </div>
      </div>

      {/* Invoices Table */}
      <div className="card overflow-hidden p-0">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading invoices...</div>
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            Error loading invoices. Please try again.
          </div>
        ) : invoices.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p>No invoices found.</p>
            {isAdmin && (
              <Link to="/invoices/new" className="text-blue-600 hover:underline mt-2 inline-block">
                Create your first invoice
              </Link>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Invoice #
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Balance Due
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Issue Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Due Date
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {invoices.map((invoice) => (
                  <tr
                    key={invoice.id}
                    className={`hover:bg-gray-50 cursor-pointer ${
                      invoice.status === 'overdue' ? 'bg-red-50' : ''
                    }`}
                    onClick={() => navigate(`/invoices/${invoice.id}`)}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="font-medium text-gray-900">{invoice.invoice_number}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={invoice.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <span className="font-semibold text-gray-900">
                        {formatCurrency(invoice.total)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <span
                        className={`font-semibold ${
                          invoice.balance_due > 0 ? 'text-red-600' : 'text-green-600'
                        }`}
                      >
                        {formatCurrency(invoice.balance_due)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(invoice.issue_date)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <span className={invoice.status === 'overdue' ? 'text-red-600 font-medium' : ''}>
                        {formatDate(invoice.due_date)}
                      </span>
                    </td>
                    <td
                      className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex justify-end gap-2">
                        <Link
                          to={`/invoices/${invoice.id}`}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          View
                        </Link>
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
              invoices
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
