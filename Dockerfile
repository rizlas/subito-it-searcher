FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

FROM python:3.14-slim-bookworm AS subito-it-researcher

RUN groupadd --gid 1000 subito && \
    useradd --uid 1000 --gid subito --shell /bin/sh \
    --no-create-home --system subito

COPY --from=builder --chown=subito:subito /app /app

ENV PATH="/app/.venv/bin:$PATH"

USER subito

WORKDIR /app

ENTRYPOINT ["python3", "subito-searcher.py"]
