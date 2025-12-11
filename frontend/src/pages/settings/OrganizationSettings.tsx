/**
 * Organization Settings Page
 *
 * WHAT: Page for managing organization settings and preferences.
 *
 * WHY: Allows organization admins to:
 * - Update organization name
 * - Configure notification preferences
 * - Set timezone
 * - Upload organization logo
 *
 * HOW: React form with React Query for data fetching and mutations.
 * Uses controlled inputs with validation and optimistic updates.
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import * as organizationService from '../../services/organization';
import type { Organization, OrganizationSettings as OrgSettings } from '../../types';

/**
 * Common timezone options
 *
 * WHY: Predefined list for dropdown selection.
 */
const TIMEZONE_OPTIONS = [
  { value: 'America/New_York', label: 'Eastern Time (ET)' },
  { value: 'America/Chicago', label: 'Central Time (CT)' },
  { value: 'America/Denver', label: 'Mountain Time (MT)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
  { value: 'America/Phoenix', label: 'Arizona (MST)' },
  { value: 'America/Anchorage', label: 'Alaska Time (AKT)' },
  { value: 'Pacific/Honolulu', label: 'Hawaii Time (HST)' },
  { value: 'UTC', label: 'UTC' },
  { value: 'Europe/London', label: 'London (GMT/BST)' },
  { value: 'Europe/Paris', label: 'Paris (CET/CEST)' },
  { value: 'Asia/Tokyo', label: 'Tokyo (JST)' },
  { value: 'Australia/Sydney', label: 'Sydney (AEST/AEDT)' },
];

/**
 * Form state type
 */
interface FormState {
  name: string;
  timezone: string;
  notification_email: string;
  logo_url: string;
}

/**
 * OrganizationSettings Component
 */
function OrganizationSettings() {
  const queryClient = useQueryClient();
  const { organization, setOrganization } = useAuthStore();

  // Fetch organization data
  const { data: orgData, isLoading } = useQuery<Organization>({
    queryKey: ['organization'],
    queryFn: organizationService.getCurrentOrganization,
    initialData: organization || undefined,
  });

  // Derive initial form state from orgData
  const initialFormData: FormState = {
    name: orgData?.name || '',
    timezone: orgData?.settings?.timezone || '',
    notification_email: orgData?.settings?.notification_email || '',
    logo_url: orgData?.settings?.logo_url || '',
  };

  // Form state - initialize from orgData
  const [formData, setFormData] = useState<FormState>(initialFormData);
  const [isDirty, setIsDirty] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Track if orgData changed (for reset)
  const orgDataKey = orgData ? `${orgData.id}-${orgData.updated_at}` : '';

  // Update organization mutation
  const updateMutation = useMutation({
    mutationFn: organizationService.updateOrganization,
    onSuccess: (data) => {
      // Update cache
      queryClient.setQueryData(['organization'], data);
      // Update auth store
      setOrganization(data);
      // Reset form state
      setIsDirty(false);
      setSuccessMessage('Settings saved successfully!');
      setErrorMessage(null);
      // Update form with new data
      setFormData({
        name: data.name || '',
        timezone: data.settings?.timezone || '',
        notification_email: data.settings?.notification_email || '',
        logo_url: data.settings?.logo_url || '',
      });
      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMessage(null), 3000);
    },
    onError: (error: Error) => {
      setErrorMessage(error.message || 'Failed to save settings');
      setSuccessMessage(null);
    },
  });

  // Sync form with orgData when it changes (e.g., from initial load)
  // Using key-based reset pattern instead of useEffect with setState
  const [lastOrgDataKey, setLastOrgDataKey] = useState(orgDataKey);
  if (orgDataKey && orgDataKey !== lastOrgDataKey && !isDirty) {
    setLastOrgDataKey(orgDataKey);
    setFormData({
      name: orgData?.name || '',
      timezone: orgData?.settings?.timezone || '',
      notification_email: orgData?.settings?.notification_email || '',
      logo_url: orgData?.settings?.logo_url || '',
    });
  }

  /**
   * Handle input changes
   */
  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setIsDirty(true);
    // Clear messages on change
    setSuccessMessage(null);
    setErrorMessage(null);
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const settings: OrgSettings = {
      timezone: formData.timezone || undefined,
      notification_email: formData.notification_email || undefined,
      logo_url: formData.logo_url || undefined,
    };

    updateMutation.mutate({
      name: formData.name,
      settings,
    });
  };

  /**
   * Reset form to original values
   */
  const handleReset = () => {
    if (orgData) {
      setFormData({
        name: orgData.name || '',
        timezone: orgData.settings?.timezone || '',
        notification_email: orgData.settings?.notification_email || '',
        logo_url: orgData.settings?.logo_url || '',
      });
      setIsDirty(false);
      setSuccessMessage(null);
      setErrorMessage(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div
          className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"
          role="status"
          aria-label="Loading"
        />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Organization Settings</h1>
        <p className="mt-1 text-sm text-gray-600">
          Manage your organization's profile and preferences.
        </p>
      </div>

      {/* Success/Error Messages */}
      {successMessage && (
        <div
          className="mb-6 p-4 rounded-md bg-green-50 border border-green-200"
          role="alert"
          aria-live="polite"
        >
          <div className="flex">
            <svg
              className="h-5 w-5 text-green-400"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
                clipRule="evenodd"
              />
            </svg>
            <p className="ml-3 text-sm font-medium text-green-800">{successMessage}</p>
          </div>
        </div>
      )}

      {errorMessage && (
        <div
          className="mb-6 p-4 rounded-md bg-red-50 border border-red-200"
          role="alert"
          aria-live="assertive"
        >
          <div className="flex">
            <svg
              className="h-5 w-5 text-red-400"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
                clipRule="evenodd"
              />
            </svg>
            <p className="ml-3 text-sm font-medium text-red-800">{errorMessage}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Organization Profile Section */}
        <section className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Organization Profile
          </h2>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            {/* Organization Name */}
            <div className="sm:col-span-2">
              <label
                htmlFor="name"
                className="block text-sm font-medium text-gray-700"
              >
                Organization Name
              </label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                placeholder="Acme Corporation"
              />
              <p className="mt-1 text-sm text-gray-500">
                This name will be displayed throughout the application.
              </p>
            </div>

            {/* Logo URL */}
            <div className="sm:col-span-2">
              <label
                htmlFor="logo_url"
                className="block text-sm font-medium text-gray-700"
              >
                Logo URL
              </label>
              <input
                type="url"
                id="logo_url"
                name="logo_url"
                value={formData.logo_url}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                placeholder="https://example.com/logo.png"
              />
              <p className="mt-1 text-sm text-gray-500">
                URL to your organization's logo image.
              </p>
            </div>
          </div>
        </section>

        {/* Preferences Section */}
        <section className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Preferences
          </h2>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            {/* Timezone */}
            <div>
              <label
                htmlFor="timezone"
                className="block text-sm font-medium text-gray-700"
              >
                Timezone
              </label>
              <select
                id="timezone"
                name="timezone"
                value={formData.timezone}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                <option value="">Select timezone...</option>
                {TIMEZONE_OPTIONS.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-sm text-gray-500">
                Used for scheduling and date/time display.
              </p>
            </div>

            {/* Notification Email */}
            <div>
              <label
                htmlFor="notification_email"
                className="block text-sm font-medium text-gray-700"
              >
                Notification Email
              </label>
              <input
                type="email"
                id="notification_email"
                name="notification_email"
                value={formData.notification_email}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                placeholder="notifications@company.com"
              />
              <p className="mt-1 text-sm text-gray-500">
                Email address for organization-wide notifications.
              </p>
            </div>
          </div>
        </section>

        {/* Form Actions */}
        <div className="flex justify-end space-x-3">
          <button
            type="button"
            onClick={handleReset}
            disabled={!isDirty || updateMutation.isPending}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Reset
          </button>
          <button
            type="submit"
            disabled={!isDirty || updateMutation.isPending}
            className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-primary-600 border border-transparent rounded-md shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {updateMutation.isPending ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </button>
        </div>
      </form>

      {/* Organization Info (Read-only) */}
      <section className="mt-8 bg-gray-50 rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">
          Organization Information
        </h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-medium text-gray-500">Organization ID</dt>
            <dd className="mt-1 text-sm text-gray-900">{orgData?.id}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Created</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {orgData?.created_at
                ? new Date(orgData.created_at).toLocaleDateString()
                : '-'}
            </dd>
          </div>
          {orgData?.stripe_customer_id && (
            <div>
              <dt className="text-sm font-medium text-gray-500">
                Billing Status
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  Active
                </span>
              </dd>
            </div>
          )}
        </dl>
      </section>
    </div>
  );
}

export default OrganizationSettings;
