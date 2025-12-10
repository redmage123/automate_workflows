# Authentication & Security Sub-Board

**Parent**: Master Kanban Board
**Sprint**: 1-2 (Foundation & Authentication)
**Focus**: OWASP compliance, JWT auth, RBAC, audit logging

---

## 🔴 Blocked

*None currently*

---

## 🟡 In Progress

### SEC-001: Custom Exception Hierarchy (2 points)
**Assigned**: Implementation Agent
**Priority**: P0

**Description**:
Create comprehensive custom exception hierarchy for the application, ensuring we NEVER use base Exception class.

**Architecture Review** (Architecture Agent):
- Exception hierarchy should mirror HTTP status codes
- Base AppException class with `status_code` and `to_dict()` method
- Domain-specific exceptions inheriting from base (Auth, Validation, Resource, External)
- Include contextual data for debugging without leaking sensitive info

**Security Review** (Cybersecurity Agent):
- Error messages must not expose stack traces in production
- No sensitive data (passwords, tokens) in exception messages
- Log full context server-side, return sanitized messages to client
- OWASP A04 (Insecure Design): Fail securely with proper error handling

**Test Plan** (Test Design Agent):
```python
# tests/unit/core/test_exceptions.py

def test_app_exception_to_dict():
    """Verify exception serializes to JSON without sensitive data"""
    exc = AppException(message="Test error", user_id=123, password="secret")
    result = exc.to_dict()

    assert result["message"] == "Test error"
    assert "user_id" in result["details"]
    assert "password" not in result["details"]  # Sensitive data excluded

def test_authentication_error_status_code():
    """Verify authentication errors return 401"""
    exc = AuthenticationError()
    assert exc.status_code == 401

def test_authorization_error_status_code():
    """Verify authorization errors return 403"""
    exc = AuthorizationError()
    assert exc.status_code == 403
```

**Implementation Checklist**:
- [ ] Create `app/core/exceptions.py`
- [ ] Implement base `AppException` class
- [ ] Create auth exceptions (AuthenticationError, AuthorizationError)
- [ ] Create validation exceptions (ValidationError, InputError)
- [ ] Create resource exceptions (ResourceNotFoundError, DuplicateError)
- [ ] Create external service exceptions (StripeError, N8nError, S3Error)
- [ ] Write unit tests (100% coverage)
- [ ] Document WHY each exception exists
- [ ] Add exception handler to FastAPI app
- [ ] Test error responses in API integration tests

**Acceptance Criteria**:
- [ ] All custom exceptions inherit from AppException
- [ ] HTTP status codes correctly mapped
- [ ] Exception serialization tested
- [ ] No base Exception usage in codebase
- [ ] Documentation explains exception hierarchy

---

## ⚪ Todo (Priority Order)

### SEC-002: JWT Authentication System (8 points)
**Assigned**: Security Agent + Implementation Agent
**Priority**: P0
**Dependencies**: SEC-001

**Description**:
Implement secure JWT-based authentication system with token generation, validation, and refresh.

**Architecture Review**:
- HS256 algorithm (symmetric) for simplicity in v1, RS256 (asymmetric) for v2
- 24-hour token expiration balances security and UX
- Include user_id, org_id, role in token payload for RBAC
- Refresh token strategy: Short-lived access token + long-lived refresh token

**Security Review** (OWASP Compliance):
- **A07 (Authentication Failures)**:
  - Secure secret (min 32 chars, random, env variable)
  - Short expiration (24h for access, 30d for refresh)
  - Token validation on every protected endpoint
  - No sensitive data in JWT payload (it's base64, not encrypted)
- Token should include `exp`, `iat`, `nbf` claims
- Implement token blacklist for logout (Redis)
- Rate limit login attempts (5 per minute per IP)

**Test Plan**:
```python
# tests/unit/core/test_auth.py

def test_create_access_token():
    """Test JWT token creation with correct claims"""
    data = {"user_id": 1, "org_id": 1, "role": "ADMIN"}
    token = create_access_token(data)

    decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert decoded["user_id"] == 1
    assert decoded["org_id"] == 1
    assert decoded["role"] == "ADMIN"
    assert "exp" in decoded

def test_verify_token_expired():
    """Test that expired tokens are rejected"""
    # Create token with past expiration
    data = {"user_id": 1, "exp": datetime.utcnow() - timedelta(hours=1)}
    token = jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(AuthenticationError, match="expired"):
        verify_token(token)

def test_verify_token_invalid_signature():
    """Test that tokens with wrong signature are rejected"""
    token = jwt.encode({"user_id": 1}, "wrong-secret", algorithm="HS256")

    with pytest.raises(AuthenticationError, match="invalid"):
        verify_token(token)
```

**Implementation Checklist**:
- [ ] Install python-jose[cryptography]
- [ ] Create `app/core/auth.py`
- [ ] Implement `create_access_token(data: dict) -> str`
- [ ] Implement `verify_token(token: str) -> dict`
- [ ] Implement `get_current_user` dependency
- [ ] Implement `require_admin` dependency
- [ ] Create token blacklist (Redis set)
- [ ] Implement logout (blacklist token)
- [ ] Write comprehensive tests (TDD)
- [ ] Document token structure and claims
- [ ] Add rate limiting on login endpoint

**Acceptance Criteria**:
- [ ] Tokens contain user_id, org_id, role
- [ ] Expired tokens rejected
- [ ] Invalid signature rejected
- [ ] Token blacklist functional
- [ ] Rate limiting prevents brute force
- [ ] 100% test coverage

---

### SEC-003: RBAC Middleware (5 points)
**Assigned**: Security Agent
**Priority**: P0
**Dependencies**: SEC-002

**Description**:
Implement Role-Based Access Control enforcing ADMIN vs CLIENT permissions.

**Security Review** (OWASP A01 - Broken Access Control):
- **Defense in Depth**: Authorization checked at multiple layers
  1. Route level (dependency injection)
  2. Service level (verify org ownership)
  3. DAO level (org-scoped queries)
- Never trust client-provided role information
- Role stored in JWT (verified via signature)
- Admin can cross organizations, Client cannot

**Test Plan**:
```python
# tests/integration/api/test_rbac.py

@pytest.mark.asyncio
async def test_admin_can_access_admin_endpoint(admin_client):
    """Test admin role can access admin-only endpoints"""
    response = await admin_client.get("/api/admin/users")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_client_cannot_access_admin_endpoint(client_client):
    """Test client role cannot access admin endpoints"""
    response = await client_client.get("/api/admin/users")
    assert response.status_code == 403
    assert "permission denied" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_client_cannot_access_other_org_project(client_client):
    """Test org-scoping prevents cross-org access"""
    # Create project in org 1
    other_org_project_id = await create_project(org_id=1)

    # Try to access from org 2
    response = await client_client.get(f"/api/projects/{other_org_project_id}")
    assert response.status_code == 404  # Not found (don't leak existence)
```

**Implementation Checklist**:
- [ ] Create `app/core/deps.py` for dependencies
- [ ] Implement `get_current_user(token: str) -> User`
- [ ] Implement `require_admin(user: User) -> User`
- [ ] Implement `get_current_org(user: User) -> Organization`
- [ ] Add RBAC decorator to admin routes
- [ ] Implement org-scoping in all DAOs
- [ ] Write integration tests for all role combinations
- [ ] Document RBAC architecture
- [ ] Add authorization audit logging

**Acceptance Criteria**:
- [ ] ADMIN can access all endpoints
- [ ] CLIENT limited to their org's data
- [ ] Cross-org access attempts blocked
- [ ] Authorization failures logged
- [ ] Tests cover all role/permission combos

---

### SEC-004: Org-Scoping Enforcement (5 points)
**Assigned**: Architecture Agent + Implementation Agent
**Priority**: P0
**Dependencies**: SEC-003, INF-003

**Description**:
Enforce multi-tenancy isolation by automatically scoping all database queries to user's organization.

**Architecture Review**:
- **Pattern**: Inject org_id into all DAO queries via dependency injection
- **Layer**: Enforcement at DAO level (not just service layer)
- **Fail-Safe**: Queries without org_id should fail (no cross-org leaks)
- **Performance**: Add indexes on org_id for all multi-tenant tables

**Security Review** (OWASP A01 - Broken Access Control):
- Most critical security control for multi-tenancy
- Test matrix: User from Org A tries to access resources from Org B
- Resource IDs should be UUIDs (harder to enumerate) - consider for v2
- Audit log must capture org_id for all operations

**Test Plan**:
```python
# tests/integration/dao/test_org_scoping.py

@pytest.mark.asyncio
async def test_dao_filters_by_org(db_session):
    """Test DAO automatically filters by org_id"""
    # Create projects in different orgs
    proj1 = await project_dao.create(org_id=1, title="Org 1 Project")
    proj2 = await project_dao.create(org_id=2, title="Org 2 Project")

    # Get projects for org 1
    org1_projects = await project_dao.get_by_org(org_id=1)

    assert len(org1_projects) == 1
    assert org1_projects[0].id == proj1.id
    assert proj2.id not in [p.id for p in org1_projects]

@pytest.mark.asyncio
async def test_cross_org_access_raises_error(db_session):
    """Test accessing resource from wrong org raises error"""
    proj = await project_dao.create(org_id=1, title="Test")

    with pytest.raises(ProjectNotFoundError):
        await project_dao.get_by_id_and_org(proj.id, org_id=2)
```

**Implementation Checklist**:
- [ ] Add `get_by_org()` method to all DAOs
- [ ] Add `get_by_id_and_org()` for single resource retrieval
- [ ] Update all DAO queries to include org_id filter
- [ ] Add org_id indexes to all multi-tenant tables
- [ ] Create migration for indexes
- [ ] Write tests for each DAO (org-scoping)
- [ ] Document org-scoping pattern
- [ ] Add org_id validation in services

**Acceptance Criteria**:
- [ ] All queries scoped to org_id
- [ ] Cross-org access attempts fail
- [ ] Performance acceptable with indexes
- [ ] Tests verify org isolation
- [ ] Documentation clear

---

### SEC-005: OWASP Security Headers (3 points)
**Assigned**: Security Agent
**Priority**: P0
**Dependencies**: None

**Description**:
Implement security headers to protect against common web vulnerabilities.

**Security Review** (OWASP A05 - Security Misconfiguration):
- **Headers to Implement**:
  - `Strict-Transport-Security`: Force HTTPS
  - `X-Content-Type-Options`: Prevent MIME sniffing
  - `X-Frame-Options`: Prevent clickjacking
  - `X-XSS-Protection`: Enable browser XSS filter
  - `Content-Security-Policy`: Restrict resource loading
  - `Referrer-Policy`: Control referrer information

**Test Plan**:
```python
# tests/integration/api/test_security_headers.py

@pytest.mark.asyncio
async def test_security_headers_present(client):
    """Verify all security headers are set"""
    response = await client.get("/")

    assert "Strict-Transport-Security" in response.headers
    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "X-XSS-Protection" in response.headers
```

**Implementation Checklist**:
- [ ] Create security headers middleware
- [ ] Add middleware to FastAPI app
- [ ] Configure CSP for frontend assets
- [ ] Test headers in all responses
- [ ] Document header purposes
- [ ] Verify headers with security scanner

**Acceptance Criteria**:
- [ ] All security headers present
- [ ] CSP configured correctly
- [ ] Headers tested automatically
- [ ] No security scanner warnings

---

### AUTH-001: User Model + DAO (3 points)
### AUTH-002: Organization Model + DAO (3 points)
### AUTH-003: Password Hashing (2 points)
### AUTH-004: JWT Token Generation (3 points)
### AUTH-005: Login Endpoint (5 points)
### AUTH-006: Session Validation Middleware (3 points)
### AUTH-007: Logout Endpoint (2 points)
### AUTH-008: Email Registration (8 points)
### AUDIT-001: Audit Log Model + DAO (3 points)
### AUDIT-002: Audit Logging Middleware (5 points)

*Additional items collapsed for brevity - see master board for full details*

---

## Definition of Done

A task is considered DONE when:
- [ ] **Tests written FIRST** (TDD)
- [ ] All tests passing (unit + integration)
- [ ] Code coverage >= 80%
- [ ] Security review completed (OWASP checklist)
- [ ] Accessibility review (if frontend)
- [ ] DAO pattern used (if database access)
- [ ] Custom exceptions (no base Exception)
- [ ] Comprehensive documentation (WHY included)
- [ ] Code review approved
- [ ] Merged to main branch

---

## Notes

### Security Best Practices
- Always validate JWT on protected endpoints
- Never trust client-provided org_id or role
- Log all authentication and authorization failures
- Use constant-time comparison for secrets
- Implement rate limiting on auth endpoints
- Review OWASP Top 10 for each feature

### Testing Strategy
- Unit tests: Fast, isolated, mock external dependencies
- Integration tests: Real database, test transactions
- E2E tests: Full auth flow (register → login → access resource → logout)
- Security tests: Attempt bypasses, injection, XSS
