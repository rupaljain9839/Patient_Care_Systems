"""SmartCare AI chat interface — shared across patient, doctor, and admin roles."""
import streamlit as st

from services.chat_service import save_message, get_history, clear_history
from ai.smartcare_agent import generate_response
from views.components import render_page_header

SUGGESTED_QUESTIONS = {
    "patient": [
        "What does my blood pressure mean?",
        "Is my heart rate normal?",
        "What foods are heart-healthy?",
        "What should I do in a heart emergency?",
    ],
    "doctor": [
        "What's my schedule today?",
        "How many patients do I have this week?",
        "What's a normal ejection fraction range?",
        "Do I have any appointments with no reason listed?",
    ],
    "admin": [
        "How many appointments are booked this week?",
        "Which specialties have staffing gaps?",
        "Who are our busiest doctors right now?",
        "How many patients and doctors do we have?",
    ],
}

SUBTITLES = {
    "patient": "Ask about your heart-health vitals or general cardiac wellness",
    "doctor": "Ask about your schedule, patients, or clinical reference info",
    "admin": "Ask about appointment volume, staffing, and system-wide stats",
}

DISCLAIMERS = {
    "patient": (
        "This assistant gives general information only and is not a substitute for professional "
        "medical advice. In an emergency, call your local emergency number immediately."
    ),
    "doctor": "This assistant only has access to your own patients and schedule — not other doctors'.",
    "admin": "This assistant has access to system-wide operational stats only — not individual patient health data.",
}

AVATARS = {
    "user": {"patient": "🧑", "doctor": "🩺", "admin": "🛡"},
    "assistant": "💬",
}


def render_chatbot(user):
    role = user.get("role", "patient")
    user_avatar = AVATARS["user"].get(role, "🧑")
    bot_avatar = AVATARS["assistant"]

    header_col, button_col = st.columns([5, 1])
    with header_col:
        render_page_header("SmartCare AI", SUBTITLES.get(role, SUBTITLES["patient"]), badge_text="IPCMS")
    with button_col:
        st.write("")
        if st.button("🆕 New Chat", use_container_width=True):
            clear_history(user["id"])
            st.session_state.pop("smartcare_pending", None)
            st.rerun()

    st.caption(DISCLAIMERS.get(role, DISCLAIMERS["patient"]))

    history = get_history(user["id"], limit=50)

    for turn in history:
        avatar = user_avatar if turn["role"] == "user" else bot_avatar
        with st.chat_message("user" if turn["role"] == "user" else "assistant", avatar=avatar):
            st.write(turn["content"])

    pending_message = st.session_state.pop("smartcare_pending", None)

    if not history:
        st.write("")
        st.caption("Try asking:")
        questions = SUGGESTED_QUESTIONS.get(role, SUGGESTED_QUESTIONS["patient"])
        cols = st.columns(2)
        for i, question in enumerate(questions):
            with cols[i % 2]:
                if st.button(question, key=f"smartcare_suggest_{i}", use_container_width=True):
                    st.session_state["smartcare_pending"] = question
                    st.rerun()

    user_message = pending_message or st.chat_input("Ask SmartCare AI...")

    if user_message:
        save_message(user["id"], "user", user_message)
        with st.chat_message("user", avatar=user_avatar):
            st.write(user_message)

        with st.chat_message("assistant", avatar=bot_avatar):
            with st.spinner("Thinking..."):
                try:
                    history_for_llm = [{"role": t["role"], "content": t["content"]} for t in history]
                    answer = generate_response(user, user_message, history_for_llm)
                except Exception as e:
                    answer = (
                        f"Sorry, I couldn't process that right now ({e}). "
                        "Please try again in a moment."
                    )
                st.write(answer)

        save_message(user["id"], "assistant", answer)