/**
 * N8n Environments Page
 *
 * WHAT: Management page for n8n environment configurations.
 *
 * WHY: Allows admins to configure per-organization n8n instances:
 * - Set base URL for n8n API
 * - Configure API keys (securely stored)
 * - Test connectivity
 * - View environment status
 *
 * HOW: CRUD operations via React Query with secure key handling.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import { Link } from 'react-router-dom';
import {
  getEnvironments,
  createEnvironment,
  updateEnvironment,
  deleteEnvironment,
  testEnvironmentConnection,
} from '../../services/workflows';
import type { N8nEnvironmentCreate, N8nEnvironmentUpdate } from '../../types/workflow';

export default function EnvironmentsPage() {
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState<{
    name: string;
    base_url: string;
    api_key: string;
    is_active: boolean;
  }>({
    name: '',
    base_url: '',
    api_key: '',
    is_active: true,
  });

  /**
   * Fetch environments list
   *
   * WHY: Load existing n8n configurations for display/editing.
   */
  const { data: environmentsData, isLoading, error } = useQuery({
    queryKey: ['n8n-environments'],
    queryFn: () => getEnvironments({ active_only: false, limit: 10 }),
    retry: false,
  });

  const environment = environmentsData?.items?.[0] || null;

  /**
   * Create environment mutation
   */
  const createMutation = useMutation({
    mutationFn: (data: N8nEnvironmentCreate) => createEnvironment(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['n8n-environments'] });
      setIsCreating(false);
      resetForm();
    },
  });

  /**
   * Update environment mutation
   */
  const updateMutation = useMutation({
    mutationFn: (data: N8nEnvironmentUpdate) => updateEnvironment(environment!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['n8n-environments'] });
      setIsEditing(false);
      resetForm();
    },
  });

  /**
   * Delete environment mutation
   */
  const deleteMutation = useMutation({
    mutationFn: () => deleteEnvironment(environment!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['n8n-environments'] });
    },
  });

  /**
   * Reset form to initial state
   */
  const resetForm = () => {
    setFormData({
      name: '',
      base_url: '',
      api_key: '',
      is_active: true,
    });
  };

  /**
   * Start editing existing environment
   */
  const handleStartEdit = () => {
    if (environment) {
      setFormData({
        name: environment.name,
        base_url: environment.base_url,
        api_key: '', // Don't pre-fill API key for security
        is_active: environment.is_active,
      });
      setIsEditing(true);
    }
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (isCreating) {
      await createMutation.mutateAsync({
        name: formData.name,
        base_url: formData.base_url,
        api_key: formData.api_key,
        is_active: formData.is_active,
      });
    } else if (isEditing) {
      const updateData: N8nEnvironmentUpdate = {
        name: formData.name,
        base_url: formData.base_url,
        is_active: formData.is_active,
      };
      // Only include API key if user entered a new one
      if (formData.api_key) {
        updateData.api_key = formData.api_key;
      }
      await updateMutation.mutateAsync(updateData);
    }
  };

  /**
   * Test connection to n8n instance
   *
   * WHY: Verify credentials before saving.
   */
  const handleTestConnection = async () => {
    setConnectionStatus('testing');
    setConnectionError(null);
    try {
      await testEnvironmentConnection();
      setConnectionStatus('success');
    } catch (err) {
      setConnectionStatus('error');
      setConnectionError((err as Error).message || 'Connection failed');
    }
  };

  /**
   * Handle delete with confirmation
   */
  const handleDelete = () => {
    if (window.confirm('Are you sure you want to delete this n8n environment configuration? This cannot be undone.')) {
      deleteMutation.mutate();
    }
  };

  const hasEnvironment = !!environment && !error;
  const isFormOpen = isCreating || isEditing;
  const isPending = createMutation.isPending || updateMutation.isPending;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading environment...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">n8n Environment</h1>
          <p className="mt-1 text-gray-500">
            Configure your organization's n8n instance for workflow automation.
          </p>
        </div>
        <Link to="/workflows" className="btn-secondary">
          Back to Workflows
        </Link>
      </div>

      {/* Current Environment Display */}
      {hasEnvironment && !isFormOpen && (
        <div className="card">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{environment.name}</h2>
              <p className="mt-1 text-gray-500">{environment.base_url}</p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`px-3 py-1 text-sm font-medium rounded-full ${
                  environment.is_active
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {environment.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-gray-500">Created</dt>
              <dd className="text-gray-900">{new Date(environment.created_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Last Updated</dt>
              <dd className="text-gray-900">{environment.updated_at ? new Date(environment.updated_at).toLocaleString() : 'Never'}</dd>
            </div>
          </dl>

          {/* Actions */}
          {isAdmin && (
            <div className="mt-6 flex items-center gap-3">
              <button onClick={handleTestConnection} className="btn-secondary" disabled={connectionStatus === 'testing'}>
                {connectionStatus === 'testing' ? 'Testing...' : 'Test Connection'}
              </button>
              <button onClick={handleStartEdit} className="btn-secondary">
                Edit Configuration
              </button>
              <button onClick={handleDelete} className="btn-danger" disabled={deleteMutation.isPending}>
                Delete
              </button>
            </div>
          )}

          {/* Connection Status */}
          {connectionStatus !== 'idle' && (
            <div className={`mt-4 p-3 rounded-lg ${
              connectionStatus === 'testing' ? 'bg-blue-50 text-blue-700' :
              connectionStatus === 'success' ? 'bg-green-50 text-green-700' :
              'bg-red-50 text-red-700'
            }`}>
              {connectionStatus === 'testing' && 'Testing connection...'}
              {connectionStatus === 'success' && 'Connection successful! n8n instance is reachable.'}
              {connectionStatus === 'error' && `Connection failed: ${connectionError}`}
            </div>
          )}
        </div>
      )}

      {/* No Environment - Create Prompt */}
      {!hasEnvironment && !isFormOpen && (
        <div className="card text-center py-12">
          <div className="text-gray-400 mb-4">
            <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-gray-900">No n8n Environment Configured</h2>
          <p className="mt-2 text-gray-500 max-w-md mx-auto">
            Configure your n8n instance to enable workflow automation. You'll need your n8n base URL and API key.
          </p>
          {isAdmin && (
            <button
              onClick={() => setIsCreating(true)}
              className="mt-6 btn-primary"
            >
              Configure n8n Environment
            </button>
          )}
        </div>
      )}

      {/* Create/Edit Form */}
      {isFormOpen && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {isCreating ? 'Configure n8n Environment' : 'Edit n8n Environment'}
          </h2>

          {/* Error Display */}
          {(createMutation.isError || updateMutation.isError) && (
            <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800">
                {(createMutation.error as Error)?.message ||
                  (updateMutation.error as Error)?.message ||
                  'An error occurred'}
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                Environment Name *
              </label>
              <input
                type="text"
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                placeholder="Production n8n"
                required
              />
            </div>

            {/* Base URL */}
            <div>
              <label htmlFor="base_url" className="block text-sm font-medium text-gray-700">
                n8n Base URL *
              </label>
              <input
                type="url"
                id="base_url"
                value={formData.base_url}
                onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                placeholder="https://n8n.example.com"
                required
              />
              <p className="mt-1 text-sm text-gray-500">
                The base URL of your n8n instance (without trailing slash).
              </p>
            </div>

            {/* API Key */}
            <div>
              <label htmlFor="api_key" className="block text-sm font-medium text-gray-700">
                API Key {isCreating ? '*' : '(leave blank to keep current)'}
              </label>
              <input
                type="password"
                id="api_key"
                value={formData.api_key}
                onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                placeholder={isEditing ? '••••••••' : 'Enter API key'}
                required={isCreating}
              />
              <p className="mt-1 text-sm text-gray-500">
                Your n8n API key. This will be encrypted and stored securely.
              </p>
            </div>

            {/* Active Toggle */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="is_active" className="text-sm text-gray-700">
                Environment is active
              </label>
            </div>

            {/* Form Actions */}
            <div className="flex justify-end gap-3 pt-4">
              <button
                type="button"
                onClick={() => {
                  setIsCreating(false);
                  setIsEditing(false);
                  resetForm();
                }}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button type="submit" disabled={isPending} className="btn-primary">
                {isPending ? 'Saving...' : isCreating ? 'Create Environment' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Help Text */}
      <div className="card bg-blue-50 border-blue-200">
        <h3 className="font-medium text-blue-900">Getting Started with n8n</h3>
        <p className="mt-2 text-sm text-blue-700">
          n8n is a workflow automation platform. To use it with this platform:
        </p>
        <ol className="mt-2 text-sm text-blue-700 list-decimal list-inside space-y-1">
          <li>Set up your n8n instance (self-hosted or cloud)</li>
          <li>Generate an API key in n8n Settings → API</li>
          <li>Enter your n8n URL and API key above</li>
          <li>Create workflow templates and instances to automate tasks</li>
        </ol>
      </div>
    </div>
  );
}
