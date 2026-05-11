#!/bin/sh
# Production startup script for SHL AI Recommender

set -e

echo "Starting SHL AI Recommender API"

# Check required environment variables
if [ -z "$GROQ_API_KEY" ]; then
    echo "Error: GROQ_API_KEY is not set"
    exit 1
fi

# Set defaults for optional variables
export GROQ_MODEL=${GROQ_MODEL:-openai/gpt-oss-120b}
export GROQ_FALLBACK_MODEL=${GROQ_FALLBACK_MODEL:-openai/gpt-oss-20b}
export GROQ_FAST_MODEL=${GROQ_FAST_MODEL:-openai/gpt-oss-20b}
export CATALOG_PATH=${CATALOG_PATH:-Data/shl_product_catalog.json}
export CHAT_TIMEOUT_SECONDS=${CHAT_TIMEOUT_SECONDS:-25}
export PORT=${PORT:-8000}
export WEB_CONCURRENCY=${WEB_CONCURRENCY:-1}

echo "Configuration:"
echo "  GROQ_MODEL: $GROQ_MODEL"
echo "  CATALOG_PATH: $CATALOG_PATH"
echo "  CHAT_TIMEOUT_SECONDS: $CHAT_TIMEOUT_SECONDS"
echo "  PORT: $PORT"
echo "  WEB_CONCURRENCY: $WEB_CONCURRENCY"

# Check catalog exists
if [ ! -f "$CATALOG_PATH" ]; then
    echo "Error: Catalog not found at $CATALOG_PATH"
    exit 1
fi

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers "$WEB_CONCURRENCY" \
    --access-log \
    --log-level info
