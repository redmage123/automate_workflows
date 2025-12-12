/**
 * Register Page Component
 *
 * WHAT: User registration form for creating new accounts.
 *
 * WHY: Self-service onboarding for new clients with organization creation.
 *
 * HOW: Form with email, password, and organization name fields using
 * react-hook-form and zod validation. Creates both user and organization
 * in a single transaction.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAuthStore } from '../../store';
import { registerSchema, type RegisterFormData } from '../../utils/validation';
import { FormField, Input, PasswordInput, FormError, SubmitButton } from '../../components/forms';

function Register() {
  const { register: registerUser, isLoading, error, setError } = useAuthStore();
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      name: '',
      organization_name: '',
      email: '',
      password: '',
      confirmPassword: '',
    },
  });

  const onSubmit = async (data: RegisterFormData) => {
    setError(null);

    try {
      await registerUser({
        name: data.name,
        email: data.email,
        password: data.password,
        password_confirm: data.confirmPassword,
        organization_name: data.organization_name,
      });
      setSuccess(true);
    } catch {
      // Error is handled by the store
    }
  };

  if (success) {
    return (
      <div className="flex min-h-screen flex-col justify-center py-12 sm:px-6 lg:px-8">
        <div className="sm:mx-auto sm:w-full sm:max-w-md">
          <div className="bg-white px-4 py-8 shadow sm:rounded-lg sm:px-10">
            <div className="text-center">
              <svg
                className="mx-auto h-12 w-12 text-green-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <h2 className="mt-4 text-2xl font-semibold text-gray-900">
                Registration successful!
              </h2>
              <p className="mt-2 text-gray-600">
                Please check your email to verify your account.
              </p>
              <div className="mt-6">
                <Link to="/login" className="btn-primary inline-block">
                  Go to login
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h1 className="text-center text-3xl font-bold text-primary-600">
          Automation Platform
        </h1>
        <h2 className="mt-6 text-center text-2xl font-semibold text-gray-900">
          Create your account
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          Already have an account?{' '}
          <Link
            to="/login"
            className="font-medium text-primary-600 hover:text-primary-500"
          >
            Sign in
          </Link>
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white px-4 py-8 shadow sm:rounded-lg sm:px-10">
          <form className="space-y-6" onSubmit={handleSubmit(onSubmit)}>
            <FormError error={error} />

            <FormField
              label="Full name"
              name="name"
              required
              error={errors.name}
            >
              <Input
                id="name"
                type="text"
                autoComplete="name"
                placeholder="John Doe"
                error={!!errors.name}
                errorId="name-error"
                {...register('name')}
              />
            </FormField>

            <FormField
              label="Organization name"
              name="organization_name"
              required
              error={errors.organization_name}
            >
              <Input
                id="organization_name"
                type="text"
                placeholder="Your company name"
                error={!!errors.organization_name}
                errorId="organization_name-error"
                {...register('organization_name')}
              />
            </FormField>

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
              helpText="Must be at least 8 characters with uppercase, lowercase, and number"
            >
              <PasswordInput
                id="password"
                autoComplete="new-password"
                error={!!errors.password}
                errorId="password-error"
                {...register('password')}
              />
            </FormField>

            <FormField
              label="Confirm password"
              name="confirmPassword"
              required
              error={errors.confirmPassword}
            >
              <PasswordInput
                id="confirmPassword"
                autoComplete="new-password"
                error={!!errors.confirmPassword}
                errorId="confirmPassword-error"
                {...register('confirmPassword')}
              />
            </FormField>

            <SubmitButton
              isLoading={isLoading}
              loadingText="Creating account..."
              fullWidth
            >
              Create account
            </SubmitButton>

            <p className="text-center text-xs text-gray-500">
              By creating an account, you agree to our{' '}
              <a href="#" className="text-primary-600 hover:text-primary-500">
                Terms of Service
              </a>{' '}
              and{' '}
              <a href="#" className="text-primary-600 hover:text-primary-500">
                Privacy Policy
              </a>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}

export default Register;
