FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app
COPY Data ./Data
COPY scripts ./scripts
COPY streamlit_app.py .

# Create non-root user for security
RUN chmod +x scripts/start_production.sh && \
    useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Render sets PORT at runtime. 8000 is the local/default fallback.
EXPOSE 8000

# Health check for backend API
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start production API
CMD ["./scripts/start_production.sh"]
