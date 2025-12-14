# ============================================================================
# Dockerfile for GoldArb (PAXG-XAUT Grid Trading Strategy)
# ============================================================================
# This creates a production-ready container for running the grid trading
# strategy on Bybit for PAXG-XAUT pair.
# ============================================================================

# Stage 1: Base image with Python
FROM python:3.11-slim AS base

# Metadata
LABEL maintainer="patrick@project25"
LABEL description="NautilusTrader PAXG-XAUT Grid Strategy on Bybit"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Stage 2: Dependencies installation
# ============================================================================
FROM base AS dependencies

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 3: Application
# ============================================================================
FROM base AS application

# Copy installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/configs

# Copy application code
COPY run_live.py .
COPY config_live.py .
COPY paxg_xaut_grid_strategy.py .

# Copy configuration template (will be overridden by env vars or volumes)
COPY .env.example .

# Create non-root user for security
RUN useradd -m -u 1000 trader && \
    chown -R trader:trader /app

# Switch to non-root user
USER trader

# Health check (checks if the process is running)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Expose port for potential monitoring/metrics (optional)
# EXPOSE 8080

# Set default command
CMD ["python", "run_live.py"]
