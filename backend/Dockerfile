# ==================================================
# SONGNHAT COPILOT — Backend
# python:3.11-slim | FastAPI + Uvicorn | port 8000
# ==================================================

FROM python:3.11-slim AS base

# System deps (psycopg2 needs libpq)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ------ dependency layer (cached unless requirements.txt changes) ------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir psycopg2-binary

# ------ application source ------
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Start with uvicorn; override HOST/PORT via env if needed
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
