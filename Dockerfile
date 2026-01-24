ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# System deps (curl for healthcheck, kept minimal)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN python -m pip install -U pip

COPY pyproject.toml README.md /app/
COPY src /app/src

# Install runtime deps + Flask for web dashboard
RUN python -m pip install . flask flask-cors

CMD ["python", "-m", "trading_bot", "--help"]
