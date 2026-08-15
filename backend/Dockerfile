# syntax=docker/dockerfile:1

# ---- Base ----------------------------------------------------------------
FROM python:3.12-slim AS base

# Prevents Python from writing .pyc files / buffers stdout, both useful in
# containers for smaller images and immediate log visibility.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed to build psycopg2 and argon2-cffi wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Dependencies (cached layer) ------------------------------------------
FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Runtime ---------------------------------------------------------------
FROM deps AS runtime

# Run as non-root — never run application code as root in a container.
RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY . .

RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command runs the API. docker-compose overrides this for the
# celery worker service using the same image.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
