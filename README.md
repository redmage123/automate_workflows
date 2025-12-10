# Automation Services Platform

A comprehensive platform for managing automation services, client onboarding, proposals, payments, and n8n workflow orchestration.

## Architecture

- **Frontend**: Next.js 14 (App Router, TypeScript, Tailwind CSS, shadcn/ui)
- **Backend**: FastAPI (Python 3.11+) with SQLAlchemy 2.0
- **Database**: PostgreSQL
- **Auth**: NextAuth.js + JWT
- **Payments**: Stripe
- **Workflows**: n8n (self-hosted)
- **Storage**: S3-compatible
- **Jobs/Queue**: Dramatiq + Redis
- **Deployment**: Docker Compose + Traefik

## Project Structure

```
/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/      # API routers
│   │   ├── core/     # Config, security, auth
│   │   ├── models/   # SQLAlchemy models
│   │   ├── schemas/  # Pydantic schemas
│   │   ├── services/ # Business logic
│   │   └── jobs/     # Background tasks
│   ├── alembic/      # DB migrations
│   └── tests/
├── frontend/         # Next.js frontend
├── infra/           # Docker Compose, Traefik
└── rust/            # Future Rust services
```

## Quick Start (Docker Compose - Recommended)

The fastest way to get started is using Docker Compose, which sets up all services automatically.

### 1. Clone and Configure

```bash
git clone https://github.com/redmage123/automate.git
cd automate

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

## Milestones

- [x] Milestone 1: Repo scaffold, auth flow
- [ ] Milestone 2: Onboarding and projects
- [ ] Milestone 3: Proposals + PDFs + payments
- [ ] Milestone 4: n8n integration
- [ ] Milestone 5: Project tracker + tickets + notifications
- [ ] Milestone 6: Deploy and harden
- [ ] Milestone 7: Rust services (optional)

## API Documentation

Once running, visit:
- Backend API docs: http://localhost:8000/docs
- Frontend: http://localhost:3000

## License

MIT
