"""Doctor landing page after login."""
from datetime import date, timedelta

import streamlit as st

from core.database import session_scope
from models.models import Doctor
from services.health_service import search_patients, add_health_record, get_latest_vitals, get_doctor_patient_conditions
from services.appointment_service import (
    get_doctor_appointments,
    get_doctor_appointments_in_range,
    get_doctor_stats,
    update_appointment_status,
)
from services.prescription_service import create_prescription, get_doctor_prescriptions
from services.lab_service import get_pending_bookings_for_patient, create_lab_report
from views.components import (
    render_stat_card,
    render_vitals_card,
    render_sidebar_brand,
    render_sidebar_user,
    render_page_header,
    render_html,
)

STATUS_COLORS = {"booked": "#19a7ce", "completed": "#2bb3a3", "cancelled": "#c62839"}


def _sidebar(user):
    if "doctor_nav" not in st.session_state:
        st.session_state["doctor_nav"] = "portal"

    with st.sidebar:
        render_sidebar_brand()
        render_sidebar_user(user["full_name"], "Doctor")

        if st.button("🩺 Doctor Portal", use_container_width=True):
            st.session_state["doctor_nav"] = "portal"
            st.rerun()
        if st.button("📄 Write Prescription", use_container_width=True):
            st.session_state["doctor_nav"] = "prescription"
            st.rerun()
        if st.button("🧪 Issue Lab Report", use_container_width=True):
            st.session_state["doctor_nav"] = "lab_report"
            st.rerun()
        if st.button("➕ Doctors", use_container_width=True):
            st.session_state["doctor_nav"] = "doctors"
            st.rerun()
        if st.button("💬 SmartCare AI", use_container_width=True):
            st.session_state["doctor_nav"] = "chat"
            st.rerun()

        st.write("")
        if st.button("↩ Log out", use_container_width=True):
            st.session_state.pop("user", None)
            st.session_state.pop("doctor_nav", None)
            st.rerun()


def _week_calendar(doctor_user_id: int):
    if "doc_week_offset" not in st.session_state:
        st.session_state["doc_week_offset"] = 0

    nav1, nav2, nav3, nav4 = st.columns([1, 1, 2, 2])
    with nav1:
        if st.button("◀", use_container_width=True):
            st.session_state["doc_week_offset"] -= 1
            st.rerun()
    with nav2:
        if st.button("▶", use_container_width=True):
            st.session_state["doc_week_offset"] += 1
            st.rerun()
    with nav3:
        if st.button("Today", use_container_width=True):
            st.session_state["doc_week_offset"] = 0
            st.rerun()

    today = date.today()
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=st.session_state["doc_week_offset"])
    days = [week_start + timedelta(days=i) for i in range(7)]
    st.caption(f"{days[0].strftime('%d %b')} – {days[-1].strftime('%d %b %Y')}")

    appts = get_doctor_appointments_in_range(doctor_user_id, days[0], days[-1])
    by_date = {d: [] for d in days}
    for a in appts:
        if a["scheduled_date"] in by_date:
            by_date[a["scheduled_date"]].append(a)

    cols = st.columns(7)
    for i, d in enumerate(days):
        with cols[i]:
            is_today = d == today
            header_style = "background:#19a7ce; color:white;" if is_today else "background:white; color:#0b3d5c; border:1px solid #d7edf5;"
            day_appts = sorted(by_date[d], key=lambda x: x["start_time"])
            if day_appts:
                chips = "".join(
                    f'<div style="background:#dff3fa; border-radius:8px; padding:0.4rem 0.5rem; '
                    f'margin-bottom:0.35rem; font-size:0.72rem;"><b>{a["start_time"].strftime("%H:%M")}'
                    f'-{a["end_time"].strftime("%H:%M") if a["end_time"] else ""}</b><br>{a["patient_name"]}</div>'
                    for a in day_appts
                )
            else:
                chips = '<div style="color:#a5707a; font-size:0.7rem; padding-top:0.3rem;">—</div>'

            render_html(f"""
                <div style="{header_style} border-radius:10px; padding:0.5rem; text-align:center;
                            font-weight:800; font-size:0.75rem; margin-bottom:0.5rem;">
                    {d.strftime('%a')}<br>{d.strftime('%d %b')}
                </div>
                {chips}
            """)


def _appointments_tab(user):
    appts = get_doctor_appointments(user["id"], upcoming_only=True)
    if not appts:
        st.info("No upcoming appointments.")
        return

    for a in appts:
        color = STATUS_COLORS.get(a["status"], "#5c8aa0")
        c1, c2, c3 = st.columns([4, 1, 1])
        with c1:
            render_html(f"""
                <div style="background:white; border-radius:14px; padding:0.9rem 1.2rem; margin-bottom:0.7rem;
                            box-shadow:0 2px 10px rgba(20,108,148,0.1); border:1px solid #d7edf5;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <b style="color:#0b3d5c;">{a['patient_name']}</b>
                        <div style="background:{color}; color:white; border-radius:8px; padding:0.2rem 0.6rem;
                                    font-size:0.75rem; font-weight:800; text-transform:capitalize;">{a['status']}</div>
                    </div>
                    <div style="color:#5c8aa0; font-size:0.85rem; margin-top:0.3rem;">
                        {a['scheduled_date'].strftime('%A, %d %B %Y')} at {a['start_time'].strftime('%H:%M')}
                        {' · ' + a['reason'] if a['reason'] else ''}
                    </div>
                </div>
            """)
        with c2:
            if st.button("Complete", key=f"complete_{a['id']}"):
                update_appointment_status(a["id"], "completed")
                st.rerun()
        with c3:
            if st.button("Cancel", key=f"doc_cancel_{a['id']}"):
                update_appointment_status(a["id"], "cancelled")
                st.rerun()


def _analytics_tab(user):
    appts = get_doctor_appointments_in_range(user["id"], date.today() - timedelta(days=30), date.today() + timedelta(days=30))
    if not appts:
        st.info("No appointment data yet for analytics.")
        return

    per_day = {}
    by_status = {}
    for a in appts:
        d_key = a["scheduled_date"].isoformat()
        per_day[d_key] = per_day.get(d_key, 0) + 1
        by_status[a["status"]] = by_status.get(a["status"], 0) + 1

    st.subheader("Appointments per day (±30 days)")
    st.bar_chart(per_day)

    st.subheader("By status")
    st.bar_chart(by_status)


def _patient_conditions_tab(user):
    conditions = get_doctor_patient_conditions(user["id"])
    if not conditions:
        st.info("No patient conditions recorded yet — these come from vitals you've recorded.")
        return

    for c in conditions:
        render_html(f"""
            <div style="background:white; border-radius:14px; padding:0.9rem 1.2rem; margin-bottom:0.7rem;
                        box-shadow:0 2px 10px rgba(20,108,148,0.1); border:1px solid #d7edf5;">
                <b style="color:#0b3d5c;">{c['patient_name']}</b>
                <div style="color:#5c8aa0; font-size:0.88rem; margin-top:0.2rem;">{c['diagnosis']}</div>
            </div>
        """)


def _record_vitals_section(doctor_user_id: int):
    st.subheader("Record Patient Vitals")

    search_query = st.text_input("Search patient by name or email", key="patient_search")
    matches = search_patients(search_query, limit=8) if search_query else search_patients("", limit=8)

    if not matches:
        st.info("No patients found.")
        return

    options = {f"{m['full_name']} ({m['email']})": m["id"] for m in matches}
    selected_label = st.selectbox("Select Patient", list(options.keys()))
    selected_patient_id = options[selected_label]

    with st.expander("View this patient's latest vitals", expanded=False):
        render_vitals_card(get_latest_vitals(selected_patient_id))

    with st.form("record_vitals_form"):
        col1, col2 = st.columns(2)
        with col1:
            heart_rate = st.number_input("Heart Rate (bpm)", min_value=0, max_value=300, step=1, value=0)
            blood_pressure = st.text_input("Blood Pressure (e.g. 120/80)")
            troponin = st.number_input("Troponin (ng/mL)", min_value=0.0, step=0.001, format="%.3f")
            ejection_fraction = st.number_input("Ejection Fraction (%)", min_value=0, max_value=100, step=1, value=0)
        with col2:
            cardiac_output = st.number_input("Cardiac Output (L/min)", min_value=0.0, step=0.1, format="%.2f")
            pulse_oximetry = st.number_input("Pulse Oximetry (%)", min_value=0, max_value=100, step=1, value=0)
            ecg_note = st.text_input("ECG / EKG Note")
            diagnosis = st.text_input("Diagnosis")

        notes = st.text_area("Additional Notes")
        submitted = st.form_submit_button("Save Vitals", use_container_width=True)

    if submitted:
        result = add_health_record(
            patient_id=selected_patient_id,
            doctor_user_id=doctor_user_id,
            heart_rate=heart_rate or None,
            blood_pressure=blood_pressure,
            troponin=troponin or None,
            ejection_fraction=ejection_fraction or None,
            cardiac_output=cardiac_output or None,
            pulse_oximetry=pulse_oximetry or None,
            ecg_note=ecg_note,
            diagnosis=diagnosis,
            notes=notes,
        )
        if result.ok:
            st.success(result.message)
            st.rerun()
        else:
            st.error(result.message)


def _render_write_prescription(user):
    render_page_header("Write Prescription", "Issue a new prescription for a patient", badge_text="IPCMS")

    search_query = st.text_input("Search patient by name or email", key="rx_patient_search")
    matches = search_patients(search_query, limit=8) if search_query else search_patients("", limit=8)
    if not matches:
        st.info("No patients found.")
        return

    options = {f"{m['full_name']} ({m['email']})": m["id"] for m in matches}
    selected_label = st.selectbox("Select Patient", list(options.keys()), key="rx_patient_select")
    selected_patient_id = options[selected_label]

    diagnosis = st.text_input("Diagnosis", key="rx_diagnosis")
    notes = st.text_area("Additional Notes (optional)", key="rx_notes")

    if "rx_items" not in st.session_state:
        st.session_state["rx_items"] = [{"medicine_name": "", "dosage": "", "frequency": "", "duration": "", "instructions": ""}]

    st.write("**Medicines**")
    for i, item in enumerate(st.session_state["rx_items"]):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            item["medicine_name"] = st.text_input("Medicine", value=item["medicine_name"], key=f"rx_med_{i}")
        with c2:
            item["dosage"] = st.text_input("Dosage", value=item["dosage"], key=f"rx_dosage_{i}")
        with c3:
            item["frequency"] = st.text_input("Frequency", value=item["frequency"], key=f"rx_freq_{i}")
        with c4:
            item["duration"] = st.text_input("Duration", value=item["duration"], key=f"rx_duration_{i}")
        with c5:
            item["instructions"] = st.text_input("Instructions", value=item["instructions"], key=f"rx_instr_{i}")

    if st.button("+ Add another medicine", key="rx_add_item"):
        st.session_state["rx_items"].append({"medicine_name": "", "dosage": "", "frequency": "", "duration": "", "instructions": ""})
        st.rerun()

    st.write("")
    if st.button("Issue Prescription", key="rx_submit", type="primary", use_container_width=True):
        items = [i for i in st.session_state["rx_items"] if i["medicine_name"].strip()]
        result = create_prescription(user["id"], selected_patient_id, diagnosis, notes, items)
        if result.ok:
            st.success(result.message)
            st.session_state["rx_items"] = [{"medicine_name": "", "dosage": "", "frequency": "", "duration": "", "instructions": ""}]
            st.rerun()
        else:
            st.error(result.message)

    st.divider()
    st.subheader("Prescriptions you've issued")
    issued = get_doctor_prescriptions(user["id"])
    if not issued:
        st.info("No prescriptions issued yet.")
    else:
        for p in issued:
            st.write(f"**{p['patient_name']}** — {p['diagnosis']} · {p['created_at'].strftime('%d %b %Y') if p['created_at'] else ''}")


def _render_issue_lab_report(user):
    render_page_header("Issue Lab Report", "Enter results for a patient's lab test", badge_text="IPCMS")

    search_query = st.text_input("Search patient by name or email", key="lab_patient_search")
    matches = search_patients(search_query, limit=8) if search_query else search_patients("", limit=8)
    if not matches:
        st.info("No patients found.")
        return

    options = {f"{m['full_name']} ({m['email']})": m["id"] for m in matches}
    selected_label = st.selectbox("Select Patient", list(options.keys()), key="lab_patient_select")
    selected_patient_id = options[selected_label]

    pending = get_pending_bookings_for_patient(selected_patient_id)
    booking_id = None
    test_name = ""
    if pending:
        booking_options = {"— Write a report without a booking —": None}
        booking_options.update({f"{b['test_name']} (booking #{b['id']})": b["id"] for b in pending})
        booking_label = st.selectbox("Link to a pending booking (optional)", list(booking_options.keys()), key="lab_booking_select")
        booking_id = booking_options[booking_label]
        if booking_id:
            test_name = next(b["test_name"] for b in pending if b["id"] == booking_id)

    if not booking_id:
        test_name = st.text_input("Test Name", value=test_name, key="lab_test_name")

    result_summary = st.text_input("Result Summary", key="lab_result_summary")
    findings = st.text_area("Findings", key="lab_findings")
    recommendation = st.text_area("Recommendation", key="lab_recommendation")

    if st.button("Issue Lab Report", key="lab_submit", type="primary", use_container_width=True):
        result = create_lab_report(
            doctor_user_id=user["id"],
            patient_id=selected_patient_id,
            test_name=test_name,
            result_summary=result_summary,
            findings=findings,
            recommendation=recommendation,
            booking_id=booking_id,
        )
        if result.ok:
            st.success(result.message)
            st.rerun()
        else:
            st.error(result.message)


def render_doctor_portal():
    user = st.session_state["user"]
    _sidebar(user)

    nav = st.session_state.get("doctor_nav")

    if nav == "chat":
        from views.chatbot_view import render_chatbot
        render_chatbot(user)
        return

    if nav == "doctors":
        from views.doctors_view import render_doctors_view
        render_doctors_view()  # no on_book callback — doctors browse, they don't self-book
        return

    if nav == "prescription":
        _render_write_prescription(user)
        return

    if nav == "lab_report":
        _render_issue_lab_report(user)
        return

    with session_scope() as session:
        profile = session.query(Doctor).filter(Doctor.user_id == user["id"]).first()
        specialty_name = profile.specialty.name if (profile and profile.specialty) else "Not set"
        fee = profile.consultation_fee if profile else None
        experience = profile.experience_years if profile else None

    subtitle = f"{specialty_name}"
    if experience is not None:
        subtitle += f" · {experience} yrs experience"
    if fee:
        subtitle += f" · ₹{fee:.0f} per consultation"

    render_page_header(user["full_name"], subtitle, badge_text="IPCMS")

    stats = get_doctor_stats(user["id"])
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_stat_card("Today", stats["today"], "teal")
        if stats["today"] == 0:
            st.caption("nothing booked")
    with col2:
        render_stat_card("Upcoming", stats["upcoming"], "pink")
    with col3:
        render_stat_card("Completed", stats["completed"], "rose")
    with col4:
        render_stat_card("Unique patients", stats["unique_patients"], "peach")

    st.write("")
    tab_schedule, tab_appointments, tab_analytics, tab_conditions = st.tabs(
        ["Schedule", "Appointments", "Analytics", "Patient conditions"]
    )
    with tab_schedule:
        _week_calendar(user["id"])
    with tab_appointments:
        _appointments_tab(user)
    with tab_analytics:
        _analytics_tab(user)
    with tab_conditions:
        _patient_conditions_tab(user)

    st.divider()
    _record_vitals_section(user["id"])