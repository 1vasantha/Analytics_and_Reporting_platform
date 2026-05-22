# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --------- Builder stage ---------
FROM base AS builder
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
    fastapi==0.115.0 "uvicorn[standard]==0.32.0" python-multipart==0.0.12 websockets==13.1 \
    "sqlalchemy[asyncio]==2.0.35" asyncpg==0.29.0 alembic==1.13.3 psycopg2-binary==2.9.9 \
    pydantic==2.9.2 pydantic-settings==2.5.2 email-validator==2.2.0 \
    "python-jose[cryptography]==3.3.0" "passlib[bcrypt]==1.7.4" bcrypt==4.0.1 \
    "celery[redis]==5.4.0" redis==5.1.1 flower==2.0.1 \
    httpx==0.27.2 pandas==2.2.3 numpy==2.1.2 \
    aiosmtplib==3.0.2 jinja2==3.1.4 \
    structlog==24.4.0 prometheus-client==0.21.0

# --------- Runtime stage ---------
FROM base AS runtime
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . /app

RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
