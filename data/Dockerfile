# Pipeline de dados (job): baixa SSP-SP/IBGE e gera o lake (bronze/silver/gold + análises).
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8

# Volumes esperados: /app/raw (XLSX baixados) e /app/lake (Parquet). Ver docker-compose.yml.
CMD ["python", "-m", "sinalbr_data", "all"]
