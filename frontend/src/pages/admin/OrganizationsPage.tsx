/**
 * Admin Organizations Page
 *
 * WHAT: Organization management interface for admins.
 *
 * WHY: Admins need to view and manage all platform organizations.
 *
 * HOW: Data table with organization metrics and suspend/activate actions.
 */

import { useState, useEffect } from 'react';
import {
  getAdminOrganizations,
  suspendOrganization,
  activateOrganization,
} from '../../services';
import type { AdminOrgListItem } from '../../types';

function OrganizationsPage() {
  const [orgs, setOrgs] = useState<AdminOrgListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('');
  const limit = 20;

  const fetchOrgs = async () => {
    try {
      setLoading(true);
      setError(null);
      const params: Record<string, unknown> = {
        skip: page * limit,
        limit,
      };
      if (search) params.search = search;
      if (activeFilter !== '') params.is_active = activeFilter === 'true';

      const response = await getAdminOrganizations(params);
      setOrgs(response.items);
      setTotal(response.total);
    } catch (err) {
      setError('Failed to load organizations');
      console.error('Organizations fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrgs();
  }, [page, activeFilter]);

  const handleSearch = () => {
    setPage(0);
    fetchOrgs();
  };

  const handleSuspend = async (orgId: number) => {
    if (!confirm('Are you sure you want to suspend this organization? This will deactivate all users.')) return;
    try {
      await suspendOrganization(orgId);
      fetchOrgs();
    } catch (err) {
      setError('Failed to suspend organization');
    }
  };

  const handleActivate = async (orgId: number) => {
    try {
      await activateOrganization(orgId);
      fetchOrgs();
    } catch (err) {
      setError('Failed to activate organization');
    }
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div>
      {/* Page header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Organization Management</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage all platform organizations ({total} total)
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="card mb-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search
            </label>
            <div className="flex">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Organization name..."
                className="input flex-1"
              />
              <button
                onClick={handleSearch}
                className="btn-secondary ml-2"
              >
                Search
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              value={activeFilter}
              onChange={(e) => {
                setActiveFilter(e.target.value);
                setPage(0);
              }}
              className="input"
            >
              <option value="">All Status</option>
              <option value="true">Active</option>
              <option value="false">Suspended</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="rounded-md bg-red-50 p-4 mb-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-red-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">{error}</h3>
            </div>
          </div>
        </div>
      )}

      {/* Organizations grid */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          <div className="col-span-full flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          </div>
        ) : orgs.length === 0 ? (
          <div className="col-span-full text-center py-12 text-gray-500">
            No organizations found
          </div>
        ) : (
          orgs.map((org) => (
            <div key={org.id} className="card">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    {org.name}
                  </h3>
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      org.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {org.is_active ? 'Active' : 'Suspended'}
                  </span>
                </div>
                <div className="text-right">
                  {org.is_active ? (
                    <button
                      onClick={() => handleSuspend(org.id)}
                      className="text-red-600 hover:text-red-900 text-sm"
                    >
                      Suspend
                    </button>
                  ) : (
                    <button
                      onClick={() => handleActivate(org.id)}
                      className="text-green-600 hover:text-green-900 text-sm"
                    >
                      Activate
                    </button>
                  )}
                </div>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Users</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {org.user_count}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Projects</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {org.project_count}
                  </p>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-gray-200">
                <p className="text-sm text-gray-500">
                  Created {new Date(org.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-between">
          <p className="text-sm text-gray-700">
            Showing <span className="font-medium">{page * limit + 1}</span> to{' '}
            <span className="font-medium">
              {Math.min((page + 1) * limit, total)}
            </span>{' '}
            of <span className="font-medium">{total}</span> organizations
          </p>
          <div className="flex space-x-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="btn-secondary disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="btn-secondary disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default OrganizationsPage;
