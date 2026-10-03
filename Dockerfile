# Multi-Stage Production Dockerfile for PhishGuard-X
FROM python:3.12-slim as builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install PyTorch from the CPU-only wheel index first. gnn_model.py only ever loads weights
# with map_location="cpu" (see get_gnn_model()); the default PyPI torch wheels pull in several
# GB of unused CUDA packages, which is what made the CI install slow before this fix (see the
# Phase 0 commit that made the same change to .github/workflows/ci.yml). Exporting PYTHONPATH to
# this stage's --prefix target lets the second pip see torch as already installed, so it is not
# reinstalled from PyPI. NOT verified with an actual docker build in this environment (no Docker
# available here) - verify on first real build.
ENV PYTHONPATH=/install/lib/python3.12/site-packages
RUN pip install --no-cache-dir --prefix=/install torch --index-url https://download.pytorch.org/whl/cpu
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
