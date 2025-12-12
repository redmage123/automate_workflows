/**
 * Project Form Page
 *
 * WHAT: Form for creating and editing projects.
 *
 * WHY: Single component handles both create and edit modes:
 * - Reduces code duplication
 * - Consistent form experience
 * - Proper validation and error handling
 *
 * HOW: Uses react-hook-form with zod validation. Detects mode from URL
 * (new vs :id/edit) and fetches existing data for edit.
 */

import { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { getProject, createProject, updateProject } from '../../services/projects';
import { projectSchema, type ProjectFormData } from '../../utils/validation';
import { FormField, Input, Textarea, Select, FormError, SubmitButton } from '../../components/forms';
import type { ProjectCreateRequest, ProjectUpdateRequest, ProjectPriority } from '../../types';
import { PROJECT_PRIORITY_CONFIG } from '../../types/project';

/**
 * ProjectFormPage Component
 *
 * WHAT: Unified form for creating and editing projects.
 *
 * WHY: Single component reduces duplication and ensures consistent behavior.
 *
 * HOW:
 * 1. Detects mode from URL parameters (new vs :id/edit)
 * 2. Fetches existing project data for edit mode
 * 3. Validates form with zod before submission
 * 4. Navigates to project detail on success
 */
export default function ProjectFormPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEditMode = id !== undefined && id !== 'new';
  const projectId = isEditMode ? parseInt(id, 10) : 0;

  // Fetch existing project for edit mode
  const { data: existingProject, isLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: isEditMode && projectId > 0,
  });

  // Derive initial form values from existing project
  const defaultValues = useMemo<ProjectFormData>(() => {
    if (!existingProject) {
      return {
        name: '',
        description: '',
        priority: 'medium',
        estimatedHours: '',
        actualHours: '',
        startDate: '',
        dueDate: '',
      };
    }
    return {
      name: existingProject.name,
      description: existingProject.description || '',
      priority: existingProject.priority,
      estimatedHours: existingProject.estimated_hours?.toString() || '',
      actualHours: existingProject.actual_hours?.toString() || '',
      startDate: existingProject.start_date?.split('T')[0] || '',
      dueDate: existingProject.due_date?.split('T')[0] || '',
    };
  }, [existingProject]);

  // React Hook Form setup with zod validation
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ProjectFormData>({
    resolver: zodResolver(projectSchema),
    defaultValues,
  });

  // Reset form when default values change (project loaded for edit)
  useEffect(() => {
    reset(defaultValues);
  }, [defaultValues, reset]);

  // Form-level error state for API errors
  const [apiError, setApiError] = useState<string | null>(null);

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: ProjectCreateRequest) => createProject(data),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      navigate(`/projects/${project.id}`);
    },
    onError: (err: Error) => {
      setApiError(err.message || 'Failed to create project');
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (data: ProjectUpdateRequest) => updateProject(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      navigate(`/projects/${projectId}`);
    },
    onError: (err: Error) => {
      setApiError(err.message || 'Failed to update project');
    },
  });

  /**
   * Form submission handler
   *
   * WHAT: Validates form and submits to API.
   *
   * WHY: Zod validation ensures data integrity before API call.
   */
  const onSubmit = (data: ProjectFormData) => {
    setApiError(null);

    // Build request data
    const requestData: ProjectCreateRequest | ProjectUpdateRequest = {
      name: data.name.trim(),
      description: data.description?.trim() || null,
      priority: data.priority as ProjectPriority,
      estimated_hours: data.estimatedHours ? parseFloat(data.estimatedHours) : null,
      start_date: data.startDate ? new Date(data.startDate).toISOString() : null,
      due_date: data.dueDate ? new Date(data.dueDate).toISOString() : null,
    };

    // Add actual_hours only for edit mode
    if (isEditMode) {
      (requestData as ProjectUpdateRequest).actual_hours = data.actualHours
        ? parseFloat(data.actualHours)
        : null;
    }

    // Submit based on mode
    if (isEditMode) {
      updateMutation.mutate(requestData as ProjectUpdateRequest);
    } else {
      createMutation.mutate(requestData as ProjectCreateRequest);
    }
  };

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  if (isEditMode && isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading project...</div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm">
          <Link to="/projects" className="text-gray-500 hover:text-gray-700">
            Projects
          </Link>
          <span className="text-gray-400">/</span>
          <span className="text-gray-900">{isEditMode ? 'Edit Project' : 'New Project'}</span>
        </div>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">
          {isEditMode ? `Edit ${existingProject?.name || 'Project'}` : 'Create New Project'}
        </h1>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="card space-y-6">
        {/* API Error Display */}
        <FormError error={apiError} />

        {/* Name */}
        <FormField
          label="Project Name"
          name="name"
          required
          error={errors.name}
        >
          <Input
            id="name"
            type="text"
            maxLength={255}
            placeholder="e.g., Website Automation Project"
            error={!!errors.name}
            errorId="name-error"
            {...register('name')}
          />
        </FormField>

        {/* Description */}
        <FormField
          label="Description"
          name="description"
          error={errors.description}
        >
          <Textarea
            id="description"
            rows={5}
            maxLength={5000}
            placeholder="Describe the project scope and objectives..."
            error={!!errors.description}
            errorId="description-error"
            {...register('description')}
          />
        </FormField>

        {/* Priority */}
        <FormField
          label="Priority"
          name="priority"
          error={errors.priority}
        >
          <Select
            id="priority"
            error={!!errors.priority}
            errorId="priority-error"
            {...register('priority')}
          >
            {Object.entries(PROJECT_PRIORITY_CONFIG).map(([value, config]) => (
              <option key={value} value={value}>
                {config.label}
              </option>
            ))}
          </Select>
        </FormField>

        {/* Hours */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField
            label="Estimated Hours"
            name="estimatedHours"
            error={errors.estimatedHours}
          >
            <Input
              id="estimatedHours"
              type="number"
              min="0"
              step="0.5"
              placeholder="e.g., 40"
              error={!!errors.estimatedHours}
              errorId="estimatedHours-error"
              {...register('estimatedHours')}
            />
          </FormField>
          {isEditMode && (
            <FormField
              label="Actual Hours"
              name="actualHours"
              error={errors.actualHours}
            >
              <Input
                id="actualHours"
                type="number"
                min="0"
                step="0.5"
                placeholder="e.g., 25"
                error={!!errors.actualHours}
                errorId="actualHours-error"
                {...register('actualHours')}
              />
            </FormField>
          )}
        </div>

        {/* Dates */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField
            label="Start Date"
            name="startDate"
            error={errors.startDate}
          >
            <Input
              id="startDate"
              type="date"
              error={!!errors.startDate}
              errorId="startDate-error"
              {...register('startDate')}
            />
          </FormField>
          <FormField
            label="Due Date"
            name="dueDate"
            error={errors.dueDate}
          >
            <Input
              id="dueDate"
              type="date"
              error={!!errors.dueDate}
              errorId="dueDate-error"
              {...register('dueDate')}
            />
          </FormField>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t">
          <Link to={isEditMode ? `/projects/${projectId}` : '/projects'} className="btn-secondary">
            Cancel
          </Link>
          <SubmitButton
            isLoading={isSubmitting}
            loadingText="Saving..."
          >
            {isEditMode ? 'Save Changes' : 'Create Project'}
          </SubmitButton>
        </div>
      </form>
    </div>
  );
}
