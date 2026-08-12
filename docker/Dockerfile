FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first so they're cached separately from app code.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.14-slim-bookworm AS runtime

RUN useradd --create-home --uid 1000 chii

WORKDIR /app

COPY --from=builder --chown=chii:chii /app /app
RUN mkdir -p /app/state && chown chii:chii /app/state

USER chii

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/app/state/chii.db

# The `/app/state` directory holds only the SQLite DB file (not source), and
# `chii/logs/` is pure runtime output. Both are safe to volume-mount without
# shadowing app code on the next image update.
#
# See `docker/compose.yaml`.
VOLUME ["/app/state", "/app/chii/logs"]

ENTRYPOINT ["python", "run.py"]
