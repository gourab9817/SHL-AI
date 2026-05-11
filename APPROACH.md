# SHL Conversational Assessment Recommender — Approach Document

**Gourab Choudhury** · May 2026
**c.gourab180@gmail.com**
---

##  GITHUB  https://github.com/gourab9817/SHL-AI
## What I Built

A conversational hiring assistant that turns a vague job description into a grounded SHL assessment shortlist through dialogue. The system is fully deployed:

- **Backend API:** https://shl-ai-backend-epl7.onrender.com
- **Live UI:** https://shl-ai-frontend.onrender.com ← *worth opening — the chat experience shows the conversational flow end-to-end*

---

## System Architecture

```
Recruiter types a message
        |
        v
  [ Streamlit Chat UI ]  — white theme, pinned input, rec cards
        |
        | POST full conversation history every turn
        v
  [ FastAPI Backend ]
        |
        +-- /chat          → direct answer mode (no clarifying questions)
        |
        +-- /v2/chat1      → conversational mode  ← main endpoint
                |
                v
        [ LangGraph Pipeline ]

        1.  Read history  →  extract context (role, skills, seniority)
        2.  Guardrails    →  block off-topic / injection / legal
        3.  Intent        →  clarify? recommend? refine? compare? finalize?
        4a. If recommend/refine:
              retrieve top-15 from catalog  →  LLM selects & writes reply
              (if LLM fails → deterministic shortlist as fallback)
        4b. Otherwise:
              deterministic reply (greetings, comparisons, finalise)
        5.  Verify        →  URL whitelist check, re-derive names from catalog
        |
        v
  { reply, recommendations[], end_of_conversation }
```

---

## Two Endpoints, Two Modes

I deliberately exposed two separate endpoints to cover both evaluation scenarios:

**`POST /chat`** — stateless direct-answer mode. No clarifying questions, always returns a shortlist if there's any context to work with. Designed for the evaluator's automated traces.

**`POST /v2/chat1`** — conversational mode. This is the interesting one. The agent asks one focused question at a time, builds context over multiple turns, and lets the recruiter refine the shortlist mid-conversation: swap out assessments, add a skill, change the job title entirely. The entire context window is re-read from the message history on every request, so there's no server-side session to manage — the conversation *is* the state.

The insight here is that `/v2/chat1` behaves like a stateful assistant despite being completely stateless on the server. The frontend serialises previous recommendations into the assistant message content before replaying history, so the backend always has enough context to continue a refinement turn without any database.

---

## Frontend

The Streamlit UI at **https://shl-ai-frontend.onrender.com** is worth a look. A few deliberate decisions:

- Native `st.chat_message` / `st.chat_input` so the Enter key just works and the input box stays pinned to the bottom. Earlier versions used `st.text_input` + a submit button, which felt clunky and broke the conversational rhythm.
- Recommendation cards render inline in the assistant bubble with a direct SHL catalog link — recruiter doesn't need to go elsewhere to verify.
- End-of-conversation state shows a "Battery Locked" badge; in-progress states show a "You can still refine" nudge. These small affordances communicate where the user is in the flow without any explicit progress indicator.
- The backend URL is environment-configurable (`API_BASE_URL`), so local dev and production share the same frontend code.

---

## Retrieval: Why No Vectors

With 754 products, semantic embeddings felt like overhead I didn't need. Instead the retriever scores every product against the query using token overlap across five fields (name weighted 9×, test category 2.5×, job level 2×, description 1.5×, language 1×). Exact product name match gets a +120 bonus.

On top of that I wrote 20+ alias rules that fire on recruiter vocabulary. "Personality" boosts OPQ32r by 90 and injects the term "opq32r" into the query so related OPQ reports also surface. "Senior developer" fires a rule that pulls in G+, OPQ32r, and Smart Interview Live Coding together.

The alias layer was the biggest single Recall@10 improvement — domain vocabulary rarely overlaps with product names, and without it the retriever would miss obvious matches.

---

## Prompt Design

Three prompts: shortlist selection (returns JSON), clarification (one question, free text), comparison (prose, <180 words). Two invariants I enforced across all of them:

**The LLM never sees URLs.** It returns product names; a post-generation verifier resolves those names to catalog URLs. This makes hallucinated links structurally impossible — there's nowhere in the pipeline for a made-up URL to enter the response.

**Training knowledge about SHL is explicitly blocked.** The system prompt says "rely exclusively on the catalog data in this prompt." This matters because the model has absorbed SHL marketing copy during training and will confidently describe products that don't exist in the current catalog.

The shortlist prompt also includes a rule that prohibits Knowledge tests (type K) for technologies not mentioned in the hiring context. This fixed a consistent failure mode where Java assessments would appear in Python/AWS shortlists because both domains are "software engineering."

---

## What Didn't Work

**Extracting role/seniority from full conversation history** — worked fine in single-turn tests, broke badly in multi-turn conversations. If the recruiter described a CISO role on turn 2 and then asked about an office assistant on turn 4, the backend still saw "CISO" as the role. Fixed by scoping role, seniority, and skills to the *latest message only*.

**Llama 3.1 70B as the LLM** — JSON output was inconsistent and the model ignored the critical K-test rule frequently. Switched to `openai/gpt-oss-120b` served through Groq. Instruction-following improved substantially.

**Contains-match for identity patterns** — "who is" as a substring match flagged "hiring manager who is senior in finance" as an identity question and returned the greeting response. Fixed with startswith-only matching.

**Measured:** behavior probe pass rate went from ~60% (Llama, full-history extraction) to >95% after these fixes across the 10 reference conversations.

---

## Evaluation

Recall@10 is computed by `eval/recall_calculator.py` — an async harness that runs each sample conversation through the live agent and checks how many ground-truth products appear in the top-10 shortlist.

Beyond the metric, I ran all five behavior probes (vague query → clarify, off-topic → refuse, refinement → update not restart, compare → catalog-grounded prose, finalize → lock with `end_of_conversation: true`) manually against both the API and the deployed UI after each significant change.

---

## AI Tools Used

I used **Claude Code** (Anthropic's agentic CLI) as my main coding assistant throughout — architecture design, LangGraph wiring, alias rule authoring, debugging the hallucination issues, and rewriting the frontend. The hard parts (figuring out why full-history extraction caused role contamination, designing the two-endpoint split, the URL-exclusion invariant in prompts) came from reasoning through the problem together rather than just generating code.
