/**
 * Workflow Templates Page
 *
 * WHAT: Displays library of reusable workflow templates.
 *
 * WHY: Provides a catalog of pre-built automation patterns:
 * - Quick template discovery by category
 * - Template details and default configurations
 * - One-click workflow creation from templates
 *
 * HOW: Fetches templates and groups by category for browsing.
 */

import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../../store';
import { getTemplates } from '../../services/workflows';
import type { WorkflowTemplate } from '../../types/workflow';

/**
 * Category display configuration
 *
 * WHY: Provides visual distinction for different template categories.
 */
const CATEGORY_CONFIG: Record<string, { label: string; bgColor: string; color: string }> = {
  onboarding: { label: 'Onboarding', bgColor: 'bg-blue-100', color: 'text-blue-700' },
  notification: { label: 'Notification', bgColor: 'bg-purple-100', color: 'text-purple-700' },
  integration: { label: 'Integration', bgColor: 'bg-green-100', color: 'text-green-700' },
  reporting: { label: 'Reporting', bgColor: 'bg-orange-100', color: 'text-orange-700' },
  automation: { label: 'Automation', bgColor: 'bg-indigo-100', color: 'text-indigo-700' },
  custom: { label: 'Custom', bgColor: 'bg-gray-100', color: 'text-gray-700' },
};

/**
 * Get category config with fallback
 */
function getCategoryConfig(category: string) {
  return CATEGORY_CONFIG[category] || CATEGORY_CONFIG.custom;
}

export default function TemplatesPage() {
  const navigate = useNavigate();
  const isAdmin = useAuthStore((state) => state.user?.role === 'ADMIN');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  /**
   * Fetch all templates
   *
   * WHY: Load complete template library for browsing.
   */
  const { data, isLoading, error } = useQuery({
    queryKey: ['workflow-templates-library'],
    queryFn: () => getTemplates({ skip: 0, limit: 100 }),
  });

  const templates = data?.items || [];

  /**
   * Extract unique categories from templates
   *
   * WHY: Build category filter options dynamically.
   */
  const categories = useMemo(() => {
    const cats = new Set(templates.map((t) => t.category));
    return Array.from(cats).sort();
  }, [templates]);

  /**
   * Filter templates by category and search query
   *
   * WHY: Allow users to narrow down template selection.
   */
  const filteredTemplates = useMemo(() => {
    return templates.filter((template) => {
      const matchesCategory = !selectedCategory || template.category === selectedCategory;
      const matchesSearch =
        !searchQuery ||
        template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        template.description?.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [templates, selectedCategory, searchQuery]);

  /**
   * Group templates by category for display
   *
   * WHY: Organize templates visually by type.
   */
  const groupedTemplates = useMemo(() => {
    if (selectedCategory) {
      return { [selectedCategory]: filteredTemplates };
    }
    const groups: Record<string, WorkflowTemplate[]> = {};
    filteredTemplates.forEach((template) => {
      if (!groups[template.category]) {
        groups[template.category] = [];
      }
      groups[template.category].push(template);
    });
    return groups;
  }, [filteredTemplates, selectedCategory]);

  /**
   * Handle template selection to create new workflow
   */
  const handleUseTemplate = (templateId: number) => {
    navigate(`/workflows/new?template_id=${templateId}`);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading templates...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">Error loading templates</h2>
        <p className="mt-2 text-gray-500">Could not load the template library.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflow Templates</h1>
          <p className="mt-1 text-gray-500">
            Browse pre-built automation templates to get started quickly.
          </p>
        </div>
        <div className="flex gap-3">
          <Link to="/workflows" className="btn-secondary">
            View Workflows
          </Link>
          {isAdmin && (
            <Link to="/workflows/new" className="btn-primary">
              Create Custom
            </Link>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-wrap items-center gap-4">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search templates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
          </div>

          {/* Category Filter */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-gray-500">Category:</span>
            <button
              onClick={() => setSelectedCategory(null)}
              className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                selectedCategory === null
                  ? 'bg-blue-100 text-blue-700 border-blue-300'
                  : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
              }`}
            >
              All
            </button>
            {categories.map((category) => {
              const config = getCategoryConfig(category);
              return (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                    selectedCategory === category
                      ? `${config.bgColor} ${config.color} border-current`
                      : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {config.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Templates Grid */}
      {filteredTemplates.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">No templates found matching your criteria.</p>
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="mt-2 text-blue-600 hover:underline"
            >
              Clear search
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(groupedTemplates).map(([category, categoryTemplates]) => (
            <div key={category}>
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {getCategoryConfig(category).label}
                <span className="ml-2 text-sm font-normal text-gray-500">
                  ({categoryTemplates.length})
                </span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {categoryTemplates.map((template) => (
                  <TemplateCard
                    key={template.id}
                    template={template}
                    onUse={() => handleUseTemplate(template.id)}
                    isAdmin={isAdmin}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Template Card Component
 *
 * WHAT: Displays individual template with actions.
 *
 * WHY: Provides at-a-glance template info and quick actions.
 *
 * HOW: Shows template details, config preview, and use button.
 */
interface TemplateCardProps {
  template: WorkflowTemplate;
  onUse: () => void;
  isAdmin: boolean;
}

function TemplateCard({ template, onUse, isAdmin }: TemplateCardProps) {
  const [showConfig, setShowConfig] = useState(false);
  const categoryConfig = getCategoryConfig(template.category);

  return (
    <div className="card hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">{template.name}</h3>
          <span
            className={`inline-block mt-1 px-2 py-0.5 text-xs font-medium rounded-full ${categoryConfig.bgColor} ${categoryConfig.color}`}
          >
            {categoryConfig.label}
          </span>
        </div>
        {!template.is_public && (
          <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">Private</span>
        )}
      </div>

      <p className="mt-3 text-sm text-gray-600 line-clamp-2">
        {template.description || 'No description available.'}
      </p>

      {/* Default Config Preview */}
      {template.default_config && Object.keys(template.default_config).length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setShowConfig(!showConfig)}
            className="text-xs text-blue-600 hover:underline"
          >
            {showConfig ? 'Hide' : 'Show'} default configuration
          </button>
          {showConfig && (
            <pre className="mt-2 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-32">
              {JSON.stringify(template.default_config, null, 2)}
            </pre>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex items-center justify-between">
        <span className="text-xs text-gray-400">v{template.version}</span>
        {isAdmin && (
          <button onClick={onUse} className="btn-primary text-sm px-4 py-1.5">
            Use Template
          </button>
        )}
      </div>
    </div>
  );
}
