# Test Infrastructure

Comprehensive testing infrastructure for the Automation Services Platform backend.

## Test Structure

```
tests/
├── conftest.py              # Pytest configuration and shared fixtures
├── factories.py             # Test data factories for creating test objects
├── unit/                    # Unit tests (fast, isolated)
│   ├── core/               # Core functionality tests
│   ├── dao/                # Data access object tests
│   └── middleware/         # Middleware tests
├── integration/            # Integration tests (database, services)
│   └── api/               # API endpoint integration tests
└── e2e/                   # End-to-end tests (full user workflows)
```

## Test Types

### Unit Tests (`tests/unit/`)

**Purpose**: Test individual functions, classes, and methods in isolation.

**Characteristics**:
- Fast execution (< 1 second per test)
- No external dependencies (database, Redis, APIs)
- Mock external services
- High coverage of edge cases

**When to write**: For all business logic, utilities, and helper functions.

**Example**:
```python
def test_hash_password():
    """Test password hashing function."""
    password = "SecurePassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
```

### Integration Tests (`tests/integration/`)

**Purpose**: Test multiple components working together.

**Characteristics**:
- Uses real database (SQLite in-memory for tests)
- Tests full request-response cycle
- Verifies database operations
- Tests authentication flows

**When to write**: For API endpoints, DAO operations, and service interactions.

**Example**:
```python
async def test_login_flow(client, db_session):
    """Test complete login flow."""
    # Create user
    user = await UserFactory.create(db_session, email="test@example.com")

    # Login
    response = await client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "Password123!"
    })

    assert response.status_code == 200
    assert "access_token" in response.json()
```

### E2E Tests (`tests/e2e/`)

**Purpose**: Test complete user workflows from start to finish.

**Characteristics**:
- Tests real user scenarios
- May involve external services
- Slower execution
- Fewer in number (focus on critical paths)

**When to write**: For critical user journeys (registration → project creation → payment).

## Test Fixtures

### Database Fixtures

#### `db_engine`
Creates a fresh SQLite in-memory database for each test function.

```python
async def test_with_database(db_engine):
    """Test uses database engine."""
    pass
```

#### `db_session`
Provides a database session that is automatically rolled back after the test.

```python
async def test_with_session(db_session):
    """Test uses database session."""
    user = User(email="test@example.com")
    db_session.add(user)
    await db_session.commit()
```

#### `client`
HTTP client for making API requests in tests.

```python
async def test_api_endpoint(client):
    """Test API endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
```

## Test Factories

Factories provide a consistent way to create test data.

### OrganizationFactory

```python
from tests.factories import OrganizationFactory

org = await OrganizationFactory.create(
    session,
    name="Acme Corp",
    description="Test organization"
)
```

### UserFactory

```python
from tests.factories import UserFactory

# Create regular user
user = await UserFactory.create(
    session,
    email="user@example.com",
    password="Password123!"
)

# Create admin
admin = await UserFactory.create_admin(
    session,
    email="admin@example.com"
)

# Create client
client = await UserFactory.create_client(
    session,
    email="client@example.com"
)
```

### TestDataBuilder

For complex scenarios with multiple related objects:

```python
from tests.factories import TestDataBuilder

builder = TestDataBuilder(session)
await builder.with_multi_tenant_setup()

org1 = builder.get_organization(0)  # First organization
user1 = builder.get_user(0)  # First user (admin of org1)
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Type

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# E2E tests only
pytest tests/e2e/
```

### Run with Coverage

```bash
# Generate coverage report
pytest --cov=app --cov-report=html

# View report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Run Specific Test File

```bash
pytest tests/unit/core/test_auth.py -v
```

### Run Specific Test Function

```bash
pytest tests/unit/core/test_auth.py::test_hash_password -v
```

### Run Tests Matching Pattern

```bash
pytest -k "auth" -v  # Run all tests with "auth" in name
```

## Test Markers

Markers categorize tests for selective execution.

```python
@pytest.mark.unit
def test_something():
    """Unit test."""
    pass

@pytest.mark.integration
async def test_api():
    """Integration test."""
    pass

@pytest.mark.slow
async def test_slow_operation():
    """Slow test."""
    pass
```

Run tests by marker:
```bash
pytest -m unit  # Run only unit tests
pytest -m "not slow"  # Skip slow tests
```

## Coverage Requirements

- **Minimum**: 80% overall coverage
- **Critical modules**: 90%+ coverage
  - `app/core/auth.py`
  - `app/core/deps.py`
  - `app/dao/*.py`
  - `app/api/*.py`

Check coverage:
```bash
pytest --cov=app --cov-report=term-missing
```

## Best Practices

### 1. Test Organization
- One test file per module
- Group related tests in classes
- Use descriptive test names

```python
class TestUserAuthentication:
    """Tests for user authentication."""

    async def test_login_with_valid_credentials(self):
        """Test login succeeds with correct password."""
        pass

    async def test_login_with_invalid_credentials(self):
        """Test login fails with incorrect password."""
        pass
```

### 2. Test Independence
- Each test should be completely independent
- Use fixtures for setup/teardown
- Don't rely on test execution order

### 3. Clear Assertions
```python
# ✅ Good
assert user.email == "test@example.com"
assert user.is_active is True

# ❌ Bad
assert user.email  # What are we testing?
```

### 4. Test Edge Cases
- Empty inputs
- Null values
- Maximum lengths
- Invalid formats
- Boundary conditions

### 5. Security Testing
- Test authentication failures
- Test authorization boundaries
- Test input validation
- Test SQL injection prevention
- Test XSS prevention

### 6. Use WHY Comments
Explain the reasoning behind tests:

```python
async def test_email_case_insensitive(self):
    """
    Test that email lookup is case-insensitive.

    WHY: Users may enter their email in different cases.
    Preventing duplicate accounts with different cases improves UX.
    """
    pass
```

## Debugging Tests

### Run with Verbose Output
```bash
pytest -vv
```

### Show Print Statements
```bash
pytest -s
```

### Stop on First Failure
```bash
pytest -x
```

### Run Last Failed Tests
```bash
pytest --lf
```

### Drop into Debugger on Failure
```bash
pytest --pdb
```

## Continuous Integration

Tests run automatically on:
- Every pull request
- Every commit to main branch
- Nightly on develop branch

CI pipeline fails if:
- Any test fails
- Coverage drops below 80%
- Code quality checks fail (black, ruff, mypy)

## Writing New Tests

### TDD Workflow

1. **RED**: Write a failing test
```python
async def test_create_project(self, client, db_session):
    """Test project creation."""
    response = await client.post("/api/projects", json={
        "name": "New Project"
    })
    assert response.status_code == 201
```

2. **GREEN**: Write minimal code to pass
```python
@router.post("/projects", status_code=201)
async def create_project(data: ProjectCreate):
    return {"id": 1, "name": data.name}
```

3. **REFACTOR**: Improve code while keeping tests green

### Test Checklist

When adding a new feature, ensure:
- [ ] Unit tests for business logic
- [ ] Integration tests for API endpoints
- [ ] Edge cases covered
- [ ] Error cases tested
- [ ] Security scenarios tested (RBAC, org-scoping)
- [ ] Documentation updated
- [ ] Coverage maintained above 80%

## Troubleshooting

### Tests Pass Locally But Fail in CI

**Possible causes**:
- Database state differences
- Timezone issues
- Dependency version mismatches

**Solution**: Use Docker locally to match CI environment:
```bash
docker-compose run backend pytest
```

### Slow Tests

**Identify slow tests**:
```bash
pytest --durations=10
```

**Speed up tests**:
- Use factories instead of manual object creation
- Mock external services
- Use in-memory SQLite for unit tests
- Batch database operations

### Flaky Tests

**Signs**:
- Sometimes passes, sometimes fails
- Different results on different runs

**Common causes**:
- Race conditions
- Datetime comparisons
- Random data
- Shared state between tests

**Solutions**:
- Use `freezegun` for time-dependent tests
- Seed random generators
- Ensure test independence
- Add explicit waits for async operations

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [httpx testing guide](https://www.python-httpx.org/async/)
- [SQLAlchemy testing](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
