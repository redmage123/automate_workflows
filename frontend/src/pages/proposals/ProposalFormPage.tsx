/**
 * Proposal Form Page
 *
 * WHAT: Form for creating, editing, and revising proposals.
 *
 * WHY: Single component handles all proposal write operations:
 * - Create new proposal
 * - Edit draft proposal
 * - Create revision of existing proposal
 *
 * HOW: Detects mode from URL and loads existing data as needed.
 */

import { useState, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProposal, createProposal, updateProposal, reviseProposal } from '../../services/proposals';
import { getProjects } from '../../services/projects';
import type { LineItem, ProposalCreateRequest, ProposalUpdateRequest, ProposalReviseRequest } from '../../types';

/**
 * Form state type for managing proposal form data
 */
interface FormState {
  title: string;
  description: string;
  projectId: number | '';
  lineItems: LineItem[];
  discountPercent: string;
  taxPercent: string;
  validUntil: string;
  notes: string;
  clientNotes: string;
  terms: string;
}

/**
 * Line item editor component
 */
function LineItemRow({
  item,
  index,
  onChange,
  onRemove,
}: {
  item: LineItem;
  index: number;
  onChange: (index: number, item: LineItem) => void;
  onRemove: (index: number) => void;
}) {
  const handleChange = (field: keyof LineItem, value: string | number) => {
    const updated = { ...item, [field]: value };
    // Recalculate amount
    if (field === 'quantity' || field === 'unit_price') {
      updated.amount = updated.quantity * updated.unit_price;
    }
    onChange(index, updated);
  };

  return (
    <div className="grid grid-cols-12 gap-2 items-start">
      <div className="col-span-5">
        <input
          type="text"
          className="input w-full text-sm"
          value={item.description}
          onChange={(e) => handleChange('description', e.target.value)}
          placeholder="Description"
          required
        />
      </div>
      <div className="col-span-2">
        <input
          type="number"
          className="input w-full text-sm"
          value={item.quantity}
          onChange={(e) => handleChange('quantity', parseFloat(e.target.value) || 0)}
          placeholder="Qty"
          min="0"
          step="0.5"
          required
        />
      </div>
      <div className="col-span-2">
        <input
          type="number"
          className="input w-full text-sm"
          value={item.unit_price}
          onChange={(e) => handleChange('unit_price', parseFloat(e.target.value) || 0)}
          placeholder="Price"
          min="0"
          step="0.01"
          required
        />
      </div>
      <div className="col-span-2 text-right pt-2">
        <span className="text-sm font-medium text-gray-900">
          ${item.amount.toFixed(2)}
        </span>
      </div>
      <div className="col-span-1 text-right">
        <button
          type="button"
          onClick={() => onRemove(index)}
          className="p-2 text-red-600 hover:text-red-800"
          aria-label="Remove item"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default function ProposalFormPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Determine mode: create, edit, or revise
  const isReviseMode = window.location.pathname.includes('/revise');
  const isEditMode = !isReviseMode && id !== undefined && id !== 'new';
  const isCreateMode = !isEditMode && !isReviseMode;
  const proposalId = (isEditMode || isReviseMode) ? parseInt(id || '0', 10) : 0;
  const projectIdFromUrl = searchParams.get('project_id');

  // Fetch existing proposal for edit/revise mode
  const { data: existingProposal, isLoading: loadingProposal } = useQuery({
    queryKey: ['proposal', proposalId],
    queryFn: () => getProposal(proposalId),
    enabled: proposalId > 0,
  });

  // Fetch projects for dropdown
  const { data: projectsData } = useQuery({
    queryKey: ['projects-list'],
    queryFn: () => getProjects({ limit: 100, active_only: true }),
  });

  const projects = projectsData?.items || [];

  // Build default form state
  const defaultFormState: FormState = useMemo(() => ({
    title: '',
    description: '',
    projectId: projectIdFromUrl ? parseInt(projectIdFromUrl, 10) : '',
    lineItems: [],
    discountPercent: '',
    taxPercent: '',
    validUntil: '',
    notes: '',
    clientNotes: '',
    terms: '',
  }), [projectIdFromUrl]);

  // Build form state from existing proposal
  const proposalFormState = useMemo<FormState | null>(() => {
    if (!existingProposal) return null;
    return {
      title: isReviseMode ? `${existingProposal.title} (Revised)` : existingProposal.title,
      description: existingProposal.description || '',
      projectId: existingProposal.project_id,
      lineItems: existingProposal.line_items || [],
      discountPercent: existingProposal.discount_percent?.toString() || '',
      taxPercent: existingProposal.tax_percent?.toString() || '',
      validUntil: existingProposal.valid_until?.split('T')[0] || '',
      notes: existingProposal.notes || '',
      clientNotes: existingProposal.client_notes || '',
      terms: existingProposal.terms || '',
    };
  }, [existingProposal, isReviseMode]);

  // Form state - use existing proposal state if available
  const [formState, setFormState] = useState<FormState>(defaultFormState);
  const [initializedProposalId, setInitializedProposalId] = useState<number | null>(null);
  const [error, setError] = useState('');

  // Initialize form from proposal (only once per proposal) - using state comparison
  if (proposalFormState && existingProposal && initializedProposalId !== existingProposal.id) {
    setInitializedProposalId(existingProposal.id);
    setFormState(proposalFormState);
  }

  // Helper to update form state
  const updateForm = (updates: Partial<FormState>) => {
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

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: ProposalCreateRequest) => createProposal(data),
    onSuccess: (proposal) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      navigate(`/proposals/${proposal.id}`);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to create proposal');
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (data: ProposalUpdateRequest) => updateProposal(proposalId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposal', proposalId] });
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      navigate(`/proposals/${proposalId}`);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to update proposal');
    },
  });

  // Revise mutation
  const reviseMutation = useMutation({
    mutationFn: (data: ProposalReviseRequest) => reviseProposal(proposalId, data),
    onSuccess: (proposal) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      navigate(`/proposals/${proposal.id}`);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to create revision');
    },
  });

  const handleAddLineItem = () => {
    updateForm({ lineItems: [...formState.lineItems, { description: '', quantity: 1, unit_price: 0, amount: 0 }] });
  };

  const handleLineItemChange = (index: number, item: LineItem) => {
    const updated = [...formState.lineItems];
    updated[index] = item;
    updateForm({ lineItems: updated });
  };

  const handleRemoveLineItem = (index: number) => {
    updateForm({ lineItems: formState.lineItems.filter((_, i) => i !== index) });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation
    if (!formState.title.trim()) {
      setError('Title is required');
      return;
    }
    if (!formState.projectId) {
      setError('Please select a project');
      return;
    }

    // Build request data
    const data: ProposalCreateRequest | ProposalUpdateRequest | ProposalReviseRequest = {
      title: formState.title.trim(),
      description: formState.description.trim() || null,
      line_items: formState.lineItems.length > 0 ? formState.lineItems : null,
      discount_percent: formState.discountPercent ? parseFloat(formState.discountPercent) : null,
      tax_percent: formState.taxPercent ? parseFloat(formState.taxPercent) : null,
      valid_until: formState.validUntil ? new Date(formState.validUntil + 'T23:59:59').toISOString() : null,
      notes: formState.notes.trim() || null,
      client_notes: formState.clientNotes.trim() || null,
      terms: formState.terms.trim() || null,
    };

    // Add project_id only for create
    if (isCreateMode) {
      (data as ProposalCreateRequest).project_id = formState.projectId as number;
    }

    // Submit
    if (isReviseMode) {
      reviseMutation.mutate(data as ProposalReviseRequest);
    } else if (isEditMode) {
      updateMutation.mutate(data as ProposalUpdateRequest);
    } else {
      createMutation.mutate(data as ProposalCreateRequest);
    }
  };

  const isSubmitting = createMutation.isPending || updateMutation.isPending || reviseMutation.isPending;

  if ((isEditMode || isReviseMode) && loadingProposal) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading proposal...</div>
      </div>
    );
  }

  const pageTitle = isReviseMode ? 'Create Revision' : isEditMode ? 'Edit Proposal' : 'New Proposal';

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm">
          <Link to="/proposals" className="text-gray-500 hover:text-gray-700">
            Proposals
          </Link>
          <span className="text-gray-400">/</span>
          <span className="text-gray-900">{pageTitle}</span>
        </div>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">{pageTitle}</h1>
        {isReviseMode && existingProposal && (
          <p className="mt-1 text-sm text-gray-500">
            Creating revision of "{existingProposal.title}" (v{existingProposal.version})
          </p>
        )}
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700" role="alert">
            {error}
          </div>
        )}

        {/* Basic Info */}
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Basic Information</h2>

          {/* Title */}
          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
              Title <span className="text-red-500">*</span>
            </label>
            <input
              id="title"
              type="text"
              className="input w-full"
              value={formState.title}
              onChange={(e) => updateForm({ title: e.target.value })}
              required
              maxLength={255}
              placeholder="e.g., Website Automation Proposal"
            />
          </div>

          {/* Project */}
          <div>
            <label htmlFor="project" className="block text-sm font-medium text-gray-700 mb-1">
              Project <span className="text-red-500">*</span>
            </label>
            <select
              id="project"
              className="input w-full"
              value={formState.projectId}
              onChange={(e) => updateForm({ projectId: e.target.value ? parseInt(e.target.value, 10) : '' })}
              required
              disabled={isEditMode || isReviseMode}
            >
              <option value="">Select a project...</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>

          {/* Description */}
          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
              Scope of Work
            </label>
            <textarea
              id="description"
              className="input w-full min-h-[120px]"
              value={formState.description}
              onChange={(e) => updateForm({ description: e.target.value })}
              maxLength={10000}
              placeholder="Describe the scope of work..."
            />
          </div>

          {/* Valid Until */}
          <div className="max-w-xs">
            <label htmlFor="valid-until" className="block text-sm font-medium text-gray-700 mb-1">
              Valid Until
            </label>
            <input
              id="valid-until"
              type="date"
              className="input w-full"
              value={formState.validUntil}
              onChange={(e) => updateForm({ validUntil: e.target.value })}
            />
          </div>
        </div>

        {/* Line Items */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Line Items</h2>
            <button
              type="button"
              onClick={handleAddLineItem}
              className="text-blue-600 hover:text-blue-800 text-sm font-medium"
            >
              + Add Item
            </button>
          </div>

          {formState.lineItems.length === 0 ? (
            <p className="text-gray-500 text-sm">No line items. Click "Add Item" to add pricing details.</p>
          ) : (
            <div className="space-y-2">
              {/* Header */}
              <div className="grid grid-cols-12 gap-2 text-xs font-medium text-gray-500 uppercase">
                <div className="col-span-5">Description</div>
                <div className="col-span-2">Quantity</div>
                <div className="col-span-2">Unit Price</div>
                <div className="col-span-2 text-right">Amount</div>
                <div className="col-span-1"></div>
              </div>
              {formState.lineItems.map((item, index) => (
                <LineItemRow
                  key={index}
                  item={item}
                  index={index}
                  onChange={handleLineItemChange}
                  onRemove={handleRemoveLineItem}
                />
              ))}
            </div>
          )}

          {/* Discount & Tax */}
          <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200">
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

          {/* Totals Preview */}
          <div className="pt-4 border-t border-gray-200 text-right">
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
              <div className="flex justify-end gap-8 text-lg font-semibold pt-2 border-t border-gray-200">
                <span className="text-gray-900">Total:</span>
                <span className="w-24">${totals.total.toFixed(2)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Notes & Terms */}
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Notes & Terms</h2>

          <div>
            <label htmlFor="client-notes" className="block text-sm font-medium text-gray-700 mb-1">
              Client Notes
            </label>
            <textarea
              id="client-notes"
              className="input w-full min-h-[80px]"
              value={formState.clientNotes}
              onChange={(e) => updateForm({ clientNotes: e.target.value })}
              maxLength={5000}
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
              maxLength={10000}
              placeholder="Payment terms, timeline, etc..."
            />
          </div>

          <div>
            <label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-1">
              Internal Notes
              <span className="text-gray-400 font-normal ml-2">(not visible to client)</span>
            </label>
            <textarea
              id="notes"
              className="input w-full min-h-[80px] bg-yellow-50"
              value={formState.notes}
              onChange={(e) => updateForm({ notes: e.target.value })}
              maxLength={5000}
              placeholder="Internal notes for your team..."
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link
            to={proposalId ? `/proposals/${proposalId}` : '/proposals'}
            className="btn-secondary"
          >
            Cancel
          </Link>
          <button type="submit" className="btn-primary" disabled={isSubmitting}>
            {isSubmitting
              ? 'Saving...'
              : isReviseMode
              ? 'Create Revision'
              : isEditMode
              ? 'Save Changes'
              : 'Create Proposal'}
          </button>
        </div>
      </form>
    </div>
  );
}
