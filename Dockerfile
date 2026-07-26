# Multi-Stage Production Dockerfile for PhishGuard-X
FROM python:3.12-slim as builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final Runtime Image
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

# Expose FastAPI HTTP Port
EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Run FastAPI Server via run.py
CMD ["python", "run.py"]
