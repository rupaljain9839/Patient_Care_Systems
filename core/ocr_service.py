"""OCR + AI summary for a photo of an external medical document (a prescription,
lab report, or discharge summary from outside this hospital, say). Two stages:

1. Tesseract OCR reads the raw text out of the image (via pytesseract).
2. The same Groq LLM used everywhere else in the app (ai/llm.py) turns that raw,
   possibly messy OCR text into a plain-language summary.

Nothing here is saved to the database — this is a read-only "help me understand
this document" tool, not a way to import records into the system.

NOTE: this used to be built on PaddleOCR/PaddlePaddle, but that stack turned out
to be fragile to install on a Windows CPU-only machine — dependency wheels not
published for some version pins, a C++-level PIR/oneDNN incompatibility bug in
newer releases, and an old transitive dependency (PyMuPDF) that fails to even
build from source on Windows due to a path-length issue in its bundled files.
Tesseract has none of that: it's a single, mature system binary with a thin
Python wrapper, no ML framework underneath, and no PIR/oneDNN-style rough edges.
"""
import io
import shutil
from functools import lru_cache

from PIL import Image
from langchain_core.messages import SystemMessage, HumanMessage

from ai.llm import get_llm


@lru_cache(maxsize=1)
def _tesseract_available() -> bool:
    """True if the Tesseract binary is actually installed and on PATH. pytesseract
    is just a thin wrapper — it calls out to the real `tesseract` executable,
    which is a separate install (see the OCR page's own error message for
    install instructions if this is False)."""
    return shutil.which("tesseract") is not None


def extract_text_from_image(image_bytes: bytes) -> str:
    """Runs OCR on raw image bytes (JPG/PNG) and returns the recognized text."""
    if not _tesseract_available():
        raise RuntimeError(
            "Tesseract isn't installed (or isn't on PATH). Install it from "
            "https://github.com/UB-Mannheim/tesseract/wiki (Windows) — see the "
            "Scan Document page for full setup steps."
        )

    import pytesseract

    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image)
    return text.strip()


_SUMMARY_PROMPT = """The text below was extracted via OCR from a photo of a medical
document — could be a prescription, lab report, discharge summary, medicine
packaging, or similar. OCR can introduce small errors (misread letters/numbers),
so use judgement on obvious typos rather than taking every character literally.

Format your answer as Markdown tables, grouped into sections — this is a hard
requirement, not a suggestion. Use this structure:

1. Start with one short sentence naming what kind of document this looks like.
2. Then one or more tables, each with a bold section heading above it (e.g.
   "**Medicine Details**", "**Additional Information**", "**Test Results**" —
   pick headings that fit what's actually in the document). Every table has
   exactly two columns: `Category` and `Details`.
3. For a medicine/prescription document, a "Medicine Details" table typically
   covers rows like Generic Name, Brand Name, Dosage, Frequency, Purpose — and
   an "Additional Information" table covers rows like Manufacturer, Packaging,
   Prescription Status, Expiry. Adjust the rows to whatever's actually present;
   don't invent values that aren't in the text — write "Not visible on the
   packaging" or "Not mentioned" for a field you'd expect but don't see.
4. For a lab report, use a "Test Results" table instead (Category = test name,
   Details = result/value), plus an "Additional Information" table for doctor
   name, date, etc.
5. If the text is too garbled to make sense of, say so honestly in plain text
   instead of forcing it into a table with guessed values.

Example table format:
| Category | Details |
|---|---|
| Generic Name | Cetirizine Hydrochloride Tablets I.P. |
| Dosage | 10mg |

You are not a doctor — describe what the document says, don't add your own
clinical interpretation, dosing advice, or diagnosis.

--- OCR TEXT ---
{text}
"""


def summarize_document_text(raw_text: str) -> str:
    if not raw_text.strip():
        return "No readable text was found in that image."
    llm = get_llm()
    messages = [
        SystemMessage(content="You are a careful medical document summarizer. You never diagnose, prescribe, or recommend treatment changes — only describe what the document itself says."),
        HumanMessage(content=_SUMMARY_PROMPT.format(text=raw_text[:6000])),
    ]
    response = llm.invoke(messages)
    return response.content