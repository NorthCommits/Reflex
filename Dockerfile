FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.9.26

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY reflex ./reflex
COPY alembic ./alembic
COPY alembic.ini ./
COPY seed.py ./
COPY entrypoint.sh ./

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
