#!/bin/sh

set -e

export PORT=${PORT:-8501}
export API_BASE_URL=${API_BASE_URL:-http://localhost:8000}

echo "Starting SHL AI Streamlit frontend"
echo "  PORT: $PORT"
echo "  API_BASE_URL: $API_BASE_URL"

exec streamlit run streamlit_app.py \
    --server.port="$PORT" \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false
