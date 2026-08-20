"""Doctor directory — patients browse specialists, fees, and hours here."""
import streamlit as st

from services.doctor_service import list_doctors, format_availability_summary
from services.auth_service import list_specialties
from views.components import render_page_header, render_html


def _doctor_card_html(doc: dict, availability: str) -> str:
    fee_badge = f"₹{doc['consultation_fee']:.0f}" if doc["consultation_fee"] else "Fee not set"
    return f"""
        <div style="background:white; border-radius:16px; padding:1.1rem 1.3rem; margin-bottom:1rem;
                    box-shadow:0 4px 14px rgba(20,108,148,0.12); border:1px solid #d7edf5; height:100%;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div style="font-size:1.6rem;">{doc['specialty_icon']}</div>
                <div style="background:#19a7ce; color:white; border-radius:8px; padding:0.25rem 0.6rem;
                            font-weight:800; font-size:0.85rem;">{fee_badge}</div>
            </div>
            <div style="font-weight:900; font-size:1.15rem; color:#0b3d5c; margin-top:0.6rem;">{doc['full_name']}</div>
            <div style="color:#19a7ce; font-weight:700; font-size:0.9rem;">{doc['specialty']}</div>
            <div style="color:#5c8aa0; font-size:0.85rem; margin-top:0.2rem;">{doc['experience_years']} yrs experience</div>
            <div style="color:#5c8aa0; font-size:0.82rem; margin-top:0.5rem;">🕐 {availability}</div>
            <div style="color:#0b3d5c; font-size:0.88rem; margin-top:0.6rem;">{doc['bio'] or 'No bio provided.'}</div>
        </div>
    """


def render_doctors_view(on_book=None):
    """on_book: optional callback(doctor_id, specialty_id) called when a 'Book' button is clicked."""
    render_page_header("Doctors", "Browse specialists, fees and clinic hours", badge_text="IPCMS")

    specialties = list_specialties()

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        specialty_options = ["All specialties"] + [name for _, name in specialties]
        specialty_choice = st.selectbox("Specialty", specialty_options)
    with col2:
        search = st.text_input("Search by name", placeholder="e.g. Iyer")
    with col3:
        sort_choice = st.selectbox("Sort by", ["Fee: low to high", "Fee: high to low", "Most experienced", "Name"])

    specialty_id = None
    if specialty_choice != "All specialties":
        specialty_id = next(sid for sid, name in specialties if name == specialty_choice)

    sort_map = {
        "Fee: low to high": "fee_asc",
        "Fee: high to low": "fee_desc",
        "Most experienced": "experience_desc",
        "Name": "name",
    }
    doctors = list_doctors(specialty_id=specialty_id, search=search, sort=sort_map[sort_choice])

    st.caption(f"{len(doctors)} doctor(s)")

    if not doctors:
        st.info("No doctors match these filters.")
        return

    cols = st.columns(3)
    for i, doc in enumerate(doctors):
        availability = format_availability_summary(doc["id"])
        with cols[i % 3]:
            render_html(_doctor_card_html(doc, availability))
            if on_book and st.button("Book Appointment", key=f"book_doc_{doc['id']}", use_container_width=True):
                on_book(doc["id"], doc["specialty_id"])