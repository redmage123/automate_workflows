# ADR-009: OAuth, Subscriptions & Polish Sprint

## Status
Accepted

## Context

With the MVP complete (474 points across 8 sprints), Sprint 9 focuses on three parallel tracks to enhance the platform:

1. **OAuth Integration (AUTH-010)**: Users expect social login options. Google OAuth is the most requested.
2. **Subscription Management (PAY-010)**: Current payment flow is one-time. Need recurring billing for SaaS model.
3. **Polish (POLISH-004, POLISH-005)**: Form validation UX and responsive design need refinement.

### Business Requirements

1. **Google OAuth (AUTH-010)**
   - "Sign in with Google" button on login/register pages
   - Link existing accounts to Google
   - Auto-create organization for new OAuth users
   - Maintain existing email/password login option

2. **Stripe Subscriptions (PAY-010)**
   - Subscription plans (Free, Pro, Enterprise)
   - Billing portal for customers
   - Usage-based pricing option
   - Webhook handling for subscription events
   - Grace period for failed payments

3. **Form Validation (POLISH-004)**
   - Real-time validation feedback
   - Inline error messages below fields
   - Consistent error styling across all forms
   - Accessibility improvements (ARIA)

4. **Responsive Design (POLISH-005)**
   - Mobile-first audit
   - Sidebar collapse on mobile
   - Table horizontal scroll
   - Form stacking on small screens
   - Touch-friendly tap targets

## Decision

### 1. Google OAuth with `authlib`

**Choice**: Use `authlib` library for OAuth 2.0 implementation

**Why**:
- Well-maintained, security-audited library
- Supports OAuth 2.0 and OpenID Connect
- Easy to extend for other providers (GitHub, Microsoft)
- Async support with httpx

**Flow**:
```
1. User clicks "Sign in with Google"
2. Redirect to Google OAuth consent screen
3. Google redirects back with authorization code
4. Backend exchanges code for tokens
5. Fetch user info from Google
6. Create/link user account
7. Issue JWT tokens
```

**Database Changes**:
```python
class OAuthAccount(Base):
    id: int
    user_id: int  # FK to users
    provider: str  # "google", "github", etc.
    provider_user_id: str  # Google's user ID
    email: str  # Email from provider
    access_token: str  # Encrypted
    refresh_token: str  # Encrypted, nullable
    expires_at: datetime
    created_at: datetime
```

### 2. Stripe Subscriptions

**Choice**: Stripe Billing with Customer Portal

**Why**:
- Already using Stripe for payments
- Customer Portal reduces UI work
- Handles proration, upgrades, downgrades
- Built-in dunning management

**Plans**:
```python
SUBSCRIPTION_PLANS = {
    "free": {
        "stripe_price_id": None,  # No charge
        "projects_limit": 3,
        "workflows_limit": 5,
        "users_limit": 2,
    },
    "pro": {
        "stripe_price_id": "price_xxx",
        "monthly_price": 49.00,
        "projects_limit": 20,
        "workflows_limit": 50,
        "users_limit": 10,
    },
    "enterprise": {
        "stripe_price_id": "price_yyy",
        "monthly_price": 199.00,
        "projects_limit": None,  # Unlimited
        "workflows_limit": None,
        "users_limit": None,
    },
}
```

**Database Changes**:
```python
class Subscription(Base):
    id: int
    org_id: int  # FK to organizations
    stripe_subscription_id: str
    stripe_price_id: str
    plan: str  # "free", "pro", "enterprise"
    status: str  # "active", "past_due", "canceled", "trialing"
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime
```

**Webhook Events**:
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`
- `invoice.paid`

### 3. Form Validation Improvements

**Choice**: Enhance React Hook Form with custom validation UI

**Approach**:
- Create reusable `FormField` component with error display
- Add `useFormValidation` hook for common patterns
- Implement debounced async validation (email uniqueness)
- ARIA attributes for screen readers

**Components**:
```typescript
// Reusable form field with validation
<FormField
  name="email"
  label="Email Address"
  type="email"
  required
  validation={{
    required: "Email is required",
    pattern: {
      value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
      message: "Invalid email format"
    }
  }}
  asyncValidation={checkEmailUnique}
/>
```

### 4. Responsive Design

**Choice**: Tailwind responsive utilities with mobile-first approach

**Breakpoints**:
- `sm`: 640px (large phones)
- `md`: 768px (tablets)
- `lg`: 1024px (laptops)
- `xl`: 1280px (desktops)

**Key Changes**:
- Sidebar: Full width drawer on mobile, fixed on desktop
- Tables: Horizontal scroll wrapper on mobile
- Forms: Stack labels above inputs on mobile
- Cards: Single column on mobile, grid on desktop
- Navigation: Bottom nav or hamburger menu on mobile

## Consequences

### Positive

1. **User Convenience**: OAuth reduces friction for new signups
2. **Recurring Revenue**: Subscriptions enable SaaS business model
3. **Better UX**: Validation feedback prevents form errors
4. **Mobile Users**: Responsive design reaches wider audience
5. **Extensibility**: OAuth architecture supports future providers

### Negative

1. **Complexity**: OAuth adds security surface area
2. **Dependency**: Reliance on Google availability
3. **Testing**: Subscription flows harder to test
4. **Migration**: Existing users need plan assignment

### Mitigations

1. **OAuth Security**: Use state parameter, validate tokens server-side
2. **Google Dependency**: Keep email/password as fallback
3. **Subscription Testing**: Stripe test mode, mock webhooks
4. **Migration**: Default existing users to "pro" plan

## Implementation Guide

### Phase 1: Google OAuth (AUTH-010)

1. Install `authlib` and `httpx`
2. Create `OAuthAccount` model and migration
3. Create `OAuthService` for Google integration
4. Add OAuth endpoints:
   - `GET /api/auth/oauth/google` - Initiate OAuth flow
   - `GET /api/auth/oauth/google/callback` - Handle callback
   - `POST /api/auth/oauth/link` - Link existing account
   - `DELETE /api/auth/oauth/unlink` - Unlink OAuth
5. Frontend: Add Google sign-in button
6. Frontend: Account settings to manage linked accounts
7. Unit and integration tests

### Phase 2: Stripe Subscriptions (PAY-010)

1. Create `Subscription` model and migration
2. Create `SubscriptionService` for Stripe Billing
3. Add subscription endpoints:
   - `GET /api/subscriptions/plans` - List available plans
   - `GET /api/subscriptions/current` - Get current subscription
   - `POST /api/subscriptions/checkout` - Create checkout session
   - `POST /api/subscriptions/portal` - Create billing portal session
   - `POST /api/subscriptions/cancel` - Cancel subscription
4. Add webhook handlers for subscription events
5. Implement usage limits based on plan
6. Frontend: Pricing page with plan comparison
7. Frontend: Billing settings page
8. Integration tests with Stripe test mode

### Phase 3: Form Validation (POLISH-004)

1. Create `FormField` component with error display
2. Create `useFormValidation` hook
3. Update all forms to use new components:
   - Login form
   - Register form
   - Forgot password form
   - Project form
   - Proposal form
   - Ticket form
   - Settings forms
4. Add async validation for email uniqueness
5. Accessibility audit with jest-axe
6. Unit tests for validation logic

### Phase 4: Responsive Design (POLISH-005)

1. Audit all pages on mobile viewport
2. Update MainLayout sidebar for mobile:
   - Hamburger menu button
   - Slide-out drawer
   - Overlay backdrop
3. Add table scroll wrappers
4. Stack form layouts on mobile
5. Update card grids for mobile
6. Test on real devices
7. Fix any overflow issues

## Testing Strategy

### OAuth Tests
- Mock Google OAuth responses
- Test account creation flow
- Test account linking/unlinking
- Test error handling (invalid tokens, etc.)

### Subscription Tests
- Use Stripe test mode
- Mock webhook events
- Test plan limits enforcement
- Test upgrade/downgrade flows

### Form Validation Tests
- Unit tests for validation rules
- Integration tests for async validation
- Accessibility tests with jest-axe

### Responsive Tests
- Viewport-based visual tests
- Touch interaction tests
- Overflow detection tests

## Security Considerations

1. **OAuth**: Validate state parameter, use PKCE, encrypt tokens
2. **Subscriptions**: Verify webhook signatures, validate plan access
3. **Forms**: Server-side validation always, sanitize inputs
4. **Responsive**: Ensure touch targets are 44x44px minimum

## Dependencies

- `authlib` - OAuth 2.0 library
- `httpx` - Async HTTP client (for OAuth)
- Stripe Billing (existing Stripe account)

## Migration Path

1. Deploy OAuth with feature flag disabled
2. Run migrations for OAuthAccount and Subscription tables
3. Enable OAuth sign-in
4. Create subscription plans in Stripe dashboard
5. Assign existing orgs to "pro" plan (free trial)
6. Enable subscription features
7. Monitor for issues

## References

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Authlib Documentation](https://docs.authlib.org/)
- [Stripe Billing Documentation](https://stripe.com/docs/billing)
- [Stripe Customer Portal](https://stripe.com/docs/billing/subscriptions/integrating-customer-portal)
- [WCAG Form Guidelines](https://www.w3.org/WAI/tutorials/forms/)
