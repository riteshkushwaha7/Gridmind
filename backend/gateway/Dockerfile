FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=backend-gateway \
    SERVICE_PORT=8000

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

COPY config.py .
COPY shared ./shared
COPY gateway ./gateway

ENV PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fs http://localhost:8000/health || exit 1

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
