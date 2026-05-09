# SHL-AI

Conversational SHL assessment recommender for the AI Intern take-home assignment.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your `GROQ_API_KEY` to `.env` before enabling the LLM-backed stages.

## Run

```bash
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Test

```bash
pytest
```
