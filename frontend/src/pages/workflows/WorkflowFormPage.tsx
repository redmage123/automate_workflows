/**
 * Workflow Form Page
 *
 * WHAT: Form for creating and editing workflow instances.
 *
 * WHY: Provides unified interface for:
 * - Creating new workflows from templates
 * - Creating custom workflows
 * - Editing existing workflow configurations
 *
 * HOW: Uses React Hook Form with React Query mutations.
 */

import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { useForm, Controller, type ControllerRenderProps } from 'react-hook-form';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getWorkflowInstance,
  createWorkflowInstance,
  updateWorkflowInstance,
  getTemplates,
} from '../../services/workflows';
import { getProjects } from '../../services/projects';
import type { WorkflowInstanceCreate, WorkflowInstanceUpdate, WorkflowTemplate } from '../../types/workflow';

/**
 * Form data structure
 *
 * WHY: Defines the shape of form data for workflow creation/editing.
 */
interface WorkflowFormData {
  name: string;
  description: string;
  template_id: number | null;
  project_id: number | null;
  config: string;
}

export default function WorkflowFormPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const workflowId = id ? parseInt(id, 10) : null;
  const isEdit = workflowId !== null;
  const preselectedProjectId = searchParams.get('project_id');
  const preselectedTemplateId = searchParams.get('template_id');

  const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplate | null>(null);

  /**
   * Form setup with React Hook Form
   *
   * WHY: Provides form validation and controlled inputs.
   */
  const {
    register,
    handleSubmit,
    control,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<WorkflowFormData>({
    defaultValues: {
      name: '',
      description: '',
      template_id: preselectedTemplateId ? parseInt(preselectedTemplateId, 10) : null,
      project_id: preselectedProjectId ? parseInt(preselectedProjectId, 10) : null,
      config: '{}',
    },
  });

  const watchedTemplateId = watch('template_id');

  /**
   * Fetch existing workflow for editing
   *
   * WHY: Populate form with existing data when editing.
   */
  const { data: workflow, isLoading: isLoadingWorkflow } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => getWorkflowInstance(workflowId!),
    enabled: isEdit,
  });

  /**
   * Fetch available templates
   *
   * WHY: Allow users to select from pre-built workflow templates.
   */
  const { data: templatesData } = useQuery({
    queryKey: ['workflow-templates'],
    queryFn: () => getTemplates({ skip: 0, limit: 100 }),
  });

  /**
   * Fetch projects for linking
   *
   * WHY: Allow workflows to be associated with projects.
   */
  const { data: projectsData } = useQuery({
    queryKey: ['projects-for-workflow'],
    queryFn: () => getProjects({ skip: 0, limit: 100 }),
  });

  /**
   * Populate form when workflow data loads
   */
  useEffect(() => {
    if (workflow) {
      reset({
        name: workflow.name,
        description: workflow.description || '',
        template_id: workflow.template_id,
        project_id: workflow.project_id,
        config: JSON.stringify(workflow.config || {}, null, 2),
      });
    }
  }, [workflow, reset]);

  /**
   * Update config when template selection changes
   *
   * WHY: Pre-fill configuration from template defaults.
   */
  useEffect(() => {
    if (watchedTemplateId && templatesData?.items) {
      const template = templatesData.items.find((t) => t.id === watchedTemplateId);
      if (template) {
        setSelectedTemplate(template);
        if (!isEdit) {
          setValue('config', JSON.stringify(template.default_config || {}, null, 2));
          if (!watch('name')) {
            setValue('name', `${template.name} Workflow`);
          }
        }
      }
    } else {
      setSelectedTemplate(null);
    }
  }, [watchedTemplateId, templatesData, isEdit, setValue, watch]);

  /**
   * Create workflow mutation
   */
  const createMutation = useMutation({
    mutationFn: (data: WorkflowInstanceCreate) => createWorkflowInstance(data),
    onSuccess: (newWorkflow) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      navigate(`/workflows/${newWorkflow.id}`);
    },
  });

  /**
   * Update workflow mutation
   */
  const updateMutation = useMutation({
    mutationFn: (data: WorkflowInstanceUpdate) => updateWorkflowInstance(workflowId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] });
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      navigate(`/workflows/${workflowId}`);
    },
  });

  /**
   * Form submission handler
   *
   * WHY: Validates and submits workflow data.
   *
   * HOW: Parses config JSON and calls appropriate mutation.
   */
  const onSubmit = async (data: WorkflowFormData) => {
    let config = {};
    try {
      config = data.config ? JSON.parse(data.config) : {};
    } catch {
      return;
    }

    if (isEdit) {
      await updateMutation.mutateAsync({
        name: data.name,
        description: data.description || undefined,
        config,
      });
    } else {
      await createMutation.mutateAsync({
        name: data.name,
        description: data.description || undefined,
        template_id: data.template_id || undefined,
        project_id: data.project_id || undefined,
        config,
      });
    }
  };

  /**
   * Validate JSON config
   *
   * WHY: Ensure config is valid JSON before submission.
   */
  const validateJson = (value: string): true | string => {
    if (!value || value.trim() === '') return true;
    try {
      JSON.parse(value);
      return true;
    } catch {
      return 'Invalid JSON format';
    }
  };

  const templates = templatesData?.items || [];
  const projects = projectsData?.items || [];
  const isLoading = isEdit && isLoadingWorkflow;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading workflow...</div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm">
          <Link to="/workflows" className="text-gray-500 hover:text-gray-700">
            Workflows
          </Link>
          <span className="text-gray-400">/</span>
          <span className="text-gray-900">{isEdit ? 'Edit' : 'New'}</span>
        </div>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">
          {isEdit ? 'Edit Workflow' : 'Create Workflow'}
        </h1>
      </div>

      {/* Error Display */}
      {(createMutation.isError || updateMutation.isError) && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">
            {(createMutation.error as Error)?.message ||
              (updateMutation.error as Error)?.message ||
              'An error occurred'}
          </p>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <div className="card">
          <div className="space-y-4">
            {/* Template Selection (only for new workflows) */}
            {!isEdit && templates.length > 0 && (
              <div>
                <label htmlFor="template_id" className="block text-sm font-medium text-gray-700">
                  Template (Optional)
                </label>
                <select
                  id="template_id"
                  {...register('template_id', { valueAsNumber: true })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="">No template - custom workflow</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name} ({template.category})
                    </option>
                  ))}
                </select>
                {selectedTemplate && (
                  <p className="mt-1 text-sm text-gray-500">{selectedTemplate.description}</p>
                )}
              </div>
            )}

            {/* Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                Workflow Name *
              </label>
              <input
                type="text"
                id="name"
                {...register('name', { required: 'Name is required' })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                placeholder="Enter workflow name"
              />
              {errors.name && (
                <p className="mt-1 text-sm text-red-600">{errors.name.message}</p>
              )}
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                id="description"
                rows={3}
                {...register('description')}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                placeholder="Describe what this workflow does..."
              />
            </div>

            {/* Project Link (only for new workflows) */}
            {!isEdit && projects.length > 0 && (
              <div>
                <label htmlFor="project_id" className="block text-sm font-medium text-gray-700">
                  Link to Project (Optional)
                </label>
                <select
                  id="project_id"
                  {...register('project_id', { valueAsNumber: true })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="">No project link</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Configuration */}
            <div>
              <label htmlFor="config" className="block text-sm font-medium text-gray-700">
                Configuration (JSON)
              </label>
              <Controller
                name="config"
                control={control}
                rules={{ validate: validateJson }}
                render={({ field }: { field: ControllerRenderProps<WorkflowFormData, 'config'> }) => (
                  <textarea
                    id="config"
                    rows={8}
                    {...field}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 font-mono text-sm"
                    placeholder='{"key": "value"}'
                  />
                )}
              />
              {errors.config && (
                <p className="mt-1 text-sm text-red-600">{errors.config.message}</p>
              )}
              <p className="mt-1 text-sm text-gray-500">
                Enter workflow configuration as valid JSON. This will be passed to the n8n workflow.
              </p>
            </div>
          </div>
        </div>

        {/* Form Actions */}
        <div className="flex justify-end gap-3">
          <Link to="/workflows" className="btn-secondary">
            Cancel
          </Link>
          <button type="submit" disabled={isSubmitting} className="btn-primary">
            {isSubmitting
              ? isEdit
                ? 'Saving...'
                : 'Creating...'
              : isEdit
              ? 'Save Changes'
              : 'Create Workflow'}
          </button>
        </div>
      </form>
    </div>
  );
}
