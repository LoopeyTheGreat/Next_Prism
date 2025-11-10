# Next_Prism Dockerfile
# Multi-stage build for optimized production image
# Based on Debian Bookworm for stability and compatibility

# Stage 1: Builder
FROM python:3.11-slim-bookworm AS builder

LABEL maintainer="LoopeyTheGreat"
LABEL description="Next_Prism Photo Sync Orchestrator - Builder Stage"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-warn-script-location -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim-bookworm

LABEL maintainer="LoopeyTheGreat"
LABEL description="Next_Prism Photo Sync Orchestrator"
LABEL version="0.1.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/nextprism/.local/bin:$PATH \
    APP_HOME=/app \
    CONFIG_PATH=/app/config/config.yaml

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
    curl \
    ca-certificates \
    # Docker CLI (for exec commands)
    docker.io \
    # SSH client (for Swarm proxy communication)
    openssh-client \
    # File monitoring tools
    inotify-tools \
    # Image processing (optional, for future features)
    libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash nextprism && \
    mkdir -p /app /app/config /app/logs /app/data && \
    chown -R nextprism:nextprism /app

# Switch to non-root user
USER nextprism
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder --chown=nextprism:nextprism /root/.local /home/nextprism/.local

# Copy application code
COPY --chown=nextprism:nextprism src/ /app/src/
COPY --chown=nextprism:nextprism scripts/ /app/scripts/

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/config /app/data && \
    chmod +x /app/scripts/*.sh 2>/dev/null || true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${APP_PORT:-8080}/api/health || exit 1

# Expose web UI port
EXPOSE 8080

# Volume mount points
VOLUME ["/app/config", "/app/logs", "/app/data"]

# Default command (will be overridden in docker-compose)
CMD ["python", "-m", "uvicorn", "src.web.main:app", "--host", "0.0.0.0", "--port", "8080"]
