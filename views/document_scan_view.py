"""Patient-facing: upload a photo of a document (an external prescription, lab
report, etc.) and get an OCR-extracted, AI-summarized readout. Read-only — this
doesn't save anything to the patient's records, it's just a way to quickly
understand a document they already have."""
import streamlit as st

from core.ocr_service import extract_text_from_image, summarize_document_text
from views.components import render_page_header


def render_document_scan(user):
    render_page_header("Scan a Document", "Upload a photo and get an instant summary", badge_text="PCMS-HS")
    st.caption(
        "Good for prescriptions, lab reports, or discharge summaries from outside "
        "this hospital. This doesn't save the document anywhere — it's just for "
        "reading it. For best results, use a clear, well-lit, non-blurry photo."
    )

    uploaded = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])
    if not uploaded:
        return

    st.image(uploaded, caption="Uploaded image", use_container_width=True)

    if st.button("🔍 Scan & Summarize", type="primary", use_container_width=True):
        with st.spinner("Reading the document..."):
            try:
                raw_text = extract_text_from_image(uploaded.getvalue())
            except Exception as e:
                st.error(f"Couldn't read that image: {e}")
                return

        if not raw_text.strip():
            st.warning("No readable text was found in that image. Try a clearer, better-lit photo.")
            return

        with st.spinner("Summarizing..."):
            try:
                summary = summarize_document_text(raw_text)
            except Exception as e:
                st.error(f"Couldn't summarize that: {e}")
                return

        st.subheader("Summary")
        st.write(summary)

        with st.expander("View raw extracted text"):
            st.text(raw_text)