/**
 * Root Application Component
 *
 * WHAT: Main application component with routing and providers.
 *
 * WHY: Central component that sets up:
 * - React Router for navigation
 * - Auth state initialization
 * - Global providers (React Query, etc.)
 * - Route protection
 *
 * HOW: Uses React Router v6 with layout routes and auth guards.
 */

import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './store';

// Layout components (to be created)
import MainLayout from './components/layout/MainLayout';

// Page components
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';
import ForgotPassword from './pages/auth/ForgotPassword';
import Dashboard from './pages/dashboard/Dashboard';
import OrganizationSettings from './pages/settings/OrganizationSettings';
import NotFound from './pages/NotFound';

// Project pages
import { ProjectsPage, ProjectDetailPage, ProjectFormPage } from './pages/projects';

// Proposal pages
import { ProposalsPage, ProposalDetailPage, ProposalFormPage } from './pages/proposals';

// Onboarding pages
import { ClientOnboardingPage } from './pages/onboarding';

// Invoice pages
import { InvoicesPage, InvoiceDetailPage } from './pages/invoices';

// Workflow pages
import {
  WorkflowsPage,
  WorkflowDetailPage,
  WorkflowFormPage,
  TemplatesPage,
  EnvironmentsPage,
} from './pages/workflows';

/**
 * React Query client
 *
 * WHY: Configured with sensible defaults for API caching
 * and error handling.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

/**
 * Protected Route Component
 *
 * WHAT: Wrapper for routes requiring authentication.
 *
 * WHY: Redirects unauthenticated users to login.
 *
 * HOW: Checks auth state and renders children or redirects.
 */
function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

/**
 * Public Route Component
 *
 * WHAT: Wrapper for routes that should redirect authenticated users.
 *
 * WHY: Prevents authenticated users from accessing login/register pages.
 *
 * HOW: Checks auth state and redirects to dashboard if logged in.
 */
function PublicRoute() {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}

/**
 * App Component
 *
 * WHAT: Root component setting up providers and routes.
 *
 * WHY: Single entry point for the application.
 *
 * HOW: Wraps app in providers and defines route structure.
 */
function App() {
  const loadUser = useAuthStore((state) => state.loadUser);

  /**
   * Load user on app initialization
   *
   * WHY: Restore session if user has valid token.
   */
  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public routes (redirect if authenticated) */}
          <Route element={<PublicRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
          </Route>

          {/* Protected routes (require authentication) */}
          <Route element={<ProtectedRoute />}>
            <Route element={<MainLayout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/settings" element={<OrganizationSettings />} />

              {/* Project routes */}
              <Route path="/projects" element={<ProjectsPage />} />
              <Route path="/projects/new" element={<ProjectFormPage />} />
              <Route path="/projects/:id" element={<ProjectDetailPage />} />
              <Route path="/projects/:id/edit" element={<ProjectFormPage />} />

              {/* Proposal routes */}
              <Route path="/proposals" element={<ProposalsPage />} />
              <Route path="/proposals/new" element={<ProposalFormPage />} />
              <Route path="/proposals/:id" element={<ProposalDetailPage />} />
              <Route path="/proposals/:id/edit" element={<ProposalFormPage />} />
              <Route path="/proposals/:id/revise" element={<ProposalFormPage />} />

              {/* Onboarding routes */}
              <Route path="/onboarding" element={<ClientOnboardingPage />} />

              {/* Invoice routes */}
              <Route path="/invoices" element={<InvoicesPage />} />
              <Route path="/invoices/:id" element={<InvoiceDetailPage />} />

              {/* Workflow routes */}
              <Route path="/workflows" element={<WorkflowsPage />} />
              <Route path="/workflows/new" element={<WorkflowFormPage />} />
              <Route path="/workflows/templates" element={<TemplatesPage />} />
              <Route path="/workflows/environment" element={<EnvironmentsPage />} />
              <Route path="/workflows/:id" element={<WorkflowDetailPage />} />
              <Route path="/workflows/:id/edit" element={<WorkflowFormPage />} />

              {/* Future routes */}
              {/* <Route path="/tickets" element={<TicketList />} /> */}
            </Route>
          </Route>

          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* 404 Not Found */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
