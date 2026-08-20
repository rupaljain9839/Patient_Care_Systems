"""SmartCare AI chat interface — shared across patient, doctor, and admin roles."""
import hashlib
import traceback

import streamlit as st

from services.chat_service import save_message, get_history, clear_history
from ai.smartcare_agent import generate_response
from ai.voice import speech_to_text_input
from core.ocr_service import extract_text_from_image
from views.components import render_page_header, render_speak_button, render_autoplay_and_stop

SUGGESTED_QUESTIONS = {
    "patient": [
        "What medicines have I been prescribed?",
        "What did my last lab report say?",
        "I want to order a medicine",
        "Book me a lab test",
        "Is my heart rate normal?",
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
        render_page_header("SmartCare AI", SUBTITLES.get(role, SUBTITLES["patient"]), badge_text="PCMS-HS")
    with button_col:
        st.write("")
        if st.button("🆕 New Chat", use_container_width=True):
            clear_history(user["id"])
            st.session_state.pop("smartcare_pending", None)
            st.session_state.pop("smartcare_last_voice_ts", None)
            st.session_state.pop("smartcare_doc_text", None)
            st.session_state.pop("smartcare_doc_name", None)
            st.session_state.pop("smartcare_doc_hash", None)
            st.rerun()

    st.caption(DISCLAIMERS.get(role, DISCLAIMERS["patient"]))

    history = get_history(user["id"], limit=50)

    for i, turn in enumerate(history):
        avatar = user_avatar if turn["role"] == "user" else bot_avatar
        with st.chat_message("user" if turn["role"] == "user" else "assistant", avatar=avatar):
            st.write(turn["content"])
            if turn["role"] == "assistant":
                render_speak_button(turn["content"], key=f"listen_hist_{i}")

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

    st.markdown('<div class="smartcare-input-bar-marker"></div>', unsafe_allow_html=True)
    with st.container():
        if role == "patient" and st.session_state.get("smartcare_doc_text"):
            att_col1, att_col2 = st.columns([6, 1])
            with att_col1:
                st.caption(f"📎 Attached: **{st.session_state.get('smartcare_doc_name', 'document')}** — ask me anything about it.")
            with att_col2:
                if st.button("✕ Remove", key="smartcare_doc_remove", use_container_width=True):
                    st.session_state.pop("smartcare_doc_text", None)
                    st.session_state.pop("smartcare_doc_name", None)
                    st.session_state.pop("smartcare_doc_hash", None)
                    st.rerun()

        show_upload = role == "patient" and not st.session_state.get("smartcare_doc_text")
        if show_upload:
            col_upload, col_input, col_mic = st.columns([1, 5, 1])
        else:
            col_input, col_mic = st.columns([6, 1])

        if show_upload:
            with col_upload:
                uploaded_doc = st.file_uploader(
                    "Attach", type=["jpg", "jpeg", "png"], key="smartcare_doc_uploader",
                    label_visibility="collapsed",
                )
                if uploaded_doc is not None:
                    doc_bytes = uploaded_doc.getvalue()
                    doc_hash = hashlib.md5(doc_bytes).hexdigest()
                    if st.session_state.get("smartcare_doc_hash") != doc_hash:
                        with st.spinner("Reading the image..."):
                            try:
                                extracted = extract_text_from_image(doc_bytes)
                            except Exception as e:
                                extracted = None
                                st.error(f"Couldn't read that image: {e}")
                        if extracted:
                            st.session_state["smartcare_doc_text"] = extracted
                            st.session_state["smartcare_doc_name"] = uploaded_doc.name
                            st.session_state["smartcare_doc_hash"] = doc_hash
                            st.rerun()
                        elif extracted is not None:
                            st.warning("No readable text was found in that image. Try a clearer, better-lit photo.")

        with col_input:
            with st.form("smartcare_send_form", clear_on_submit=True, border=False):
                form_col1, form_col2 = st.columns([6, 1])
                with form_col1:
                    typed_message = st.text_input(
                        "Message", value="", key="smartcare_typed_input",
                        placeholder="Ask SmartCare AI...", label_visibility="collapsed",
                    )
                with form_col2:
                    sent = st.form_submit_button("↑", use_container_width=True)
        with col_mic:
            voice_result = speech_to_text_input(key="smartcare_voice")

    if voice_result and isinstance(voice_result, dict):
        transcript = (voice_result.get("text") or "").strip()
        ts = voice_result.get("ts")
        if transcript and st.session_state.get("smartcare_last_voice_ts") != ts:
            st.session_state["smartcare_last_voice_ts"] = ts
            st.session_state["smartcare_pending"] = transcript
            st.rerun()

    user_message = pending_message or (typed_message.strip() if sent and typed_message.strip() else None)

    if user_message:
        save_message(user["id"], "user", user_message)
        with st.chat_message("user", avatar=user_avatar):
            st.write(user_message)

        with st.chat_message("assistant", avatar=bot_avatar):
            with st.spinner("Thinking..."):
                had_error = False
                try:
                    history_for_llm = [{"role": t["role"], "content": t["content"]} for t in history]
                    document_context = st.session_state.get("smartcare_doc_text") if role == "patient" else None
                    answer = generate_response(user, user_message, history_for_llm, document_context=document_context)
                except Exception:
                    had_error = True
                    print("[SmartCare AI] generate_response() failed for the chat UI:")
                    traceback.print_exc()
                    answer = (
                        "Sorry, I ran into a hiccup processing that. Please try again in a "
                        "moment, or rephrase your question."
                    )
                st.write(answer)
                if not had_error:
                    render_autoplay_and_stop(answer, key=f"latest_{len(history)}")

        save_message(user["id"], "assistant", answer)

    st.markdown('<div style="height:120px;"></div>', unsafe_allow_html=True)