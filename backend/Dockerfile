# =============================================================================
# NexusAI Backend Production Dockerfile (Python 3.10 Slim - CPU Optimized)
# =============================================================================
FROM python:3.10-slim as builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-optimized PyTorch wheel first to prevent installing 5GB+ CUDA binaries
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy backend requirements and install dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Pre-cache local SentenceTransformers and Cross-Encoder weights in build layer
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); \
    CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# =============================================================================
# Production Runtime Stage
# =============================================================================
FROM python:3.10-slim as runner

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    APP_ENV=production \
    PORT=8000

# Install curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user and group (UID 10001)
RUN groupadd -g 10001 nexusgroup && \
    useradd -u 10001 -g nexusgroup -s /bin/bash -m nexususer

# Copy installed Python packages and model cache from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache /home/nexususer/.cache

# Copy application source code
COPY backend /app/backend
COPY pytest.ini /app/pytest.ini

# Create storage directories and set ownership to nexususer
RUN mkdir -p /app/data/uploads /app/data/chromadb /app/data/eval_runs && \
    chown -R nexususer:nexusgroup /app /home/nexususer

USER nexususer

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

