FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JOBPILOT_CHECKPOINT_DB=/data/workflow_checkpoints.db \
    JOBPILOT_EXPORT_DIR=/data/generated

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY app ./app

RUN uv sync --frozen --no-dev --extra agent --extra documents

RUN mkdir -p /data/generated
VOLUME ["/data"]
EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
