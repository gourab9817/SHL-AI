"""Streamlit frontend for SHL AI Conversational Recommender."""

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

# Custom CSS
st.markdown("""
<style>
    .recommendation-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid #1f77b4;
    }
    .rec-name {
        font-weight: bold;
        color: #1f77b4;
    }
    .rec-type {
        font-size: 0.85em;
        color: #666;
    }
    .health-check {
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        margin: 10px 0;
    }
    .health-ok {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    .health-error {
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
    .message-box {
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #1976d2;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-left: 4px solid #757575;
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
if "conversation_active" not in st.session_state:
    st.session_state.conversation_active = False
if "health_status" not in st.session_state:
    st.session_state.health_status = None


def check_health():
    """Check API health."""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Health check failed: {str(e)}")
        return False


def send_message(user_input):
    """Send message to API and get response."""
    try:
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Prepare request
        payload = {
            "messages": [
                {"role": msg["role"], "content": msg["content"]}
                for msg in st.session_state.messages
            ]
        }

        # Call API
        response = requests.post(CHAT_ENDPOINT, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()

            # Add assistant message to history
            st.session_state.messages.append(
                {"role": "assistant", "content": data["reply"]}
            )

            return data
        else:
            st.error(f"API Error: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        st.error("Request timeout (>30s). Please try again.")
        st.session_state.messages.pop()  # Remove failed user message
        return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.session_state.messages.pop()  # Remove failed user message
        return None


# Header
st.markdown("# 🎯 SHL Assessment Recommender")
st.markdown("Find the right SHL assessments for your hiring needs")

# Sidebar with health check
with st.sidebar:
    st.markdown("## Status")

    # Health check button
    if st.button("🔄 Check Health", key="health_btn"):
        st.session_state.health_status = check_health()

    # Display health status
    if st.session_state.health_status is not None:
        if st.session_state.health_status:
            st.markdown(
                '<div class="health-check health-ok">✅ API is healthy</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="health-check health-error">❌ API is unavailable</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # Clear conversation button
    if st.button("🗑️ Clear Conversation", key="clear_btn"):
        st.session_state.messages = []
        st.session_state.conversation_active = False
        st.rerun()

    st.divider()
    st.markdown("**About**")
    st.markdown(
        """
    This tool helps you select the right SHL assessments for:
    - Leadership roles
    - Technical positions
    - Sales teams
    - Admin roles
    - Graduate programs
    - And more...
    """
    )

# Main content area
st.markdown("## Chat")

# Display conversation history
if st.session_state.messages:
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(
                f'<div class="message-box user-message"><b>You:</b> {message["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="message-box assistant-message"><b>Assistant:</b> {message["content"]}</div>',
                unsafe_allow_html=True,
            )

# Input area
st.divider()

# User input
col1, col2 = st.columns([0.9, 0.1])

with col1:
    user_input = st.text_input(
        "Enter your assessment need:",
        placeholder="e.g., Senior Java engineer, graduate trainee, contact center agent...",
        key="user_input",
    )

with col2:
    send_button = st.button("Send", key="send_btn", use_container_width=True)

# Process user input
if send_button and user_input:
    response_data = send_message(user_input)

    if response_data:
        # Display recommendations if any
        if response_data.get("recommendations"):
            st.markdown("### 📋 Recommended Assessments")

            for rec in response_data["recommendations"]:
                with st.container():
                    col1, col2 = st.columns([0.7, 0.3])
                    with col1:
                        st.markdown(
                            f"""
                        <div class="recommendation-box">
                            <div class="rec-name">✓ {rec['name']}</div>
                            <div class="rec-type">Type: {rec['test_type']}</div>
                            <a href="{rec['url']}" target="_blank">View on SHL →</a>
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )

            # Show end of conversation status
            if response_data.get("end_of_conversation"):
                st.success(
                    "✅ **Conversation Complete** - Your assessment battery is locked in!"
                )
            else:
                st.info("💡 You can refine this list by asking to add, drop, or modify items.")

        else:
            st.info("No recommendations at this time. The assistant may be asking for clarification.")

        # Rerun to show updated conversation
        st.rerun()

# Footer
st.divider()
st.markdown(
    """
<div style='text-align: center; color: #666; font-size: 0.9em;'>
    <p>🚀 SHL AI Recommender | Powered by FastAPI + Streamlit</p>
    <p>For more information, visit the <a href='http://localhost:8000/docs'>API Docs</a></p>
</div>
""",
    unsafe_allow_html=True,
)
