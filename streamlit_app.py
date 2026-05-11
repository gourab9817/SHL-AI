"""Streamlit frontend for SHL AI Conversational Recommender."""

import requests
import streamlit as st

from app.chat_history import build_assistant_history_content

st.set_page_config(
    page_title="SHL Assessment Recommender",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* ── Base & global text color ────────────────────────────── */
    * { box-sizing: border-box; }

    /* Force light background everywhere */
    html, body,
    [data-testid="stAppViewContainer"],
    [data-testid="stMainBlockContainer"],
    .main, .block-container {
        background-color: #f8fafc !important;
        color: #1f2937 !important;
    }

    [data-testid="stHeader"] { background: transparent !important; }

    /* Global text override — defeats Streamlit dark-theme inheritance */
    p, span, div, h1, h2, h3, h4, h5, h6, li, label, small {
        color: #1f2937;
    }

    /* ── App header ──────────────────────────────────────────── */
    .app-header {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white !important;
        padding: 28px 32px;
        border-radius: 16px;
        margin-bottom: 16px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.28);
    }
    .app-header h1,
    .app-header p { color: white !important; }
    .app-header h1 { font-size: 1.65em; font-weight: 700; margin: 0 0 6px; }
    .app-header p  { font-size: 0.92em; opacity: 0.9; margin: 0; }

    /* ── Control buttons ─────────────────────────────────────── */
    .stButton > button {
        background: white !important;
        color: #374151 !important;
        border: 1.5px solid #e5e7eb !important;
        border-radius: 10px !important;
        padding: 8px 14px !important;
        font-weight: 500 !important;
        font-size: 0.87em !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
        transition: all 0.18s !important;
    }
    .stButton > button:hover {
        border-color: #6366f1 !important;
        color: #6366f1 !important;
        background: #f5f3ff !important;
        box-shadow: 0 3px 10px rgba(99, 102, 241, 0.15) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Chat message container ──────────────────────────────── */
    [data-testid="stChatMessage"] {
        background: white !important;
        border-radius: 14px !important;
        padding: 14px 18px !important;
        margin: 6px 0 !important;
        box-shadow: 0 1px 5px rgba(0,0,0,0.07) !important;
        border: 1px solid #f0f4f8 !important;
    }

    /* Force dark text inside every chat bubble */
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] span,
    [data-testid="stChatMessage"] div,
    [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] strong {
        color: #1f2937 !important;
    }

    /* ── Recommendation cards ────────────────────────────────── */
    .rec-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-left: 4px solid #6366f1;
        padding: 14px 16px;
        border-radius: 10px;
        margin: 8px 0;
        transition: all 0.18s;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }
    .rec-card:hover {
        box-shadow: 0 5px 14px rgba(99, 102, 241, 0.13);
        border-left-color: #8b5cf6;
        transform: translateX(3px);
    }
    .rec-name {
        font-weight: 600;
        color: #1f2937 !important;
        font-size: 0.95em;
        margin-bottom: 4px;
    }
    .rec-type {
        display: inline-block;
        background: #f3f4f6;
        color: #6b7280 !important;
        font-size: 0.78em;
        padding: 2px 8px;
        border-radius: 5px;
        margin-bottom: 8px;
    }
    .rec-link {
        color: #6366f1 !important;
        text-decoration: none;
        font-weight: 500;
        font-size: 0.87em;
    }
    .rec-link:hover { color: #8b5cf6 !important; text-decoration: underline; }

    /* ── Chat input ──────────────────────────────────────────── */
    /* Outer wrapper */
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] > div {
        background: white !important;
        border-radius: 14px !important;
    }
    /* The actual textarea */
    [data-testid="stChatInput"] textarea {
        font-size: 0.95em !important;
        color: #1f2937 !important;
        background: white !important;
        caret-color: #6366f1 !important;   /* visible blinking cursor */
        border: 1.5px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        outline: none !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12) !important;
    }
    [data-testid="stChatInput"] textarea::placeholder {
        color: #9ca3af !important;
    }

    /* ── Spinner ─────────────────────────────────────────────── */
    .stSpinner > div { border-top-color: #6366f1 !important; }

    /* ── Empty state ─────────────────────────────────────────── */
    .empty-state { text-align: center; padding: 60px 20px; }
    .empty-icon  { font-size: 3em; margin-bottom: 16px; }
    .empty-state h3 { font-size: 1.05em; color: #6b7280 !important; margin: 0 0 8px; font-weight: 600; }
    .empty-state p  { font-size: 0.88em; color: #9ca3af !important; margin: 0 0 20px; }
    .chip {
        display: inline-block;
        background: #f3f4f6;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.82em;
        color: #374151 !important;
        margin: 3px;
        border: 1px solid #e5e7eb;
    }

    /* ── Notification toasts ─────────────────────────────────── */
    [data-testid="stSuccess"],
    [data-testid="stInfo"],
    [data-testid="stError"] {
        border-radius: 10px !important;
        font-size: 0.9em !important;
        margin: 8px 0 !important;
    }

    /* ── Divider spacing ─────────────────────────────────────── */
    [data-testid="stDivider"] { margin: 6px 0 !important; }
</style>
""", unsafe_allow_html=True)

API_BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = f"{API_BASE_URL}/v2/chat1"


def check_health() -> bool:
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def call_api(messages: list[dict]) -> tuple[dict | None, str | None]:
    """POST /chat and return (data, error_message)."""
    try:
        api_msgs = []
        for message in messages:
            if message["role"] == "assistant":
                api_content = build_assistant_history_content(
                    str(message.get("content", "")),
                    message.get("recommendations", []),
                )
            else:
                api_content = str(message.get("content", ""))
            api_msgs.append({"role": message["role"], "content": api_content})
        r = requests.post(CHAT_ENDPOINT, json={"messages": api_msgs}, timeout=30)
        if r.status_code == 200:
            return r.json(), None
        return None, f"Server error ({r.status_code})"
    except requests.exceptions.Timeout:
        return None, "Request timed out — please try again."
    except Exception as exc:
        return None, f"Connection error: {exc}"


def render_assistant_content(msg: dict) -> None:
    """Render assistant reply, recommendation cards, and status badge."""
    if msg.get("content"):
        st.write(msg["content"])

    recs = msg.get("recommendations", [])
    if recs:
        st.markdown("---")
        st.markdown("**📊 Recommended Assessments**")
        for rec in recs:
            st.markdown(
                f"""<div class="rec-card">
                    <div class="rec-name">{rec['name']}</div>
                    <span class="rec-type">{rec['test_type']}</span><br>
                    <a href="{rec['url']}" target="_blank" class="rec-link">View on SHL →</a>
                </div>""",
                unsafe_allow_html=True,
            )

    eoc = msg.get("end_of_conversation", False)
    if eoc:
        st.success("✅ **Assessment Battery Locked** — Your selection is finalized. You can still adjust skills or the job description to regenerate it.")
    elif recs:
        st.info("💡 You can refine your selection — add skills, remove or swap assessments, or modify the job description.")


# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>🎯 SHL Assessment Recommender</h1>
    <p>Find the perfect assessments for your hiring needs</p>
</div>
""", unsafe_allow_html=True)

# ── Top controls ──────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    if st.button("⚡ Health Check", use_container_width=True):
        if check_health():
            st.success("API is healthy")
        else:
            st.error("API unavailable")
with c2:
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
with c3:
    st.markdown(
        "<a href='http://localhost:8000/docs' target='_blank' "
        "style='color:#6366f1; font-weight:500; font-size:0.88em; text-decoration:none;'>"
        "📖 API Documentation →</a>",
        unsafe_allow_html=True,
    )

st.divider()

# ── Conversation history ──────────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant", avatar="🎯"):
            render_assistant_content(msg)

# ── Empty state ───────────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="empty-state">
        <div class="empty-icon">🎯</div>
        <h3>Start a conversation</h3>
        <p>Describe a job role or hiring need and I'll recommend the right SHL assessments.</p>
        <div>
            <span class="chip">Senior Java developer</span>
            <span class="chip">Graduate trainee program</span>
            <span class="chip">Sales manager role</span>
            <span class="chip">Data scientist hire</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Chat input (Enter key works natively, stays pinned to bottom) ─────────────
if prompt := st.chat_input("Describe your hiring need or ask a question…"):
    # Show user message right away
    with st.chat_message("user"):
        st.write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Call API and stream the response into the assistant bubble
    with st.chat_message("assistant", avatar="🎯"):
        with st.spinner("Thinking…"):
            data, error = call_api(st.session_state.messages)

        if error:
            st.error(f"❌ {error}")
            st.session_state.messages.pop()          # roll back the user message
        else:
            assistant_msg: dict = {
                "role": "assistant",
                "content": data.get("reply", ""),
                "recommendations": data.get("recommendations", []),
                "end_of_conversation": data.get("end_of_conversation", False),
            }
            render_assistant_content(assistant_msg)
            st.session_state.messages.append(assistant_msg)
