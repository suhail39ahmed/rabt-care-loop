FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY services ./services
COPY data ./data
COPY benchmark ./benchmark

RUN uv sync --frozen --no-dev --extra azure

ENV PYTHONPATH=/app/services/orchestrator:/app/services:/app
ENV RABT_DB=/data/rabt.db
ENV API_HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn app.main:app --app-dir services/orchestrator --host 0.0.0.0 --port ${PORT:-8000}"]
