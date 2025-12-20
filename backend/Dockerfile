# BrandGuard Backend - Production Dockerfile
# Multi-stage build for optimized production image
#
# Reference: ADVERIFY-BE-3 - Production deployment infrastructure

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2: Production
# =============================================================================
FROM python:3.11-slim as production

# Install FFmpeg for yt-dlp audio extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Security: Run as non-root user
RUN groupadd -r brandguard && useradd -r -g brandguard brandguard

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy GCP credentials (for local development)
COPY --chown=brandguard:brandguard brandguard-481014-b6b02cb2d900.json /app/service-account.json

# Copy application code
COPY --chown=brandguard:brandguard . .

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check
# Reference: ADVERIFY-BE-1 (S-1.1.2) - Health check endpoints
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

# Switch to non-root user
USER brandguard

# Run the application
# Using uvicorn with optimized settings for production
CMD ["uvicorn", "main:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "4", \
    "--loop", "uvloop", \
    "--http", "httptools", \
    "--no-access-log"]
