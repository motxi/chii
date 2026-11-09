FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 chii \
    && mkdir /app \
    && chown chii:chii /app

USER chii
WORKDIR /app

# Install dependencies first so they're cached separately from app code.
COPY --chown=chii:chii pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY --chown=chii:chii . .
RUN uv sync --frozen --no-dev

ENTRYPOINT ["python", "run.py"]
