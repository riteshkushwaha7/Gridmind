FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=backend-ppo \
    SERVICE_PORT=8011

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py .
COPY shared ./shared
COPY ppo ./ppo

ENV PYTHONPATH=/app

EXPOSE 8011

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fs http://localhost:8011/health || exit 1

CMD ["uvicorn", "ppo.inference:app", "--host", "0.0.0.0", "--port", "8011"]
