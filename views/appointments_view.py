"""Patient-facing appointments page — Book / Calendar / My appointments."""
from datetime import date, timedelta

import streamlit as st

from services.doctor_service import list_doctors
from services.auth_service import list_specialties
from services.appointment_service import (
    get_available_slots,
    get_slot_summary,
    book_appointment,
    get_patient_appointments,
    get_patient_appointments_in_range,
    get_next_appointment,
    cancel_appointment,
)
from views.components import render_page_header, render_html, compact_html

STATUS_COLORS = {"booked": "#19a7ce", "completed": "#2bb3a3", "cancelled": "#c62839"}


def _next_appointment_banner(patient_id: int):
    nxt = get_next_appointment(patient_id)
    if not nxt:
        return
    is_today = nxt["scheduled_date"] == date.today()
    badge = '<div style="background:#19a7ce; color:white; border-radius:10px; padding:0.4rem 0.9rem; font-weight:800; font-size:0.85rem;">Today</div>' if is_today else ""
    render_html(f"""
        <div style="background:white; border-radius:16px; padding:1.2rem 1.5rem; margin-bottom:1.2rem;
                    box-shadow:0 4px 16px rgba(20,108,148,0.12); border:1px solid #d7edf5;
                    display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div style="letter-spacing:0.1em; font-size:0.75rem; font-weight:800; color:#19a7ce;">NEXT APPOINTMENT</div>
                <div style="font-size:1.2rem; font-weight:900; color:#0b3d5c; margin-top:0.3rem;">
                    {nxt['doctor_name']} · {nxt['specialty']}
                </div>
                <div style="color:#5c8aa0; font-size:0.88rem; margin-top:0.2rem;">
                    {nxt['scheduled_date'].strftime('%A, %d %B')} at {nxt['start_time'].strftime('%H:%M')}
                    {' · ' + nxt['reason'] if nxt['reason'] else ''}
                </div>
            </div>
            {badge}
        </div>
    """)


def _book_tab(patient_id: int):
    specialties = list_specialties()
    if not specialties:
        st.warning("No specialties available yet.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        specialty_options = [name for _, name in specialties]
        default_idx = 0
        if st.session_state.get("appt_prefill_specialty_id"):
            for i, (sid, _) in enumerate(specialties):
                if sid == st.session_state["appt_prefill_specialty_id"]:
                    default_idx = i
                    break
        specialty_choice = st.selectbox("Specialty", specialty_options, index=default_idx)
    specialty_id = next(sid for sid, name in specialties if name == specialty_choice)

    doctors = list_doctors(specialty_id=specialty_id, sort="fee_asc")
    if not doctors:
        st.info("No doctors registered under this specialty yet.")
        return

    doctor_labels = [f"Dr. {d['full_name']} — ₹{d['consultation_fee']:.0f} · {d['experience_years']}y" for d in doctors]
    with col2:
        default_doc_idx = 0
        if st.session_state.get("appt_prefill_doctor_id"):
            for i, d in enumerate(doctors):
                if d["id"] == st.session_state["appt_prefill_doctor_id"]:
                    default_doc_idx = i
                    break
        doctor_choice = st.selectbox("Doctor", doctor_labels, index=default_doc_idx)
    doctor = doctors[doctor_labels.index(doctor_choice)]

    with col3:
        chosen_date = st.date_input("Date", min_value=date.today(), value=date.today())

    st.caption(f"ℹ️ {doctor['bio'] or 'No bio provided.'}")

    st.session_state.pop("appt_prefill_specialty_id", None)
    st.session_state.pop("appt_prefill_doctor_id", None)

    st.subheader("Available slots")
    total, free = get_slot_summary(doctor["id"], chosen_date)
    if total == 0:
        st.info(f"{doctor['full_name']} has no availability set for this day. Try another date or doctor.")
        return
    st.caption(f"{free} of {total} slots free")

    reason = st.text_input("Reason for visit (optional)")

    available = get_available_slots(doctor["id"], chosen_date)
    if not available:
        st.warning("All slots for this day are booked. Please pick another date.")
        return

    cols = st.columns(4)
    for i, slot_time in enumerate(available):
        with cols[i % 4]:
            if st.button(f"🕐 {slot_time.strftime('%H:%M')}", key=f"slot_{slot_time}", use_container_width=True):
                result = book_appointment(patient_id, doctor["id"], chosen_date, slot_time, reason)
                if result.ok:
                    st.success(result.message)
                    st.rerun()
                else:
                    st.error(result.message)


def _calendar_tab(patient_id: int):
    if "appt_month_offset" not in st.session_state:
        st.session_state["appt_month_offset"] = 0

    nav1, nav2, nav3 = st.columns([1, 1, 4])
    with nav1:
        if st.button("◀ Previous", use_container_width=True):
            st.session_state["appt_month_offset"] -= 1
            st.rerun()
    with nav2:
        if st.button("Today", use_container_width=True):
            st.session_state["appt_month_offset"] = 0
            st.rerun()
    with nav3:
        if st.button("Next ▶", use_container_width=False):
            st.session_state["appt_month_offset"] += 1
            st.rerun()

    today = date.today()
    # Step to the target month by offset, keeping day=1 to avoid month-length issues
    # (e.g. Jan 31 + 1 month would overflow into March otherwise).
    year = today.year
    month = today.month + st.session_state["appt_month_offset"]
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    first_of_month = date(year, month, 1)

    st.caption(first_of_month.strftime("%B %Y"))
    st.caption("Showing your own appointments only.")

    # Build a full 6-week (42-day) grid starting on the Monday on/before the 1st,
    # so every month — regardless of how many weeks it spans or which weekday it
    # starts on — renders as a complete, consistently-sized grid.
    grid_start = first_of_month - timedelta(days=first_of_month.weekday())
    days = [grid_start + timedelta(days=i) for i in range(42)]

    appts = get_patient_appointments_in_range(patient_id, days[0], days[-1])
    by_date = {d: [] for d in days}
    for a in appts:
        if a["scheduled_date"] in by_date:
            by_date[a["scheduled_date"]].append(a)

    weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for col, label in zip(header_cols, weekday_labels):
        col.markdown(
            f'<div style="text-align:center; font-weight:800; font-size:0.78rem; '
            f'color:var(--ipcms-text-muted); padding-bottom:0.3rem;">{label}</div>',
            unsafe_allow_html=True,
        )

    for week in range(6):
        cols = st.columns(7)
        for i in range(7):
            d = days[week * 7 + i]
            with cols[i]:
                is_today = d == today
                in_month = d.month == first_of_month.month
                day_appts = sorted(by_date[d], key=lambda x: x["start_time"])

                if is_today:
                    cell_style = "background:var(--ipcms-gradient); color:white;"
                elif not in_month:
                    cell_style = "background:transparent; color:#c3cae0;"
                else:
                    cell_style = "background:white; color:var(--ipcms-text-dark); border:1px solid rgba(91,110,245,0.08);"

                MAX_SHOWN = 2
                shown = day_appts[:MAX_SHOWN]
                extra = len(day_appts) - MAX_SHOWN
                badge_color = "rgba(255,255,255,0.22)" if is_today else "var(--ipcms-gradient-soft)"
                badge_text_color = "white" if is_today else "var(--ipcms-primary-dark)"
                chips = "".join(
                    compact_html(f"""
                        <div style="background:{badge_color}; color:{badge_text_color}; border-radius:6px;
                                    padding:0.15rem 0.35rem; margin-top:0.25rem; font-size:0.66rem;
                                    font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                            {a['start_time'].strftime('%H:%M')} {a['doctor_name'].split()[-1] if a['doctor_name'] else ''}
                        </div>
                    """)
                    for a in shown
                )
                if extra > 0:
                    more_color = "rgba(255,255,255,0.85)" if is_today else "var(--ipcms-text-muted)"
                    chips += f'<div style="font-size:0.62rem; color:{more_color}; margin-top:0.15rem;">+{extra} more</div>'

                render_html(f"""
                    <div style="{cell_style} border-radius:10px; padding:0.4rem 0.4rem 0.5rem;
                                min-height:74px; margin-bottom:0.4rem;">
                        <div style="font-weight:800; font-size:0.8rem;">{d.day}</div>
                        {chips}
                    </div>
                """)


def _my_appointments_tab(patient_id: int):
    appts = get_patient_appointments(patient_id, upcoming_only=False)
    if not appts:
        st.info("You haven't booked any appointments yet.")
        return

    for a in appts:
        color = STATUS_COLORS.get(a["status"], "#5c8aa0")
        c1, c2 = st.columns([5, 1])
        with c1:
            render_html(f"""
                <div style="background:white; border-radius:14px; padding:0.9rem 1.2rem; margin-bottom:0.7rem;
                            box-shadow:0 2px 10px rgba(20,108,148,0.1); border:1px solid #d7edf5;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <b style="color:#0b3d5c;">{a['doctor_name']}</b>
                            <span style="color:#5c8aa0;"> · {a['specialty']}</span>
                        </div>
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
            if a["status"] == "booked" and a["scheduled_date"] >= date.today():
                if st.button("Cancel", key=f"cancel_{a['id']}"):
                    result = cancel_appointment(a["id"], patient_id)
                    if result.ok:
                        st.success(result.message)
                        st.rerun()
                    else:
                        st.error(result.message)


def render_appointments_view(user):
    render_page_header("Appointments", "Book a slot and track your visits", badge_text="PCMS-HS")
    _next_appointment_banner(user["id"])

    tab_book, tab_calendar, tab_my = st.tabs(["Book", "Calendar", "My appointments"])
    with tab_book:
        _book_tab(user["id"])
    with tab_calendar:
        _calendar_tab(user["id"])
    with tab_my:
        _my_appointments_tab(user["id"])