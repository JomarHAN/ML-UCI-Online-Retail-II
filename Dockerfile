# syntax=docker/dockerfile:1.7
# ============================================================================
# Dockerfile for the UCI Online Retail recommendation API
# ============================================================================
# Multi-stage build:
#   Stage 1 (builder): installs dependencies into a venv with uv
#   Stage 2 (runtime): copies just the venv + app code into a small final image
# 
# Why multi-stage?
#   - Build tools, caches, and dev files stay out of the final image
#   - Smaller image -> faster deploys, less attck surface
#   - Reproducible: the build stage is deterministic from pyproject.toml + uv.lock
# 
# Build:    docker build -t uci-retail-api:latest .
# Run:      docker run -p 8000:8000 uci-retail-api:latest
# Inspect:  docker run -it --rm uci-retail-api:latest bash
# ============================================================================


# ---------------------------------------------------------------------------
# Stage 1: builder
# ---------------------------------------------------------------------------
# Use Astral's official uv image.It bundles uv pre-installed and is based on
# python:3.12-slim-bookworm underneath. Pinning the digest in production gives
# full reproducibility; we use the named tag here for readability.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Environment variables that improve uv behavior inside containers:
#   - UV_COMPILE_BYTECODE=1: compile .py to .pyc at install time (faster cold start)
#   - UV_LINK_MODE=copy: copy files instead of hardlinking (works inside Docker)
#   - UV_PROJECT_ENVIRONMENT: where uv will put the venv (we want it predictable)
ENV UV_LINK_MODE=1  \
    UV_LINK_MODE=copy   \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Copy ONLY the dependency manifests first.
# This is the critical layer-caching trick: as long as pyproject.toml and 
# uv.lock are unchanged, Docker reuses the cached layer if installed packages.
# even when your source code changes. Result: source-only edits rebuild in seconds.
COPY pyproject.toml uv.lock* ./

# Install dependencies into the venv at UV_PROJECT_ENVIRONMENT.
# --no-install-project: install dependencies only, not the project itself yet
# --frozen: refuse to update uv.lock; the lockfile is the source of truth
# --no-dev: skip the dev dependency group (no pytest, jupyter, etc. in prod)
# A bind mount caches the uv download cache across builds.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now copy the acatual source. Subsequent code-only changes only invalidate
# from this layer onward, not the deps layer above.
COPY src/ ./src/

# Install the project itself (so `from src.api.main import app` resolves).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
# Use the same Python base, but without uv -- we don't need it at runtime.
# python:3.12-slim-bookworm is ~120MB; adding out deps brings it to ~1GB 
# (XGBoost, SHAP, pandas, numpy are heavy). That's normal for ML images,
FROM python:3.12-slim-bookworm AS runtime

# Security: install ONLY runtime dependencies. libgomp1 is required by
# XGBoost/LightGBM/sklearn for OpenMP parallelism. curl is for HEALTHCHECK.
# --no-install-recommends keeps the image lean.
# Clean apt cache in the same layer to avoid bloating the image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root uses. NEVER run containers as root in production --
# if the container is breached, root inside container is the first step
# toward privilege escalation on the host.
# UID 1000 matches the typical default on Linux hosts, so bind-mounted volumes
# from a developer's laptop will have correct ownership
RUN groupadd --system --gid 1000 app && \
    useradd --system --uid 1000 --gid app --home-dir /app --shell /bin/bash app


WORKDIR /app

# Copy the prepared venv from the builder. Owned by `app` so the runtime user
# can read it. This is the big payload -- ~800MB of compiled Python deps.
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Copy source code with correct ownership
COPY --chown=app:app /src ./src

# Make sure the venv is on Path so `python` and `uvicorn` resolve to it.
# PYTHONUNBUFFERED=1 means logs flush immediately (no buffering surprises).
# PYTHONDONTWRITEBYTECODE=1 save disk not not writing .pyc files at runtime
# (we already compiled them in the builder via UV_COMPILE_BYTECODE).
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to the non-root user. From here, the container cannot write outside
# /app or do anything privileged
USER app

# Document the port the app listens on. (EXPOSE is documentation only;
# the port still has to be published with -p at runtime.)
EXPOSE 8000

# Container-native healthcheck. Docker and ECS use this to determine if 
# the container is healthy and should receive traffic
# - --interval=30s: check every 30 seconds after start
# - --timeout=5s: each check must respond within 5s
# - --start-period=60s: give the app 60s to load models before checks count
# - --retries=3: 3 consecutive failures = unhealthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries= \
    CMD curl --fail http://localhost:8000/health || exit 1

# Default command. Using JSON-array form (not shell form) so signals (SIGTERM,
# SIGINT) reach the Python process directly. This matters: when ECS replaces
# the container during deployment, it sends SIGTERM and expect graceful
# shutdown -- uvicorn handles SIGTERM cleanly only if it receives it directly.
# 
# --host 0.0.0.0: listen on all interfaces (required inside containers)
# --port 8000:  matches EXPOSE above
# --workers 1:  single worker since we load models into memory once.
#               For high traffic, scale horizontally (more containers) instead
#               of vertically (more workers) -- each worker loads its own models.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]