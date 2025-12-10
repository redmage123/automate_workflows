# WHY: Multi-stage build reduces final image size by excluding build tools
# and development dependencies from the production image.

# Build stage
FROM python:3.11-slim as builder

# WHY: Setting PYTHONUNBUFFERED ensures Python output is sent straight to
# the terminal without being buffered, crucial for real-time log viewing.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
# WHY: postgresql-client needed for database operations, gcc for building
# Python packages with C extensions (like psycopg2, cryptography).
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
# WHY: Installing dependencies in a separate layer allows Docker to cache
# them, speeding up subsequent builds when only application code changes.
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .

# Production stage
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install only runtime dependencies
# WHY: Minimal runtime dependencies reduce attack surface and image size.
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
# WHY: Copying from builder stage avoids reinstalling packages and
# keeps build tools out of the final image.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create non-root user
# WHY: Running as non-root improves security by limiting potential damage
# if the container is compromised (OWASP A05: Security Misconfiguration).
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
# WHY: Docker health checks allow orchestrators (Docker Compose, Kubernetes)
# to automatically restart unhealthy containers.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

# Start application
# WHY: Using uvicorn with --host 0.0.0.0 allows external access to the container.
# --workers 4 enables multiprocessing for better performance under load.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
