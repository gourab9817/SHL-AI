"""Streamlit frontend for SHL AI Conversational Recommender - ChatGPT-style UI."""

import json
import requests
import streamlit as st
from datetime import datetime

# Page config
st.set_page_config(
    page_title="SHL Assessment Recommender",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Modern minimal CSS
st.markdown("""
<style>
    * { margin: 0; padding: 0; }

    body {
        background-color: #ffffff;
    }

    .stChatMessage {
        padding: 12px 0;
    }

    .user-msg {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 16px;
        border-bottom-right-radius: 4px;
        margin-left: auto;
        margin-right: 0;
        max-width: 70%;
        word-wrap: break-word;
    }

    .assistant-msg {
        background: #f0f0f0;
        color: #333;
        padding: 12px 16px;
        border-radius: 16px;
        border-bottom-left-radius: 4px;
        margin-right: auto;
        margin-left: 0;
        max-width: 70%;
        word-wrap: break-word;
    }

    .rec-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 14px;
        border-radius: 8px;
        margin: 8px 0;
        border-left: 4px solid #667eea;
    }

    .rec-name {
        font-weight: 600;
        font-size: 0.95em;
        margin-bottom: 4px;
    }

    .rec-type {
        font-size: 0.85em;
        opacity: 0.9;
        margin-bottom: 8px;
    }

    .rec-link {
        color: white;
        text-decoration: none;
        font-size: 0.9em;
        padding: 4px 8px;
        background: rgba(255,255,255,0.2);
        border-radius: 4px;
        display: inline-block;
        transition: all 0.2s;
    }

    .rec-link:hover {
        background: rgba(255,255,255,0.3);
    }

    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        border-top: 1px solid #e0e0e0;
        padding: 16px;
        z-index: 100;
    }

    .chat-container {
        margin-bottom: 100px;
        padding: 24px;
    }

    h1, h2, h3 {
        color: #333;
    }

    .header {
        padding: 24px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 0;
        margin-bottom: 0;
    }

    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 24px;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }

    .stButton > button:hover {
        opacity: 0.9;
        transform: translateY(-2px);
    }

    .clear-btn {
        background: #ff6b6b !important;
    }

    .info-badge {
        background: #e3f2fd;
        color: #1976d2;
        padding: 12px 16px;
        border-radius: 8px;
        border-left: 4px solid #1976d2;
        margin: 12px 0;
    }

    .success-badge {
        background: #d4edda;
        color: #155724;
        padding: 12px 16px;
        border-radius: 8px;
        border-left: 4px solid #28a745;
        margin: 12px 0;
    }
</style>
""", unsafe_allow_html=True)

# Config
API_BASE_URL = "http://localhost:8000"
HEALTH_ENDPOINT = f"{API_BASE_URL}/health"
CHAT_ENDPOINT = f"{API_BASE_URL}/chat"

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

def check_health():
    """Check API health."""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        return response.status_code == 200
    except:
        return False

def send_message(user_input):
    """Send message to API and get response."""
    try:
        st.session_state.messages.append({"role": "user", "content": user_input})

        payload = {"messages": st.session_state.messages}
        response = requests.post(CHAT_ENDPOINT, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            st.session_state.messages.append({"role": "assistant", "content": data["reply"]})
            return data
        else:
            st.session_state.messages.pop()
            return None
    except requests.exceptions.Timeout:
        st.session_state.messages.pop()
        st.error("Request timeout. Please try again.")
        return None
    except Exception as e:
        st.session_state.messages.pop()
        st.error(f"Error: {str(e)}")
        return None

# Header
st.markdown("""
<div class="header" style="margin: -1rem -1rem 1rem -1rem; padding: 2rem;">
    <h1 style="margin-bottom: 0.5rem;">🎯 SHL Assessment Recommender</h1>
    <p style="margin: 0; opacity: 0.95;">Find the perfect assessments for your hiring needs</p>
</div>
""", unsafe_allow_html=True)

# Status row
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    if st.button("🔄 Check Health", use_container_width=True):
        status = check_health()
        if status:
            st.success("✅ API is healthy")
        else:
            st.error("❌ API unavailable")

with col2:
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

with col3:
    st.markdown("[📖 API Docs](http://localhost:8000/docs)", unsafe_allow_html=True)

st.divider()

# Chat display
chat_container = st.container()

with chat_container:
    if not st.session_state.messages:
        st.markdown("""
        <div style='text-align: center; padding: 60px 20px; color: #999;'>
            <p style='font-size: 1.2em; margin-bottom: 10px;'>No conversation yet</p>
            <p>Start by describing your hiring need below</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for message in st.session_state.messages:
            if message["role"] == "user":
                col1, col2 = st.columns([0.25, 0.75])
                with col2:
                    st.markdown(f"""
                    <div class="user-msg">{message["content"]}</div>
                    """, unsafe_allow_html=True)
            else:
                col1, col2 = st.columns([0.75, 0.25])
                with col1:
                    st.markdown(f"""
                    <div class="assistant-msg">{message["content"]}</div>
                    """, unsafe_allow_html=True)

st.divider()

# Input area
st.markdown("### Your message")
col1, col2 = st.columns([0.85, 0.15])

with col1:
    user_input = st.text_input(
        "Type here...",
        placeholder="e.g., Senior Java developer, graduate trainee, sales manager...",
        label_visibility="collapsed",
        key="input_field"
    )

with col2:
    send_clicked = st.button("Send", use_container_width=True)

if send_clicked and user_input.strip():
    response_data = send_message(user_input)

    if response_data:
        with chat_container:
            st.divider()

            # Display recommendations
            if response_data.get("recommendations"):
                st.markdown("### 📊 Recommended Assessments")

                cols = st.columns(1)
                with cols[0]:
                    for i, rec in enumerate(response_data["recommendations"], 1):
                        st.markdown(f"""
                        <div class="rec-card">
                            <div class="rec-name">{i}. {rec['name']}</div>
                            <div class="rec-type">Type: <strong>{rec['test_type']}</strong></div>
                            <a href="{rec['url']}" target="_blank" class="rec-link">View on SHL →</a>
                        </div>
                        """, unsafe_allow_html=True)

            # Status
            if response_data.get("end_of_conversation"):
                st.markdown("""
                <div class="success-badge">
                    ✅ <strong>Assessment Battery Locked</strong><br>
                    You can review and finalize your selection.
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="info-badge">
                    💡 <strong>Refine your selection</strong><br>
                    Ask to add, remove, or modify any assessments.
                </div>
                """, unsafe_allow_html=True)

        st.rerun()

# Footer
st.markdown("""
<div style='text-align: center; color: #999; font-size: 0.85em; margin-top: 60px; padding: 20px;'>
    <p>🚀 SHL Assessment Recommender | Powered by FastAPI + Streamlit</p>
</div>
""", unsafe_allow_html=True)
