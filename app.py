"""Streamlit entry point."""
import streamlit as st

from core.config import settings
from core.database import init_db
from core.theme import apply_theme
from views.auth_view import render_auth_view
from views.patient_dashboard import render_patient_dashboard
from views.doctor_portal import render_doctor_portal
from views.admin_portal import render_admin_portal

st.set_page_config(page_title=settings.app_name, page_icon="🩺", layout="wide")

apply_theme()

# Ensure tables exist (safe to call repeatedly).
init_db()

if "user" not in st.session_state:
    render_auth_view()
else:
    role = st.session_state["user"]["role"]
    if role == "patient":
        render_patient_dashboard()
    elif role == "doctor":
        render_doctor_portal()
    elif role == "admin":
        render_admin_portal()
    else:
        st.error("Unknown role. Please log out and log back in.")
        if st.button("Logout"):
            st.session_state.pop("user", None)
            st.rerun()