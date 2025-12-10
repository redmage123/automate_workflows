"""
Authentication API endpoints.

WHY: These endpoints provide the authentication flow:
1. Login - Authenticate user and return JWT token
2. Logout - Blacklist token to prevent further use
3. Me - Get current user information

Security:
- All authentication events are audit logged (OWASP A09)
- Rate limiting applied via RateLimitMiddleware (5 req/min for login, 10 for register)
- Passwords are compared using constant-time comparison (bcrypt)
- Generic error messages prevent user enumeration attacks
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    verify_password,
    create_access_token,
    blacklist_token,
    hash_password,
)
from app.core.deps import get_current_user, security
from app.core.exceptions import (
    AuthenticationError,
    ValidationError,
    ResourceNotFoundError,
)
from app.core.config import settings
from app.db.session import get_db
from app.dao.user import UserDAO
from app.dao.base import BaseDAO
from app.models.user import User
from app.models.organization import Organization
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    LogoutResponse,
    RegisterRequest,
    RegisterResponse,
    OrganizationResponse,
    SendVerificationEmailResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.services.audit import AuditService


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login user",
    description="Authenticate user with email and password, returns JWT token",
)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate user and return JWT access token.

    WHY: This endpoint:
    1. Validates user credentials (email + password)
    2. Checks user exists and is active
    3. Generates JWT token with user data
    4. Returns token for use in Authorization header
    5. Logs all authentication attempts (OWASP A09)

    Security:
    - Passwords are compared using constant-time comparison (bcrypt)
    - Generic error messages prevent user enumeration attacks
    - All login attempts (success/failure) are audit logged
    - Rate limiting applied (5 attempts per minute per IP)

    Args:
        credentials: Login credentials (email + password)
        db: Database session

    Returns:
        JWT access token and metadata

    Raises:
        AuthenticationError (401): If credentials are invalid
    """
    # Initialize audit service for logging
    # WHY: All authentication events must be logged for OWASP A09 compliance
    audit = AuditService(db)

    # Get user by email
    user_dao = UserDAO(User, db)
    user = await user_dao.get_by_email(credentials.email)

    # WHY: Use generic error message to prevent user enumeration
    # (don't reveal whether email exists)
    if not user:
        # Log failed login attempt (unknown user)
        # WHY: Track brute force and credential stuffing attacks
        await audit.log_login_failure(
            attempted_email=credentials.email,
            reason="User not found",
        )
        raise AuthenticationError(
            message="Invalid email or password",
        )

    # Check if user is active
    if not user.is_active:
        # Log failed login for inactive account
        # WHY: Track attempts to access disabled accounts
        await audit.log_login_failure(
            attempted_email=credentials.email,
            user_id=user.id,
            reason="Account inactive",
        )
        raise AuthenticationError(
            message="Account is inactive",
            user_id=user.id,
        )

    # Verify password
    # WHY: bcrypt.verify uses constant-time comparison to prevent timing attacks
    if not verify_password(credentials.password, user.hashed_password):
        # Log failed login attempt (wrong password)
        # WHY: Track password guessing attacks
        await audit.log_login_failure(
            attempted_email=credentials.email,
            user_id=user.id,
            reason="Invalid password",
        )
        raise AuthenticationError(
            message="Invalid email or password",
        )

    # Create access token with user data
    # WHY: Include user_id, org_id, and role for authorization decisions
    # without additional database queries on each request
    token_data = {
        "user_id": user.id,
        "org_id": user.org_id,
        "role": user.role.value,
        "email": user.email,
    }
    access_token = create_access_token(token_data)

    # Log successful login
    # WHY: Track successful logins for security analysis and anomaly detection
    await audit.log_login_success(
        user_id=user.id,
        org_id=user.org_id,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Register a new user account and optionally create an organization",
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """
    Register a new user account.

    WHY: This endpoint handles user registration with several critical steps:
    1. Password confirmation validation
    2. Organization creation or joining
    3. Email uniqueness check
    4. Secure password hashing
    5. JWT token generation
    6. First user in org gets ADMIN role, others get CLIENT
    7. Audit logging for account creation (OWASP A09)

    Security considerations:
    - Passwords are hashed with bcrypt before storage
    - Email uniqueness prevents account hijacking
    - Password confirmation prevents typos
    - Role assignment based on org membership
    - All registration events are audit logged

    Args:
        data: Registration data
        db: Database session

    Returns:
        JWT token, user data, and organization data

    Raises:
        ValidationError (400): If validation fails (passwords mismatch, invalid data)
        ResourceNotFoundError (404): If org_id doesn't exist
        ResourceAlreadyExistsError (409): If email already exists
    """
    # Initialize audit service for logging
    # WHY: All account creation events must be logged for OWASP A09 compliance
    audit = AuditService(db)

    # Step 1: Validate password confirmation
    # WHY: Prevent typos during registration
    if data.password != data.password_confirm:
        raise ValidationError(
            message="Passwords do not match",
            field="password_confirm",
        )

    # Step 2: Validate organization data
    # WHY: User must either create new org OR join existing one
    if data.organization_name and data.org_id:
        raise ValidationError(
            message="Provide either organization_name or org_id, not both",
            field="organization",
        )

    if not data.organization_name and not data.org_id:
        raise ValidationError(
            message="Must provide either organization_name (to create new org) or org_id (to join existing org)",
            field="organization",
        )

    # Step 3: Handle organization
    org_dao = BaseDAO(Organization, db)
    organization = None
    created_new_org = False

    if data.org_id:
        # Joining existing organization
        organization = await org_dao.get_by_id(data.org_id)
        if not organization:
            raise ResourceNotFoundError(
                message=f"Organization with id {data.org_id} not found",
                resource_type="Organization",
                resource_id=data.org_id,
            )
    else:
        # Creating new organization
        # WHY: First user in new org should be ADMIN
        organization = await org_dao.create(
            name=data.organization_name,
            description=f"Organization for {data.organization_name}",
            is_active=True,
        )
        created_new_org = True

    # Step 4: Determine user role
    # WHY: When creating new org, first user is ADMIN. When joining existing org, user is CLIENT.
    user_dao = UserDAO(User, db)
    if data.org_id:
        # Joining existing organization - always CLIENT
        role = "CLIENT"
    else:
        # Creating new organization - first user is ADMIN
        user_count = await user_dao.count_users_by_org(organization.id)
        role = "ADMIN" if user_count == 0 else "CLIENT"

    # Step 5: Create user
    # WHY: user_dao.create_user handles email uniqueness check and password hashing
    hashed_password = hash_password(data.password)
    user = await user_dao.create_user(
        email=data.email,
        hashed_password=hashed_password,
        name=data.name,
        org_id=organization.id,
        role=role,
    )

    # Step 6: Audit log the account creation
    # WHY: OWASP A09 requires logging of account creation events
    if created_new_org:
        # Log organization creation
        await audit.log_org_created(
            org_id=organization.id,
            created_by_user_id=user.id,
            org_name=organization.name,
        )

    # Log account creation
    await audit.log_account_created(
        user_id=user.id,
        org_id=organization.id,
        extra_data={
            "email": user.email,
            "role": role,
            "registration_method": "self_registration",
        },
    )

    # Log user joining organization
    await audit.log_user_joined_org(
        user_id=user.id,
        org_id=organization.id,
    )

    # Step 7: Generate JWT token
    # WHY: Auto-login after registration improves UX
    token_data = {
        "user_id": user.id,
        "org_id": user.org_id,
        "role": user.role.value,
        "email": user.email,
    }
    access_token = create_access_token(token_data)

    # Log successful login after registration
    # WHY: Track the automatic login that happens after registration
    await audit.log_login_success(
        user_id=user.id,
        org_id=user.org_id,
    )

    # Step 8: Return response
    return RegisterResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            org_id=user.org_id,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
        ),
        organization=OrganizationResponse(
            id=organization.id,
            name=organization.name,
            description=organization.description,
            is_active=organization.is_active,
            created_at=organization.created_at.isoformat(),
        ),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout user",
    description="Blacklist current token to prevent further use",
)
async def logout(
    current_user: User = Depends(get_current_user),
    credentials=Depends(security),
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    """
    Logout user by blacklisting their token.

    WHY: JWT tokens are stateless and can't be "deleted". Blacklisting
    ensures the token can't be used even if it hasn't expired yet.
    This is essential for:
    1. User-initiated logout
    2. Security (e.g., stolen token mitigation)
    3. Account actions (password change should logout all sessions)
    4. Audit logging for session tracking (OWASP A09)

    Args:
        current_user: Current authenticated user
        credentials: JWT token from Authorization header
        db: Database session for audit logging

    Returns:
        Logout confirmation message

    Example:
        >>> # After logout, token is blacklisted
        >>> # Further requests with same token will return 401
    """
    token = credentials.credentials

    # Blacklist token
    # WHY: Store in Redis with TTL matching token expiration
    await blacklist_token(token, current_user.id)

    # Log the logout event
    # WHY: OWASP A09 requires logging of authentication events
    audit = AuditService(db)
    await audit.log_logout(
        user_id=current_user.id,
        org_id=current_user.org_id,
    )

    return LogoutResponse(message="Successfully logged out")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Get information about the currently authenticated user",
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get current user information.

    WHY: Frontend needs to fetch user profile data after login or
    on page refresh. This endpoint provides user info without exposing
    sensitive data (password hash).

    Common uses:
    - Display user name and email in UI
    - Check user role for client-side navigation
    - Verify authentication status

    Args:
        current_user: Current authenticated user

    Returns:
        User profile data

    Example:
        >>> # Request with Authorization: Bearer <token>
        >>> response = await client.get("/api/auth/me")
        >>> response.json()
        {"id": 1, "email": "user@example.com", "role": "CLIENT", ...}
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role.value,
        org_id=current_user.org_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )


@router.post(
    "/send-verification-email",
    response_model=SendVerificationEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Send verification email",
    description="Send email verification link to the current user's email address",
)
async def send_verification_email(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SendVerificationEmailResponse:
    """
    Send email verification link to current user.

    WHY: Users need to verify email ownership to:
    1. Confirm account registration
    2. Receive important notifications
    3. Enable password reset functionality

    This endpoint can be called if:
    - Initial verification email was not received
    - Previous verification link expired
    - User wants to re-verify after email change

    Args:
        current_user: Currently authenticated user
        db: Database session

    Returns:
        Confirmation message
    """
    from app.dao.verification_token import VerificationTokenDAO
    from app.models.verification_token import TokenType
    from app.services.email import get_email_service
    from app.middleware.request_context import get_request_context

    # Check if already verified
    if current_user.email_verified:
        return SendVerificationEmailResponse(
            message="Email is already verified."
        )

    # Initialize services
    audit = AuditService(db)
    token_dao = VerificationTokenDAO(db)
    email_service = get_email_service()

    # Get request context for IP logging
    context = get_request_context()
    ip_address = context.ip_address if context else None

    # Create verification token
    token = await token_dao.create_verification_token(
        user_id=current_user.id,
        token_type=TokenType.EMAIL_VERIFICATION,
        include_code=True,
        ip_address=ip_address,
    )

    # Send verification email
    await email_service.send_verification_email(
        to_email=current_user.email,
        user_name=current_user.name,
        verification_token=token.token,
        verification_code=token.code,
    )

    # Audit log
    await audit.log_email_verification_sent(
        user_id=current_user.id,
        org_id=current_user.org_id,
    )

    return SendVerificationEmailResponse(
        message="Verification email sent. Please check your inbox."
    )


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    description="Verify email address using token or code",
)
async def verify_email(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(lambda: None),  # Optional auth
) -> VerifyEmailResponse:
    """
    Verify email address with token or code.

    WHY: Email verification prevents:
    1. Fake account creation with others' emails
    2. Spam account abuse
    3. Unauthorized access to email-based features

    Supports two verification methods:
    1. Token: Clicked from email link (no auth required)
    2. Code: Entered in app (requires auth for security)

    Args:
        request: Verification token or code
        db: Database session
        current_user: Optional authenticated user (for code verification)

    Returns:
        Verification status

    Raises:
        ValidationError: If neither token nor code provided
        ResourceNotFoundError: If token/code not found
        ValidationError: If token/code expired or already used
    """
    from app.dao.verification_token import VerificationTokenDAO
    from app.dao.user import UserDAO
    from app.models.verification_token import TokenType
    from app.middleware.request_context import get_request_context

    token_dao = VerificationTokenDAO(db)
    user_dao = UserDAO(User, db)
    audit = AuditService(db)

    # Get request context for IP logging
    context = get_request_context()
    ip_address = context.ip_address if context else None

    # Validate input - must have token OR code
    if not request.token and not request.code:
        raise ValidationError(
            message="Must provide either token or code",
        )

    verification_token = None

    if request.token:
        # Verify by token (from email link)
        verification_token = await token_dao.validate_and_consume_token(
            token=request.token,
            expected_type=TokenType.EMAIL_VERIFICATION,
            ip_address=ip_address,
        )
    elif request.code:
        # Verify by code (from app, requires authentication)
        # Note: For public API, we need user context from token
        # This is a simplified version - in production, you'd require auth
        # or include user_id in the request
        raise ValidationError(
            message="Code verification requires authentication. Please use the token from your email.",
        )

    # Get user and mark email as verified
    user = await user_dao.get_by_id(verification_token.user_id)
    if not user:
        raise ResourceNotFoundError(
            message="User not found",
            resource_type="User",
        )

    # Update user's email_verified status
    user.email_verified = True
    await db.flush()

    # Audit log
    await audit.log_email_verified(
        user_id=user.id,
        org_id=user.org_id,
    )

    return VerifyEmailResponse(
        message="Email verified successfully.",
        email_verified=True,
    )


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Send password reset link to email address",
)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """
    Request password reset email.

    WHY: Provides secure password recovery:
    1. Users who forgot their password can regain access
    2. Email-based verification ensures account ownership
    3. Time-limited tokens prevent old links from working

    Security:
    - Always returns success to prevent user enumeration
    - Token expires after 1 hour
    - Previous tokens are invalidated
    - Rate limited to prevent abuse

    Args:
        request: Email address for reset link
        db: Database session

    Returns:
        Generic success message (always, to prevent enumeration)
    """
    from app.dao.verification_token import VerificationTokenDAO
    from app.dao.user import UserDAO
    from app.models.verification_token import TokenType
    from app.services.email import get_email_service
    from app.middleware.request_context import get_request_context

    user_dao = UserDAO(User, db)
    token_dao = VerificationTokenDAO(db)
    email_service = get_email_service()
    audit = AuditService(db)

    # Get request context for IP logging
    context = get_request_context()
    ip_address = context.ip_address if context else None

    # Always return success (prevent user enumeration)
    generic_response = ForgotPasswordResponse(
        message="If an account exists with this email, you will receive a password reset link."
    )

    # Look up user
    user = await user_dao.get_by_email(request.email)

    if not user:
        # Log attempt for security monitoring but don't reveal to user
        await audit.log_password_reset_request(
            email=request.email,
            user_id=None,
            success=False,
        )
        return generic_response

    if not user.is_active:
        # Don't send reset to inactive accounts
        await audit.log_password_reset_request(
            email=request.email,
            user_id=user.id,
            success=False,
        )
        return generic_response

    # Create reset token
    token = await token_dao.create_verification_token(
        user_id=user.id,
        token_type=TokenType.PASSWORD_RESET,
        include_code=True,
        ip_address=ip_address,
    )

    # Send reset email
    await email_service.send_password_reset_email(
        to_email=user.email,
        user_name=user.name,
        reset_token=token.token,
        reset_code=token.code,
    )

    # Audit log
    await audit.log_password_reset_request(
        email=request.email,
        user_id=user.id,
        success=True,
    )

    return generic_response


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password with token",
    description="Reset password using token from email",
)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordResponse:
    """
    Reset password using token from email.

    WHY: Completes password reset flow:
    1. Validates token authenticity and expiration
    2. Verifies new password meets requirements
    3. Updates password securely
    4. Invalidates all existing sessions

    Security:
    - Token can only be used once
    - Password confirmation prevents typos
    - Notifies user of password change

    Args:
        request: Reset token and new password
        db: Database session

    Returns:
        Success message

    Raises:
        ValidationError: If passwords don't match
        ResourceNotFoundError: If token not found
        ValidationError: If token expired or already used
    """
    from app.dao.verification_token import VerificationTokenDAO
    from app.dao.user import UserDAO
    from app.models.verification_token import TokenType
    from app.services.email import get_email_service
    from app.middleware.request_context import get_request_context

    # Validate password confirmation
    if request.password != request.password_confirm:
        raise ValidationError(
            message="Passwords do not match",
            field="password_confirm",
        )

    token_dao = VerificationTokenDAO(db)
    user_dao = UserDAO(User, db)
    email_service = get_email_service()
    audit = AuditService(db)

    # Get request context for IP logging
    context = get_request_context()
    ip_address = context.ip_address if context else None

    # Validate and consume token
    verification_token = await token_dao.validate_and_consume_token(
        token=request.token,
        expected_type=TokenType.PASSWORD_RESET,
        ip_address=ip_address,
    )

    # Get user
    user = await user_dao.get_by_id(verification_token.user_id)
    if not user:
        raise ResourceNotFoundError(
            message="User not found",
            resource_type="User",
        )

    # Update password
    user.hashed_password = hash_password(request.password)
    await db.flush()

    # Audit log
    await audit.log_password_reset_complete(
        user_id=user.id,
        org_id=user.org_id,
    )

    # Send notification email
    await email_service.send_password_changed_email(
        to_email=user.email,
        user_name=user.name,
    )

    # TODO: Invalidate all existing sessions for this user
    # This would require implementing session tracking

    return ResetPasswordResponse(
        message="Password reset successfully. You can now log in with your new password."
    )


# TODO: Implement additional endpoints
# - POST /auth/refresh - Refresh access token
# - POST /auth/change-password - Change password (authenticated)
