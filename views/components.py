"""Reusable styled UI pieces shared across views. Styling comes from the
classes defined in core/theme.py (injected once via apply_theme() in app.py).

Two Streamlit HTML-rendering gotchas this file works around, permanently:

1. A <div> opened in one st.markdown() call and closed in a later, separate
   call (or with st.columns()/st.info() in between) does NOT nest correctly —
   each st.markdown() call is its own independent HTML fragment, so the
   browser auto-closes the dangling tag at the end of that call. Every
   function below builds ONE complete HTML string per call.

2. st.markdown() still runs Markdown parsing even with unsafe_allow_html=True,
   and any line indented 4+ spaces is treated as a code block — turning nicely
   -indented multi-line HTML into literal visible text for some elements.
   _compact() strips all indentation/newlines before every render call so this
   can never happen, regardless of how the Python source is formatted.
"""
import base64
import json

import streamlit as st
import streamlit.components.v1 as components


def _compact(html: str) -> str:
    return "".join(line.strip() for line in html.strip().splitlines())


def _md(html: str):
    st.markdown(_compact(html), unsafe_allow_html=True)


# Public aliases — other view files (appointments_view.py, doctors_view.py, etc.)
# should use these instead of duplicating the compaction logic.
compact_html = _compact
render_html = _md


# Light pastel fills for stat cards — paired with the dark, bold text color
# that .ipcms-stat-card .label / .value already define in core/theme.py.
LIGHT_FILLS = {
    "pink": ("#ffe3ec", "#ffcfe0"),
    "teal": ("#d7f5ef", "#bfeee2"),
    "peach": ("#ffe9d6", "#ffdab8"),
    "rose": ("#f7dde1", "#f0c7cf"),
}


def render_stat_card(label: str, value, fill: str = "pink"):
    c1, c2 = LIGHT_FILLS.get(fill, LIGHT_FILLS["pink"])
    _md(f"""
        <div class="ipcms-stat-card" style="background: linear-gradient(135deg, {c1} 0%, {c2} 100%);">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
        </div>
    """)


def render_sidebar_brand(app_name: str = "PCMS-HS", tagline: str = "Patient Care Management System for Healthcare Services"):
    _md(f"""
        <div class="ipcms-brand-box">
            <div class="icon">+</div>
            <div>
                <div class="name">{app_name}</div>
                <div class="tagline">{tagline}</div>
            </div>
        </div>
    """)


def render_sidebar_user(full_name: str, role_label: str):
    _md(f"""
        <div class="ipcms-user-box">
            <div class="name">{full_name}</div>
            <div class="role">{role_label}</div>
        </div>
    """)


def render_page_header(title: str, subtitle: str = "", badge_text: str = ""):
    badge_html = f'<div class="ipcms-header-badge">{badge_text}</div>' if badge_text else ""
    _md(f"""
        <div class="ipcms-header-card">
            <div>
                <div class="title">{title}</div>
                <div class="subtitle">{subtitle}</div>
            </div>
            {badge_html}
        </div>
    """)


def render_panel(label: str, body_html: str):
    """Single-call panel: label + body_html rendered together so the box actually wraps its content."""
    _md(f'<div class="ipcms-panel"><div class="panel-label">{label}</div>{_compact(body_html)}</div>')


def render_empty_panel(label: str, empty_message: str):
    render_panel(label, f'<div class="panel-empty">{empty_message}</div>')


def render_diagnosis_panel(label: str, diagnosis: str, blood_pressure: str, heart_rate: str):
    body = f"""
        <div class="panel-title">{diagnosis}</div>
        <div class="mini-stats">
            <div><div class="k">Blood pressure</div><div class="v">{blood_pressure}</div></div>
            <div><div class="k">Heart rate</div><div class="v">{heart_rate}</div></div>
        </div>
    """
    render_panel(label, body)


def _vitals_pill_html(label: str, value, unit: str = "") -> str:
    display = f"{value}{unit}" if value not in (None, "") else "—"
    return _compact(f"""
        <div class="ipcms-vitals-pill">
            <div class="k">{label}</div>
            <div class="v">{display}</div>
        </div>
    """)


def render_speak_button(text: str, key: str = ""):
    """A 'Listen' button that speaks `text` aloud using the browser's own
    speechSynthesis — no server round-trip, no API cost, no session state needed.
    Runs entirely client-side inside its own small iframe. Used for PAST messages,
    which should only be read aloud on request, not replayed automatically."""
    safe_text = json.dumps(text or "")
    html = f"""
        <div style="display:flex;">
            <button onclick='
                window.speechSynthesis.cancel();
                var msg = new SpeechSynthesisUtterance({safe_text});
                msg.rate = 1.0;
                window.speechSynthesis.speak(msg);
            ' style="
                display:flex; align-items:center; gap:0.35rem;
                background:#eaf7fb; color:#146c94; border:1px solid #b9e6f2;
                border-radius:8px; padding:0.3rem 0.7rem; font-size:0.8rem;
                font-weight:700; cursor:pointer;
            ">🔊 Listen</button>
        </div>
    """
    components.html(_compact(html), height=40)


def render_autoplay_and_stop(text: str, key: str):
    """Speaks `text` aloud AUTOMATICALLY the moment this renders, and shows a 'Stop'
    button (not 'Listen') to interrupt playback early — since speech has already
    started, the useful action is stopping it, not starting it again. Only call this
    for a message that JUST arrived (e.g. right after generate_response()) — calling
    it for history on every rerun would replay old answers every time the page
    refreshes, which render_speak_button avoids by staying manual."""
    safe_text = json.dumps(text or "")
    btn_id = f"scv-stop-{key}"
    html = f"""
        <div style="display:flex;">
            <button id="{btn_id}" style="
                display:flex; align-items:center; gap:0.35rem;
                background:#fdeeee; color:#b23b3b; border:1px solid #f3c9c9;
                border-radius:8px; padding:0.3rem 0.7rem; font-size:0.8rem;
                font-weight:700; cursor:pointer;
            ">⏹ Stop</button>
        </div>
        <script>
            (function() {{
                var synth = window.speechSynthesis;
                synth.cancel();
                var msg = new SpeechSynthesisUtterance({safe_text});
                msg.rate = 1.0;
                synth.speak(msg);
                document.getElementById("{btn_id}").onclick = function() {{
                    synth.cancel();
                }};
            }})();
        </script>
    """
    components.html(_compact(html), height=40)


def render_pdf_inline(pdf_bytes: bytes, height: int = 650):
    """Shows a PDF directly in the page (browser's native PDF viewer inside an
    iframe) instead of forcing a download. Works entirely client-side — the PDF
    bytes are base64-encoded into a data: URI, so there's no extra file to host
    or clean up."""
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{height}" '
        f'style="border:none; border-radius:14px; box-shadow:var(--ipcms-shadow-card);"></iframe>',
        unsafe_allow_html=True,
    )


def render_vitals_card(vitals: dict | None):
    """Heart-centered vitals display, built as ONE compacted HTML string (flexbox
    columns, not st.columns) so the whole thing renders inside the baby-pink box."""
    if not vitals:
        _md("""
            <div class="ipcms-vitals-wrap">
                <div class="ipcms-vitals-title">LIVE VITALS</div>
                <div class="panel-empty">No vitals recorded yet. Your doctor will add these after your next check-up.</div>
            </div>
        """)
        return

    left_col = (
        _vitals_pill_html("Blood Pressure", vitals.get("blood_pressure"), " mmHg" if vitals.get("blood_pressure") else "")
        + _vitals_pill_html("Troponin", vitals.get("troponin"), " ng/mL" if vitals.get("troponin") is not None else "")
        + _vitals_pill_html("Ejection Fraction", vitals.get("ejection_fraction"), "%" if vitals.get("ejection_fraction") is not None else "")
    )
    mid_col = (
        '<div style="text-align:center; font-size:4.5rem; line-height:1;">❤️</div>'
        + _vitals_pill_html("ECG / EKG", vitals.get("ecg_note"))
    )
    right_col = (
        _vitals_pill_html("Cardiac Output", vitals.get("cardiac_output"), " L/min" if vitals.get("cardiac_output") is not None else "")
        + _vitals_pill_html("Pulse Oximetry", vitals.get("pulse_oximetry"), "%" if vitals.get("pulse_oximetry") is not None else "")
        + _vitals_pill_html("Heart Rate", vitals.get("heart_rate"), " bpm" if vitals.get("heart_rate") is not None else "")
    )

    recorded_html = ""
    if vitals.get("recorded_at"):
        recorded_html = (
            f'<div style="margin-top:0.6rem; font-size:0.82rem; color:#a5707a;">'
            f'Last recorded: {vitals["recorded_at"].strftime("%d %b %Y, %I:%M %p")}</div>'
        )

    _md(f"""
        <div class="ipcms-vitals-wrap">
            <div class="ipcms-vitals-title">LIVE VITALS</div>
            <div style="display:flex; gap:1.2rem; align-items:flex-start;">
                <div style="flex:1; min-width:0;">{left_col}</div>
                <div style="flex:1; min-width:0;">{mid_col}</div>
                <div style="flex:1; min-width:0;">{right_col}</div>
            </div>
            {recorded_html}
        </div>
    """)