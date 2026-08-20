"""Login and registration UI. On success, sets st.session_state['user'] and reruns.
Doctor accounts are created by admins only (see views/admin_portal.py)."""
import datetime as dt

import streamlit as st

from services.auth_service import authenticate, register_patient


def _set_logged_in_user(user_id: int, role: str):
    from services.auth_service import get_user_summary

    st.session_state["user"] = get_user_summary(user_id)
    st.rerun()


def _login_form():
    st.subheader("Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Please enter both email and password.")
            return

        result = authenticate(email, password)
        if result.ok:
            st.success(result.message)
            _set_logged_in_user(result.user_id, result.role)
        else:
            st.error(result.message)


def _patient_register_form():
    st.subheader("Patient Registration")
    with st.form("patient_register_form"):
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
        with col2:
            phone = st.text_input("Phone")
            gender = st.selectbox("Gender", ["Female", "Male", "Other", "Prefer not to say"])
            dob = st.date_input(
                "Date of Birth",
                min_value=dt.date(1900, 1, 1),
                max_value=dt.date.today(),
                value=dt.date(2000, 1, 1),
            )

        st.caption("Password must be 8+ characters with an uppercase letter, a number, and a special character.")
        submitted = st.form_submit_button("Create Patient Account", use_container_width=True)

    if submitted:
        if not full_name or not email or not password:
            st.error("Full name, email, and password are required.")
            return

        result = register_patient(
            full_name=full_name,
            email=email,
            password=password,
            phone=phone,
            gender=gender,
            dob=dob,
        )
        if result.ok:
            st.success(result.message + " Please log in.")
        else:
            st.error(result.message)


def render_auth_view():
    st.markdown('<span class="auth-marker"></span>', unsafe_allow_html=True)
    st.markdown('<div class="auth-brand-title">Integrated Patient Care Management System</div>', unsafe_allow_html=True)
    st.markdown('<div class="auth-brand-subtitle">AI-powered smart healthcare platform</div>', unsafe_allow_html=True)

    tab_login, tab_patient = st.tabs(["Login", "Register as Patient"])
    with tab_login:
        _login_form()
    with tab_patient:
        _patient_register_form()