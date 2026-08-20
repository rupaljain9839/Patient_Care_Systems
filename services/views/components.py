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
import streamlit as st


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


def render_sidebar_brand(app_name: str = "IPCMS", tagline: str = "Integrated Patient Care Management System"):
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