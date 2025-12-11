/**
 * Admin Dashboard Page
 *
 * WHAT: Main admin dashboard showing platform-wide metrics.
 *
 * WHY: Admins need visibility into platform operations:
 * - User and organization counts
 * - Revenue metrics
 * - Project and ticket status
 *
 * HOW: Fetches data from analytics API and displays in stat cards.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardSummary } from '../../services';
import type { DashboardSummaryResponse } from '../../types';

/**
 * Stat card configuration.
 */
interface StatCard {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: string;
  color: string;
  link?: string;
}

/**
 * Format currency for display.
 */
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function AdminDashboard() {
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const data = await getDashboardSummary();
        setSummary(data);
      } catch (err) {
        setError('Failed to load dashboard data');
        console.error('Dashboard fetch error:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const stats: StatCard[] = summary
    ? [
        {
          title: 'Total Users',
          value: summary.total_users,
          subtitle: 'Active accounts',
          icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
          color: 'blue',
          link: '/admin/users',
        },
        {
          title: 'Organizations',
          value: summary.total_organizations,
          subtitle: `${summary.active_organizations} active`,
          icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
          color: 'green',
          link: '/admin/organizations',
        },
        {
          title: 'Total Revenue',
          value: formatCurrency(summary.total_revenue),
          subtitle: `${formatCurrency(summary.revenue_mtd)} MTD`,
          icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
          color: 'yellow',
          link: '/admin/analytics',
        },
        {
          title: 'Active Projects',
          value: summary.active_projects,
          subtitle: `${summary.total_projects} total`,
          icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
          color: 'purple',
        },
        {
          title: 'Open Tickets',
          value: summary.open_tickets,
          subtitle: `${summary.overdue_tickets} overdue`,
          icon: 'M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z',
          color: summary.overdue_tickets > 0 ? 'red' : 'gray',
        },
      ]
    : [];

  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    yellow: 'bg-yellow-100 text-yellow-600',
    purple: 'bg-purple-100 text-purple-600',
    red: 'bg-red-100 text-red-600',
    gray: 'bg-gray-100 text-gray-600',
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md bg-red-50 p-4">
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
    );
  }

  return (
    <div>
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Platform overview and management
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 mb-8">
        {stats.map((stat) => {
          const content = (
            <div className="card hover:shadow-md transition-shadow">
              <div className="flex items-center">
                <div
                  className={`flex-shrink-0 rounded-md p-3 ${colorClasses[stat.color]}`}
                >
                  <svg
                    className="h-6 w-6"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d={stat.icon}
                    />
                  </svg>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">
                    {stat.title}
                  </p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {stat.value}
                  </p>
                </div>
              </div>
              {stat.subtitle && (
                <p className="mt-4 text-sm text-gray-500">{stat.subtitle}</p>
              )}
            </div>
          );

          return stat.link ? (
            <Link key={stat.title} to={stat.link}>
              {content}
            </Link>
          ) : (
            <div key={stat.title}>{content}</div>
          );
        })}
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 mb-8">
        <Link
          to="/admin/users"
          className="card hover:shadow-md transition-shadow"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            User Management
          </h2>
          <p className="text-sm text-gray-500">
            View, create, and manage user accounts across all organizations.
          </p>
        </Link>

        <Link
          to="/admin/organizations"
          className="card hover:shadow-md transition-shadow"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            Organization Management
          </h2>
          <p className="text-sm text-gray-500">
            Manage organizations, view metrics, and handle suspensions.
          </p>
        </Link>

        <Link
          to="/admin/audit-logs"
          className="card hover:shadow-md transition-shadow"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            Audit Logs
          </h2>
          <p className="text-sm text-gray-500">
            View security audit trail and user activity history.
          </p>
        </Link>
      </div>

      {/* Analytics link */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Analytics Dashboard
            </h2>
            <p className="text-sm text-gray-500">
              View detailed analytics on projects, revenue, and user activity.
            </p>
          </div>
          <Link
            to="/admin/analytics"
            className="btn-primary"
          >
            View Analytics
          </Link>
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;
