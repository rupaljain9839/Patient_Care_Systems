"""Patient-facing Pharmacy page — Browse Pharmacy, My Prescriptions, Lab Tests, My Orders."""
import streamlit as st

from services.pharmacy_service import list_medicines, place_order, get_patient_orders, CATEGORIES as MED_CATEGORIES
from services.prescription_service import get_patient_prescriptions, generate_prescription_pdf
from services.lab_service import (
    list_lab_tests,
    book_lab_test,
    get_patient_bookings,
    get_patient_reports,
    generate_lab_report_pdf,
    CATEGORIES as LAB_CATEGORIES,
)
from views.components import render_page_header, render_html

STATUS_COLORS = {"pending": "#e2824f", "completed": "#2bb3a3", "placed": "#19a7ce", "cancelled": "#c62839"}


def _cart():
    if "pharmacy_cart" not in st.session_state:
        st.session_state["pharmacy_cart"] = {}
    return st.session_state["pharmacy_cart"]


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


def _browse_pharmacy_tab(user):
    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox("Category", ["All"] + MED_CATEGORIES, key="pharmacy_category")
    with col2:
        search = st.text_input("Search medicine", placeholder="e.g. Atorvastatin", key="pharmacy_search")

    medicines = list_medicines(category=category, search=search)
    st.caption(f"{len(medicines)} medicines available")

    cart = _cart()

    if not medicines:
        st.info("No medicines match this search.")
    else:
        cols = st.columns(4)
        for i, m in enumerate(medicines):
            with cols[i % 4]:
                render_html(_medicine_card_html(m))
                if m["stock"] > 0:
                    qty = st.number_input("Qty", min_value=1, max_value=m["stock"], value=1, key=f"qty_{m['id']}", label_visibility="collapsed")
                    if st.button("Add to Cart", key=f"add_{m['id']}", use_container_width=True):
                        cart[m["id"]] = cart.get(m["id"], 0) + qty
                        st.rerun()
                else:
                    st.button("Out of Stock", key=f"oos_{m['id']}", use_container_width=True, disabled=True)

    if cart:
        st.divider()
        st.subheader("🛒 Cart")
        all_meds = {m["id"]: m for m in list_medicines(active_only=False)}
        total = 0.0
        for med_id, qty in list(cart.items()):
            med = all_meds.get(med_id)
            if not med:
                continue
            line_total = med["price"] * qty
            total += line_total
            c1, c2 = st.columns([5, 1])
            c1.write(f"{med['icon']} **{med['name']}** × {qty} — ₹{line_total:.0f}")
            if c2.button("Remove", key=f"remove_{med_id}"):
                cart.pop(med_id, None)
                st.rerun()

        st.write(f"**Total: ₹{total:.0f}**")
        if st.button("Place Order", type="primary", use_container_width=True):
            result = place_order(user["id"], cart)
            if result.ok:
                st.success(result.message)
                st.session_state["pharmacy_cart"] = {}
                st.rerun()
            else:
                st.error(result.message)


def _my_prescriptions_tab(user):
    prescriptions = get_patient_prescriptions(user["id"])
    if not prescriptions:
        st.info("No prescriptions yet — your doctor will issue these after a consultation.")
        return

    for p in prescriptions:
        c1, c2 = st.columns([5, 1])
        with c1:
            render_html(f"""
                <div style="background:white; border-radius:14px; padding:0.9rem 1.2rem; margin-bottom:0.7rem;
                            box-shadow:0 2px 10px rgba(20,108,148,0.1); border:1px solid #d7edf5;">
                    <b style="color:#0b3d5c;">Dr. {p['doctor_name']}</b>
                    <span style="color:#5c8aa0;"> · {p['specialty']}</span>
                    <div style="color:#5c8aa0; font-size:0.85rem; margin-top:0.3rem;">
                        {p['diagnosis']} · {p['item_count']} medicine(s) · {p['created_at'].strftime('%d %b %Y') if p['created_at'] else ''}
                    </div>
                </div>
            """)
        with c2:
            st.download_button(
                "📄 PDF", data=generate_prescription_pdf(p["id"]),
                file_name=f"prescription_{p['id']}.pdf", mime="application/pdf",
                key=f"presc_pdf_{p['id']}", use_container_width=True,
            )


def _lab_tests_tab(user):
    sub_book, sub_reports = st.tabs(["Book a Test", "My Reports & Bookings"])

    with sub_book:
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox("Category", ["All"] + LAB_CATEGORIES, key="lab_category")
        with col2:
            search = st.text_input("Search test", placeholder="e.g. Lipid Profile", key="lab_search")

        tests = list_lab_tests(category=category, search=search)
        if not tests:
            st.info("No lab tests match this search.")
        for t in tests:
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{t['name']}** — {t['category']} · ₹{t['price']:.0f}  \n{t['description'] or ''}")
            if c2.button("Book", key=f"book_test_{t['id']}", use_container_width=True):
                result = book_lab_test(user["id"], t["id"])
                if result.ok:
                    st.success(result.message)
                    st.rerun()
                else:
                    st.error(result.message)

    with sub_reports:
        st.subheader("Bookings")
        bookings = get_patient_bookings(user["id"])
        if not bookings:
            st.info("No lab tests booked yet.")
        for b in bookings:
            color = STATUS_COLORS.get(b["status"], "#5c8aa0")
            render_html(f"""
                <div style="background:white; border-radius:14px; padding:0.8rem 1.1rem; margin-bottom:0.6rem;
                            box-shadow:0 2px 10px rgba(20,108,148,0.1); border:1px solid #d7edf5;
                            display:flex; justify-content:space-between; align-items:center;">
                    <div><b style="color:#0b3d5c;">{b['test_name']}</b>
                        <span style="color:#5c8aa0; font-size:0.85rem;"> · {b['created_at'].strftime('%d %b %Y') if b['created_at'] else ''}</span>
                    </div>
                    <div style="background:{color}; color:white; border-radius:8px; padding:0.2rem 0.6rem;
                                font-size:0.75rem; font-weight:800; text-transform:capitalize;">{b['status']}</div>
                </div>
            """)

        st.divider()
        st.subheader("Reports")
        reports = get_patient_reports(user["id"])
        if not reports:
            st.info("No lab reports issued yet.")
        for r in reports:
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{r['test_name']}** — Dr. {r['doctor_name']} · {r['created_at'].strftime('%d %b %Y') if r['created_at'] else ''}")
            c2.download_button(
                "📄 PDF", data=generate_lab_report_pdf(r["id"]),
                file_name=f"lab_report_{r['id']}.pdf", mime="application/pdf",
                key=f"lab_pdf_{r['id']}", use_container_width=True,
            )


def _my_orders_tab(user):
    orders = get_patient_orders(user["id"])
    if not orders:
        st.info("No medicine orders yet.")
        return

    for o in orders:
        color = STATUS_COLORS.get(o["status"], "#5c8aa0")
        items_str = ", ".join(f"{i['name']} × {i['quantity']}" for i in o["items"])
        render_html(f"""
            <div style="background:white; border-radius:14px; padding:0.9rem 1.2rem; margin-bottom:0.7rem;
                        box-shadow:0 2px 10px rgba(20,108,148,0.1); border:1px solid #d7edf5;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="color:#0b3d5c;">Order #{o['id']}</b>
                    <div style="background:{color}; color:white; border-radius:8px; padding:0.2rem 0.6rem;
                                font-size:0.75rem; font-weight:800; text-transform:capitalize;">{o['status']}</div>
                </div>
                <div style="color:#5c8aa0; font-size:0.85rem; margin-top:0.3rem;">{items_str}</div>
                <div style="color:#0b3d5c; font-weight:700; margin-top:0.3rem;">₹{o['total_amount']:.0f}</div>
            </div>
        """)


def render_pharmacy(user):
    render_page_header("Pharmacy", "Available medicines and your prescriptions", badge_text="IPCMS")

    tab_browse, tab_presc, tab_lab, tab_orders = st.tabs(
        ["Browse Pharmacy", "My Prescriptions", "Lab Tests", "My Orders"]
    )
    with tab_browse:
        _browse_pharmacy_tab(user)
    with tab_presc:
        _my_prescriptions_tab(user)
    with tab_lab:
        _lab_tests_tab(user)
    with tab_orders:
        _my_orders_tab(user)