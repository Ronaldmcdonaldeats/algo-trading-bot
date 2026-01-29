# Multi-stage build: builder stage for compilation
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /build

# System deps: build-essential for scipy/numpy compilation
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install pip and wheels
RUN python -m pip install --no-cache-dir -U pip setuptools wheel

# Copy only project metadata
COPY pyproject.toml /build/

# Pre-build wheels for heavy packages
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels \
    scipy xgboost scikit-learn scikit-optimize numpy pandas flask flask-cors gunicorn

# Final runtime stage - minimal image
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# Only runtime deps needed (curl for health checks)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Use pre-built wheels from builder
COPY --from=builder /wheels /wheels

# Install from wheels (much faster than building from source)
RUN python -m pip install --no-cache-dir --no-index --find-links /wheels \
    /wheels/* && rm -rf /wheels

# Copy application code
COPY src /app/src
COPY pyproject.toml /app/
# Copy scripts and config (optional)
COPY scripts /app/scripts/ 
COPY config /app/config/

# Install app
RUN python -m pip install --no-cache-dir -e .

# Health check
HEALTHCHECK --interval=10s --timeout=3s --retries=2 --start-period=5s \
    CMD curl -f http://localhost:5000/health || exit 1

# Production WSGI server command - optimized for startup
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--worker-class", "sync", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "warning", "trading_bot.web_api:app"]
