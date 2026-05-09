#!/bin/bash
# Development startup script

echo "🔧 Starting SHL AI Recommender API (Development)"

if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  GROQ_API_KEY not set - will use deterministic fallback"
else
    echo "✓ GROQ_API_KEY is set"
fi

echo "Starting development server (with auto-reload)..."
echo ""
echo "📍 Server: http://localhost:8000"
echo "📚 Docs: http://localhost:8000/docs"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
