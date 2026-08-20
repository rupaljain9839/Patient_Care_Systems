"""Admin landing page after login. Admins are the only ones who can create doctor accounts."""
from datetime import time

import streamlit as st

from core.database import session_scope
from models.models import User, Doctor, Specialty
from services.auth_service import register_doctor, list_specialties
from core.email_service import send_doctor_credentials_email
from services.health_service import get_admin_vitals_overview
from services.doctor_service import (
    list_all_doctor_slots,
    add_doctor_slot,
    delete_doctor_slot,
    DAY_FULL_NAMES,
    list_doctors_admin,
    update_doctor,
    set_doctor_active,
    delete_doctor_permanently,
)
from services.appointment_service import (
    get_admin_appointment_overview,
    get_all_appointments,
    cancel_appointment,
    get_busiest_doctors,
    get_staffing_gaps,
)
from services.enquiry_service import get_all_enquiries, update_enquiry_status, STATUS_OPTIONS
from services.pharmacy_service import (
    list_medicines,
    add_medicine,
    update_medicine,
    delete_medicine,
    get_all_orders,
    CATEGORIES as MED_CATEGORIES,
)
from services.lab_service import (
    list_lab_tests,
    add_lab_test,
    update_lab_test,
    delete_lab_test,
    get_all_bookings,
    get_all_reports,
    generate_lab_report_pdf,
    CATEGORIES as LAB_CATEGORIES,
)
from services.prescription_service import get_all_prescriptions, generate_prescription_pdf
from views.components import (
    render_stat_card,
    render_sidebar_brand,
    render_sidebar_user,
    render_page_header,
    render_html,
)

STATUS_COLORS = {"booked": "#19a7ce", "completed": "#2bb3a3", "cancelled": "#c62839"}
ENQUIRY_STATUS_COLORS = {"new": "#19a7ce", "contacted": "#e2824f", "resolved": "#2bb3a3"}


def _sidebar(user):
    if "admin_nav" not in st.session_state:
        st.session_state["admin_nav"] = "console"

    with st.sidebar:
        render_sidebar_brand()
        render_sidebar_user(user["full_name"], "Admin")

        if st.button("🛡 Admin Console", use_container_width=True):
            st.session_state["admin_nav"] = "console"
            st.rerun()
        if st.button("➕ Doctors", use_container_width=True):
            st.session_state["admin_nav"] = "doctors"
            st.rerun()
        if st.button("💊 Pharmacy", use_container_width=True):
            st.session_state["admin_nav"] = "pharmacy"
            st.rerun()
        if st.button("💬 SmartCare AI", use_container_width=True):
            st.session_state["admin_nav"] = "chat"
            st.rerun()

        st.write("")
        if st.button("↩ Log out", use_container_width=True):
            st.session_state.pop("user", None)
            st.session_state.pop("admin_nav", None)
            st.rerun()


def _analytics_tab():
    overview = get_admin_appointment_overview()

    col1, col2 = st.columns(2)
    with col1:
        render_stat_card("Total Appointments", overview["total"], "teal")
    with col2:
        render_stat_card("Upcoming Appointments", overview["upcoming"], "peach")

    if overview["per_day"]:
        st.write("")
        st.subheader("Appointments per day")
        st.bar_chart(overview["per_day"])

    col3, col4 = st.columns(2)
    with col3:
        if overview["by_status"]:
            st.subheader("By status")
            import plotly.graph_objects as go

            status_colors = {"booked": "#19a7ce", "completed": "#f0899a", "no_show": "#6e1622", "cancelled": "#e2824f"}
            labels = list(overview["by_status"].keys())
            values = list(overview["by_status"].values())
            colors = [status_colors.get(l, "#5c8aa0") for l in labels]

            fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.55, marker=dict(colors=colors))])
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
            st.plotly_chart(fig, use_container_width=True)
    with col4:
        if overview["by_specialty"]:
            st.subheader("By specialty")
            st.bar_chart(overview["by_specialty"])

    st.write("")
    col5, col6 = st.columns(2)
    with col5:
        st.subheader("Busiest doctors (upcoming)")
        busiest = get_busiest_doctors(limit=6)
        if busiest:
            st.bar_chart({name: count for name, count in busiest})
        else:
            st.info("No upcoming appointments yet.")
    with col6:
        st.subheader("Staffing gaps")
        gaps = get_staffing_gaps()
        if not gaps:
            st.success("Every specialty has a doctor with bookable hours.")
        else:
            st.warning(f"No bookable doctor for: {', '.join(gaps)}")

    st.divider()
    st.subheader("Vitals")
    vitals_overview = get_admin_vitals_overview()
    render_stat_card("Total Vitals Records", vitals_overview["total_records"], "rose")

    if vitals_overview["heart_rate_series"]:
        st.write("")
        import pandas as pd

        df = pd.DataFrame(vitals_overview["heart_rate_series"])
        avg_by_date = df.groupby("date")["heart_rate"].mean()
        st.subheader("Average Heart Rate Trend")
        st.line_chart(avg_by_date)


def _create_doctor_tab():
    specialties = list_specialties()
    if not specialties:
        st.warning("No specialties exist yet. Run seed_data.py, or add one in the Specialties tab first.")
    specialty_options = ["— None —"] + [name for _, name in specialties]

    with st.form("admin_add_doctor_form"):
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name")
            email = st.text_input("Email", help="This is the doctor's LOGIN email/username.")
            temp_password = st.text_input(
                "Temporary Password",
                type="password",
                help="Share this with the doctor directly; they can change it after logging in.",
            )
            phone = st.text_input("Phone")
            personal_email = st.text_input(
                "Personal Email (optional)",
                help="If provided, the login email and temporary password above will be emailed here automatically.",
            )
        with col2:
            gender = st.selectbox("Gender", ["Female", "Male", "Other", "Prefer not to say"])
            specialty_choice = st.selectbox("Specialty", specialty_options)
            years_experience = st.number_input("Years of Experience", min_value=0, max_value=60, step=1)
            consultation_fee = st.number_input("Consultation Fee", min_value=0.0, step=50.0)

        bio = st.text_area("Short Bio")
        submitted = st.form_submit_button("Create Doctor Account", use_container_width=True)

    if submitted:
        if not full_name or not email or not temp_password:
            st.error("Full name, email, and a temporary password are required.")
            return

        specialty_id = None
        if specialty_choice != "— None —":
            specialty_id = next(sid for sid, name in specialties if name == specialty_choice)

        result = register_doctor(
            full_name=full_name,
            email=email,
            password=temp_password,
            phone=phone,
            gender=gender,
            specialty_id=specialty_id,
            experience_years=int(years_experience),
            consultation_fee=float(consultation_fee),
            bio=bio,
        )
        if result.ok:
            st.success(f"{result.message} They can log in with the email and temporary password above.")
            if personal_email:
                email_result = send_doctor_credentials_email(
                    to_email=personal_email,
                    doctor_name=full_name,
                    login_email=email,
                    password=temp_password,
                    specialty=specialty_choice if specialty_choice != "— None —" else "",
                )
                if email_result.ok:
                    st.success(email_result.message)
                else:
                    st.warning(email_result.message)
        else:
            st.error(result.message)

    st.divider()
    st.subheader("Registered Doctors")
    with session_scope() as session:
        doctors = session.query(Doctor).all()
        if not doctors:
            st.info("No doctors registered yet — add one above.")
        for doc in doctors:
            c1, c2, c3 = st.columns([3, 2, 2])
            c1.write(f"**{doc.user.full_name}**")
            c2.write(doc.specialty.name if doc.specialty else "No specialty set")
            c3.write(f"{doc.experience_years or 0} yrs experience")


def _availability_tab():
    st.subheader("Set Doctor Availability")

    with session_scope() as session:
        doctors = session.query(Doctor).all()
        doctor_options = {d.user.full_name: d.id for d in doctors}

    if not doctor_options:
        st.info("No doctors registered yet — add one in the Create doctor tab first.")
        return

    with st.form("add_availability_form"):
        doctor_name = st.selectbox("Doctor", list(doctor_options.keys()))
        days = st.multiselect(
            "Days of week",
            options=list(range(7)),
            format_func=lambda i: DAY_FULL_NAMES[i],
        )
        col1, col2 = st.columns(2)
        with col1:
            start_time = st.time_input("Start time", value=time(9, 0))
        with col2:
            end_time = st.time_input("End time", value=time(13, 0))

        submitted = st.form_submit_button("Add Availability", use_container_width=True)

    if submitted:
        if not days:
            st.error("Select at least one day.")
        elif end_time <= start_time:
            st.error("End time must be after start time.")
        else:
            add_doctor_slot(doctor_options[doctor_name], days, start_time, end_time)
            st.success(f"Added availability for {doctor_name}.")
            st.rerun()

    st.divider()
    st.subheader("Existing Availability")
    slots = list_all_doctor_slots()
    if not slots:
        st.info("No availability set for any doctor yet — patients won't see any bookable slots until this is added.")
        return

    for s in slots:
        c1, c2, c3 = st.columns([3, 3, 1])
        c1.write(f"**{s['doctor_name']}**")
        c2.write(f"{s['day_name']} · {s['start_time'].strftime('%H:%M')}–{s['end_time'].strftime('%H:%M')}")
        if c3.button("Remove", key=f"del_slot_{s['id']}"):
            delete_doctor_slot(s["id"])
            st.rerun()


def _all_appointments_tab():
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Status", ["All", "Booked", "Completed", "Cancelled"])
    with col2:
        st.write("")

    appts = get_all_appointments(status_filter=status_filter)
    st.caption(f"{len(appts)} appointment(s)")

    if not appts:
        st.info("No appointments match this filter.")
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
                            <b style="color:#0b3d5c;">{a['patient_name']}</b>
                            <span style="color:#5c8aa0;"> with {a['doctor_name']} · {a['specialty']}</span>
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
            if a["status"] == "booked":
                if st.button("Cancel", key=f"admin_cancel_{a['id']}"):
                    cancel_appointment(a["id"])
                    st.rerun()


def _enquiries_tab():
    status_choice = st.selectbox("Filter by status", ["All"] + [s.title() for s in STATUS_OPTIONS])
    filter_value = None if status_choice == "All" else status_choice.lower()

    rows = get_all_enquiries(filter_value)
    st.caption(f"{len(rows)} enquiry(ies)")

    if not rows:
        st.info("No enquiries match this filter.")
        return

    for r in rows:
        color = ENQUIRY_STATUS_COLORS.get(r["status"], "#5c8aa0")
        message_html = (
            f'<div style="color:#5c8aa0; font-size:0.85rem; margin-top:0.3rem;">\u201c{r["message"]}\u201d</div>'
            if r["message"] != "—"
            else ""
        )
        submitted_str = r["created_at"].strftime("%d %b %Y, %I:%M %p") if r["created_at"] else ""

        c1, c2 = st.columns([5, 1])
        with c1:
            render_html(f"""
                <div style="background:white; border-radius:14px; padding:0.9rem 1.2rem; margin-bottom:0.7rem;
                            box-shadow:0 2px 10px rgba(20,108,148,0.1); border:1px solid #d7edf5;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <b style="color:#0b3d5c;">{r['patient_name']}</b>
                            <span style="color:#5c8aa0;"> · {r['phone']} · Preferred: {r['preferred_time']}</span>
                        </div>
                        <div style="background:{color}; color:white; border-radius:8px; padding:0.2rem 0.6rem;
                                    font-size:0.75rem; font-weight:800; text-transform:capitalize;">{r['status']}</div>
                    </div>
                    {message_html}
                    <div style="color:#93a3b8; font-size:0.78rem; margin-top:0.3rem;">{submitted_str}</div>
                </div>
            """)
        with c2:
            new_status = st.selectbox(
                "Status",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(r["status"]) if r["status"] in STATUS_OPTIONS else 0,
                key=f"enquiry_status_{r['id']}",
                label_visibility="collapsed",
            )
            if new_status != r["status"]:
                result = update_enquiry_status(r["id"], new_status)
                if result.ok:
                    st.rerun()


def _specialties_tab():
    with session_scope() as session:
        specialties = session.query(Specialty).order_by(Specialty.name).all()
        if not specialties:
            st.info("No specialties seeded yet. Run seed_data.py.")
        for s in specialties:
            st.write(f"{s.icon or ''} **{s.name}** — {s.description or 'No description'}")


def _render_doctors_management():
    from services.auth_service import list_specialties

    render_page_header("Doctors", "View, update, or remove doctors in the hospital", badge_text="PCMS-HS")

    search = st.text_input("Search by name", placeholder="e.g. Iyer")
    doctors = list_doctors_admin()
    if search:
        doctors = [d for d in doctors if search.lower() in d["full_name"].lower()]

    st.caption(f"{len(doctors)} doctor(s)")
    if not doctors:
        st.info("No doctors match this search.")
        return

    specialties = list_specialties()
    specialty_names = [name for _, name in specialties]

    for doc in doctors:
        status_color = "#2bb3a3" if doc["is_active"] else "#c62839"
        status_label = "Active" if doc["is_active"] else "Deactivated"

        render_html(f"""
            <div style="background:white; border-radius:14px; padding:1rem 1.3rem; margin-bottom:0.6rem;
                        box-shadow:0 2px 10px rgba(20,108,148,0.1); border:1px solid #d7edf5;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <b style="color:#0b3d5c; font-size:1.05rem;">{doc['full_name']}</b>
                        <span style="color:#19a7ce; font-weight:700;"> · {doc['specialty']}</span>
                    </div>
                    <div style="background:{status_color}; color:white; border-radius:8px; padding:0.2rem 0.7rem;
                                font-size:0.75rem; font-weight:800;">{status_label}</div>
                </div>
                <div style="color:#5c8aa0; font-size:0.85rem; margin-top:0.3rem;">
                    {doc['email']} · {doc['phone'] or 'No phone'} · {doc['experience_years']} yrs experience · ₹{doc['consultation_fee']:.0f}
                </div>
            </div>
        """)

        with st.expander(f"Edit / Manage — {doc['full_name']}"):
            with st.form(f"edit_doctor_{doc['id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_specialty = st.selectbox(
                        "Specialty", specialty_names,
                        index=specialty_names.index(doc["specialty"]) if doc["specialty"] in specialty_names else 0,
                        key=f"spec_{doc['id']}",
                    )
                    new_experience = st.number_input(
                        "Years of Experience", min_value=0, max_value=60, step=1,
                        value=doc["experience_years"], key=f"exp_{doc['id']}",
                    )
                with col2:
                    new_fee = st.number_input(
                        "Consultation Fee", min_value=0.0, step=50.0,
                        value=doc["consultation_fee"], key=f"fee_{doc['id']}",
                    )
                    new_phone = st.text_input("Phone", value=doc["phone"] or "", key=f"phone_{doc['id']}")

                new_bio = st.text_area("Bio", value=doc["bio"], key=f"bio_{doc['id']}")
                save = st.form_submit_button("Save changes", use_container_width=True)

            if save:
                new_specialty_id = next((sid for sid, name in specialties if name == new_specialty), None)
                ok, msg = update_doctor(
                    doc["id"],
                    specialty_id=new_specialty_id,
                    experience_years=int(new_experience),
                    consultation_fee=float(new_fee),
                    bio=new_bio,
                    phone=new_phone,
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                if doc["is_active"]:
                    if st.button("Deactivate", key=f"deactivate_{doc['id']}", use_container_width=True):
                        ok, msg = set_doctor_active(doc["user_id"], False)
                        st.success(msg) if ok else st.error(msg)
                        st.rerun()
                else:
                    if st.button("Reactivate", key=f"reactivate_{doc['id']}", use_container_width=True):
                        ok, msg = set_doctor_active(doc["user_id"], True)
                        st.success(msg) if ok else st.error(msg)
                        st.rerun()
            with c2:
                confirm_key = f"confirm_delete_{doc['id']}"
                if not st.session_state.get(confirm_key):
                    if st.button("Delete permanently", key=f"delete_{doc['id']}", use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    st.warning(f"Permanently delete {doc['full_name']}? This cannot be undone.")
                    yc, nc = st.columns(2)
                    with yc:
                        if st.button("Yes, delete", key=f"confirm_yes_{doc['id']}", use_container_width=True):
                            ok, msg = delete_doctor_permanently(doc["id"])
                            st.session_state.pop(confirm_key, None)
                            if ok:
                                st.success(msg)
                            else:
                                st.error(msg)
                            st.rerun()
                    with nc:
                        if st.button("Cancel", key=f"confirm_no_{doc['id']}", use_container_width=True):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()


def _render_console():
    render_page_header("Admin Console", "Full oversight of PCMS-HS", badge_text="PCMS-HS")

    with session_scope() as session:
        total_patients = session.query(User).filter(User.role == "patient").count()
        total_doctors = session.query(User).filter(User.role == "doctor").count()

    appt_overview = get_admin_appointment_overview()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_stat_card("Patients", total_patients, "pink")
    with col2:
        render_stat_card("Doctors", total_doctors, "rose")
    with col3:
        render_stat_card("Appointments", appt_overview["total"], "teal")
    with col4:
        render_stat_card("Upcoming", appt_overview["upcoming"], "peach")

    st.write("")
    tab_analytics, tab_create_doctor, tab_availability, tab_all_appts, tab_enquiries, tab_specialties = st.tabs(
        ["Analytics", "Create doctor", "Availability", "All appointments", "Enquiries", "Specialties"]
    )
    with tab_analytics:
        _analytics_tab()
    with tab_create_doctor:
        _create_doctor_tab()
    with tab_availability:
        _availability_tab()
    with tab_all_appts:
        _all_appointments_tab()
    with tab_enquiries:
        _enquiries_tab()
    with tab_specialties:
        _specialties_tab()


# ---------- Pharmacy: catalog management (admin edits) + oversight (admin reads only) ----------

def _medicines_tab():
    st.subheader("Add Medicine")
    with st.form("admin_add_medicine_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name")
            category = st.selectbox("Category", MED_CATEGORIES)
            price = st.number_input("Price (₹)", min_value=0.0, step=5.0)
        with col2:
            stock = st.number_input("Stock", min_value=0, step=1)
            icon = st.text_input("Icon (emoji fallback, shown if no image)", value="💊", max_chars=4)
        description = st.text_area("Description")
        image_file = st.file_uploader("Medicine Image (optional)", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("Add Medicine", use_container_width=True)

    if submitted:
        result = add_medicine(name, category, description, price, int(stock), icon, image_file=image_file)
        if result.ok:
            st.success(result.message)
            st.rerun()
        else:
            st.error(result.message)

    st.divider()
    st.subheader("Existing Medicines")
    medicines = list_medicines(active_only=False)
    if not medicines:
        st.info("No medicines added yet.")
        return

    for m in medicines:
        status_label = "Active" if m["is_active"] else "Hidden"
        status_color = "#2bb3a3" if m["is_active"] else "#c62839"

        col_img, col_info = st.columns([1, 5])
        with col_img:
            if m.get("image_url"):
                st.image(f"static/{m['image_url']}", width=70)
            else:
                st.markdown(f"<div style='font-size:2.2rem; text-align:center;'>{m['icon']}</div>", unsafe_allow_html=True)
        with col_info:
            render_html(f"""
                <div style="background:white; border-radius:14px; padding:1rem 1.3rem; margin-bottom:0.6rem;
                            box-shadow:0 2px 10px rgba(20,108,148,0.1); border:1px solid #d7edf5;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div><b style="color:#0b3d5c;">{m['name']}</b>
                            <span style="color:#19a7ce; font-weight:700;"> · {m['category']}</span>
                        </div>
                        <div style="background:{status_color}; color:white; border-radius:8px; padding:0.2rem 0.7rem;
                                    font-size:0.75rem; font-weight:800;">{status_label}</div>
                    </div>
                    <div style="color:#5c8aa0; font-size:0.85rem; margin-top:0.3rem;">
                        ₹{m['price']:.0f} · {m['stock']} in stock
                    </div>
                </div>
            """)
        with st.expander(f"Edit — {m['name']}"):
            with st.form(f"edit_medicine_{m['id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_price = st.number_input("Price (₹)", min_value=0.0, step=5.0, value=m["price"], key=f"med_price_{m['id']}")
                    new_stock = st.number_input("Stock", min_value=0, step=1, value=m["stock"], key=f"med_stock_{m['id']}")
                with col2:
                    new_category = st.selectbox("Category", MED_CATEGORIES, index=MED_CATEGORIES.index(m["category"]) if m["category"] in MED_CATEGORIES else 0, key=f"med_cat_{m['id']}")
                    new_icon = st.text_input("Icon (fallback)", value=m["icon"], max_chars=4, key=f"med_icon_{m['id']}")
                new_image_file = st.file_uploader("Replace image (optional)", type=["png", "jpg", "jpeg", "webp"], key=f"med_image_{m['id']}")
                save = st.form_submit_button("Save changes", use_container_width=True)

            if save:
                result = update_medicine(
                    m["id"], price=float(new_price), stock=int(new_stock),
                    category=new_category, icon=new_icon, image_file=new_image_file,
                )
                if result.ok:
                    st.success(result.message)
                    st.rerun()
                else:
                    st.error(result.message)

            c1, c2 = st.columns(2)
            with c1:
                new_active = not m["is_active"]
                if st.button("Reactivate" if not m["is_active"] else "Hide from patients", key=f"med_toggle_{m['id']}", use_container_width=True):
                    update_medicine(m["id"], is_active=new_active)
                    st.rerun()
            with c2:
                if st.button("Delete permanently", key=f"med_delete_{m['id']}", use_container_width=True):
                    result = delete_medicine(m["id"])
                    if result.ok:
                        st.success(result.message)
                    else:
                        st.error(result.message)
                    st.rerun()


def _lab_tests_tab():
    st.subheader("Add Lab Test")
    with st.form("admin_add_labtest_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Test Name")
            category = st.selectbox("Category", LAB_CATEGORIES)
        with col2:
            price = st.number_input("Price (₹)", min_value=0.0, step=50.0)
        description = st.text_area("Description")
        submitted = st.form_submit_button("Add Lab Test", use_container_width=True)

    if submitted:
        result = add_lab_test(name, category, description, price)
        if result.ok:
            st.success(result.message)
            st.rerun()
        else:
            st.error(result.message)

    st.divider()
    st.subheader("Existing Lab Tests")
    tests = list_lab_tests(active_only=False)
    if not tests:
        st.info("No lab tests added yet.")
        return

    for t in tests:
        status_label = "Active" if t["is_active"] else "Hidden"
        status_color = "#2bb3a3" if t["is_active"] else "#c62839"
        render_html(f"""
            <div style="background:white; border-radius:14px; padding:1rem 1.3rem; margin-bottom:0.6rem;
                        box-shadow:0 2px 10px rgba(20,108,148,0.1); border:1px solid #d7edf5;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div><b style="color:#0b3d5c;">{t['name']}</b>
                        <span style="color:#19a7ce; font-weight:700;"> · {t['category']}</span>
                    </div>
                    <div style="background:{status_color}; color:white; border-radius:8px; padding:0.2rem 0.7rem;
                                font-size:0.75rem; font-weight:800;">{status_label}</div>
                </div>
                <div style="color:#5c8aa0; font-size:0.85rem; margin-top:0.3rem;">₹{t['price']:.0f}</div>
            </div>
        """)
        with st.expander(f"Edit — {t['name']}"):
            with st.form(f"edit_labtest_{t['id']}"):
                new_price = st.number_input("Price (₹)", min_value=0.0, step=50.0, value=t["price"], key=f"lab_price_{t['id']}")
                new_category = st.selectbox("Category", LAB_CATEGORIES, index=LAB_CATEGORIES.index(t["category"]) if t["category"] in LAB_CATEGORIES else 0, key=f"lab_cat_{t['id']}")
                save = st.form_submit_button("Save changes", use_container_width=True)

            if save:
                result = update_lab_test(t["id"], price=float(new_price), category=new_category)
                if result.ok:
                    st.success(result.message)
                    st.rerun()
                else:
                    st.error(result.message)

            c1, c2 = st.columns(2)
            with c1:
                new_active = not t["is_active"]
                if st.button("Reactivate" if not t["is_active"] else "Hide from patients", key=f"lab_toggle_{t['id']}", use_container_width=True):
                    update_lab_test(t["id"], is_active=new_active)
                    st.rerun()
            with c2:
                if st.button("Delete permanently", key=f"lab_delete_{t['id']}", use_container_width=True):
                    result = delete_lab_test(t["id"])
                    if result.ok:
                        st.success(result.message)
                    else:
                        st.error(result.message)
                    st.rerun()


def _medicine_orders_tab():
    st.caption("Read-only — orders are placed by patients, not editable here.")
    orders = get_all_orders()
    if not orders:
        st.info("No medicine orders yet.")
        return
    for o in orders:
        items_str = ", ".join(f"{i['name']} × {i['quantity']}" for i in o["items"])
        st.write(f"**Order #{o['id']}** — {o['patient_name']} · {o['status'].title()} · ₹{o['total_amount']:.0f}")
        st.caption(f"{items_str} · {o['created_at'].strftime('%d %b %Y') if o['created_at'] else ''}")
        st.divider()


def _lab_bookings_tab():
    st.caption("Read-only — bookings are made by patients, reports are issued by doctors.")
    status_choice = st.selectbox("Filter by status", ["All", "Pending", "Completed", "Cancelled"], key="admin_lab_booking_filter")
    bookings = get_all_bookings(status_filter=status_choice)
    if not bookings:
        st.info("No lab bookings match this filter.")
        return
    for b in bookings:
        st.write(f"**{b['test_name']}** — {b['patient_name']} · {b['status'].title()}")
        st.caption(b["created_at"].strftime("%d %b %Y") if b["created_at"] else "")
        st.divider()


def _prescriptions_oversight_tab():
    st.caption("Read-only — only doctors can write prescriptions.")
    prescriptions = get_all_prescriptions()
    if not prescriptions:
        st.info("No prescriptions issued yet.")
        return
    for p in prescriptions:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.write(f"**{p['patient_name']}** — Dr. {p['doctor_name']} · {p['diagnosis']}")
            st.caption(p["created_at"].strftime("%d %b %Y") if p["created_at"] else "")
        with c2:
            st.download_button(
                "📄 PDF", data=generate_prescription_pdf(p["id"]),
                file_name=f"prescription_{p['id']}.pdf", mime="application/pdf",
                key=f"admin_presc_pdf_{p['id']}", use_container_width=True,
            )
        if p["notes"]:
            st.caption(f"Notes: {p['notes']}")
        if p["items"]:
            st.table([
                {"Medicine": i["medicine_name"], "Dosage": i["dosage"] or "—",
                 "Frequency": i["frequency"] or "—", "Duration": i["duration"] or "—",
                 "Instructions": i["instructions"] or "—"}
                for i in p["items"]
            ])
        st.divider()


def _lab_reports_oversight_tab():
    st.caption("Read-only — only doctors can issue lab reports.")
    reports = get_all_reports()
    if not reports:
        st.info("No lab reports issued yet.")
        return
    for r in reports:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.write(f"**{r['test_name']}** — {r['patient_name']} · Dr. {r['doctor_name']}")
            st.caption(r["created_at"].strftime("%d %b %Y") if r["created_at"] else "")
        with c2:
            st.download_button(
                "📄 PDF", data=generate_lab_report_pdf(r["id"]),
                file_name=f"lab_report_{r['id']}.pdf", mime="application/pdf",
                key=f"admin_lab_pdf_{r['id']}", use_container_width=True,
            )
        if r["result_summary"]:
            st.write(f"**Result:** {r['result_summary']}")
        if r["findings"]:
            st.write(f"**Findings:** {r['findings']}")
        if r["recommendation"]:
            st.write(f"**Recommendation:** {r['recommendation']}")
        st.divider()


def _render_pharmacy():
    render_page_header("Pharmacy", "Manage the medicine and lab test catalog", badge_text="PCMS-HS")

    tab_meds, tab_labs, tab_orders, tab_bookings, tab_rx, tab_reports = st.tabs(
        ["Medicines", "Lab Tests", "Medicine Orders", "Lab Bookings", "Prescriptions", "Lab Reports"]
    )
    with tab_meds:
        _medicines_tab()
    with tab_labs:
        _lab_tests_tab()
    with tab_orders:
        _medicine_orders_tab()
    with tab_bookings:
        _lab_bookings_tab()
    with tab_rx:
        _prescriptions_oversight_tab()
    with tab_reports:
        _lab_reports_oversight_tab()


def render_admin_portal():
    user = st.session_state["user"]
    _sidebar(user)

    nav = st.session_state.get("admin_nav")

    if nav == "chat":
        from views.chatbot_view import render_chatbot
        render_chatbot(user)
        return

    if nav == "doctors":
        _render_doctors_management()
        return

    if nav == "pharmacy":
        _render_pharmacy()
        return

    _render_console()