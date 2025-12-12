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
 * HOW: Uses react-hook-form with zod validation and React Query
 * mutations for API calls. Detects mode from URL (new vs :id/edit)
 * and fetches existing data for edit mode.
 */

import { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { getTicket, createTicket, updateTicket } from '../../services/tickets';
import { getProjects } from '../../services/projects';
import { ticketSchema, type TicketFormData } from '../../utils/validation';
import { FormField, Input, Textarea, Select, FormError, SubmitButton } from '../../components/forms';
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
 * 4. Validates form with zod before submission
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
  const defaultValues = useMemo<TicketFormData>(() => {
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
      subject: '',
      description: '',
      priority: 'medium',
      category: 'general',
      projectId: preselectedProjectId,
    };
  }, [existingTicket, preselectedProjectId]);

  // React Hook Form setup with zod validation
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TicketFormData>({
    resolver: zodResolver(ticketSchema),
    defaultValues,
  });

  // Reset form when default values change (ticket loaded for edit)
  useEffect(() => {
    reset(defaultValues);
  }, [defaultValues, reset]);

  // Form-level error state for API errors
  const [apiError, setApiError] = useState<string | null>(null);

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
      setApiError(err.message || 'Failed to create ticket');
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
      setApiError(err.message || 'Failed to update ticket');
    },
  });

  /**
   * Form submission handler
   *
   * WHAT: Validates form and submits to API.
   *
   * WHY: Zod validation ensures data integrity before API call.
   *
   * HOW:
   * 1. Clear previous API errors
   * 2. Build request object from validated form data
   * 3. Call appropriate mutation (create or update)
   */
  const onSubmit = (data: TicketFormData) => {
    setApiError(null);

    // Build request data
    const requestData: TicketCreateRequest | TicketUpdateRequest = {
      subject: data.subject.trim(),
      description: data.description.trim(),
      priority: data.priority as TicketPriority,
      category: data.category as TicketCategory,
      project_id: data.projectId ? parseInt(data.projectId, 10) : null,
    };

    // Submit based on mode
    if (isEditMode) {
      updateMutation.mutate(requestData as TicketUpdateRequest);
    } else {
      createMutation.mutate(requestData as TicketCreateRequest);
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
      <form onSubmit={handleSubmit(onSubmit)} className="card space-y-6">
        {/* API Error Display */}
        <FormError error={apiError} />

        {/* Subject Field */}
        <FormField
          label="Subject"
          name="subject"
          required
          error={errors.subject}
          helpText="A clear, concise summary helps us route your request faster"
        >
          <Input
            id="subject"
            type="text"
            maxLength={255}
            placeholder="Brief summary of the issue or request"
            error={!!errors.subject}
            errorId="subject-error"
            {...register('subject')}
          />
        </FormField>

        {/* Description Field */}
        <FormField
          label="Description"
          name="description"
          required
          error={errors.description}
        >
          <Textarea
            id="description"
            rows={7}
            placeholder={`Please provide details about your issue or request. Include:
- What you were trying to do
- What happened instead
- Steps to reproduce (if applicable)
- Any error messages you received`}
            error={!!errors.description}
            errorId="description-error"
            {...register('description')}
          />
        </FormField>

        {/* Priority and Category Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Priority Selection */}
          <FormField
            label="Priority"
            name="priority"
            error={errors.priority}
            helpText="Higher priority = faster SLA response time"
          >
            <Select
              id="priority"
              error={!!errors.priority}
              errorId="priority-error"
              {...register('priority')}
            >
              {Object.entries(TICKET_PRIORITY_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </Select>
          </FormField>

          {/* Category Selection */}
          <FormField
            label="Category"
            name="category"
            error={errors.category}
          >
            <Select
              id="category"
              error={!!errors.category}
              errorId="category-error"
              {...register('category')}
            >
              {Object.entries(TICKET_CATEGORY_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.label}
                </option>
              ))}
            </Select>
          </FormField>
        </div>

        {/* Project Association */}
        {projectsData && projectsData.items.length > 0 && (
          <FormField
            label="Related Project"
            name="projectId"
            helpText="Linking to a project helps provide context for your request"
          >
            <Select
              id="projectId"
              {...register('projectId')}
            >
              <option value="">No project (general support)</option>
              {projectsData.items.map((project) => (
                <option key={project.id} value={project.id.toString()}>
                  {project.name}
                </option>
              ))}
            </Select>
          </FormField>
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
          <SubmitButton
            isLoading={isSubmitting}
            loadingText="Saving..."
          >
            {isEditMode ? 'Save Changes' : 'Submit Ticket'}
          </SubmitButton>
        </div>
      </form>
    </div>
  );
}
