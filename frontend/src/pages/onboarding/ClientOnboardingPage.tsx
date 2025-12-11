/**
 * Client Onboarding Page
 *
 * WHAT: Multi-step wizard for onboarding new clients.
 *
 * WHY: Streamlines the client onboarding process by:
 * - Collecting organization details
 * - Creating initial project
 * - Generating first proposal
 * - Setting up communication preferences
 *
 * HOW: Multi-step form with progress indicator and validation.
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import { createProject } from '../../services/projects';
import { createProposal } from '../../services/proposals';
import type { ProjectCreateRequest, ProposalCreateRequest, LineItem, ProjectPriority } from '../../types';

/**
 * Step indicator component
 */
function StepIndicator({ currentStep, steps }: { currentStep: number; steps: string[] }) {
  return (
    <nav aria-label="Progress" className="mb-8">
      <ol className="flex items-center justify-center">
        {steps.map((step, index) => {
          const stepNumber = index + 1;
          const isActive = stepNumber === currentStep;
          const isComplete = stepNumber < currentStep;

          return (
            <li key={step} className="flex items-center">
              <div
                className={`flex items-center justify-center w-10 h-10 rounded-full border-2 ${
                  isComplete
                    ? 'bg-green-600 border-green-600 text-white'
                    : isActive
                    ? 'border-blue-600 text-blue-600'
                    : 'border-gray-300 text-gray-400'
                }`}
              >
                {isComplete ? (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : (
                  stepNumber
                )}
              </div>
              <span
                className={`ml-2 text-sm font-medium ${
                  isActive ? 'text-blue-600' : isComplete ? 'text-green-600' : 'text-gray-400'
                }`}
              >
                {step}
              </span>
              {index < steps.length - 1 && (
                <div
                  className={`w-16 h-0.5 mx-4 ${
                    isComplete ? 'bg-green-600' : 'bg-gray-300'
                  }`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/**
 * Form state interface
 */
interface OnboardingFormState {
  // Step 1: Project details
  projectName: string;
  projectDescription: string;
  projectPriority: ProjectPriority;
  estimatedHours: string;
  startDate: string;
  dueDate: string;
  // Step 2: Proposal details
  proposalTitle: string;
  proposalDescription: string;
  lineItems: LineItem[];
  discountPercent: string;
  taxPercent: string;
  validUntil: string;
  // Step 3: Notes
  clientNotes: string;
  internalNotes: string;
  terms: string;
}

const defaultFormState: OnboardingFormState = {
  projectName: '',
  projectDescription: '',
  projectPriority: 'medium',
  estimatedHours: '',
  startDate: '',
  dueDate: '',
  proposalTitle: '',
  proposalDescription: '',
  lineItems: [{ description: '', quantity: 1, unit_price: 0, amount: 0 }],
  discountPercent: '',
  taxPercent: '',
  validUntil: '',
  clientNotes: '',
  internalNotes: '',
  terms: '',
};

const STEPS = ['Project', 'Proposal', 'Review'];

export default function ClientOnboardingPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { organization } = useAuthStore();

  const [currentStep, setCurrentStep] = useState(1);
  const [formState, setFormState] = useState<OnboardingFormState>(defaultFormState);
  const [error, setError] = useState('');

  const updateForm = (updates: Partial<OnboardingFormState>) => {
    setFormState((prev) => ({ ...prev, ...updates }));
  };

  // Calculate totals
  const totals = useMemo(() => {
    const subtotal = formState.lineItems.reduce((sum, item) => sum + item.amount, 0);
    const discount = subtotal * (parseFloat(formState.discountPercent) || 0) / 100;
    const afterDiscount = subtotal - discount;
    const tax = afterDiscount * (parseFloat(formState.taxPercent) || 0) / 100;
    const total = afterDiscount + tax;
    return { subtotal, discount, tax, total };
  }, [formState.lineItems, formState.discountPercent, formState.taxPercent]);

  // Create project mutation
  const createProjectMutation = useMutation({
    mutationFn: (data: ProjectCreateRequest) => createProject(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to create project');
    },
  });

  // Create proposal mutation
  const createProposalMutation = useMutation({
    mutationFn: (data: ProposalCreateRequest) => createProposal(data),
    onSuccess: (proposal) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      navigate(`/proposals/${proposal.id}`);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to create proposal');
    },
  });

  const handleLineItemChange = (index: number, field: keyof LineItem, value: string | number) => {
    const updated = [...formState.lineItems];
    updated[index] = { ...updated[index], [field]: value };
    if (field === 'quantity' || field === 'unit_price') {
      updated[index].amount = updated[index].quantity * updated[index].unit_price;
    }
    updateForm({ lineItems: updated });
  };

  const handleAddLineItem = () => {
    updateForm({
      lineItems: [...formState.lineItems, { description: '', quantity: 1, unit_price: 0, amount: 0 }],
    });
  };

  const handleRemoveLineItem = (index: number) => {
    if (formState.lineItems.length > 1) {
      updateForm({ lineItems: formState.lineItems.filter((_, i) => i !== index) });
    }
  };

  const validateStep1 = (): boolean => {
    if (!formState.projectName.trim()) {
      setError('Project name is required');
      return false;
    }
    return true;
  };

  const validateStep2 = (): boolean => {
    if (!formState.proposalTitle.trim()) {
      setError('Proposal title is required');
      return false;
    }
    if (formState.lineItems.every((item) => !item.description.trim())) {
      setError('At least one line item is required');
      return false;
    }
    return true;
  };

  const handleNext = () => {
    setError('');

    if (currentStep === 1 && !validateStep1()) return;
    if (currentStep === 2 && !validateStep2()) return;

    if (currentStep < STEPS.length) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
      setError('');
    }
  };

  const handleSubmit = async () => {
    setError('');

    // Step 1: Create project
    const projectData: ProjectCreateRequest = {
      name: formState.projectName.trim(),
      description: formState.projectDescription.trim() || null,
      priority: formState.projectPriority,
      estimated_hours: formState.estimatedHours ? parseFloat(formState.estimatedHours) : null,
      start_date: formState.startDate ? new Date(formState.startDate).toISOString() : null,
      due_date: formState.dueDate ? new Date(formState.dueDate).toISOString() : null,
    };

    try {
      const project = await createProjectMutation.mutateAsync(projectData);

      // Step 2: Create proposal
      const proposalData: ProposalCreateRequest = {
        project_id: project.id,
        title: formState.proposalTitle.trim(),
        description: formState.proposalDescription.trim() || null,
        line_items: formState.lineItems.filter((item) => item.description.trim()),
        discount_percent: formState.discountPercent ? parseFloat(formState.discountPercent) : null,
        tax_percent: formState.taxPercent ? parseFloat(formState.taxPercent) : null,
        valid_until: formState.validUntil
          ? new Date(formState.validUntil + 'T23:59:59').toISOString()
          : null,
        client_notes: formState.clientNotes.trim() || null,
        notes: formState.internalNotes.trim() || null,
        terms: formState.terms.trim() || null,
      };

      await createProposalMutation.mutateAsync(proposalData);
    } catch {
      // Error already handled by mutation onError
    }
  };

  const isSubmitting = createProjectMutation.isPending || createProposalMutation.isPending;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Client Onboarding</h1>
        <p className="mt-1 text-sm text-gray-500">
          Create a new project and proposal for {organization?.name || 'your organization'}
        </p>
      </div>

      {/* Progress indicator */}
      <StepIndicator currentStep={currentStep} steps={STEPS} />

      {/* Error message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700\" role="alert">
          {error}
        </div>
      )}

      {/* Step 1: Project Details */}
      {currentStep === 1 && (
        <div className="card space-y-6">
          <h2 className="text-lg font-semibold text-gray-900">Project Details</h2>

          <div>
            <label htmlFor="project-name" className="block text-sm font-medium text-gray-700 mb-1">
              Project Name <span className="text-red-500">*</span>
            </label>
            <input
              id="project-name"
              type="text"
              className="input w-full"
              value={formState.projectName}
              onChange={(e) => updateForm({ projectName: e.target.value })}
              placeholder="e.g., Website Automation Project"
              required
            />
          </div>

          <div>
            <label htmlFor="project-desc" className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              id="project-desc"
              className="input w-full min-h-[100px]"
              value={formState.projectDescription}
              onChange={(e) => updateForm({ projectDescription: e.target.value })}
              placeholder="Describe the project scope..."
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="priority" className="block text-sm font-medium text-gray-700 mb-1">
                Priority
              </label>
              <select
                id="priority"
                className="input w-full"
                value={formState.projectPriority}
                onChange={(e) => updateForm({ projectPriority: e.target.value as ProjectPriority })}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
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
          </div>

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
        </div>
      )}

      {/* Step 2: Proposal Details */}
      {currentStep === 2 && (
        <div className="space-y-6">
          <div className="card space-y-6">
            <h2 className="text-lg font-semibold text-gray-900">Proposal Details</h2>

            <div>
              <label htmlFor="proposal-title" className="block text-sm font-medium text-gray-700 mb-1">
                Proposal Title <span className="text-red-500">*</span>
              </label>
              <input
                id="proposal-title"
                type="text"
                className="input w-full"
                value={formState.proposalTitle}
                onChange={(e) => updateForm({ proposalTitle: e.target.value })}
                placeholder="e.g., Website Automation Proposal"
                required
              />
            </div>

            <div>
              <label htmlFor="proposal-desc" className="block text-sm font-medium text-gray-700 mb-1">
                Scope of Work
              </label>
              <textarea
                id="proposal-desc"
                className="input w-full min-h-[100px]"
                value={formState.proposalDescription}
                onChange={(e) => updateForm({ proposalDescription: e.target.value })}
                placeholder="Describe what will be delivered..."
              />
            </div>

            <div>
              <label htmlFor="valid-until" className="block text-sm font-medium text-gray-700 mb-1">
                Valid Until
              </label>
              <input
                id="valid-until"
                type="date"
                className="input w-full max-w-xs"
                value={formState.validUntil}
                onChange={(e) => updateForm({ validUntil: e.target.value })}
              />
            </div>
          </div>

          {/* Line Items */}
          <div className="card space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Line Items</h3>
              <button
                type="button"
                onClick={handleAddLineItem}
                className="text-blue-600 hover:text-blue-800 text-sm font-medium"
              >
                + Add Item
              </button>
            </div>

            <div className="space-y-3">
              {formState.lineItems.map((item, index) => (
                <div key={index} className="grid grid-cols-12 gap-2 items-start">
                  <div className="col-span-5">
                    <input
                      type="text"
                      className="input w-full text-sm"
                      value={item.description}
                      onChange={(e) => handleLineItemChange(index, 'description', e.target.value)}
                      placeholder="Description"
                    />
                  </div>
                  <div className="col-span-2">
                    <input
                      type="number"
                      className="input w-full text-sm"
                      value={item.quantity}
                      onChange={(e) => handleLineItemChange(index, 'quantity', parseFloat(e.target.value) || 0)}
                      placeholder="Qty"
                      min="0"
                      step="0.5"
                    />
                  </div>
                  <div className="col-span-2">
                    <input
                      type="number"
                      className="input w-full text-sm"
                      value={item.unit_price}
                      onChange={(e) => handleLineItemChange(index, 'unit_price', parseFloat(e.target.value) || 0)}
                      placeholder="Price"
                      min="0"
                      step="0.01"
                    />
                  </div>
                  <div className="col-span-2 text-right pt-2">
                    <span className="text-sm font-medium">${item.amount.toFixed(2)}</span>
                  </div>
                  <div className="col-span-1 text-right">
                    <button
                      type="button"
                      onClick={() => handleRemoveLineItem(index)}
                      className="p-2 text-red-600 hover:text-red-800 disabled:opacity-50"
                      disabled={formState.lineItems.length === 1}
                      aria-label="Remove item"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Discount & Tax */}
            <div className="grid grid-cols-2 gap-4 pt-4 border-t">
              <div>
                <label htmlFor="discount" className="block text-sm font-medium text-gray-700 mb-1">
                  Discount %
                </label>
                <input
                  id="discount"
                  type="number"
                  className="input w-full"
                  value={formState.discountPercent}
                  onChange={(e) => updateForm({ discountPercent: e.target.value })}
                  min="0"
                  max="100"
                  step="0.1"
                  placeholder="0"
                />
              </div>
              <div>
                <label htmlFor="tax" className="block text-sm font-medium text-gray-700 mb-1">
                  Tax %
                </label>
                <input
                  id="tax"
                  type="number"
                  className="input w-full"
                  value={formState.taxPercent}
                  onChange={(e) => updateForm({ taxPercent: e.target.value })}
                  min="0"
                  max="100"
                  step="0.1"
                  placeholder="0"
                />
              </div>
            </div>

            {/* Totals */}
            <div className="pt-4 border-t text-right">
              <div className="space-y-1 text-sm">
                <div className="flex justify-end gap-8">
                  <span className="text-gray-500">Subtotal:</span>
                  <span className="font-medium w-24">${totals.subtotal.toFixed(2)}</span>
                </div>
                {totals.discount > 0 && (
                  <div className="flex justify-end gap-8">
                    <span className="text-gray-500">Discount:</span>
                    <span className="font-medium w-24 text-green-600">-${totals.discount.toFixed(2)}</span>
                  </div>
                )}
                {totals.tax > 0 && (
                  <div className="flex justify-end gap-8">
                    <span className="text-gray-500">Tax:</span>
                    <span className="font-medium w-24">${totals.tax.toFixed(2)}</span>
                  </div>
                )}
                <div className="flex justify-end gap-8 text-lg font-semibold pt-2 border-t">
                  <span>Total:</span>
                  <span className="w-24">${totals.total.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Review */}
      {currentStep === 3 && (
        <div className="space-y-6">
          {/* Project Summary */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Project Summary</h3>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-gray-500">Name</dt>
                <dd className="font-medium">{formState.projectName}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Priority</dt>
                <dd className="font-medium capitalize">{formState.projectPriority}</dd>
              </div>
              {formState.estimatedHours && (
                <div>
                  <dt className="text-gray-500">Estimated Hours</dt>
                  <dd className="font-medium">{formState.estimatedHours}h</dd>
                </div>
              )}
              {formState.projectDescription && (
                <div className="col-span-2">
                  <dt className="text-gray-500">Description</dt>
                  <dd className="font-medium">{formState.projectDescription}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Proposal Summary */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Proposal Summary</h3>
            <dl className="grid grid-cols-2 gap-4 text-sm mb-4">
              <div>
                <dt className="text-gray-500">Title</dt>
                <dd className="font-medium">{formState.proposalTitle}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Total</dt>
                <dd className="font-medium text-lg">${totals.total.toFixed(2)}</dd>
              </div>
            </dl>

            <h4 className="text-sm font-medium text-gray-700 mb-2">Line Items</h4>
            <div className="bg-gray-50 rounded-lg p-3 space-y-2">
              {formState.lineItems
                .filter((item) => item.description.trim())
                .map((item, index) => (
                  <div key={index} className="flex justify-between text-sm">
                    <span>{item.description}</span>
                    <span className="font-medium">${item.amount.toFixed(2)}</span>
                  </div>
                ))}
            </div>
          </div>

          {/* Notes */}
          <div className="card space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Notes & Terms</h3>

            <div>
              <label htmlFor="client-notes" className="block text-sm font-medium text-gray-700 mb-1">
                Client Notes
              </label>
              <textarea
                id="client-notes"
                className="input w-full min-h-[80px]"
                value={formState.clientNotes}
                onChange={(e) => updateForm({ clientNotes: e.target.value })}
                placeholder="Notes visible to the client..."
              />
            </div>

            <div>
              <label htmlFor="terms" className="block text-sm font-medium text-gray-700 mb-1">
                Terms & Conditions
              </label>
              <textarea
                id="terms"
                className="input w-full min-h-[80px]"
                value={formState.terms}
                onChange={(e) => updateForm({ terms: e.target.value })}
                placeholder="Payment terms, timeline, etc..."
              />
            </div>

            <div>
              <label htmlFor="internal-notes" className="block text-sm font-medium text-gray-700 mb-1">
                Internal Notes
                <span className="text-gray-400 font-normal ml-2">(not visible to client)</span>
              </label>
              <textarea
                id="internal-notes"
                className="input w-full min-h-[80px] bg-yellow-50"
                value={formState.internalNotes}
                onChange={(e) => updateForm({ internalNotes: e.target.value })}
                placeholder="Internal notes for your team..."
              />
            </div>
          </div>
        </div>
      )}

      {/* Navigation buttons */}
      <div className="flex justify-between mt-8">
        <button
          type="button"
          onClick={handleBack}
          disabled={currentStep === 1}
          className="btn-secondary disabled:opacity-50"
        >
          Back
        </button>

        {currentStep < STEPS.length ? (
          <button type="button" onClick={handleNext} className="btn-primary">
            Next
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="btn-primary"
          >
            {isSubmitting ? 'Creating...' : 'Create Project & Proposal'}
          </button>
        )}
      </div>
    </div>
  );
}
