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

// Page components (to be created)
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';
import ForgotPassword from './pages/auth/ForgotPassword';
import Dashboard from './pages/dashboard/Dashboard';
import NotFound from './pages/NotFound';

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
              {/* Add more protected routes here */}
              {/* <Route path="/projects" element={<ProjectList />} /> */}
              {/* <Route path="/projects/:id" element={<ProjectDetail />} /> */}
              {/* <Route path="/proposals" element={<ProposalList />} /> */}
              {/* <Route path="/invoices" element={<InvoiceList />} /> */}
              {/* <Route path="/workflows" element={<WorkflowList />} /> */}
              {/* <Route path="/tickets" element={<TicketList />} /> */}
              {/* <Route path="/settings" element={<Settings />} /> */}
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
