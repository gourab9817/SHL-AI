#!/bin/bash
# Production startup script for SHL AI Recommender

set -e

echo "🚀 Starting SHL AI Recommender API (Production)"

# Check required environment variables
if [ -z "$GROQ_API_KEY" ]; then
    echo "❌ Error: GROQ_API_KEY is not set"
    echo "   Set it with: export GROQ_API_KEY=your_key_here"
    exit 1
fi

echo "✓ GROQ_API_KEY is set"

# Set defaults for optional variables
export GROQ_MODEL=${GROQ_MODEL:-llama-3.3-70b-versatile}
export GROQ_FALLBACK_MODEL=${GROQ_FALLBACK_MODEL:-llama-3.1-8b-instant}
export GROQ_FAST_MODEL=${GROQ_FAST_MODEL:-llama-3.1-8b-instant}
export CATALOG_PATH=${CATALOG_PATH:-Data/shl_product_catalog.json}
export CHAT_TIMEOUT_SECONDS=${CHAT_TIMEOUT_SECONDS:-25}

echo "Configuration:"
echo "  GROQ_MODEL: $GROQ_MODEL"
echo "  CATALOG_PATH: $CATALOG_PATH"
echo "  CHAT_TIMEOUT_SECONDS: $CHAT_TIMEOUT_SECONDS"

# Check catalog exists
if [ ! -f "$CATALOG_PATH" ]; then
    echo "❌ Error: Catalog not found at $CATALOG_PATH"
    exit 1
fi

echo "✓ Catalog found"

# Run tests before startup (optional - remove if not needed)
echo ""
echo "Running pre-flight health checks..."
python3 -m pytest tests/test_smoke.py -q 2>/dev/null || {
    echo "⚠️  Some tests failed, but continuing startup..."
}

echo ""
echo "🎯 Starting API server..."
echo "   Health endpoint: http://localhost:8000/health"
echo "   API docs: http://localhost:8000/docs"
echo "   Chat endpoint: POST http://localhost:8000/chat"
echo ""

# Start server with worker count based on CPU cores
WORKERS=$(($(nproc) * 2))
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "$WORKERS" \
    --access-log \
    --log-level info
