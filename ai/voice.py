"""Speech-to-text for SmartCare AI's push-to-talk voice input — FREE version.

Uses the browser's own Web Speech API (SpeechRecognition) via a small static
Streamlit component (ai/voice_component/index.html) — no server round-trip, no
API key, no per-minute cost. Works in Chrome and Edge; Safari has partial
support; Firefox does not support it (the component shows a friendly fallback
message and the patient can still type).

Design is unchanged from the paid version: whatever text comes back is handed to
the SAME generate_response() pipeline used for typed messages (see
views/chatbot_view.py), so voice still gets every existing tool for free —
appointments, prescriptions, orders, lab bookings, all of it.
"""
import os

import streamlit.components.v1 as components

_component_dir = os.path.join(os.path.dirname(__file__), "voice_component")
_voice_component = components.declare_component("smartcare_voice_input", path=_component_dir)


def speech_to_text_input(lang: str = "en-US", key: str = None):
    """Renders the mic button. Returns None until the browser finishes recognizing
    speech, then returns {"text": str, "ts": int} — ts changes on every new
    utterance (including a repeated phrase), so callers can dedupe reliably by
    comparing ts to the last one they processed rather than by text content."""
    return _voice_component(lang=lang, key=key, default=None)