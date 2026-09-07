# =============================================================================
# Couplefins — production image
#   1. python-builder — dependency venv via uv
#   2. node-builder   — SPA bundle via pnpm
#   3. runtime        — slim, non-root, uvicorn
# The API serves the built SPA from its own origin, so one container is the
# whole app: same-origin means the session cookie and the frontend's relative
# /api paths work with no production-only configuration.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Python dependencies
# ---------------------------------------------------------------------------
# Keep this tag in step with `required-version` under [tool.uv] in
# pyproject.toml. uv refuses a uv.lock whose schema is newer than it
# understands, and a stale tag fails `uv sync --locked` here at deploy time.
FROM ghcr.io/astral-sh/uv:0.12-python3.14-trixie-slim AS python-builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# `[tool.uv] package = false` — the project itself is never installed, so the
# manifest and the lock are the only inputs this stage needs.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ---------------------------------------------------------------------------
# Stage 2: Frontend bundle
# ---------------------------------------------------------------------------
FROM node:24-slim AS node-builder

WORKDIR /app/web

# Pinned to web/package.json's `packageManager`. web/package.json uses the
# pnpm-10 `pnpm.onlyBuiltDependencies` shape, which pnpm 11 reads differently.
RUN npm install -g pnpm@10.33.2

COPY web/package.json web/pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# No build args: nothing under web/src reads import.meta.env, every API call is
# a relative path, and vite.config.ts reads nothing outside web/. The bundle is
# the same in every environment.
COPY web/ ./
RUN pnpm build

# ---------------------------------------------------------------------------
# Stage 3: Runtime
# ---------------------------------------------------------------------------
FROM python:3.14-slim-trixie AS runtime

LABEL org.opencontainers.image.source="https://github.com/w-ash/couplefins" \
      org.opencontainers.image.description="Household finance tool for couples"

RUN groupadd --gid 1000 couplefins && \
    useradd --uid 1000 --gid couplefins --create-home couplefins

WORKDIR /app

COPY --chown=couplefins:couplefins --from=python-builder /app/.venv /app/.venv

# src/ carries the app, the default seed taxonomy under
# application/use_cases/seed_data/, and anchors _WEB_DIST (parents[3] of app.py).
COPY --chown=couplefins:couplefins src/ src/

# Migrations run in-process at startup. alembic.ini ships so `fly ssh console`
# can inspect history with the CLI.
COPY --chown=couplefins:couplefins alembic/ alembic/
COPY --chown=couplefins:couplefins alembic.ini ./


COPY --chown=couplefins:couplefins --from=node-builder /app/web/dist web/dist/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER couplefins
EXPOSE 8000

# Fly uses its own check; this one reports status under plain `docker run`.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')"]

# --timeout-graceful-shutdown is load-bearing, and 30s is a deliberate middle.
# uvicorn drains connections *before* running lifespan shutdown, so a shutdown
# sentinel in the event bus would arrive too late; this timeout is the only
# bound. /api/v1/events is an SSE response blocked on `await queue.get()` that
# never ends on its own, so unbounded, one open browser tab stalls every deploy
# until the platform SIGKILLs the machine.
#
# Not lower, because a chat reply legitimately streams for tens of seconds and
# would be truncated mid-answer. Not higher, because it must stay under the
# platform's kill_timeout (60s in fly.toml) so shutdown is always clean. The
# cost is that a deploy with a browser tab open pauses here for up to 30s;
# the frontend's EventSource reconnects on its own afterwards.
#
# --limit-max-requests is deliberately absent: with one worker there is no
# worker manager, so reaching the cap kills the process with no signal at all.
CMD ["uvicorn", "src.interface.api.app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", \
     "--no-access-log", \
     "--timeout-graceful-shutdown", "30", \
     "--limit-concurrency", "50"]
