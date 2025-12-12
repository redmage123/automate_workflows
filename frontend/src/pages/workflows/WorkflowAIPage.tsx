/**
 * Workflow AI Generation Page
 *
 * WHAT: Page for creating workflows from natural language descriptions.
 *
 * WHY: Enables non-technical users to create automations by describing
 * what they want in plain English, powered by GPT-5.2.
 *
 * HOW: Multi-step flow:
 * 1. User enters description
 * 2. AI generates workflow
 * 3. User reviews and optionally refines
 * 4. User saves the workflow
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getAIServiceStatus,
  generateWorkflowFromDescription,
  refineWorkflow,
  validateWorkflow,
  createWorkflowInstance,
  type WorkflowGenerationResponse,
  type WorkflowValidationResponse,
} from '../../services/workflows';

/**
 * Example prompts to help users understand what they can create
 */
const EXAMPLE_PROMPTS = [
  'When a new row is added to Google Sheets, send a Slack notification to #sales with the customer details',
  'Every Monday at 9am, send a summary email of all tickets created last week',
  'When a webhook is triggered, validate the data, add it to a database, and send a confirmation email',
  'Monitor a website for changes and alert me via Telegram when content changes',
];

export default function WorkflowAIPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // State
  const [description, setDescription] = useState('');
  const [generatedWorkflow, setGeneratedWorkflow] = useState<WorkflowGenerationResponse | null>(
    null
  );
  const [validation, setValidation] = useState<WorkflowValidationResponse | null>(null);
  const [refinementFeedback, setRefinementFeedback] = useState('');
  const [showJsonEditor, setShowJsonEditor] = useState(false);
  const [editedJson, setEditedJson] = useState('');
  const [workflowName, setWorkflowName] = useState('');

  /**
   * Check if AI service is available
   */
  const { data: aiStatus, isLoading: isLoadingStatus } = useQuery({
    queryKey: ['ai-service-status'],
    queryFn: getAIServiceStatus,
  });

  /**
   * Generate workflow mutation
   */
  const generateMutation = useMutation({
    mutationFn: (desc: string) => generateWorkflowFromDescription(desc),
    onSuccess: (result) => {
      setGeneratedWorkflow(result);
      setWorkflowName(result.name);
      setEditedJson(JSON.stringify(result, null, 2));
      // Auto-validate
      validateMutation.mutate({
        name: result.name,
        nodes: result.nodes,
        connections: result.connections,
        settings: result.settings,
      });
    },
  });

  /**
   * Refine workflow mutation
   */
  const refineMutation = useMutation({
    mutationFn: ({ workflow, feedback }: { workflow: Record<string, unknown>; feedback: string }) =>
      refineWorkflow(workflow, feedback),
    onSuccess: (result) => {
      setGeneratedWorkflow(result);
      setWorkflowName(result.name);
      setEditedJson(JSON.stringify(result, null, 2));
      setRefinementFeedback('');
      // Re-validate
      validateMutation.mutate({
        name: result.name,
        nodes: result.nodes,
        connections: result.connections,
        settings: result.settings,
      });
    },
  });

  /**
   * Validate workflow mutation
   */
  const validateMutation = useMutation({
    mutationFn: (workflow: Record<string, unknown>) => validateWorkflow(workflow),
    onSuccess: (result) => {
      setValidation(result);
    },
  });

  /**
   * Save workflow mutation
   */
  const saveMutation = useMutation({
    mutationFn: (data: { name: string; parameters: Record<string, unknown> }) =>
      createWorkflowInstance({
        name: data.name,
        parameters: data.parameters,
      }),
    onSuccess: (newWorkflow) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      navigate(`/workflows/${newWorkflow.id}`);
    },
  });

  /**
   * Handle generate workflow
   */
  const handleGenerate = () => {
    if (description.trim().length < 10) return;
    setGeneratedWorkflow(null);
    setValidation(null);
    generateMutation.mutate(description);
  };

  /**
   * Handle refine workflow
   */
  const handleRefine = () => {
    if (!generatedWorkflow || !refinementFeedback.trim()) return;
    refineMutation.mutate({
      workflow: {
        name: generatedWorkflow.name,
        nodes: generatedWorkflow.nodes,
        connections: generatedWorkflow.connections,
        settings: generatedWorkflow.settings,
      },
      feedback: refinementFeedback,
    });
  };

  /**
   * Handle save workflow
   */
  const handleSave = () => {
    if (!generatedWorkflow) return;

    // Parse edited JSON if modified
    let workflowData = generatedWorkflow;
    if (showJsonEditor && editedJson) {
      try {
        workflowData = JSON.parse(editedJson);
      } catch {
        alert('Invalid JSON. Please fix the errors before saving.');
        return;
      }
    }

    saveMutation.mutate({
      name: workflowName || workflowData.name,
      parameters: {
        nodes: workflowData.nodes,
        connections: workflowData.connections,
        settings: workflowData.settings,
      },
    });
  };

  /**
   * Handle example click
   */
  const handleExampleClick = (example: string) => {
    setDescription(example);
  };

  /**
   * Get confidence color
   */
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-100';
    if (confidence >= 0.5) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  // Loading state
  if (isLoadingStatus) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Checking AI service availability...</div>
      </div>
    );
  }

  // AI service not available
  if (!aiStatus?.available) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <div className="flex items-center gap-2 text-sm">
            <Link to="/workflows" className="text-gray-500 hover:text-gray-700">
              Workflows
            </Link>
            <span className="text-gray-400">/</span>
            <span className="text-gray-900">AI Generator</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">Create Workflow with AI</h1>
        </div>

        <div className="card bg-yellow-50 border-yellow-200">
          <div className="flex items-start gap-3">
            <svg className="w-6 h-6 text-yellow-600 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <h3 className="font-medium text-yellow-800">AI Service Not Available</h3>
              <p className="mt-1 text-yellow-700">{aiStatus?.message}</p>
              <p className="mt-2 text-sm text-yellow-600">
                Contact your administrator to configure the OpenAI API key.
              </p>
            </div>
          </div>
        </div>

        <div className="mt-6">
          <Link to="/workflows/new" className="btn-primary">
            Create Workflow Manually
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm">
          <Link to="/workflows" className="text-gray-500 hover:text-gray-700">
            Workflows
          </Link>
          <span className="text-gray-400">/</span>
          <span className="text-gray-900">AI Generator</span>
        </div>
        <div className="flex items-center justify-between mt-2">
          <h1 className="text-2xl font-bold text-gray-900">Create Workflow with AI</h1>
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
            Powered by {aiStatus.model || 'GPT'}
          </span>
        </div>
        <p className="mt-1 text-gray-600">
          Describe what you want your workflow to do in plain English, and AI will generate it for you.
        </p>
      </div>

      {/* Step 1: Description Input */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Step 1: Describe Your Workflow
        </h2>

        <div className="space-y-4">
          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
              What should this workflow do?
            </label>
            <textarea
              id="description"
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Example: When a new customer signs up, send them a welcome email and add their details to a Google Sheet..."
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              disabled={generateMutation.isPending}
            />
            <p className="mt-1 text-sm text-gray-500">
              Be specific about triggers, actions, and conditions. Minimum 10 characters.
            </p>
          </div>

          {/* Example Prompts */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Try an example:</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_PROMPTS.map((example, idx) => (
                <button
                  key={idx}
                  onClick={() => handleExampleClick(example)}
                  className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-full transition-colors"
                >
                  {example.substring(0, 40)}...
                </button>
              ))}
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleGenerate}
              disabled={description.trim().length < 10 || generateMutation.isPending}
              className="btn-primary flex items-center gap-2"
            >
              {generateMutation.isPending ? (
                <>
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Generating...
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Generate Workflow
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Error Display */}
      {generateMutation.isError && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">
            {(generateMutation.error as Error)?.message || 'Failed to generate workflow'}
          </p>
        </div>
      )}

      {/* Step 2: Generated Workflow */}
      {generatedWorkflow && (
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Step 2: Review Generated Workflow
          </h2>

          {/* Workflow Info */}
          <div className="space-y-4">
            {/* Name Input */}
            <div>
              <label htmlFor="workflowName" className="block text-sm font-medium text-gray-700 mb-1">
                Workflow Name
              </label>
              <input
                type="text"
                id="workflowName"
                value={workflowName}
                onChange={(e) => setWorkflowName(e.target.value)}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              />
            </div>

            {/* Confidence Badge */}
            <div className="flex items-center gap-4">
              <span
                className={`text-sm font-medium px-3 py-1 rounded-full ${getConfidenceColor(generatedWorkflow.confidence)}`}
              >
                Confidence: {Math.round(generatedWorkflow.confidence * 100)}%
              </span>
              <span className="text-sm text-gray-500">
                {generatedWorkflow.nodes.length} nodes
              </span>
            </div>

            {/* Explanation */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-medium text-blue-900 mb-1">What this workflow does:</h4>
              <p className="text-blue-800">{generatedWorkflow.explanation}</p>
            </div>

            {/* Suggestions */}
            {generatedWorkflow.suggestions.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <h4 className="font-medium text-yellow-900 mb-2">Suggestions for improvement:</h4>
                <ul className="list-disc list-inside text-yellow-800 space-y-1">
                  {generatedWorkflow.suggestions.map((suggestion, idx) => (
                    <li key={idx}>{suggestion}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Validation Results */}
            {validation && (
              <div
                className={`border rounded-lg p-4 ${
                  validation.valid
                    ? 'bg-green-50 border-green-200'
                    : 'bg-red-50 border-red-200'
                }`}
              >
                <h4
                  className={`font-medium mb-2 ${
                    validation.valid ? 'text-green-900' : 'text-red-900'
                  }`}
                >
                  {validation.valid ? 'Validation Passed' : 'Validation Issues'}
                </h4>
                {validation.errors.length > 0 && (
                  <ul className="list-disc list-inside text-red-800 space-y-1 mb-2">
                    {validation.errors.map((error, idx) => (
                      <li key={idx}>{error}</li>
                    ))}
                  </ul>
                )}
                {validation.warnings.length > 0 && (
                  <ul className="list-disc list-inside text-yellow-700 space-y-1">
                    {validation.warnings.map((warning, idx) => (
                      <li key={idx}>{warning}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {/* JSON Editor Toggle */}
            <div>
              <button
                onClick={() => setShowJsonEditor(!showJsonEditor)}
                className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
              >
                <svg
                  className={`h-4 w-4 transition-transform ${showJsonEditor ? 'rotate-90' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                {showJsonEditor ? 'Hide' : 'Show'} JSON Editor
              </button>
            </div>

            {/* JSON Editor */}
            {showJsonEditor && (
              <div>
                <textarea
                  rows={15}
                  value={editedJson}
                  onChange={(e) => setEditedJson(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 font-mono text-sm"
                />
              </div>
            )}

            {/* Refinement Input */}
            <div className="border-t pt-4">
              <h4 className="font-medium text-gray-900 mb-2">Want to make changes?</h4>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={refinementFeedback}
                  onChange={(e) => setRefinementFeedback(e.target.value)}
                  placeholder="E.g., Add error handling, change the Slack channel, add a filter..."
                  className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  disabled={refineMutation.isPending}
                />
                <button
                  onClick={handleRefine}
                  disabled={!refinementFeedback.trim() || refineMutation.isPending}
                  className="btn-secondary flex items-center gap-2"
                >
                  {refineMutation.isPending ? (
                    <>
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Refining...
                    </>
                  ) : (
                    'Refine'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Save */}
      {generatedWorkflow && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Step 3: Save Your Workflow
          </h2>

          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-600">
              {validation?.valid ? (
                <span className="text-green-600 flex items-center gap-1">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Ready to save
                </span>
              ) : (
                <span className="text-yellow-600 flex items-center gap-1">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  Review validation warnings before saving
                </span>
              )}
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setGeneratedWorkflow(null);
                  setValidation(null);
                  setDescription('');
                }}
                className="btn-secondary"
              >
                Start Over
              </button>
              <button
                onClick={handleSave}
                disabled={saveMutation.isPending}
                className="btn-primary flex items-center gap-2"
              >
                {saveMutation.isPending ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Saving...
                  </>
                ) : (
                  <>
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Save Workflow
                  </>
                )}
              </button>
            </div>
          </div>

          {saveMutation.isError && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800">
                {(saveMutation.error as Error)?.message || 'Failed to save workflow'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
