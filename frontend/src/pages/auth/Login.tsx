/**
 * Login Page Component
 *
 * WHAT: User authentication form for logging into the application.
 *
 * WHY: Entry point for returning users to access their account.
 *
 * HOW: Form with email/password fields using react-hook-form and zod
 * validation. Uses zustand auth store for login action.
 */

import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAuthStore } from '../../store';
import { loginSchema, type LoginFormData } from '../../utils/validation';
import { FormField, Input, PasswordInput, FormError, SubmitButton } from '../../components/forms';

function Login() {
  const navigate = useNavigate();
  const { login, isLoading, error, setError } = useAuthStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setError(null);

    try {
      await login(data);
      navigate('/dashboard');
    } catch {
      // Error is handled by the store
    }
  };

  return (
    <div className="flex min-h-screen flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h1 className="text-center text-3xl font-bold text-primary-600">
          Automation Platform
        </h1>
        <h2 className="mt-6 text-center text-2xl font-semibold text-gray-900">
          Sign in to your account
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          Or{' '}
          <Link
            to="/register"
            className="font-medium text-primary-600 hover:text-primary-500"
          >
            create a new account
          </Link>
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white px-4 py-8 shadow sm:rounded-lg sm:px-10">
          <form className="space-y-6" onSubmit={handleSubmit(onSubmit)}>
            <FormError error={error} />

            <FormField
              label="Email address"
              name="email"
              required
              error={errors.email}
            >
              <Input
                id="email"
                type="email"
                autoComplete="email"
                error={!!errors.email}
                errorId="email-error"
                {...register('email')}
              />
            </FormField>

            <FormField
              label="Password"
              name="password"
              required
              error={errors.password}
            >
              <PasswordInput
                id="password"
                autoComplete="current-password"
                error={!!errors.password}
                errorId="password-error"
                {...register('password')}
              />
            </FormField>

            <div className="flex items-center justify-between">
              <div className="text-sm">
                <Link
                  to="/forgot-password"
                  className="font-medium text-primary-600 hover:text-primary-500"
                >
                  Forgot your password?
                </Link>
              </div>
            </div>

            <SubmitButton
              isLoading={isLoading}
              loadingText="Signing in..."
              fullWidth
            >
              Sign in
            </SubmitButton>
          </form>
        </div>
      </div>
    </div>
  );
}

export default Login;
