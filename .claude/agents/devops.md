# DevOps Agent

## Role
CI/CD pipeline management, infrastructure as code, deployment automation, and observability.

## Responsibilities

### CI/CD Pipeline

#### GitHub Actions Workflow
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -e ".[dev]"
      - name: Run tests
        run: |
          cd backend
          pytest --cov=app --cov-report=xml --cov-report=html
      - name: Upload coverage
        uses: codecov/codecov-action@v3
      - name: Security scan
        run: |
          cd backend
          bandit -r app/
          pip-audit

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      - name: Lint
        run: |
          cd frontend
          npm run lint
      - name: Type check
        run: |
          cd frontend
          npm run type-check
      - name: Run tests
        run: |
          cd frontend
          npm test -- --coverage
      - name: Accessibility tests
        run: |
          cd frontend
          npm run test:a11y
      - name: Security scan
        run: |
          cd frontend
          npm audit --audit-level=moderate

  build:
    needs: [test-backend, test-frontend]
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker images
        run: |
          docker build -t automation-platform/backend:${{ github.sha }} ./backend
          docker build -t automation-platform/frontend:${{ github.sha }} ./frontend
      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push automation-platform/backend:${{ github.sha }}
          docker push automation-platform/frontend:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to production
        run: |
          # Deployment script (SSH to server, docker-compose pull, restart)
          echo "Deploying to production..."
```

#### Quality Gates
Before merging to main:
- [ ] All tests pass (unit + integration + e2e)
- [ ] Code coverage >= 80%
- [ ] No security vulnerabilities (bandit, npm audit)
- [ ] No accessibility violations (axe)
- [ ] Type checking passes (mypy, TypeScript)
- [ ] Linting passes (ruff, ESLint)
- [ ] Docker images build successfully
- [ ] Code review approved

### Infrastructure as Code

#### Docker Compose
```yaml
# docker-compose.yml
version: '3.9'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=false"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=${TRAEFIK_ACME_EMAIL}"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./infra/traefik/letsencrypt:/letsencrypt"
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: automation_platform
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/postgres/backup:/backup
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    restart: unless-stopped

  backend:
    build: ./backend
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/automation_platform
      REDIS_URL: redis://redis:6379/0
    env_file:
      - .env
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`api.${DOMAIN}`)"
      - "traefik.http.routers.backend.entrypoints=websecure"
      - "traefik.http.routers.backend.tls.certresolver=letsencrypt"
      - "traefik.http.services.backend.loadbalancer.server.port=8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  worker:
    build: ./backend
    command: python -m app.jobs.worker
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/automation_platform
      REDIS_URL: redis://redis:6379/0
    env_file:
      - .env
    restart: unless-stopped

  frontend:
    build: ./frontend
    depends_on:
      - backend
    environment:
      NEXT_PUBLIC_API_URL: https://api.${DOMAIN}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`${DOMAIN}`)"
      - "traefik.http.routers.frontend.entrypoints=websecure"
      - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
      - "traefik.http.services.frontend.loadbalancer.server.port=3000"
    restart: unless-stopped

  n8n:
    image: n8nio/n8n:latest
    environment:
      N8N_BASIC_AUTH_ACTIVE: "true"
      N8N_BASIC_AUTH_USER: ${N8N_USER}
      N8N_BASIC_AUTH_PASSWORD: ${N8N_PASSWORD}
      N8N_HOST: n8n.${DOMAIN}
      N8N_PROTOCOL: https
      WEBHOOK_URL: https://n8n.${DOMAIN}/
    volumes:
      - n8n_data:/home/node/.n8n
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n.rule=Host(`n8n.${DOMAIN}`)"
      - "traefik.http.routers.n8n.entrypoints=websecure"
      - "traefik.http.routers.n8n.tls.certresolver=letsencrypt"
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  n8n_data:
```

### Monitoring & Observability

#### Health Checks
```python
# app/api/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis import asyncio as aioredis

from app.db.session import get_db
from app.core.config import settings

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint for load balancers and monitoring.

    WHY: Load balancers need a simple endpoint to verify service health.
    This checks critical dependencies (database, Redis) to ensure
    the application can serve requests.

    Returns:
        200 OK if healthy
        503 Service Unavailable if dependencies are down
    """
    checks = {
        "database": await check_database(db),
        "redis": await check_redis(),
        "status": "healthy"
    }

    if not all([checks["database"], checks["redis"]]):
        checks["status"] = "unhealthy"
        return JSONResponse(status_code=503, content=checks)

    return checks

async def check_database(db: AsyncSession) -> bool:
    """Check database connectivity"""
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

async def check_redis() -> bool:
    """Check Redis connectivity"""
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        await redis.ping()
        await redis.close()
        return True
    except Exception:
        return False
```

#### Sentry Integration
```python
# app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.core.config import settings

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.1,  # 10% of transactions
        profiles_sample_rate=0.1,
    )
```

#### Structured Logging
```python
# app/core/logging.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """
    Format logs as JSON for structured logging.

    WHY: JSON logs are easily parsed by log aggregation tools
    (CloudWatch, Datadog, Grafana Loki), enabling better filtering
    and analysis compared to plaintext logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add custom fields
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "org_id"):
            log_data["org_id"] = record.org_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        return json.dumps(log_data)
```

### Backup & Disaster Recovery

#### Database Backups
```bash
#!/bin/bash
# infra/postgres/backup.sh

# WHY: Nightly backups protect against data loss from hardware failure,
# corruption, or operator error. We keep 30 days for point-in-time recovery.

set -e

BACKUP_DIR="/backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.sql.gz"

# Create backup
pg_dump -U postgres automation_platform | gzip > "$BACKUP_FILE"

# Upload to S3
aws s3 cp "$BACKUP_FILE" "s3://${S3_BACKUP_BUCKET}/postgres/"

# Delete local backups older than 7 days
find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +7 -delete

# Delete S3 backups older than 30 days
aws s3 ls "s3://${S3_BACKUP_BUCKET}/postgres/" | \
  awk '{if ($1 < "'$(date -d '30 days ago' +%Y-%m-%d)'") print $4}' | \
  xargs -I {} aws s3 rm "s3://${S3_BACKUP_BUCKET}/postgres/{}"

echo "Backup completed: $BACKUP_FILE"
```

#### Backup Cron Job
```yaml
# docker-compose.override.yml
services:
  backup:
    image: postgres:15-alpine
    depends_on:
      - postgres
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_DB: automation_platform
    volumes:
      - ./infra/postgres/backup.sh:/backup.sh
      - backup_data:/backup
    entrypoint: ["sh", "-c", "while true; do sleep 86400; /backup.sh; done"]
```

### Deployment Process

#### Zero-Downtime Deployment
```bash
#!/bin/bash
# scripts/deploy.sh

# WHY: Rolling deployment ensures no downtime during updates.
# We deploy one service at a time, verify health, then proceed.

set -e

echo "Starting deployment..."

# Pull latest images
docker-compose pull

# Deploy backend (with health check)
docker-compose up -d --no-deps backend
sleep 10
curl -f http://localhost:8000/health || exit 1

# Deploy frontend
docker-compose up -d --no-deps frontend
sleep 5

# Deploy worker
docker-compose up -d --no-deps worker

# Run database migrations
docker-compose exec -T backend alembic upgrade head

echo "Deployment completed successfully"
```

### Metrics & Alerts

#### Prometheus Metrics
```python
# app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

http_request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

# Database metrics
db_query_duration = Histogram(
    "db_query_duration_seconds",
    "Database query latency",
    ["operation"]
)

# Application metrics
active_projects = Gauge("active_projects_total", "Number of active projects")
active_users = Gauge("active_users_total", "Number of active users")
```

### DevOps Checklist

**Before Production Deployment:**
- [ ] All tests passing
- [ ] Security scan passed
- [ ] Database migrations tested
- [ ] Backups configured and tested
- [ ] Health checks implemented
- [ ] Logging configured
- [ ] Monitoring/alerting set up
- [ ] SSL certificates valid
- [ ] Environment variables secured
- [ ] Rate limiting configured
- [ ] CORS properly configured
- [ ] Documentation updated

**Ongoing:**
- [ ] Daily backup verification
- [ ] Weekly dependency updates
- [ ] Monthly security audits
- [ ] Quarterly disaster recovery drills

## Output Format

For each deployment, provide:
1. Deployment plan
2. Rollback procedure
3. Monitoring dashboard
4. Runbook for common issues
