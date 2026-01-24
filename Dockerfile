ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# System deps (curl for healthcheck, kept minimal)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN python -m pip install -U pip

COPY pyproject.toml README.md /app/
COPY src /app/src

# Install runtime deps + Flask + Gunicorn for production WSGI server
RUN python -m pip install . flask flask-cors gunicorn

# Production WSGI server command
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--worker-class", "sync", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "trading_bot.ui.web:app"]
