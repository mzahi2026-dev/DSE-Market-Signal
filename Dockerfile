# Production Dockerfile for DSE Market Signal
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Dhaka

# Install OS packages (tzdata for Bangladesh Standard Time, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/ ./backend/
COPY config/ ./config/
COPY engine/ ./engine/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY README.md ROADMAP.md pytest.ini ./

# Create data and logs directories
RUN mkdir -p /app/data /app/logs

# Create non-root system user for security
RUN groupadd -r dseuser && useradd -r -g dseuser -d /app dseuser \
    && chown -R dseuser:dseuser /app

USER dseuser

# Expose FastAPI service port
EXPOSE 8000

# Docker healthcheck querying the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command using Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
