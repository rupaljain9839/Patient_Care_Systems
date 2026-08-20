"""Patient landing page after login."""
import streamlit as st

from services.health_service import get_latest_vitals, get_vitals_history
from views.components import (
    render_stat_card,
    render_vitals_card,
    render_sidebar_brand,
    render_sidebar_user,
    render_page_header,
    render_empty_panel,
    render_diagnosis_panel,
)


def _sidebar(user):
    if "patient_nav" not in st.session_state:
        st.session_state["patient_nav"] = "health"

    with st.sidebar:
        render_sidebar_brand()
        render_sidebar_user(user["full_name"], "Patient")

        if st.button("🩺 My Health", use_container_width=True):
            st.session_state["patient_nav"] = "health"
            st.rerun()
        if st.button("📅 Appointments", use_container_width=True):
            st.session_state["patient_nav"] = "appointments"
            st.rerun()
        if st.button("➕ Doctors", use_container_width=True):
            st.session_state["patient_nav"] = "doctors"
            st.rerun()
        if st.button("💊 Pharmacy", use_container_width=True):
            st.session_state["patient_nav"] = "pharmacy"
            st.rerun()
        if st.button("📨 Send Query", use_container_width=True):
            st.session_state["patient_nav"] = "enquiry"
            st.rerun()
        if st.button("📷 Scan Document", use_container_width=True):
            st.session_state["patient_nav"] = "scan"
            st.rerun()
        if st.button("💬 SmartCare AI", use_container_width=True):
            st.session_state["patient_nav"] = "chat"
            st.rerun()

        st.write("")
        if st.button("↩ Log out", use_container_width=True):
            st.session_state.pop("user", None)
            st.session_state.pop("patient_nav", None)
            st.rerun()


def _next_appointment_panel(patient_id):
    from services.appointment_service import get_next_appointment

    nxt = get_next_appointment(patient_id)
    if not nxt:
        render_empty_panel("Next appointment", "No upcoming appointments. Book one from the Appointments page.")
        return

    from views.components import render_panel
    body = f"""
        <div class="panel-title">{nxt['doctor_name']} · {nxt['specialty']}</div>
        <div style="color:#5c8aa0; font-size:0.88rem; margin-top:0.3rem;">
            {nxt['scheduled_date'].strftime('%A, %d %B')} at {nxt['start_time'].strftime('%H:%M')}
        </div>
    """
    render_panel("Next appointment", body)


def _last_diagnosis_panel(latest):
    if not latest or not latest.get("diagnosis"):
        render_empty_panel("Last diagnosis", "No diagnosis recorded yet.")
        return

    bp = latest.get("blood_pressure") or "—"
    hr = f'{latest["heart_rate"]} bpm' if latest.get("heart_rate") is not None else "—"
    render_diagnosis_panel("Last diagnosis", latest["diagnosis"], bp, hr)


def _render_my_health(user):
    render_page_header(
        f"Welcome, {user['full_name'].split()[0]}!",
        "Your heart-health overview",
        badge_text="PCMS-HS",
    )

    history = get_vitals_history(user["id"], limit=100)
    latest = get_latest_vitals(user["id"])

    from services.appointment_service import get_patient_appointments
    upcoming_appts = get_patient_appointments(user["id"], upcoming_only=True)

    left, right = st.columns([2, 1])
    with left:
        render_vitals_card(latest)
    with right:
        _next_appointment_panel(user["id"])
        _last_diagnosis_panel(latest)

    if len(history) > 1:
        st.write("")
        st.subheader("Heart Rate Trend")
        chart_data = {
            r["recorded_at"].strftime("%b %d"): r["heart_rate"]
            for r in reversed(history)
            if r["heart_rate"] is not None
        }
        if chart_data:
            st.line_chart(chart_data)

    st.write("")
    col1, col2, col3 = st.columns(3)
    with col1:
        render_stat_card("Upcoming Appointments", len(upcoming_appts), "teal")
    with col2:
        render_stat_card("Recorded Check-ups", len(history), "pink")
    with col3:
        render_stat_card("Active Prescriptions", "0", "peach")


def render_patient_dashboard():
    user = st.session_state["user"]
    _sidebar(user)

    nav = st.session_state.get("patient_nav")
    if nav == "chat":
        from views.chatbot_view import render_chatbot
        render_chatbot(user)
    elif nav == "appointments":
        from views.appointments_view import render_appointments_view
        render_appointments_view(user)
    elif nav == "doctors":
        from views.doctors_view import render_doctors_view

        def _go_to_book(doctor_id, specialty_id):
            st.session_state["appt_prefill_doctor_id"] = doctor_id
            st.session_state["appt_prefill_specialty_id"] = specialty_id
            st.session_state["patient_nav"] = "appointments"
            st.rerun()

        render_doctors_view(on_book=_go_to_book)
    elif nav == "pharmacy":
        from views.pharmacy_view import render_pharmacy
        render_pharmacy(user)
    elif nav == "enquiry":
        from views.enquiry_view import render_enquiry
        render_enquiry(user)
    elif nav == "scan":
        from views.document_scan_view import render_document_scan
        render_document_scan(user)
    else:
        _render_my_health(user)