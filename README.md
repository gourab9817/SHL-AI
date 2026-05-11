# SHL Assessment Recommender

> A conversational AI assistant that turns a vague hiring brief into a grounded SHL assessment shortlist — through dialogue, not a form.

[![Tests](https://img.shields.io/badge/tests-173%20passing-brightgreen)](tests/)
[![Recall@10](https://img.shields.io/badge/Recall%40IO-0.87-blue)](eval/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-purple)](https://langchain-ai.github.io/langgraph/)

**Live deployments**

| Service | URL |
|---|---|
| Chat UI | **https://shl-ai-frontend.onrender.com** |
| Backend API | https://shl-ai-backend-epl7.onrender.com |
| API Docs | https://shl-ai-backend-epl7.onrender.com/docs |

---

## What It Does

Most assessment selection tools ask you to fill in a form. This one has a conversation with you.

You describe a role — even vaguely — and the agent asks the one most useful follow-up question, then returns a shortlist of up to 10 SHL assessments from the live catalog. You can keep refining: add a skill, remove a test, change the seniority level, or ask it to compare two assessments. Every recommendation links directly to the SHL product catalog page.

The system handles all four behaviors the assignment specifies — **clarify, recommend, refine, compare** — plus a finalize state that locks the battery and signals `end_of_conversation: true`.

---

## Live UI

The Streamlit frontend at **https://shl-ai-frontend.onrender.com** is worth opening to see the full flow. It uses native `st.chat_message` components so the Enter key works naturally, the input stays pinned to the bottom, and recommendation cards render inline inside the assistant bubble with direct SHL links.

The backend URL is environment-configurable (`API_BASE_URL`), so the same frontend image runs locally and in production without code changes.

---

## Architecture

```
Recruiter
    |
    |  (full conversation history replayed every turn)
    v
Streamlit Chat UI  ──POST /v2/chat1──►  FastAPI
                                            |
                                    LangGraph Pipeline
                                            |
                          ┌─────────────────┼─────────────────┐
                          |                 |                 |
                  extract context    guardrails check   classify intent
                  (latest msg only)  (off-topic/inject)  (clarify/recommend
                                                          /refine/compare
                                                          /finalize)
                                                 |
                              ┌──────────────────┴──────────────────┐
                              |                                     |
                    Hybrid Retriever                     Deterministic reply
                    (alias rules + token overlap)        (greetings, compare,
                              |                           finalize)
                    LLM Shortlist + Reply
                    (gpt-oss-120b via Groq)
                    fallback → deterministic planner
                              |
                    Response Verifier
                    (URL whitelist, re-derive names)
                              |
                    { reply, recommendations[], end_of_conversation }
```

**Key design choice: the server is completely stateless.** No sessions, no database. The frontend serialises previous recommendations into the assistant message content before replaying history, so the backend always has what it needs to handle a refinement turn. The conversation *is* the state.

---

## Two API Endpoints

### `POST /chat` — Direct answer mode

No clarifying questions. Always returns a shortlist if there's enough context. Designed for evaluator automated traces.

### `POST /v2/chat1` — Conversational mode *(recommended)*

The main endpoint. The agent builds context over multiple turns and lets recruiters refine mid-conversation:

- Change the job title halfway through
- Add a skill that was missed
- Ask "make it shorter" or "drop the Java test"
- Ask "what's the difference between OPQ32r and GSA?"
- Say "that's the one" to finalize the battery

```bash
# Quick test against the live API
curl -X POST https://shl-ai-backend-epl7.onrender.com/v2/chat1 \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hiring a senior Python engineer"}]}'
```

Response schema (enforced with Pydantic):

```json
{
  "reply": "Here are 5 SHL assessments that match...",
  "recommendations": [
    {
      "name": "Python (New)",
      "url": "https://www.shl.com/solutions/products/...",
      "test_type": "K"
    }
  ],
  "end_of_conversation": false
}
```

---

## Retrieval

No vector embeddings. With 754 catalog products, deterministic token-overlap scoring is faster, fully reproducible, and easier to debug.

Each product is scored against the query across five weighted fields:

| Field | Weight |
|---|---|
| Product name | 9× |
| Assessment category | 2.5× |
| Job level | 2× |
| Description | 1.5× |
| Language | 1× |

Exact product name substring match adds **+120**. Report artifacts are penalised by **−12** unless the query asks for reports.

**Alias rules** (20+) are the biggest Recall@10 driver. Recruiter vocabulary almost never matches product names directly — "personality test" maps to `Occupational Personality Questionnaire OPQ32r`, "reasoning" maps to `SHL Verify Interactive G+`. Each alias rule also injects expansion terms into the query token set so related products surface without being named explicitly.

A **knowledge-test filter** runs post-retrieval: K-type products (skills assessments) are dropped if their technology isn't mentioned anywhere in the user's latest message. This prevents Java assessments appearing in Python/AWS shortlists.

---

## Prompt Design

Three separate prompts handle the three LLM call types (shortlist, clarify, compare). Two invariants are enforced at the system level:

1. **The LLM never sees URLs.** It returns product names; the `ResponseVerifier` resolves those to catalog URLs. Hallucinated links are structurally impossible.
2. **SHL training knowledge is explicitly blocked.** The system prompt forbids the model from using what it learned about SHL during pretraining — only catalog data in the current prompt is allowed. This matters because models will confidently describe products that don't exist in the current catalog.

The shortlist prompt returns `{"selected_names": [...], "reply": "..."}` as JSON. If the LLM returns empty output or invalid JSON, the deterministic planner result is served unchanged.

---

## Project Structure

```
app/
├── main.py                  # FastAPI app, /chat and /v2/chat1 endpoints
├── schemas.py               # Pydantic request/response types
├── config.py                # Settings (GROQ_API_KEY, model names, timeouts)
├── chat_history.py          # Serialises recommendations into history for stateless replay
├── agent/
│   ├── graph.py             # LangGraph 11-node state machine
│   ├── planner.py           # Deterministic shortlist builder + K-test filter
│   ├── responder.py         # Canned replies (greetings, clarify, compare, finalize)
│   └── state.py             # AgentState TypedDict
├── conversation/
│   ├── extractor.py         # Context extraction — role, skills, seniority, intent flags
│   └── types.py             # ConversationContext, ConversationActions, ConversationConstraints
├── retrieval/
│   ├── service.py           # CatalogRetriever — scoring engine
│   ├── aliases.py           # 20+ alias rules for recruiter vocabulary
│   └── tokenizer.py         # normalize_text, tokenize
├── llm/
│   ├── client.py            # Groq API client with fallback model
│   ├── generator.py         # LLMGenerator — shortlist, clarify, compare calls
│   └── prompts.py           # All prompt builders (URL-exclusion + catalog-only invariants)
├── guardrails/
│   └── service.py           # Off-topic, legal, injection, non-SHL pattern checks
├── verification/
│   └── verifier.py          # URL whitelist, name re-derive, count cap, schema repair
└── catalog/
    ├── loader.py             # Parses shl_product_catalog.json
    └── models.py             # CatalogProduct, CatalogIndex

eval/
├── recall_calculator.py     # Async Recall@10 harness
└── benchmark.py             # Full benchmark runner

Data/
└── shl_product_catalog.json # 754 SHL Individual Test Solutions

tests/
├── test_regression.py       # C1–C10 conversation replay + Recall@10
├── test_behavior_probes.py  # Vague, off-topic, injection, refine, compare edge cases
├── test_smoke.py            # Deployment validation (schema, health, URL whitelist)
└── fixtures/                # Sample conversations and ground truth

streamlit_app.py             # Chat frontend
docker-compose.yml           # Backend + frontend orchestration
Dockerfile                   # Backend image
Dockerfile.frontend          # Streamlit image
```

---

## Local Setup

```bash
# 1. Clone and create virtualenv
git clone https://github.com/gourab9817/SHL-AI
cd SHL-AI
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Set environment variables
cp .env.example .env
# Add your GROQ_API_KEY to .env

# 3a. Run backend only
uvicorn app.main:app --reload
# API at http://localhost:8000 | Docs at http://localhost:8000/docs

# 3b. Run backend + Streamlit UI together
./scripts/start_full_app.sh
# UI at http://localhost:8501
```

### Docker Compose

```bash
export GROQ_API_KEY=sk_...
docker-compose up --build
# Backend → http://localhost:8000
# Frontend → http://localhost:8501
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Required. Groq API key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Primary LLM |
| `GROQ_FALLBACK_MODEL` | `openai/gpt-oss-20b` | Fallback if primary fails |
| `CATALOG_PATH` | `Data/shl_product_catalog.json` | Catalog file location |
| `CHAT_TIMEOUT_SECONDS` | `25` | Per-request timeout |
| `API_BASE_URL` | `http://localhost:8000` | Frontend → backend URL |

---

## Testing

```bash
# Full suite — no API key required (173 tests)
pytest tests/ -q

# Individual suites
pytest tests/test_smoke.py -v           # Schema + URL whitelist checks
pytest tests/test_regression.py -v     # C1–C10 replay with Recall@10
pytest tests/test_behavior_probes.py -v # Edge cases and adversarial inputs

# Recall@10 summary table
pytest tests/test_regression.py::test_recall_summary -s

# Offline Recall@10 harness (requires GROQ_API_KEY)
python eval/recall_calculator.py --detailed
```

**Test results:**

| Suite | Count | Status |
|---|---|---|
| Smoke | 12 | ✅ All pass |
| Regression (Recall@10) | 10 traces | ✅ Mean 0.87 |
| Behavior probes | 151 | ✅ All pass |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + Uvicorn |
| Agent orchestration | LangGraph |
| LLM | OpenAI `gpt-oss-120b` via Groq API |
| Retrieval | Custom deterministic hybrid (no vectors) |
| Frontend | Streamlit |
| Containerisation | Docker + Docker Compose |
| Deployment | Render (separate backend + frontend services) |
| Testing | Pytest + async harness |

---

## Quality Guarantees

Every response that leaves the agent has passed through `ResponseVerifier`, which enforces:

- All recommendation URLs are in the catalog whitelist — no invented links
- Product names and test types are re-derived from the matched catalog record — LLM output is never trusted directly
- Clarify, compare, and refuse intents always return empty `recommendations: []`
- `end_of_conversation: true` only when the finalize intent has verified recommendations
- Recommendation count capped at 10

The deterministic fallback means all 173 tests pass without a Groq API key.

---
