FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/workspace/.venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -d /usr/share/keyrings \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-17 \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock alembic.ini ./
COPY packages ./packages
COPY services ./services
COPY modules ./modules
COPY adapters ./adapters
COPY applications ./applications
COPY migrations ./migrations

RUN uv sync --frozen --all-packages --no-dev

CMD ["yggdrasil-core-api"]
