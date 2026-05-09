# Quick Start Guide

Get the SHL AI Recommender running in **2 minutes**.

## The Fastest Way: Docker Compose

```bash
# 1. Set your API key (optional for demo)
export GROQ_API_KEY=sk_...

# 2. Start everything
docker-compose up

# 3. Open browser
open http://localhost:8501
```

Done! 🎉

---

## Local Development (No Docker)

```bash
# 1. Install
pip install -r requirements.txt

# 2. Set API key (optional)
export GROQ_API_KEY=sk_...

# 3. Run
./scripts/start_full_app.sh

# 4. Open
open http://localhost:8501
```

---

## What You Get

| Component | Port | Purpose |
|-----------|------|---------|
| **Streamlit UI** | 8501 | Web interface (your browser) |
| **FastAPI Backend** | 8000 | API + Catalog |
| **Health Check** | `GET /health` | Verify API is running |

---

## Using the UI

### Step 1: Check Health
Click the **🔄 Check Health** button in the sidebar.
- Green ✅ = API is running
- Red ❌ = Start the backend

### Step 2: Start Chatting
Type in the input box: `"Senior Java engineer"`

Press **Send** or hit Enter.

### Step 3: Get Recommendations
The AI recommends assessments:
- Core Java (Advanced Level)
- Spring
- SQL
- AWS Development
- SHL Verify Interactive G+
- Occupational Personality Questionnaire OPQ32r

### Step 4: Refine (Optional)
Ask to add/drop items:
- "Add Docker"
- "Drop OPQ32r"
- "Make it shorter"

### Step 5: Confirm
Say "Perfect. Confirmed." to lock in your selection.

---

## Test Examples

### Example 1: Vague Start (AI Clarifies)
```
You: I need assessment
AI:  What role or position are you hiring for?
```

### Example 2: Full Detail (AI Recommends)
```
You: Senior backend engineer with Java, Spring, SQL, AWS
AI:  Here are recommendations...
     [Shows 5-7 assessments]
```

### Example 3: Refine Selection
```
You: Add Docker
AI:  Updated shortlist...
     [Shows updated list]
```

### Example 4: Finalize
```
You: Perfect. Confirmed. Locking it in.
AI:  ✅ Conversation Complete!
     [Shows end_of_conversation: true]
```

---

## Troubleshooting

### UI won't load (http://localhost:8501)
```bash
# Check if Streamlit is running
ps aux | grep streamlit

# If not, start manually
streamlit run streamlit_app.py
```

### "API is unavailable" (red ❌ in sidebar)
```bash
# Check if backend is running
curl http://localhost:8000/health

# If not, start in new terminal
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker won't start
```bash
# Check Docker is running
docker ps

# Try building again
docker build -t shl-recommender .
docker run -e GROQ_API_KEY=sk_... -p 8000:8000 -p 8501:8501 shl-recommender
```

---

## Full Documentation

- **[README.md](README.md)** - Overview, architecture, features
- **[STREAMLIT_UI.md](STREAMLIT_UI.md)** - Complete UI guide
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment
- **[BUILD_PLAN.md](BUILD_PLAN.md)** - Full architecture details

---

## What's Running

```
Browser (http://localhost:8501)
  ↓
Streamlit Frontend (Chat UI)
  ↓ (HTTP API calls)
FastAPI Backend (Port 8000)
  ↓
SHL Catalog (377 products indexed)
  ↓
Groq LLM (if API key set)
```

---

## Tests

```bash
# Run all tests
pytest tests/ -q

# Run just smoke tests
pytest tests/test_smoke.py -v

# View Recall@10 metric
pytest tests/test_regression.py::test_recall_summary -s
```

All 173 tests pass ✅

---

## API Endpoints

If you want to call the API directly (without Streamlit):

```bash
# Health check
curl http://localhost:8000/health

# Chat
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "messages": [
      {"role": "user", "content": "Senior Java engineer"}
    ]
  }'

# API Docs
open http://localhost:8000/docs
```

---

## Next Steps

✅ **Working locally?**
→ See [DEPLOYMENT.md](DEPLOYMENT.md) for production setup

✅ **Want to customize the UI?**
→ Edit `streamlit_app.py` (easy to modify)

✅ **Need more details?**
→ See [STREAMLIT_UI.md](STREAMLIT_UI.md)

---

## Quick Commands Reference

```bash
# Start everything (fastest)
docker-compose up

# Start locally with auto-reload
./scripts/start_full_app.sh

# Run tests
pytest tests/ -q

# View API docs
open http://localhost:8000/docs

# Check backend health
curl http://localhost:8000/health

# Clear conversation (in UI)
Click "🗑️ Clear Conversation" button
```

---

## System Requirements

- Docker: OR
- Python 3.12+ with pip

That's it! ✅

---

**Happy assessing!** 🎯
