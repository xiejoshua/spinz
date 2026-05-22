# auxd-api — Fly.io / production container
#
# Multi-stage build:
#   1. builder  — install deps + project into a virtualenv with uv (frozen lockfile)
#   2. runtime  — slim image with only the venv + source; non-root user; healthcheck
#
# Build locally:
#   docker build -t auxd-api:dev -f apps/api/Dockerfile apps/api
# Run locally with env file:
#   docker run --rm -p 8080:8080 --env-file apps/api/.env auxd-api:dev
#   curl http://localhost:8080/healthz

# -----------------------------------------------------------------------------
# Builder stage
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Pull the standalone uv binary so we get the same resolver/lockfile semantics
# as local dev (uv.lock is the source of truth — pip would re-resolve).
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install dependencies first (cache layer keyed on lockfile only).
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-install-project --no-dev

# Now bring in the source and install the project itself.
COPY src /app/src
RUN uv sync --frozen --no-dev

# -----------------------------------------------------------------------------
# Runtime stage
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Non-root user (cheap defence-in-depth — Fly enforces seccomp/userns too).
RUN groupadd --system auxd \
 && useradd --system --gid auxd --home-dir /app --shell /usr/sbin/nologin auxd

WORKDIR /app

# Copy the prepared virtualenv + the source (and only those — no uv, no caches).
COPY --from=builder --chown=auxd:auxd /app/.venv /app/.venv
COPY --from=builder --chown=auxd:auxd /app/src /app/src

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

USER auxd

EXPOSE 8080

# Liveness check the platform can scrape on its own (Fly also scrapes via
# fly.toml's [[http_service.checks]] — this one is a backstop for `docker run`).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/healthz', timeout=3).status == 200 else 1)"

# Default CMD — matches the `web` process from fly.toml's [processes] block.
# The `worker` process overrides this with `arq auxd_api.workers.main.WorkerSettings`
# (defined in fly.toml). `--proxy-headers --forwarded-allow-ips=*` is required
# because Fly's edge terminates TLS and forwards via private IPv6; without
# these flags the app sees the proxy IP instead of the client IP.
CMD ["uvicorn", "auxd_api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
