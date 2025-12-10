# Automation Services Platform

[![CI](https://github.com/redmage123/automate_workflows/actions/workflows/ci.yml/badge.svg)](https://github.com/redmage123/automate_workflows/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive multi-tenant SaaS platform for managing automation services, client onboarding, proposals, payments, and n8n workflow orchestration.

## Features

- **Multi-tenant Architecture**: Organization-based data isolation with role-based access control (RBAC)
- **Authentication & Security**: JWT-based auth with token blacklisting, OWASP Top 10 compliance
- **Audit Logging**: Comprehensive security event tracking for compliance (OWASP A09)
- **n8n Integration**: Self-hosted workflow automation with per-client isolation
- **Stripe Payments**: Subscription and one-time payment processing
- **Modern Frontend**: React + TypeScript + Tailwind CSS

## Architecture

- **Frontend**: React 18 + TypeScript + Tailwind CSS + Vite
- **Backend**: FastAPI (Python 3.11+) with SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL 15+
- **Cache/Sessions**: Redis 7+
- **Auth**: JWT with Redis token blacklisting
- **Payments**: Stripe
- **Workflows**: n8n (self-hosted)
- **Storage**: S3-compatible
- **Jobs/Queue**: Dramatiq + Redis
- **Deployment**: Docker Compose + Traefik (reverse proxy + SSL)

## Project Structure

```
/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/      # API routers
│   │   ├── core/     # Config, security, auth
│   │   ├── dao/      # Data Access Objects
│   │   ├── models/   # SQLAlchemy models
│   │   ├── schemas/  # Pydantic schemas
│   │   ├── services/ # Business logic
│   │   ├── middleware/ # Request context, security headers
│   │   └── jobs/     # Background tasks
│   ├── alembic/      # DB migrations
│   └── tests/        # Unit & integration tests (149 tests)
├── frontend/         # React frontend
├── docs/             # ADRs, specifications, kanban boards
├── infra/            # Infrastructure configs
└── .github/          # CI/CD workflows
```

## Quick Start (Docker Compose - Recommended)

The fastest way to get started is using Docker Compose, which sets up all services automatically.

### 1. Clone and Configure

```bash
git clone https://github.com/redmage123/automate_workflows.git
cd automate_workflows

# Copy environment template
cp .env.example .env

# Generate secure secrets (REQUIRED)
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))" >> .env
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env

# Edit .env and set required passwords
nano .env  # or use your preferred editor
```

**Required environment variables:**
- `POSTGRES_PASSWORD`: Strong password for PostgreSQL
- `N8N_PASSWORD`: Strong password for n8n admin interface
- `JWT_SECRET`: Auto-generated above
- `ENCRYPTION_KEY`: Auto-generated above

### 2. Start Services

```bash
# Start all services (backend, database, redis, n8n)
docker-compose up -d

# View logs
docker-compose logs -f backend

# Check service health
docker-compose ps
```

### 3. Initialize Database

```bash
# Run database migrations
docker-compose exec backend alembic upgrade head
```

### 4. Access Services

- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/docs
- **n8n (Workflows)**: http://localhost:5678
- **Frontend**: http://localhost:3000 (coming soon)
- **Traefik Dashboard**: http://localhost:8080

## Local Development (Without Docker)

If you prefer running services locally for development:

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (dev mode)
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start development server (with hot-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup (Coming Soon)

```bash
cd frontend
npm install
npm run dev
```

## Docker Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f [service_name]

# Rebuild after code changes
docker-compose up -d --build backend

# Run database migrations
docker-compose exec backend alembic upgrade head

# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "Description"

# Access database
docker-compose exec postgres psql -U postgres -d automation_platform

# Access Redis CLI
docker-compose exec redis redis-cli

# Run tests
docker-compose exec backend pytest

# Stop and remove volumes (DESTRUCTIVE)
docker-compose down -v
```

## Development Status

### Completed
- ✅ Project scaffold and infrastructure (Docker Compose, Traefik)
- ✅ Authentication flow (login, logout, registration)
- ✅ JWT token management with Redis blacklisting
- ✅ Multi-tenant organization model
- ✅ Security headers middleware (OWASP compliance)
- ✅ Audit logging middleware and service (OWASP A09)
- ✅ 149 passing tests (unit + integration)

### In Progress
- 🔄 Rate limiting for auth endpoints
- 🔄 Email verification flow
- 🔄 Password reset flow

### Planned
- [ ] Client onboarding and projects
- [ ] Proposals + PDF generation + payments
- [ ] n8n workflow integration
- [ ] Project tracker + ticketing
- [ ] Notifications system
- [ ] Admin dashboard

## Running Tests

```bash
# Backend tests
cd backend
source .venv/bin/activate  # or create venv first
pip install -e ".[dev]"
pytest -v

# With coverage
pytest --cov=app --cov-report=html
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

## Security

This project follows OWASP Top 10 security guidelines:
- **A01**: Broken Access Control → RBAC + org-scoping on every endpoint
- **A02**: Cryptographic Failures → Fernet encryption for sensitive data
- **A03**: Injection → Parameterized queries via SQLAlchemy ORM
- **A07**: Authentication Failures → JWT with short expiration, bcrypt
- **A09**: Security Logging → Comprehensive audit logs

## Contributing

1. Create an ADR in `docs/adr/` before implementing new features
2. Follow TDD: Write tests first
3. Ensure all tests pass before submitting PR
4. Follow the code style (black, ruff)

## License

MIT
