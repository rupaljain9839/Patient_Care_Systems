"""Patient 'Send Enquiry' form — a quick callback request, separate from full
appointment booking (see appointments_view.py for that)."""
import streamlit as st

from services.enquiry_service import submit_enquiry, get_patient_enquiries, PREFERRED_TIME_OPTIONS
from views.components import render_page_header


def render_enquiry(user):
    render_page_header("Send Enquiry", "Request a callback from our team", badge_text="PCMS-HS")
    st.caption("Leave your details and our team will call you back at your preferred time.")

    with st.form("send_enquiry_form"):
        name = st.text_input("Name", value=user["full_name"])
        phone = st.text_input("Phone", value=user.get("phone") or "")
        preferred_time = st.selectbox("Preferred Time To Call", PREFERRED_TIME_OPTIONS)
        message = st.text_area("What is this regarding? (optional)")
        submitted = st.form_submit_button("Submit", use_container_width=True)

    if submitted:
        result = submit_enquiry(user["id"], name, phone, preferred_time, message)
        if result.ok:
            st.success(result.message)
            st.rerun()
        else:
            st.error(result.message)

    history = get_patient_enquiries(user["id"])
    if history:
        st.divider()
        st.subheader("Your Enquiries")
        for e in history:
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**{e['preferred_time'] or 'Anytime'}**" + (f" — {e['message']}" if e["message"] else ""))
                if e["created_at"]:
                    st.caption(e["created_at"].strftime("%d %b %Y, %I:%M %p"))
            with c2:
                st.write(f"_{e['status'].title()}_")
            st.divider()