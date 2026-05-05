FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=backend-lstm \
    SERVICE_PORT=8010

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# Backend tree expected at /app: shared/, lstm/, config.py
COPY config.py .
COPY shared ./shared
COPY lstm ./lstm

ENV PYTHONPATH=/app

EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fs http://localhost:8010/health || exit 1

CMD ["uvicorn", "lstm.inference:app", "--host", "0.0.0.0", "--port", "8010"]
