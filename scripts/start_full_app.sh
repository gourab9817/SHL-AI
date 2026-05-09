#!/bin/bash
# Start both FastAPI backend and Streamlit frontend

set -e

echo "🚀 Starting SHL AI Recommender (Full App)"
echo "========================================"

# Check environment
if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  GROQ_API_KEY not set - will use deterministic fallback"
else
    echo "✓ GROQ_API_KEY is set"
fi

# Set defaults
export GROQ_MODEL=${GROQ_MODEL:-llama-3.3-70b-versatile}
export CATALOG_PATH=${CATALOG_PATH:-Data/shl_product_catalog.json}
export CHAT_TIMEOUT_SECONDS=${CHAT_TIMEOUT_SECONDS:-25}

echo ""
echo "📋 Configuration:"
echo "   Backend: http://localhost:8000"
echo "   Frontend: http://localhost:8501"
echo "   GROQ_MODEL: $GROQ_MODEL"
echo ""

# Start backend in background
echo "🔧 Starting FastAPI backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info &
BACKEND_PID=$!

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 3

# Check backend health
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Backend failed to start"
    kill $BACKEND_PID
    exit 1
fi

echo "✓ Backend is ready"
echo ""

# Start frontend
echo "🎨 Starting Streamlit frontend..."
streamlit run streamlit_app.py --server.port=8501 --server.address=0.0.0.0 &
FRONTEND_PID=$!

sleep 2

echo ""
echo "✅ Both services started!"
echo ""
echo "📍 URLs:"
echo "   🖥️  Frontend:  http://localhost:8501"
echo "   🔌 Backend:   http://localhost:8000"
echo "   📚 API Docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Keep both processes running
wait
