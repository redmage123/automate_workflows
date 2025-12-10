"""
Authentication API endpoints.

WHY: These endpoints provide the authentication flow:
1. Login - Authenticate user and return JWT token
2. Logout - Blacklist token to prevent further use
3. Me - Get current user information

Security:
- All authentication events are audit logged (OWASP A09)
- Rate limiting should be applied (TODO: implement rate limiting)
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
    - Rate limiting should be applied (TODO: implement rate limiting)

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


# TODO: Implement additional endpoints
# - POST /auth/register - User registration
# - POST /auth/refresh - Refresh access token
# - POST /auth/forgot-password - Password reset request
# - POST /auth/reset-password - Password reset with token
# - POST /auth/change-password - Change password (authenticated)
# - GET /auth/verify-email - Email verification
