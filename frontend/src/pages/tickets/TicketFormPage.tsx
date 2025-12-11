/**
 * Ticket Form Page
 *
 * WHAT: Form for creating and editing support tickets.
 *
 * WHY: Provides a comprehensive form for ticket creation with:
 * - Subject and description fields
 * - Priority selection (affects SLA calculations)
 * - Category classification
 * - Optional project association
 * - File attachment support (future)
 *
 * HOW: Uses React Query mutations for API calls. Detects mode from URL
 * (new vs :id/edit) and fetches existing data for edit mode.
 */

import { useState, useMemo } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTicket, createTicket, updateTicket } from '../../services/tickets';
import { getProjects } from '../../services/projects';
import type {
  TicketCreateRequest,
  TicketUpdateRequest,
  TicketPriority,
  TicketCategory,
} from '../../types';
import {
  TICKET_PRIORITY_CONFIG,
  TICKET_CATEGORY_CONFIG,
} from '../../types/ticket';

/**
 * Form state type for managing ticket form data
 *
 * WHY: Typed form state ensures type safety and enables
 * IntelliSense for form field access.
 */
interface FormState {
  subject: string;
  description: string;
  priority: TicketPriority;
  category: TicketCategory;
  projectId: string;
}

/**
 * Default form values for new tickets
 *
 * WHY: Sensible defaults improve UX by reducing required input.
 * Medium priority is typical for most support requests.
 */
const defaultFormState: FormState = {
  subject: '',
  description: '',
  priority: 'medium',
  category: 'general',
  projectId: '',
};

/**
 * TicketFormPage Component
 *
 * WHAT: Unified form for creating and editing tickets.
 *
 * WHY: Single component handles both modes to reduce duplication
 * and ensure consistent form behavior.
 *
 * HOW:
 * 1. Detects mode from URL parameters (new vs :id/edit)
 * 2. Fetches existing ticket data for edit mode
 * 3. Pre-fills project from URL query param if provided
 * 4. Validates form before submission
 * 5. Navigates to ticket detail on success
 */
export default function TicketFormPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Determine if editing existing ticket
  const isEditMode = id !== undefined && id !== 'new';
  const ticketId = isEditMode ? parseInt(id, 10) : 0;

  // Get optional project ID from URL query params
  const preselectedProjectId = searchParams.get('project') || '';

  /**
   * Fetch existing ticket for edit mode
   *
   * WHY: Need current values to populate form fields.
   * Only enabled when editing an existing ticket.
   */
  const { data: existingTicket, isLoading: isLoadingTicket } = useQuery({
    queryKey: ['ticket', ticketId],
    queryFn: () => getTicket(ticketId),
    enabled: isEditMode && ticketId > 0,
  });

  /**
   * Fetch projects for association dropdown
   *
   * WHY: Tickets can be linked to projects for better organization.
   * Fetching first page with limit should cover most use cases.
   */
  const { data: projectsData } = useQuery({
    queryKey: ['projects', { limit: 100 }],
    queryFn: () => getProjects({ limit: 100 }),
  });

  /**
   * Derive initial form values
   *
   * WHY: Form needs to start with either default values (create)
   * or existing ticket values (edit). useMemo prevents recalculation.
   */
  const initialFormState = useMemo<FormState>(() => {
    if (existingTicket) {
      return {
        subject: existingTicket.subject,
        description: existingTicket.description,
        priority: existingTicket.priority,
        category: existingTicket.category,
        projectId: existingTicket.project_id?.toString() || '',
      };
    }
    // For new tickets, check for preselected project from URL
    return {
      ...defaultFormState,
      projectId: preselectedProjectId,
    };
  }, [existingTicket, preselectedProjectId]);

  // Form state management
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [initializedTicketId, setInitializedTicketId] = useState<number | null>(null);
  const [error, setError] = useState('');

  /**
   * Update form state helper
   *
   * WHY: Partial updates allow changing single fields
   * without specifying all other fields.
   */
  const updateForm = (updates: Partial<FormState>) => {
    setFormState((prev) => ({ ...prev, ...updates }));
  };

  /**
   * Re-initialize form when ticket loads (only once per ticket)
   *
   * WHY: When editing, we need to populate form with existing values
   * once they're fetched. Tracking initialized ID prevents loops.
   */
  if (isEditMode && existingTicket && initializedTicketId !== existingTicket.id) {
    setInitializedTicketId(existingTicket.id);
    setFormState(initialFormState);
  }

  /**
   * Create ticket mutation
   *
   * WHY: Handles API call, cache invalidation, and navigation
   * in a single mutation object.
   */
  const createMutation = useMutation({
    mutationFn: (data: TicketCreateRequest) => createTicket(data),
    onSuccess: (ticket) => {
      // Invalidate tickets list to show new ticket
      queryClient.invalidateQueries({ queryKey: ['tickets'] });
      // Navigate to the newly created ticket
      navigate(`/tickets/${ticket.id}`);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to create ticket');
    },
  });

  /**
   * Update ticket mutation
   *
   * WHY: Handles edit mode API call with proper cache invalidation.
   */
  const updateMutation = useMutation({
    mutationFn: (data: TicketUpdateRequest) => updateTicket(ticketId, data),
    onSuccess: () => {
      // Invalidate both the specific ticket and the list
      queryClient.invalidateQueries({ queryKey: ['ticket', ticketId] });
      queryClient.invalidateQueries({ queryKey: ['tickets'] });
      // Navigate back to ticket detail
      navigate(`/tickets/${ticketId}`);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to update ticket');
    },
  });

  /**
   * Form submission handler
   *
   * WHAT: Validates form and submits to API.
   *
   * WHY: Centralized validation ensures data integrity
   * before API call.
   *
   * HOW:
   * 1. Prevent default form submission
   * 2. Validate required fields
   * 3. Build request object
   * 4. Call appropriate mutation (create or update)
   */
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validate required fields
    if (!formState.subject.trim()) {
      setError('Subject is required');
      return;
    }

    if (!formState.description.trim()) {
      setError('Description is required');
      return;
    }

    // Build request data
    const data: TicketCreateRequest | TicketUpdateRequest = {
      subject: formState.subject.trim(),
      description: formState.description.trim(),
      priority: formState.priority,
      category: formState.category,
      project_id: formState.projectId ? parseInt(formState.projectId, 10) : null,
    };

    // Submit based on mode
    if (isEditMode) {
      updateMutation.mutate(data as TicketUpdateRequest);
    } else {
      createMutation.mutate(data as TicketCreateRequest);
    }
  };

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  // Show loading state while fetching ticket for edit mode
  if (isEditMode && isLoadingTicket) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading ticket...</div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header with Breadcrumb */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm">
          <Link to="/tickets" className="text-gray-500 hover:text-gray-700">
            Tickets
          </Link>
          <span className="text-gray-400">/</span>
          <span className="text-gray-900">
            {isEditMode ? 'Edit Ticket' : 'New Ticket'}
          </span>
        </div>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">
          {isEditMode
            ? `Edit Ticket #${existingTicket?.id || ''}`
            : 'Create New Ticket'}
        </h1>
        {!isEditMode && (
          <p className="mt-1 text-sm text-gray-500">
            Submit a support request or report an issue
          </p>
        )}
      </div>

      {/* Form Card */}
      <form onSubmit={handleSubmit} className="card space-y-6">
        {/* Error Display */}
        {error && (
          <div
            className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700"
            role="alert"
          >
            {error}
          </div>
        )}

        {/* Subject Field */}
        <div>
          <label
            htmlFor="subject"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Subject <span className="text-red-500">*</span>
          </label>
          <input
            id="subject"
            type="text"
            className="input w-full"
            value={formState.subject}
            onChange={(e) => updateForm({ subject: e.target.value })}
            required
            maxLength={255}
            placeholder="Brief summary of the issue or request"
          />
          <p className="mt-1 text-sm text-gray-500">
            A clear, concise summary helps us route your request faster
          </p>
        </div>

        {/* Description Field */}
        <div>
          <label
            htmlFor="description"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Description <span className="text-red-500">*</span>
          </label>
          <textarea
            id="description"
            className="input w-full min-h-[180px]"
            value={formState.description}
            onChange={(e) => updateForm({ description: e.target.value })}
            required
            placeholder="Please provide details about your issue or request. Include:
- What you were trying to do
- What happened instead
- Steps to reproduce (if applicable)
- Any error messages you received"
          />
        </div>

        {/* Priority and Category Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Priority Selection */}
          <div>
            <label
              htmlFor="priority"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Priority
            </label>
            <select
              id="priority"
              className="input w-full"
              value={formState.priority}
              onChange={(e) =>
                updateForm({ priority: e.target.value as TicketPriority })
              }
            >
              {Object.entries(TICKET_PRIORITY_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">
              Higher priority = faster SLA response time
            </p>
          </div>

          {/* Category Selection */}
          <div>
            <label
              htmlFor="category"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Category
            </label>
            <select
              id="category"
              className="input w-full"
              value={formState.category}
              onChange={(e) =>
                updateForm({ category: e.target.value as TicketCategory })
              }
            >
              {Object.entries(TICKET_CATEGORY_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Project Association */}
        {projectsData && projectsData.items.length > 0 && (
          <div>
            <label
              htmlFor="project"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Related Project
            </label>
            <select
              id="project"
              className="input w-full"
              value={formState.projectId}
              onChange={(e) => updateForm({ projectId: e.target.value })}
            >
              <option value="">No project (general support)</option>
              {projectsData.items.map((project) => (
                <option key={project.id} value={project.id.toString()}>
                  {project.name}
                </option>
              ))}
            </select>
            <p className="mt-1 text-sm text-gray-500">
              Linking to a project helps provide context for your request
            </p>
          </div>
        )}

        {/* Priority Info Box */}
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h3 className="text-sm font-medium text-blue-900 mb-2">
            SLA Response Times
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
            <div>
              <span className="font-medium text-red-700">Urgent:</span>
              <span className="text-gray-600 ml-1">1 hour</span>
            </div>
            <div>
              <span className="font-medium text-orange-700">High:</span>
              <span className="text-gray-600 ml-1">4 hours</span>
            </div>
            <div>
              <span className="font-medium text-yellow-700">Medium:</span>
              <span className="text-gray-600 ml-1">8 hours</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Low:</span>
              <span className="text-gray-600 ml-1">24 hours</span>
            </div>
          </div>
        </div>

        {/* Form Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t">
          <Link
            to={isEditMode ? `/tickets/${ticketId}` : '/tickets'}
            className="btn-secondary"
          >
            Cancel
          </Link>
          <button
            type="submit"
            className="btn-primary"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? 'Saving...'
              : isEditMode
              ? 'Save Changes'
              : 'Submit Ticket'}
          </button>
        </div>
      </form>
    </div>
  );
}
