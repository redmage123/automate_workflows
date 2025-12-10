# Automation Platform Backend

FastAPI backend for the Automation Services Platform.

## Project Structure

```
backend/
├── alembic/              # Database migrations
│   ├── versions/         # Migration scripts
│   └── env.py           # Alembic configuration
├── app/
│   ├── api/             # API routes
│   ├── core/            # Core functionality (config, auth, security)
│   ├── dao/             # Data Access Objects
│   ├── db/              # Database configuration
│   ├── jobs/            # Background jobs (Dramatiq)
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # Business logic
│   └── main.py          # FastAPI application
├── tests/               # Test suite
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── conftest.py      # Pytest fixtures
├── Dockerfile           # Production Docker image
├── pyproject.toml       # Python dependencies and configuration
└── alembic.ini          # Alembic configuration

```

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (dev mode)
pip install -e ".[dev]"

# Copy environment variables
cp ../.env.example ../.env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head
```

### Running the Application

```bash
# Development mode (with auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python directly
python -m app.main
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_auth.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code with black
black app/ tests/

# Lint with ruff
ruff check app/ tests/

# Type check with mypy
mypy app/

# Run all quality checks
black app/ tests/ && ruff check app/ tests/ && mypy app/ && pytest
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# View current revision
alembic current
```

## Architecture

### Three-Layer Architecture

1. **API Layer** (`app/api/`): FastAPI routes, request/response handling
2. **Service Layer** (`app/services/`): Business logic, orchestration
3. **DAO Layer** (`app/dao/`): Database operations

### Key Patterns

- **DAO Pattern**: All database operations through Data Access Objects
- **Custom Exceptions**: Structured error handling with HTTP status codes
- **Dependency Injection**: FastAPI dependencies for session management
- **Test-Driven Development**: Write tests before implementation
- **Type Safety**: Full type hints with mypy validation

## API Documentation

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

## Environment Variables

See `../.env.example` for required environment variables.

Critical variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `JWT_SECRET`: Secret key for JWT tokens (min 32 chars)
- `ENCRYPTION_KEY`: Fernet key for encrypting sensitive data

## Security

- **OWASP Top 10 Compliance**: All security controls documented
- **JWT Authentication**: Token-based auth with bcrypt password hashing
- **RBAC**: Role-based access control (ADMIN/CLIENT)
- **Org-Scoping**: Multi-tenant data isolation at DAO level
- **Input Validation**: Pydantic schemas for all requests
- **Security Headers**: HSTS, CSP, X-Frame-Options, etc.

## Contributing

1. Follow TDD: Write tests first
2. Use DAO pattern for database operations
3. Document WHY, not just what
4. Ensure 80%+ code coverage
5. Pass all quality checks (black, ruff, mypy, pytest)
6. Update this README if adding new features

## License

Proprietary
