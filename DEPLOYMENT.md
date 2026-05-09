# SHL AI Recommender - Deployment Guide

This document describes how to build, test, and deploy the SHL AI Conversational Assessment Recommender API.

## Quick Start

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and set GROQ_API_KEY
   export GROQ_API_KEY=your_key_here
   ```

3. **Run tests:**
   ```bash
   # Run all tests (no GROQ key required; uses deterministic fallback)
   pytest tests/ -q

   # Run smoke tests only
   pytest tests/test_smoke.py -v

   # Run with verbose output and Recall@10 summary
   pytest tests/test_regression.py::test_recall_summary -s
   ```

4. **Start development server:**
   ```bash
   uvicorn app.main:app --reload
   ```
   - Server runs at `http://localhost:8000`
   - API docs: `http://localhost:8000/docs`

### Docker Deployment

1. **Build Docker image:**
   ```bash
   docker build -t shl-recommender:latest .
   ```

2. **Run container:**
   ```bash
   docker run -d \
     --name shl-api \
     -p 8000:8000 \
     -e GROQ_API_KEY=your_key_here \
     shl-recommender:latest
   ```

3. **Verify health:**
   ```bash
   curl http://localhost:8000/health
   ```

## Production Configuration

### Environment Variables

Set these in your deployment environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | (required) | Your Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Primary reasoning model |
| `GROQ_FALLBACK_MODEL` | `llama-3.1-8b-instant` | Fast fallback model |
| `GROQ_FAST_MODEL` | `llama-3.1-8b-instant` | Quick classifier model |
| `CATALOG_PATH` | `Data/shl_product_catalog.json` | Path to catalog JSON |
| `CHAT_TIMEOUT_SECONDS` | `25` | Request timeout (must be < 30) |

### Startup

The application automatically:
- Loads and indexes the SHL product catalog at startup
- Validates all 377 products and builds URL whitelist
- Initializes retrieval and context extraction engines
- Configures request logging middleware

Startup time: ~2-3 seconds (catalog warm-load)

### Health Check

```bash
GET /health

# Returns:
{"status": "ok"}
```

The health endpoint:
- Returns immediately (sub-100ms)
- Does not depend on LLM availability
- Suitable for load balancer health checks

### Request Logging

The application logs all HTTP requests in the format:
```
2026-05-09 12:34:56,789 INFO [app.request] POST /chat - 200 (1.23s)
```

Logs do **not** include:
- User conversation content
- Product recommendations
- Personal/sensitive data

Only endpoint, method, status code, and duration are logged.

## API Endpoints

### POST /chat

Request:
```json
{
  "messages": [
    {"role": "user", "content": "Hiring senior Java engineer..."},
    {"role": "assistant", "content": "Recommended: ..."}
  ]
}
```

Response:
```json
{
  "reply": "Agent response text",
  "recommendations": [
    {
      "name": "Product Name",
      "url": "https://www.shl.com/products/product-catalog/view/...",
      "test_type": "K"
    }
  ],
  "end_of_conversation": false
}
```

**Guarantees:**
- ✅ Response always contains all three fields
- ✅ `recommendations` is always a list (never null)
- ✅ Recommendations are 0-10 items
- ✅ All URLs are in SHL catalog whitelist
- ✅ Response completed within 25 seconds

## Testing

### Pre-Deployment Smoke Test

Run this before going live:

```bash
# Run all smoke tests
pytest tests/test_smoke.py -v

# Expected: all 12 tests pass
#   - Health endpoint responsive
#   - Chat endpoint with various inputs
#   - Invalid request rejection
#   - URL whitelist enforcement
#   - Schema compliance
```

### Regression Tests (C1-C10)

```bash
# Run all C1-C10 conversation replays
pytest tests/test_regression.py -v

# Shows Recall@10 for each trace
pytest tests/test_regression.py::test_recall_summary -s
```

**Quality gates:**
- All 50 regression tests must pass
- Mean Recall@10 ≥ 0.7 across all traces
- Current performance: Mean Recall@10 = 0.87

### Behavior Probes

```bash
# Run edge-case behavior tests
pytest tests/test_behavior_probes.py -v

# Covers:
#   - Vague requests → clarification
#   - Legal questions → refusal
#   - Prompt injection → refusal
#   - Add/drop actions → shortlist updates
#   - Finalization → end_of_conversation=True
```

## Scaling & Performance

### Throughput

- **Catalog loading:** 2-3 seconds (once per startup)
- **Per-request latency:** 
  - Vague clarification: 0.5-1s (no LLM call)
  - Full recommendation: 2-5s (Groq API latency)
  - Timeout fallback: <25s (safe response)

### Concurrency

- Stateless API: scale horizontally
- Each request is independent
- No shared state between requests
- Safe to run multiple instances behind a load balancer

### Resource Requirements

Minimum (1 instance):
- CPU: 1 core
- Memory: 512 MB (catalog + dependencies)
- Disk: 50 MB (code + catalog JSON)

### Monitoring

Key metrics to monitor:

```bash
# Request latency
tail -f app.log | grep "POST /chat"

# Error rate
grep "ERROR" app.log | wc -l

# LLM failures (fallback used)
grep "Groq error" app.log

# Catalog integrity
curl http://localhost:8000/health
```

## Troubleshooting

### Catalog fails to load

```
Error: "Could not parse catalog JSON"
```

**Solution:**
- Ensure `Data/shl_product_catalog.json` exists
- Check for malformed JSON: `python -m json.tool Data/shl_product_catalog.json`
- Run catalog loader tests: `pytest tests/test_catalog_loader.py -v`

### Groq API errors

```
Error: "Groq API error: rate_limit_exceeded"
```

**Solution:**
- Check API key: `export GROQ_API_KEY=sk_...`
- Check quota at https://console.groq.com
- System falls back to deterministic responder automatically
- Run with `GROQ_API_KEY="" pytest tests/` to test fallback

### High latency (>10s per request)

**Causes:**
- Groq API slowdown (check https://status.groq.com)
- Network latency
- Catalog retrieval overhead (first request slower)

**Solution:**
- Ensure `CHAT_TIMEOUT_SECONDS=25` (gives buffer)
- Add request caching if deploying behind a CDN
- Monitor with: `pytest tests/test_smoke.py::test_health_fast -v`

### Container build fails

```
Error: "python:3.12-slim not found"
```

**Solution:**
- Ensure Docker is running
- Pull latest images: `docker pull python:3.12-slim`
- Check Dockerfile: `cat Dockerfile`

## Deployment Checklist

- [ ] Environment variables set (GROQ_API_KEY, etc.)
- [ ] All tests pass: `pytest tests/ -q`
- [ ] Smoke tests pass: `pytest tests/test_smoke.py -v`
- [ ] Catalog loads without errors: check startup logs
- [ ] `/health` responds (test locally first)
- [ ] Docker image builds: `docker build -t shl-recommender .`
- [ ] Docker image runs: `docker run ... shl-recommender`
- [ ] Load balancer can reach health endpoint
- [ ] Logging configured and monitored
- [ ] Rate limiting in place (if behind API gateway)
- [ ] GROQ_API_KEY is secret (not in Docker image)

## Support

For issues during deployment:

1. Check logs: `docker logs shl-api` or `tail -f app.log`
2. Run tests locally: `pytest tests/test_smoke.py -v`
3. Verify catalog: `python -c "from app.catalog import load_catalog; c = load_catalog(); print(f'{len(c.products)} products')"
4. Test API endpoint: `curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"messages": [{"role": "user", "content": "Java engineer"}]}'`

## Architecture Notes

The deployment uses a stateless design:
- No persistent state between requests
- Full conversation history sent with every request
- Catalog indexed once at startup
- Safe for horizontal scaling
- 30-second timeout boundary (API returns safely at 25s)

This approach ensures reliability without complex state management or session storage.
