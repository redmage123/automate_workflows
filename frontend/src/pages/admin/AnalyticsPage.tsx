/**
 * Admin Analytics Page
 *
 * WHAT: Comprehensive analytics dashboard for platform metrics.
 *
 * WHY: Admins need detailed insights into platform usage, revenue trends,
 * and user activity to make informed business decisions.
 *
 * HOW: Fetches data from analytics API endpoints and displays
 * charts and metrics with date range filtering.
 */

import { useState, useEffect } from 'react';
import {
  getProjectMetrics,
  getRevenueMetrics,
  getUserActivityMetrics,
} from '../../services';
import type {
  ProjectMetricsResponse,
  RevenueMetricsResponse,
  UserActivityMetricsResponse,
  StatusCount,
  TimeSeriesPoint,
} from '../../types';

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

/**
 * Simple bar chart component.
 *
 * WHAT: Renders a horizontal bar chart.
 *
 * WHY: Visual representation of data distribution.
 */
function BarChart({
  data,
  colorMap,
}: {
  data: StatusCount[];
  colorMap?: Record<string, string>;
}) {
  const maxValue = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="space-y-3">
      {data.map((item) => (
        <div key={item.status}>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600 capitalize">{item.status}</span>
            <span className="font-medium">{item.count}</span>
          </div>
          <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${colorMap?.[item.status] || 'bg-primary-500'}`}
              style={{ width: `${(item.count / maxValue) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Line chart component using SVG.
 *
 * WHAT: Renders a simple line chart for time series data.
 *
 * WHY: Visualize trends over time.
 */
function LineChart({
  data,
}: {
  data: TimeSeriesPoint[];
}) {
  if (data.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-gray-500">
        No data available
      </div>
    );
  }

  const maxValue = Math.max(...data.map((d) => d.value), 1);
  const minValue = Math.min(...data.map((d) => d.value), 0);
  const range = maxValue - minValue || 1;

  const width = 100;
  const height = 50;
  const padding = 5;

  const points = data.map((d, i) => {
    const x = padding + (i / Math.max(data.length - 1, 1)) * (width - 2 * padding);
    const y = height - padding - ((d.value - minValue) / range) * (height - 2 * padding);
    return `${x},${y}`;
  });

  const pathD = `M ${points.join(' L ')}`;
  const areaD = `${pathD} L ${width - padding},${height - padding} L ${padding},${height - padding} Z`;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-48">
        {/* Area fill */}
        <path d={areaD} fill="url(#gradient)" opacity="0.3" />
        {/* Line */}
        <path
          d={pathD}
          fill="none"
          stroke="#6366f1"
          strokeWidth="0.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Points */}
        {data.map((d, i) => {
          const x = padding + (i / Math.max(data.length - 1, 1)) * (width - 2 * padding);
          const y = height - padding - ((d.value - minValue) / range) * (height - 2 * padding);
          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r="1"
              fill="#6366f1"
              className="hover:r-2 transition-all"
            />
          );
        })}
        <defs>
          <linearGradient id="gradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
      {/* X-axis labels */}
      <div className="flex justify-between text-xs text-gray-500 mt-2 px-1">
        {data.slice(0, 6).map((d, i) => (
          <span key={i}>{d.date}</span>
        ))}
        {data.length > 6 && <span>...</span>}
      </div>
    </div>
  );
}

function AnalyticsPage() {
  const [projectMetrics, setProjectMetrics] = useState<ProjectMetricsResponse | null>(null);
  const [revenueMetrics, setRevenueMetrics] = useState<RevenueMetricsResponse | null>(null);
  const [userMetrics, setUserMetrics] = useState<UserActivityMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [months, setMonths] = useState(12);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      setError(null);

      const [projects, revenue, users] = await Promise.all([
        getProjectMetrics(months),
        getRevenueMetrics(months),
        getUserActivityMetrics(months),
      ]);

      setProjectMetrics(projects);
      setRevenueMetrics(revenue);
      setUserMetrics(users);
    } catch (err) {
      setError('Failed to load analytics');
      console.error('Analytics fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [months]);

  /**
   * Color map for project statuses.
   */
  const projectStatusColors: Record<string, string> = {
    draft: 'bg-gray-400',
    active: 'bg-green-500',
    on_hold: 'bg-yellow-500',
    completed: 'bg-blue-500',
    cancelled: 'bg-red-500',
  };

  /**
   * Color map for user roles.
   */
  const roleColors: Record<string, string> = {
    ADMIN: 'bg-purple-500',
    CLIENT: 'bg-blue-500',
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div>
      {/* Page header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
          <p className="mt-1 text-sm text-gray-500">
            Platform metrics and insights
          </p>
        </div>
        <div>
          <select
            value={months}
            onChange={(e) => setMonths(parseInt(e.target.value))}
            className="input"
          >
            <option value={3}>Last 3 months</option>
            <option value={6}>Last 6 months</option>
            <option value={12}>Last 12 months</option>
            <option value={24}>Last 24 months</option>
          </select>
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

      {/* Summary stats */}
      <div className="grid grid-cols-1 gap-6 mb-8 md:grid-cols-4">
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500">Total Projects</h3>
          <p className="mt-2 text-3xl font-bold text-gray-900">
            {projectMetrics?.total_projects || 0}
          </p>
          <p className="mt-1 text-sm text-gray-500">
            {projectMetrics?.active_projects || 0} active
          </p>
        </div>
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500">Total Revenue</h3>
          <p className="mt-2 text-3xl font-bold text-green-600">
            {formatCurrency(revenueMetrics?.total_revenue || 0)}
          </p>
          <p className="mt-1 text-sm text-gray-500">
            {formatCurrency(revenueMetrics?.revenue_mtd || 0)} this month
          </p>
        </div>
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500">Total Users</h3>
          <p className="mt-2 text-3xl font-bold text-gray-900">
            {userMetrics?.total_users || 0}
          </p>
          <p className="mt-1 text-sm text-gray-500">
            {userMetrics?.active_users || 0} active
          </p>
        </div>
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500">Avg Deal Size</h3>
          <p className="mt-2 text-3xl font-bold text-gray-900">
            {formatCurrency(revenueMetrics?.average_deal_size || 0)}
          </p>
          <p className="mt-1 text-sm text-gray-500">
            {formatCurrency(revenueMetrics?.outstanding_amount || 0)} outstanding
          </p>
        </div>
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 gap-6 mb-6 lg:grid-cols-2">
        {/* Revenue trend */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Revenue Trend
          </h3>
          <LineChart data={revenueMetrics?.revenue_over_time || []} />
          {revenueMetrics?.revenue_over_time && revenueMetrics.revenue_over_time.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-sm text-gray-500">Total</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {formatCurrency(revenueMetrics.total_revenue)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">MTD</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {formatCurrency(revenueMetrics.revenue_mtd)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">YTD</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {formatCurrency(revenueMetrics.revenue_ytd)}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Projects created trend */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Projects Created
          </h3>
          <LineChart data={projectMetrics?.created_over_time || []} />
          {projectMetrics?.created_over_time && projectMetrics.created_over_time.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-sm text-gray-500">Total</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {projectMetrics.total_projects}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Active</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {projectMetrics.active_projects}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Overdue</p>
                  <p className="text-lg font-semibold text-red-600">
                    {projectMetrics.overdue_projects}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 gap-6 mb-6 lg:grid-cols-3">
        {/* Project status breakdown */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Project Status
          </h3>
          <BarChart
            data={projectMetrics?.by_status || []}
            colorMap={projectStatusColors}
          />
        </div>

        {/* User role distribution */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            User Roles
          </h3>
          <BarChart
            data={userMetrics?.users_by_role || []}
            colorMap={roleColors}
          />
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="grid grid-cols-2 gap-4 text-center">
              <div>
                <p className="text-sm text-gray-500">Verified</p>
                <p className="text-lg font-semibold text-green-600">
                  {userMetrics?.verified_users || 0}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Unverified</p>
                <p className="text-lg font-semibold text-yellow-600">
                  {userMetrics?.unverified_users || 0}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Payment method breakdown */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Payment Methods
          </h3>
          <BarChart data={revenueMetrics?.payment_method_breakdown || []} />
        </div>
      </div>

      {/* User activity trend */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          New User Registrations
        </h3>
        <LineChart data={userMetrics?.new_users_over_time || []} />
        {userMetrics?.new_users_over_time && userMetrics.new_users_over_time.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <p className="text-sm text-gray-500">Total Users</p>
                <p className="text-lg font-semibold text-gray-900">
                  {userMetrics.total_users}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Active</p>
                <p className="text-lg font-semibold text-green-600">
                  {userMetrics.active_users}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Recent Active</p>
                <p className="text-lg font-semibold text-blue-600">
                  {userMetrics.recent_active_users}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Verified</p>
                <p className="text-lg font-semibold text-purple-600">
                  {userMetrics.verified_users}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AnalyticsPage;
