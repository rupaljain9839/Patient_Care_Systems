"""Patient-facing Pharmacy page — Browse Pharmacy, My Prescriptions, Lab Tests, My Orders."""
import base64
import os

import streamlit as st

from services.pharmacy_service import list_medicines, place_order, get_patient_orders, cancel_order, CATEGORIES as MED_CATEGORIES
from services.prescription_service import get_patient_prescriptions, generate_prescription_pdf
from services.lab_service import (
    list_lab_tests,
    book_lab_test,
    get_patient_bookings,
    get_patient_reports,
    generate_lab_report_pdf,
    CATEGORIES as LAB_CATEGORIES,
)
from views.components import render_page_header, render_html, render_pdf_inline

STATUS_COLORS = {"pending": "#E08B1F", "completed": "#1FA37A", "placed": "#5B6EF5", "cancelled": "#D14F5A"}


def _cart():
    if "pharmacy_cart" not in st.session_state:
        st.session_state["pharmacy_cart"] = {}
    return st.session_state["pharmacy_cart"]


def _image_data_uri(image_url):
    """Reads an uploaded medicine image from disk and returns a base64 data URI, so it
    renders inline via render_html() regardless of whether Streamlit serves static/ as a URL."""
    if not image_url:
        return None
    full_path = os.path.join("static", image_url)
    if not os.path.exists(full_path):
        return None
    ext = os.path.splitext(image_url)[1].lstrip(".").lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext or "png")
    with open(full_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def _medicine_card_html(m: dict) -> str:
    image_uri = _image_data_uri(m.get("image_url"))
    if image_uri:
        visual = f'<img src="{image_uri}" alt="{m["name"]}">'
    else:
        visual = f'<div class="med-emoji">{m["icon"]}</div>'

    if m["stock"] == 0:
        stock_html = '<div class="med-stock-out">Out of stock</div>'
    elif m["stock"] <= 5:
        stock_html = f'<div class="med-stock-low">⚡ Only {m["stock"]} left</div>'
    else:
        stock_html = '<div class="med-stock-ok">✓ In stock</div>'

    return f"""
        <div class="ipcms-med-card">
            <div class="med-price-badge">₹{m['price']:.0f}</div>
            <div class="med-visual-wrap">{visual}</div>
            <div class="med-name">{m['name']}</div>
            <span class="med-category-pill">{m['category']}</span>
            <div class="med-desc">{m['description'] or '—'}</div>
            {stock_html}
        </div>
    """


def _browse_pharmacy_tab(user):
    category = st.pills(
        "Category", ["All"] + MED_CATEGORIES,
        selection_mode="single", default="All", key="pharmacy_category_pill",
    )
    category = category or "All"

    col_search, col_sort = st.columns([3, 1])
    with col_search:
        all_medicine_names = sorted({m["name"] for m in list_medicines(active_only=True)})
        search = st.selectbox(
            "Search medicine", [""] + all_medicine_names,
            key="pharmacy_search",
            placeholder="🔍 Search medicines, e.g. Atorvastatin",
        )
    with col_sort:
        sort_by = st.selectbox(
            "Sort by", ["Relevance", "Price: Low to High", "Price: High to Low", "Name: A-Z"],
            key="pharmacy_sort",
        )

    medicines = list_medicines(category=category, search=search)
    if sort_by == "Price: Low to High":
        medicines = sorted(medicines, key=lambda m: m["price"])
    elif sort_by == "Price: High to Low":
        medicines = sorted(medicines, key=lambda m: -m["price"])
    elif sort_by == "Name: A-Z":
        medicines = sorted(medicines, key=lambda m: m["name"])

    st.caption(f"{len(medicines)} medicine{'s' if len(medicines) != 1 else ''} available")

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
        st.write("")
        render_html('<div class="ipcms-panel"><div class="panel-label">🛒 YOUR CART</div></div>')
        all_meds = {m["id"]: m for m in list_medicines(active_only=False)}
        total = 0.0
        for med_id, qty in list(cart.items()):
            med = all_meds.get(med_id)
            if not med:
                continue
            line_total = med["price"] * qty
            total += line_total
            row_l, row_r = st.columns([6, 1])
            with row_l:
                render_html(f"""
                    <div class="ipcms-cart-row">
                        <div>
                            <div class="cart-item-name">{med['icon']} {med['name']}</div>
                            <div class="cart-item-meta">₹{med['price']:.0f} × {qty}</div>
                        </div>
                        <div class="cart-item-total">₹{line_total:.0f}</div>
                    </div>
                """)
            with row_r:
                if st.button("Remove", key=f"remove_{med_id}", use_container_width=True):
                    cart.pop(med_id, None)
                    st.rerun()

        render_html(f"""
            <div class="ipcms-cart-summary">
                <div>
                    <div class="cart-total-label">TOTAL · {sum(cart.values())} item(s)</div>
                    <div class="cart-total-value">₹{total:.0f}</div>
                </div>
            </div>
        """)
        if st.button("Place Order", type="primary", use_container_width=True, key="place_order_btn"):
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
        c1, c2 = st.columns([4, 2])
        with c1:
            render_html(f"""
                <div style="background:white; border-radius:14px; padding:0.9rem 1.2rem; margin-bottom:0.7rem;
                            box-shadow:var(--ipcms-shadow-card); border:1px solid rgba(91,110,245,0.07);">
                    <b style="color:var(--ipcms-text-dark);">Dr. {p['doctor_name']}</b>
                    <span style="color:var(--ipcms-text-muted);"> · {p['specialty']}</span>
                    <div style="color:var(--ipcms-text-muted); font-size:0.85rem; margin-top:0.3rem;">
                        {p['diagnosis']} · {p['item_count']} medicine(s) · {p['created_at'].strftime('%d %b %Y') if p['created_at'] else ''}
                    </div>
                </div>
            """)
        with c2:
            col_view, col_dl = st.columns(2)
            with col_view:
                if st.button("👁 View", key=f"presc_view_{p['id']}", use_container_width=True):
                    st.session_state[f"show_presc_pdf_{p['id']}"] = not st.session_state.get(
                        f"show_presc_pdf_{p['id']}", False
                    )
                    st.rerun()
            with col_dl:
                st.download_button(
                    "📄 PDF", data=generate_prescription_pdf(p["id"]),
                    file_name=f"prescription_{p['id']}.pdf", mime="application/pdf",
                    key=f"presc_pdf_{p['id']}", use_container_width=True,
                )

        if st.session_state.get(f"show_presc_pdf_{p['id']}", False):
            render_pdf_inline(generate_prescription_pdf(p["id"]))


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
            color = STATUS_COLORS.get(b["status"], "var(--ipcms-text-muted)")
            render_html(f"""
                <div style="background:white; border-radius:14px; padding:0.8rem 1.1rem; margin-bottom:0.6rem;
                            box-shadow:var(--ipcms-shadow-card); border:1px solid rgba(91,110,245,0.07);
                            display:flex; justify-content:space-between; align-items:center;">
                    <div><b style="color:var(--ipcms-text-dark);">{b['test_name']}</b>
                        <span style="color:var(--ipcms-text-muted); font-size:0.85rem;"> · {b['created_at'].strftime('%d %b %Y') if b['created_at'] else ''}</span>
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
            c1, c2 = st.columns([4, 2])
            c1.write(f"**{r['test_name']}** — Dr. {r['doctor_name']} · {r['created_at'].strftime('%d %b %Y') if r['created_at'] else ''}")
            with c2:
                col_view, col_dl = st.columns(2)
                with col_view:
                    if st.button("👁 View", key=f"lab_view_{r['id']}", use_container_width=True):
                        st.session_state[f"show_lab_pdf_{r['id']}"] = not st.session_state.get(
                            f"show_lab_pdf_{r['id']}", False
                        )
                        st.rerun()
                with col_dl:
                    st.download_button(
                        "📄 PDF", data=generate_lab_report_pdf(r["id"]),
                        file_name=f"lab_report_{r['id']}.pdf", mime="application/pdf",
                        key=f"lab_pdf_{r['id']}", use_container_width=True,
                    )
            if st.session_state.get(f"show_lab_pdf_{r['id']}", False):
                render_pdf_inline(generate_lab_report_pdf(r["id"]))


def _my_orders_tab(user):
    orders = get_patient_orders(user["id"])
    if not orders:
        st.info("No medicine orders yet.")
        return

    for o in orders:
        color = STATUS_COLORS.get(o["status"], "var(--ipcms-text-muted)")
        items_str = ", ".join(f"{i['name']} × {i['quantity']}" for i in o["items"])
        col_card, col_action = st.columns([5, 1])
        with col_card:
            render_html(f"""
                <div style="background:white; border-radius:14px; padding:0.9rem 1.2rem; margin-bottom:0.7rem;
                            box-shadow:var(--ipcms-shadow-card); border:1px solid rgba(91,110,245,0.07);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <b style="color:var(--ipcms-text-dark);">Order #{o['id']}</b>
                        <div style="background:{color}; color:white; border-radius:8px; padding:0.2rem 0.6rem;
                                    font-size:0.75rem; font-weight:800; text-transform:capitalize;">{o['status']}</div>
                    </div>
                    <div style="color:var(--ipcms-text-muted); font-size:0.85rem; margin-top:0.3rem;">{items_str}</div>
                    <div style="color:var(--ipcms-text-dark); font-weight:700; margin-top:0.3rem;">₹{o['total_amount']:.0f}</div>
                </div>
            """)
        with col_action:
            if o["status"] == "placed":
                if st.button("✕ Cancel", key=f"cancel_order_{o['id']}", use_container_width=True):
                    result = cancel_order(user["id"], o["id"])
                    if result.ok:
                        st.success(result.message)
                        st.rerun()
                    else:
                        st.error(result.message)


def render_pharmacy(user):
    render_page_header("Pharmacy", "Available medicines and your prescriptions", badge_text="PCMS-HS")

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