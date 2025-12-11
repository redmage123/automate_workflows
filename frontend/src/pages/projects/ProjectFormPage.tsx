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
 * HOW: Detects mode from URL (new vs :id/edit) and fetches existing data for edit.
 */

import { useState, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProject, createProject, updateProject } from '../../services/projects';
import type { ProjectCreateRequest, ProjectUpdateRequest, ProjectPriority } from '../../types';
import { PROJECT_PRIORITY_CONFIG } from '../../types/project';

/**
 * Form state type for managing project form data
 */
interface FormState {
  name: string;
  description: string;
  priority: ProjectPriority;
  estimatedHours: string;
  actualHours: string;
  startDate: string;
  dueDate: string;
}

/**
 * Default form values for new projects
 */
const defaultFormState: FormState = {
  name: '',
  description: '',
  priority: 'medium',
  estimatedHours: '',
  actualHours: '',
  startDate: '',
  dueDate: '',
};

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
  const initialFormState = useMemo<FormState>(() => {
    if (!existingProject) return defaultFormState;
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

  // Form state - track initialized project ID to avoid re-initialization
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [initializedProjectId, setInitializedProjectId] = useState<number | null>(null);
  const [error, setError] = useState('');

  // Update form state helper
  const updateForm = (updates: Partial<FormState>) => {
    setFormState((prev) => ({ ...prev, ...updates }));
  };

  // Re-initialize form when project loads (only once per project)
  if (isEditMode && existingProject && initializedProjectId !== existingProject.id) {
    setInitializedProjectId(existingProject.id);
    setFormState(initialFormState);
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: ProjectCreateRequest) => createProject(data),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      navigate(`/projects/${project.id}`);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to create project');
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
      setError(err.message || 'Failed to update project');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation
    if (!formState.name.trim()) {
      setError('Project name is required');
      return;
    }

    // Build request data
    const data: ProjectCreateRequest | ProjectUpdateRequest = {
      name: formState.name.trim(),
      description: formState.description.trim() || null,
      priority: formState.priority,
      estimated_hours: formState.estimatedHours ? parseFloat(formState.estimatedHours) : null,
      start_date: formState.startDate ? new Date(formState.startDate).toISOString() : null,
      due_date: formState.dueDate ? new Date(formState.dueDate).toISOString() : null,
    };

    // Add actual_hours only for edit mode
    if (isEditMode) {
      (data as ProjectUpdateRequest).actual_hours = formState.actualHours ? parseFloat(formState.actualHours) : null;
    }

    // Date validation
    if (formState.startDate && formState.dueDate && new Date(formState.dueDate) < new Date(formState.startDate)) {
      setError('Due date must be after start date');
      return;
    }

    // Submit
    if (isEditMode) {
      updateMutation.mutate(data as ProjectUpdateRequest);
    } else {
      createMutation.mutate(data as ProjectCreateRequest);
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
      <form onSubmit={handleSubmit} className="card space-y-6">
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700" role="alert">
            {error}
          </div>
        )}

        {/* Name */}
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
            Project Name <span className="text-red-500">*</span>
          </label>
          <input
            id="name"
            type="text"
            className="input w-full"
            value={formState.name}
            onChange={(e) => updateForm({ name: e.target.value })}
            required
            maxLength={255}
            placeholder="e.g., Website Automation Project"
          />
        </div>

        {/* Description */}
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <textarea
            id="description"
            className="input w-full min-h-[120px]"
            value={formState.description}
            onChange={(e) => updateForm({ description: e.target.value })}
            maxLength={5000}
            placeholder="Describe the project scope and objectives..."
          />
        </div>

        {/* Priority */}
        <div>
          <label htmlFor="priority" className="block text-sm font-medium text-gray-700 mb-1">
            Priority
          </label>
          <select
            id="priority"
            className="input w-full"
            value={formState.priority}
            onChange={(e) => updateForm({ priority: e.target.value as ProjectPriority })}
          >
            {Object.entries(PROJECT_PRIORITY_CONFIG).map(([value, config]) => (
              <option key={value} value={value}>
                {config.label}
              </option>
            ))}
          </select>
        </div>

        {/* Hours */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="estimated-hours" className="block text-sm font-medium text-gray-700 mb-1">
              Estimated Hours
            </label>
            <input
              id="estimated-hours"
              type="number"
              className="input w-full"
              value={formState.estimatedHours}
              onChange={(e) => updateForm({ estimatedHours: e.target.value })}
              min="0"
              step="0.5"
              placeholder="e.g., 40"
            />
          </div>
          {isEditMode && (
            <div>
              <label htmlFor="actual-hours" className="block text-sm font-medium text-gray-700 mb-1">
                Actual Hours
              </label>
              <input
                id="actual-hours"
                type="number"
                className="input w-full"
                value={formState.actualHours}
                onChange={(e) => updateForm({ actualHours: e.target.value })}
                min="0"
                step="0.5"
                placeholder="e.g., 25"
              />
            </div>
          )}
        </div>

        {/* Dates */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="start-date" className="block text-sm font-medium text-gray-700 mb-1">
              Start Date
            </label>
            <input
              id="start-date"
              type="date"
              className="input w-full"
              value={formState.startDate}
              onChange={(e) => updateForm({ startDate: e.target.value })}
            />
          </div>
          <div>
            <label htmlFor="due-date" className="block text-sm font-medium text-gray-700 mb-1">
              Due Date
            </label>
            <input
              id="due-date"
              type="date"
              className="input w-full"
              value={formState.dueDate}
              onChange={(e) => updateForm({ dueDate: e.target.value })}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t">
          <Link to={isEditMode ? `/projects/${projectId}` : '/projects'} className="btn-secondary">
            Cancel
          </Link>
          <button type="submit" className="btn-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Saving...' : isEditMode ? 'Save Changes' : 'Create Project'}
          </button>
        </div>
      </form>
    </div>
  );
}
