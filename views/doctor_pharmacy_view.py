"""Doctor's Pharmacy page — view-only. Doctors can browse the medicine catalog
(useful reference while prescribing) but cannot buy, add, or edit anything."""
import streamlit as st

from services.pharmacy_service import list_medicines, CATEGORIES
from views.components import render_page_header, render_html


def _medicine_card_html(m: dict) -> str:
    return f"""
        <div style="background:white; border-radius:16px; padding:1.1rem 1.2rem; margin-bottom:0.6rem;
                    box-shadow:0 4px 14px rgba(20,108,148,0.12); border:1px solid #d7edf5;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div style="font-size:1.8rem;">{m['icon']}</div>
                <div style="background:#19a7ce; color:white; border-radius:8px; padding:0.25rem 0.6rem;
                            font-weight:800; font-size:0.85rem;">₹{m['price']:.0f}</div>
            </div>
            <div style="font-weight:900; font-size:1.05rem; color:#0b3d5c; margin-top:0.5rem;">{m['name']}</div>
            <div style="color:#19a7ce; font-weight:700; font-size:0.85rem;">{m['category']}</div>
            <div style="color:#5c8aa0; font-size:0.82rem; margin-top:0.3rem;">{m['description'] or '—'}</div>
            <div style="color:{'#c62839' if m['stock'] == 0 else '#5c8aa0'}; font-size:0.78rem; margin-top:0.4rem;">
                {'Out of stock' if m['stock'] == 0 else f"{m['stock']} in stock"}
            </div>
        </div>
    """


def render_doctor_pharmacy(user):
    render_page_header("Pharmacy", "Browse the medicine catalog", badge_text="IPCMS")
    st.caption("View-only — for reference while prescribing. Ordering and catalog management aren't available here.")

    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox("Category", ["All"] + CATEGORIES, key="doc_pharmacy_category")
    with col2:
        search = st.text_input("Search medicine", placeholder="e.g. Atorvastatin", key="doc_pharmacy_search")

    medicines = list_medicines(category=category, search=search)
    st.caption(f"{len(medicines)} medicines available")

    if not medicines:
        st.info("No medicines match this search.")
        return

    cols = st.columns(4)
    for i, m in enumerate(medicines):
        with cols[i % 4]:
            render_html(_medicine_card_html(m))