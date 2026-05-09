# SHL-AI

Conversational SHL assessment recommender for the AI Intern take-home assignment.

## Quick Start

### 🎨 With Streamlit UI (Recommended)

```bash
# Install dependencies
pip install -r requirements.txt
export GROQ_API_KEY=sk_...

# Run both backend + frontend together
./scripts/start_full_app.sh

# Open browser
open http://localhost:8501
```

Features:
- ✨ Single-page UI
- 💬 Conversation interface
- 🎯 Visual recommendations
- 🔄 Health check status

See [STREAMLIT_UI.md](STREAMLIT_UI.md) for full guide.

---

### Local Development (Backend Only)

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Add GROQ API key
export GROQ_API_KEY=sk_...

# Run development server (auto-reload)
./scripts/start_dev.sh
# or: uvicorn app.main:app --reload

# Run tests (no API key required)
pytest tests/ -q
```

### Docker

```bash
# Build image
docker build -t shl-recommender .

# Run container
docker run -e GROQ_API_KEY=sk_... -p 8000:8000 shl-recommender

# Or use docker-compose
export GROQ_API_KEY=sk_...
docker-compose up
```

## API

### Health Check

```bash
curl http://localhost:8000/health
```

Returns: `{"status": "ok"}`

### Chat Endpoint

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hiring senior Java engineer"}
    ]
  }'
```

Response:

```json
{
  "reply": "...",
  "recommendations": [
    {
      "name": "Core Java (Advanced Level) (New)",
      "url": "https://www.shl.com/products/product-catalog/view/...",
      "test_type": "K"
    }
  ],
  "end_of_conversation": false
}
```

## Testing

```bash
# All tests (173 tests, no API key required)
pytest tests/ -q

# Smoke tests only (12 deployment validation tests)
pytest tests/test_smoke.py -v

# Regression tests (C1-C10 traces with Recall@10 metrics)
pytest tests/test_regression.py -v

# Behavior probes (edge cases and adversarial inputs)
pytest tests/test_behavior_probes.py -v

# View Recall@10 summary table
pytest tests/test_regression.py::test_recall_summary -s
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- Production configuration
- Docker deployment
- Performance tuning
- Monitoring and troubleshooting
- Deployment checklist

**Key points:**
- ✅ All 173 tests pass
- ✅ Mean Recall@10 = 0.87 (target: ≥0.70)
- ✅ Stateless API (safe for horizontal scaling)
- ✅ 25-second timeout guard (evaluator limit: 30s)
- ✅ Deterministic fallback if LLM unavailable

## Project Structure

```
app/
  ├── main.py              # FastAPI app & endpoints
  ├── schemas.py           # Pydantic request/response
  ├── config.py            # Settings & env vars
  ├── logging_config.py    # Request logging
  ├── catalog.py           # Product catalog loader
  ├── retrieval.py         # Hybrid search engine
  ├── guardrails.py        # Off-topic/legal checks
  ├── conversation/        # Context extraction
  ├── agent/               # LangGraph orchestration
  ├── llm/                 # Groq client & generation
  └── verification.py      # Output validation

Data/
  └── shl_product_catalog.json  # 377 unique products

tests/
  ├── test_regression.py   # C1-C10 replay + Recall@10
  ├── test_behavior_probes.py  # Edge cases
  ├── test_smoke.py        # Deployment validation
  └── fixtures/            # Test data & sample conversations

scripts/
  ├── start_dev.sh         # Development startup
  └── start_production.sh  # Production startup
```

## Architecture

Stateless conversational agent:

1. **Request** → Full message history sent with each call
2. **Guardrails** → Check scope (legal, off-topic, injection)
3. **Context** → Extract constraints from conversation
4. **Retrieval** → Hybrid search over 377 products
5. **Generation** → Groq LLM or deterministic fallback
6. **Verification** → Validate schema & catalog integrity
7. **Response** → Schema-compliant recommendations

No stored state between requests. Safe to scale horizontally.

## Quality

- **Schema validation:** Pydantic strict mode (`extra="forbid"`)
- **Catalog integrity:** All URLs whitelisted, test_type from catalog
- **Recall metric:** Tracks coverage on public traces (C1-C10)
- **Behavior probes:** Tests for vague, legal, injection, add/drop cases
- **Deterministic fallback:** No LLM required; tests pass without API key
