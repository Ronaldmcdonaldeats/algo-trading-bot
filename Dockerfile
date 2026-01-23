ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# System deps (kept minimal; add build-essential if you need compiled wheels)
RUN python -m pip install -U pip

COPY pyproject.toml README.md /app/
COPY src /app/src

# Install runtime deps (editable install isn't needed in containers)
RUN python -m pip install .

CMD ["python", "-m", "trading_bot", "--help"]
