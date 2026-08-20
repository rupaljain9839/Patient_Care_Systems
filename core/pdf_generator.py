"""Generates fixed-format PDFs for prescriptions and lab reports. Both follow the
same letterhead style so every prescription/report looks consistent regardless
of which doctor issued it."""
from fpdf import FPDF

HOSPITAL_NAME = "Patient Care Management System for Healthcare Services"
HOSPITAL_TAGLINE = "PCMS-HS . Cardiac Care"

# fpdf2's core "Helvetica" font only supports Latin-1 — it has no glyph for an
# em-dash, curly quotes, an ellipsis character, a bullet, etc., and raises
# FPDFUnicodeEncodingException the instant one shows up. That's not just our own
# "—" placeholders (fixed below) — free-text fields typed by a doctor (Notes,
# Findings, Recommendation, Instructions) can contain any of these just from
# normal typing (e.g. pasting from Word, which loves curly quotes), and would
# crash PDF generation just as hard. _safe() normalizes the common cases and
# then falls back to dropping anything still unsupported, so no input — ours or
# a doctor's — can ever break a prescription/report from being issued again.
_UNICODE_REPLACEMENTS = {
    "\u2014": "-",   # em dash —
    "\u2013": "-",   # en dash –
    "\u2015": "-",   # horizontal bar ―
    "\u2018": "'",   # left single quote '
    "\u2019": "'",   # right single quote '
    "\u201c": '"',   # left double quote "
    "\u201d": '"',   # right double quote "
    "\u2026": "...", # ellipsis …
    "\u2022": "-",   # bullet •
    "\u00a0": " ",   # non-breaking space
    "\u20b9": "Rs.", # rupee sign ₹
}


def _safe(text) -> str:
    if text is None:
        return ""
    text = str(text)
    for bad, good in _UNICODE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    # Final safety net: anything still outside Latin-1 (emoji, other scripts, etc.)
    # gets replaced rather than crashing the whole PDF.
    return text.encode("latin-1", errors="replace").decode("latin-1")


class _DocPDF(FPDF):
    def header(self):
        self.set_fill_color(20, 108, 148)
        self.rect(0, 0, 210, 22, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 16)
        self.set_xy(10, 6)
        self.cell(0, 8, _safe(HOSPITAL_NAME), ln=True)
        self.set_font("Helvetica", "", 10)
        self.set_x(10)
        self.cell(0, 6, _safe(HOSPITAL_TAGLINE), ln=True)
        self.ln(8)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "This is a system-generated document from PCMS-HS.", align="C")


def _section_title(pdf: _DocPDF, text: str):
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(20, 108, 148)
    pdf.cell(0, 8, _safe(text), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 11)


def _kv_line(pdf: _DocPDF, label: str, value: str):
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(35, 6, _safe(f"{label}:"))
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _safe(value) or "-", ln=True)


def build_prescription_pdf(data: dict) -> bytes:
    """data keys: patient_name, patient_age, patient_gender, doctor_name, specialty,
    date_str, diagnosis, notes, items (list of {medicine_name, dosage, frequency, duration, instructions})."""
    pdf = _DocPDF()
    pdf.add_page()

    _section_title(pdf, "Prescription")
    _kv_line(pdf, "Patient", data.get("patient_name", ""))
    _kv_line(pdf, "Age / Gender", f"{data.get('patient_age') or '-'} / {data.get('patient_gender') or '-'}")
    _kv_line(pdf, "Doctor", f"Dr. {data.get('doctor_name', '')} ({data.get('specialty', 'General')})")
    _kv_line(pdf, "Date", data.get("date_str", ""))
    pdf.ln(3)

    if data.get("diagnosis"):
        _kv_line(pdf, "Diagnosis", data["diagnosis"])
        pdf.ln(2)

    _section_title(pdf, "Rx")
    pdf.set_fill_color(223, 243, 250)
    pdf.set_font("Helvetica", "B", 9)
    col_widths = [45, 30, 35, 25, 55]
    headers = ["Medicine", "Dosage", "Frequency", "Duration", "Instructions"]
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, _safe(h), border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for item in data.get("items", []):
        pdf.cell(col_widths[0], 8, _safe(item.get("medicine_name", "")), border=1)
        pdf.cell(col_widths[1], 8, _safe(item.get("dosage", "")) or "-", border=1)
        pdf.cell(col_widths[2], 8, _safe(item.get("frequency", "")) or "-", border=1)
        pdf.cell(col_widths[3], 8, _safe(item.get("duration", "")) or "-", border=1)
        pdf.cell(col_widths[4], 8, _safe(item.get("instructions", "")) or "-", border=1)
        pdf.ln()

    if data.get("notes"):
        pdf.ln(5)
        _section_title(pdf, "Additional Notes")
        pdf.multi_cell(0, 6, _safe(data["notes"]))

    pdf.ln(15)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 6, _safe(f"Dr. {data.get('doctor_name', '')}"), ln=True, align="R")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 6, "(Digitally issued via PCMS-HS)", ln=True, align="R")

    return bytes(pdf.output())


def build_lab_report_pdf(data: dict) -> bytes:
    """data keys: patient_name, patient_age, patient_gender, doctor_name, specialty,
    date_str, test_name, result_summary, findings, recommendation."""
    pdf = _DocPDF()
    pdf.add_page()

    _section_title(pdf, "Lab Report")
    _kv_line(pdf, "Patient", data.get("patient_name", ""))
    _kv_line(pdf, "Age / Gender", f"{data.get('patient_age') or '-'} / {data.get('patient_gender') or '-'}")
    _kv_line(pdf, "Referring Doctor", f"Dr. {data.get('doctor_name', '')} ({data.get('specialty', 'General')})")
    _kv_line(pdf, "Date", data.get("date_str", ""))
    _kv_line(pdf, "Test", data.get("test_name", ""))
    pdf.ln(4)

    _section_title(pdf, "Result Summary")
    pdf.multi_cell(0, 6, _safe(data.get("result_summary")) or "-")
    pdf.ln(3)

    _section_title(pdf, "Findings")
    pdf.multi_cell(0, 6, _safe(data.get("findings")) or "-")
    pdf.ln(3)

    _section_title(pdf, "Recommendation")
    pdf.multi_cell(0, 6, _safe(data.get("recommendation")) or "-")

    pdf.ln(15)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 6, _safe(f"Dr. {data.get('doctor_name', '')}"), ln=True, align="R")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 6, "(Digitally issued via PCMS-HS)", ln=True, align="R")

    return bytes(pdf.output())