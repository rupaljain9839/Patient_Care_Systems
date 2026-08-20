"""Tools SmartCare AI can call, scoped per role via closures over the current user.
Every tool that touches 'my'/'own' data is bound to the logged-in user's id — the model
can never override whose appointments it's acting on for those. Tools that legitimately
need to reference OTHER people (a doctor by name, a patient by name for admin booking)
take that as an explicit parameter, resolved by fuzzy name match.

CONFIRMATION DESIGN: booking/ordering tools (appointments, medicines, lab tests) are
split into a "quote" tool (side-effect free — just prices/validates and stages a draft)
and a "confirm" tool (actually executes). This isn't just a prompt instruction, which a
model can ignore — _consume_action refuses to execute a draft that was staged in the
SAME agent turn, so a genuine round trip through the patient (a new chat message) is
required between quoting and booking, no matter what the model tries to do in one turn.
"""
import secrets
import time
from datetime import datetime as _dt

from langchain_core.tools import tool

from services.doctor_service import list_doctors as _list_doctors_raw
from services.appointment_service import (
    get_available_slots,
    get_slot_summary,
    book_appointment as _book_appointment,
    get_patient_appointments,
    cancel_appointment as _cancel_appointment,
    get_doctor_appointments,
    get_doctor_stats,
    get_all_appointments,
    get_admin_appointment_overview,
    get_busiest_doctors,
    get_staffing_gaps,
)
from services.health_service import get_latest_vitals, search_patients
from services.prescription_service import get_patient_prescriptions_full, get_doctor_prescriptions
from services.lab_service import (
    get_patient_reports_full,
    get_doctor_reports,
    list_lab_tests as _list_lab_tests_raw,
    book_lab_test as _book_lab_test,
)
from services.pharmacy_service import (
    list_medicines as _list_medicines_raw,
    place_order as _place_order,
    get_all_orders as _get_all_orders,
)
from ai.knowledge_base import retrieve_context


def _parse_date(date_str: str):
    date_str = (date_str or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return _dt.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _parse_time(time_str: str):
    time_str = (time_str or "").strip()
    for fmt in ("%H:%M", "%I:%M %p", "%I%p", "%H"):
        try:
            return _dt.strptime(time_str, fmt).time()
        except ValueError:
            continue
    return None


def _normalize_name(s: str) -> str:
    s = (s or "").lower().strip()
    for prefix in ("dr. ", "dr.", "dr ", "doctor "):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    return s


def _resolve_doctor(name: str):
    """Returns (doctor_dict, error_message) — exactly one of which is None.
    Handles 'Dr.' prefixes and partial/out-of-order name matches, since patients
    and doctors don't reliably type full names in database order."""
    query = _normalize_name(name)
    all_docs = _list_doctors_raw()

    matches = [d for d in all_docs if query in _normalize_name(d["full_name"]) or _normalize_name(d["full_name"]) in query]

    if not matches:
        query_tokens = set(query.split())
        matches = [
            d for d in all_docs
            if query_tokens & set(_normalize_name(d["full_name"]).split())
        ]

    if not matches:
        return None, f"No doctor found matching '{name}'."
    if len(matches) > 1:
        options = ", ".join(f"Dr. {d['full_name']} ({d['specialty']})" for d in matches)
        return None, f"Multiple doctors match '{name}': {options}. Please ask which one they mean."
    return matches[0], None


def _resolve_medicine(name: str):
    """Returns (medicine_dict, error_message) — exactly one of which is None."""
    query = _normalize_name(name)
    all_meds = _list_medicines_raw(active_only=True)

    matches = [m for m in all_meds if query in m["name"].lower() or m["name"].lower() in query]

    if not matches:
        query_tokens = set(query.split())
        matches = [m for m in all_meds if query_tokens & set(m["name"].lower().split())]

    if not matches:
        return None, f"No medicine found matching '{name}'."
    if len(matches) > 1:
        options = ", ".join(f"{m['name']} (₹{m['price']:.0f})" for m in matches)
        return None, f"Multiple medicines match '{name}': {options}. Please ask which one they mean."
    return matches[0], None


def _resolve_lab_test(name: str):
    """Returns (lab_test_dict, error_message) — exactly one of which is None."""
    query = _normalize_name(name)
    all_tests = _list_lab_tests_raw(active_only=True)

    matches = [t for t in all_tests if query in t["name"].lower() or t["name"].lower() in query]

    if not matches:
        query_tokens = set(query.split())
        matches = [t for t in all_tests if query_tokens & set(t["name"].lower().split())]

    if not matches:
        return None, f"No lab test found matching '{name}'."
    if len(matches) > 1:
        options = ", ".join(f"{t['name']} (₹{t['price']:.0f})" for t in matches)
        return None, f"Multiple lab tests match '{name}': {options}. Please ask which one they mean."
    return matches[0], None


# ---------------------------------------------------------------- Confirmation staging
# In-memory only (fine for a single-process app): {(patient_id, kind): {...}}
_PENDING_ACTIONS = {}
_ACTION_TTL_SECONDS = 15 * 60
NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"  # sentinel returned by _consume_action


def _stage_action(patient_id: int, kind: str, details: dict, turn_id: str) -> str:
    token = secrets.token_hex(3)
    _PENDING_ACTIONS[(patient_id, kind)] = {
        "token": token,
        "details": details,
        "turn_id": turn_id,
        "expires": time.time() + _ACTION_TTL_SECONDS,
    }
    return token


def _consume_action(patient_id: int, kind: str, token: str, turn_id: str):
    """Returns (details, error). error is NEEDS_CONFIRMATION if this token was staged
    in THIS SAME turn (i.e. the model is trying to execute without a real round trip
    through the patient) — the caller tool must refuse in that case, not just the
    prompt. Returns (None, "<message>") for a missing/expired/mismatched token, or
    (details, None) on a legitimate cross-turn confirmation."""
    entry = _PENDING_ACTIONS.get((patient_id, kind))
    if not entry or entry["token"] != token:
        return None, "No matching pending request found — please ask again to get a fresh quote."
    if entry["expires"] < time.time():
        _PENDING_ACTIONS.pop((patient_id, kind), None)
        return None, "That quote expired — please ask again for a fresh one."
    if entry["turn_id"] == turn_id:
        return None, NEEDS_CONFIRMATION
    _PENDING_ACTIONS.pop((patient_id, kind), None)
    return entry["details"], None


def _search_reference_tool():
    @tool
    def search_health_reference(query: str) -> str:
        """Search general cardiac health reference material for background info on a
        topic like blood pressure, heart rate, troponin, ejection fraction, ECG terms,
        pulse oximetry, lifestyle, or emergency symptoms. ALWAYS call this for a
        definitional question like "what does X mean" or "what are the symptoms of
        X" — even if X also happens to be something recorded in the patient's own
        vitals. This returns the general medical explanation; it does NOT return the
        patient's personal data (use get_health_condition for that instead)."""
        chunks = retrieve_context(query, k=3)
        return "\n\n".join(chunks) if chunks else "No reference material found for that."

    return search_health_reference


def _list_doctors_tool():
    @tool
    def list_doctors(specialty: str = "", sort_by_fee: str = "") -> str:
        """List doctors in the hospital. Optionally filter by specialty name (e.g.
        'Cardiology') and sort by fee: pass sort_by_fee='desc' to find the highest-fee
        doctors first, or 'asc' for lowest-fee first."""
        sort = "fee_desc" if sort_by_fee == "desc" else ("fee_asc" if sort_by_fee == "asc" else "name")
        docs = _list_doctors_raw(sort=sort)
        if specialty:
            docs = [d for d in docs if specialty.lower() in d["specialty"].lower()]
        if not docs:
            return "No doctors found matching that."
        return "\n".join(
            f"Dr. {d['full_name']} — {d['specialty']} — ₹{d['consultation_fee']:.0f} — {d['experience_years']} yrs experience"
            for d in docs
        )

    return list_doctors


def _check_slots_tool():
    @tool
    def check_available_slots(doctor_name: str, date: str) -> str:
        """Check available appointment slots for a named doctor on a given date
        (format: YYYY-MM-DD)."""
        target_date = _parse_date(date)
        if not target_date:
            return f"Couldn't understand the date '{date}'. Please ask for a clearer date in YYYY-MM-DD format."
        doctor, err = _resolve_doctor(doctor_name)
        if err:
            return err
        total, free = get_slot_summary(doctor["id"], target_date)
        if total == 0:
            return f"Dr. {doctor['full_name']} has no availability set for {target_date}."
        slots = get_available_slots(doctor["id"], target_date)
        if not slots:
            return f"Dr. {doctor['full_name']} is fully booked on {target_date}."
        return f"Dr. {doctor['full_name']} has {free} of {total} slots free on {target_date}: " + ", ".join(
            t.strftime("%H:%M") for t in slots
        )

    return check_available_slots


# ---------------------------------------------------------------- Patient tools

def get_patient_tools(user: dict, turn_id: str):
    patient_id = user["id"]

    @tool
    def get_health_condition() -> str:
        """Get this patient's own most recent recorded vitals and diagnosis."""
        vitals = get_latest_vitals(patient_id)
        if not vitals:
            return "No vitals have been recorded for this patient yet."
        parts = []
        if vitals.get("diagnosis"):
            parts.append(f"Diagnosis: {vitals['diagnosis']}")
        if vitals.get("blood_pressure"):
            parts.append(f"Blood pressure: {vitals['blood_pressure']} mmHg")
        if vitals.get("heart_rate") is not None:
            parts.append(f"Heart rate: {vitals['heart_rate']} bpm")
        if vitals.get("troponin") is not None:
            parts.append(f"Troponin: {vitals['troponin']} ng/mL")
        if vitals.get("ejection_fraction") is not None:
            parts.append(f"Ejection fraction: {vitals['ejection_fraction']}%")
        if vitals.get("cardiac_output") is not None:
            parts.append(f"Cardiac output: {vitals['cardiac_output']} L/min")
        if vitals.get("pulse_oximetry") is not None:
            parts.append(f"Pulse oximetry: {vitals['pulse_oximetry']}%")
        if vitals.get("ecg_note"):
            parts.append(f"ECG note: {vitals['ecg_note']}")
        return "\n".join(parts) if parts else "Vitals recorded but no values on file."

    @tool
    def list_upcoming_appointments() -> str:
        """List this patient's own upcoming appointments."""
        appts = get_patient_appointments(patient_id, upcoming_only=True)
        if not appts:
            return "No upcoming appointments."
        return "\n".join(
            f"#{a['id']}: {a['scheduled_date']} {a['start_time']} with Dr. {a['doctor_name']} ({a['specialty']}) — {a['status']}"
            for a in appts
        )

    @tool
    def get_appointment_counts() -> str:
        """Get counts of this patient's completed, pending (booked), and cancelled appointments."""
        appts = get_patient_appointments(patient_id, upcoming_only=False)
        completed = len([a for a in appts if a["status"] == "completed"])
        pending = len([a for a in appts if a["status"] == "booked"])
        cancelled = len([a for a in appts if a["status"] == "cancelled"])
        return f"Completed: {completed}, Pending (booked): {pending}, Cancelled: {cancelled}"

    @tool
    def book_appointment(doctor_name: str, date: str, time: str, reason: str = "") -> str:
        """Get a quote/hold for booking this patient an appointment with a named doctor,
        on a date (YYYY-MM-DD) and time (HH:MM, 24-hour). This does NOT book the
        appointment yet — it only checks the slot and returns a confirmation token.
        State the exact doctor, date, and time back to the patient and ask them to
        confirm. Only call confirm_appointment_booking with the returned token AFTER
        the patient replies yes in a message of their own — never call it in this same
        turn."""
        target_date = _parse_date(date)
        target_time = _parse_time(time)
        if not target_date:
            return f"Couldn't understand the date '{date}'. Ask the patient for a clearer date (YYYY-MM-DD)."
        if not target_time:
            return f"Couldn't understand the time '{time}'. Ask the patient for a clearer time (HH:MM)."
        doctor, err = _resolve_doctor(doctor_name)
        if err:
            return err
        slots = get_available_slots(doctor["id"], target_date)
        if target_time not in slots:
            if not slots:
                return f"Dr. {doctor['full_name']} has no free slots on {target_date}. Ask the patient for another date."
            return (
                f"{target_time.strftime('%H:%M')} isn't available for Dr. {doctor['full_name']} on {target_date}. "
                f"Free slots: {', '.join(t.strftime('%H:%M') for t in slots)}"
            )
        token = _stage_action(
            patient_id, "appointment",
            {"doctor_id": doctor["id"], "date": target_date, "time": target_time, "reason": reason},
            turn_id,
        )
        return (
            f"Slot available: Dr. {doctor['full_name']} ({doctor['specialty']}) on {target_date} at "
            f"{target_time.strftime('%H:%M')}, fee ₹{doctor['consultation_fee']:.0f}. Ask the patient to confirm. "
            f"If they say yes in a later message, call confirm_appointment_booking with token='{token}'."
        )

    @tool
    def confirm_appointment_booking(token: str) -> str:
        """Actually books the appointment previously quoted by book_appointment. Only
        call this after the patient has explicitly confirmed with yes in a message of
        their own — never call it in the same turn as book_appointment."""
        details, err = _consume_action(patient_id, "appointment", token, turn_id)
        if err == NEEDS_CONFIRMATION:
            return "Not booked yet — you must wait for the patient's own explicit yes in their next message before calling this."
        if err:
            return err
        result = _book_appointment(patient_id, details["doctor_id"], details["date"], details["time"], details["reason"])
        return result.message

    @tool
    def cancel_appointment(doctor_name: str = "", date: str = "", time: str = "") -> str:
        """Cancel one of this patient's own upcoming appointments. Provide whichever of
        doctor_name, date (YYYY-MM-DD), or time (HH:MM) the patient specified to narrow
        it down. If multiple appointments still match, list them and ask the patient to
        clarify instead of guessing which one to cancel."""
        appts = [a for a in get_patient_appointments(patient_id, upcoming_only=True) if a["status"] == "booked"]
        if doctor_name:
            appts = [a for a in appts if doctor_name.lower() in a["doctor_name"].lower()]
        if date:
            d = _parse_date(date)
            if d:
                appts = [a for a in appts if a["scheduled_date"] == d]
        if time:
            t = _parse_time(time)
            if t:
                appts = [a for a in appts if a["start_time"] == t]
        if not appts:
            return "No matching upcoming appointment found to cancel."
        if len(appts) > 1:
            options = "; ".join(f"#{a['id']} with Dr. {a['doctor_name']} on {a['scheduled_date']} at {a['start_time']}" for a in appts)
            return f"Multiple matching appointments found — ask the patient to specify further: {options}"
        result = _cancel_appointment(appts[0]["id"], patient_id)
        return result.message

    @tool
    def get_my_prescriptions() -> str:
        """Get this patient's own prescriptions issued by doctors, including each
        medicine's dosage, frequency, duration, and instructions. Use this to answer
        questions like 'what medicines am I on' or 'what did my doctor prescribe me'."""
        rows = get_patient_prescriptions_full(patient_id)
        if not rows:
            return "No prescriptions on file yet."
        lines = []
        for p in rows:
            date_str = p["created_at"].strftime("%d %b %Y") if p["created_at"] else ""
            lines.append(f"Prescription #{p['id']} — Dr. {p['doctor_name']} ({p['specialty']}), {date_str}")
            if p["diagnosis"] and p["diagnosis"] != "—":
                lines.append(f"  Diagnosis: {p['diagnosis']}")
            for item in p["items"]:
                details = ", ".join(filter(None, [item["dosage"], item["frequency"], item["duration"]]))
                line = f"  - {item['medicine_name']}"
                if details:
                    line += f" ({details})"
                if item["instructions"]:
                    line += f" — {item['instructions']}"
                lines.append(line)
        return "\n".join(lines)

    @tool
    def get_my_lab_reports() -> str:
        """Get this patient's own lab test reports issued by doctors, including result
        summary, findings, and recommendation for each. Use this to answer questions
        like 'what did my blood test show' or 'what were my last lab results'."""
        rows = get_patient_reports_full(patient_id)
        if not rows:
            return "No lab reports on file yet."
        lines = []
        for r in rows:
            date_str = r["created_at"].strftime("%d %b %Y") if r["created_at"] else ""
            lines.append(f"{r['test_name']} — Dr. {r['doctor_name']}, {date_str}")
            if r["result_summary"]:
                lines.append(f"  Result: {r['result_summary']}")
            if r["findings"]:
                lines.append(f"  Findings: {r['findings']}")
            if r["recommendation"]:
                lines.append(f"  Recommendation: {r['recommendation']}")
        return "\n".join(lines)

    @tool
    def search_medicines(query: str = "", category: str = "") -> str:
        """Search the pharmacy catalog by name and/or category (Cardiovascular,
        Antibiotic, Analgesic, Diabetes, Respiratory, General, Other). Returns matching
        medicines with price and stock. Use this before ordering, to confirm the exact
        medicine, price, and availability with the patient."""
        meds = _list_medicines_raw(category=category, search=query)
        if not meds:
            return "No medicines found matching that."
        return "\n".join(
            f"{m['name']} — {m['category']} — ₹{m['price']:.0f} — "
            f"{'in stock (' + str(m['stock']) + ')' if m['stock'] > 0 else 'out of stock'}"
            for m in meds[:15]
        )

    @tool
    def order_medicine(medicine_name: str, quantity: int = 1) -> str:
        """Get a price quote to order a medicine for this patient. This does NOT place
        the order yet — it only checks stock/price and returns a confirmation token.
        State the exact medicine name, unit price, quantity, and total cost back to the
        patient and ask them to confirm. Only call confirm_medicine_order with the
        returned token AFTER the patient replies yes in a message of their own — never
        call it in this same turn."""
        medicine, err = _resolve_medicine(medicine_name)
        if err:
            return err
        if quantity < 1:
            return "Quantity must be at least 1."
        if medicine["stock"] < quantity:
            return f"Only {medicine['stock']} of {medicine['name']} left in stock — can't order {quantity}."
        total = medicine["price"] * quantity
        token = _stage_action(
            patient_id, "medicine",
            {"medicine_id": medicine["id"], "quantity": quantity},
            turn_id,
        )
        return (
            f"Quote ready: {medicine['name']} x{quantity} at ₹{medicine['price']:.0f} each = ₹{total:.0f} total. "
            f"Ask the patient to confirm. If they say yes in a later message, call confirm_medicine_order "
            f"with token='{token}'."
        )

    @tool
    def confirm_medicine_order(token: str) -> str:
        """Actually places the medicine order previously quoted by order_medicine. Only
        call this after the patient has explicitly confirmed with yes in a message of
        their own — never call it in the same turn as order_medicine."""
        details, err = _consume_action(patient_id, "medicine", token, turn_id)
        if err == NEEDS_CONFIRMATION:
            return "Not ordered yet — you must wait for the patient's own explicit yes in their next message before calling this."
        if err:
            return err
        result = _place_order(patient_id, {details["medicine_id"]: details["quantity"]})
        return result.message

    @tool
    def search_lab_tests(query: str = "", category: str = "") -> str:
        """Search the lab test catalog by name and/or category (Cardiac, Blood,
        Imaging, Metabolic, General, Other). Returns matching tests with price and
        description. Use this before booking, to confirm the exact test and price with
        the patient."""
        tests = _list_lab_tests_raw(category=category, search=query)
        if not tests:
            return "No lab tests found matching that."
        return "\n".join(
            f"{t['name']} — {t['category']} — ₹{t['price']:.0f} — {t['description'] or ''}"
            for t in tests[:15]
        )

    @tool
    def book_lab_test_for_me(test_name: str, scheduled_date: str = "") -> str:
        """Get a quote to book a lab test for this patient. This does NOT book it yet —
        it only checks price and returns a confirmation token. State the exact test
        name and price back to the patient and ask them to confirm. Only call
        confirm_lab_test_booking with the returned token AFTER the patient replies yes
        in a message of their own — never call it in this same turn. scheduled_date is
        optional (format YYYY-MM-DD); leave blank if the patient didn't specify one."""
        test, err = _resolve_lab_test(test_name)
        if err:
            return err
        target_date = _parse_date(scheduled_date) if scheduled_date else None
        token = _stage_action(
            patient_id, "lab_test",
            {"test_id": test["id"], "scheduled_date": target_date},
            turn_id,
        )
        return (
            f"Quote ready: {test['name']} ({test['category']}) — ₹{test['price']:.0f}"
            f"{' on ' + str(target_date) if target_date else ''}. Ask the patient to confirm. "
            f"If they say yes in a later message, call confirm_lab_test_booking with token='{token}'."
        )

    @tool
    def confirm_lab_test_booking(token: str) -> str:
        """Actually books the lab test previously quoted by book_lab_test_for_me. Only
        call this after the patient has explicitly confirmed with yes in a message of
        their own — never call it in the same turn as book_lab_test_for_me."""
        details, err = _consume_action(patient_id, "lab_test", token, turn_id)
        if err == NEEDS_CONFIRMATION:
            return "Not booked yet — you must wait for the patient's own explicit yes in their next message before calling this."
        if err:
            return err
        result = _book_lab_test(patient_id, details["test_id"], details["scheduled_date"])
        return result.message

    return [
        _list_doctors_tool(),
        _check_slots_tool(),
        get_health_condition,
        list_upcoming_appointments,
        get_appointment_counts,
        book_appointment,
        confirm_appointment_booking,
        cancel_appointment,
        get_my_prescriptions,
        get_my_lab_reports,
        search_medicines,
        order_medicine,
        confirm_medicine_order,
        search_lab_tests,
        book_lab_test_for_me,
        confirm_lab_test_booking,
        _search_reference_tool(),
    ]


# ---------------------------------------------------------------- Doctor tools

def get_doctor_tools(user: dict):
    doctor_user_id = user["id"]

    @tool
    def list_upcoming_appointments() -> str:
        """List this doctor's own upcoming appointments."""
        appts = get_doctor_appointments(doctor_user_id, upcoming_only=True)
        if not appts:
            return "No upcoming appointments."
        return "\n".join(
            f"#{a['id']}: {a['scheduled_date']} {a['start_time']} with {a['patient_name']} — {a['status']}"
            for a in appts
        )

    @tool
    def get_appointment_counts() -> str:
        """Get this doctor's own appointment stats: today's count, total upcoming,
        completed (all-time), and unique patients."""
        stats = get_doctor_stats(doctor_user_id)
        return (
            f"Today: {stats['today']}, Upcoming: {stats['upcoming']}, "
            f"Completed: {stats['completed']}, Unique patients: {stats['unique_patients']}"
        )

    @tool
    def cancel_appointment(patient_name: str = "", date: str = "", time: str = "") -> str:
        """Cancel one of THIS doctor's own upcoming appointments. Provide whichever of
        patient_name, date (YYYY-MM-DD), or time (HH:MM) was specified to narrow it
        down. If multiple appointments still match, list them and ask which one instead
        of guessing."""
        appts = [a for a in get_doctor_appointments(doctor_user_id, upcoming_only=True) if a["status"] == "booked"]
        if patient_name:
            appts = [a for a in appts if patient_name.lower() in a["patient_name"].lower()]
        if date:
            d = _parse_date(date)
            if d:
                appts = [a for a in appts if a["scheduled_date"] == d]
        if time:
            t = _parse_time(time)
            if t:
                appts = [a for a in appts if a["start_time"] == t]
        if not appts:
            return "No matching upcoming appointment found to cancel."
        if len(appts) > 1:
            options = "; ".join(f"#{a['id']} with {a['patient_name']} on {a['scheduled_date']} at {a['start_time']}" for a in appts)
            return f"Multiple matching appointments found — ask which one: {options}"
        result = _cancel_appointment(appts[0]["id"])
        return result.message

    @tool
    def list_my_recent_prescriptions() -> str:
        """List prescriptions this doctor has personally issued, most recent first."""
        rows = get_doctor_prescriptions(doctor_user_id)[:10]
        if not rows:
            return "No prescriptions issued yet."
        return "\n".join(
            f"#{p['id']} {p['patient_name']} — {p['diagnosis']} "
            f"({p['created_at'].strftime('%d %b %Y') if p['created_at'] else ''})"
            for p in rows
        )

    @tool
    def list_my_recent_lab_reports() -> str:
        """List lab reports this doctor has personally issued, most recent first."""
        rows = get_doctor_reports(doctor_user_id)[:10]
        if not rows:
            return "No lab reports issued yet."
        return "\n".join(
            f"#{r['id']} {r['patient_name']} — {r['test_name']} "
            f"({r['created_at'].strftime('%d %b %Y') if r['created_at'] else ''})"
            for r in rows
        )

    return [
        _list_doctors_tool(),
        list_upcoming_appointments,
        get_appointment_counts,
        cancel_appointment,
        list_my_recent_prescriptions,
        list_my_recent_lab_reports,
        _search_reference_tool(),
    ]


# ---------------------------------------------------------------- Admin tools

def get_admin_tools(user: dict):
    @tool
    def list_upcoming_appointments() -> str:
        """List all upcoming appointments system-wide."""
        from datetime import date as _date

        appts = get_all_appointments(status_filter="Booked", start_date=_date.today())
        if not appts:
            return "No upcoming appointments."
        return "\n".join(
            f"#{a['id']}: {a['scheduled_date']} {a['start_time']} — {a['patient_name']} with Dr. {a['doctor_name']} ({a['specialty']})"
            for a in appts[:30]
        )

    @tool
    def get_appointment_counts() -> str:
        """Get system-wide appointment counts: total, upcoming, and breakdown by status."""
        overview = get_admin_appointment_overview()
        status_line = ", ".join(f"{k}: {v}" for k, v in overview["by_status"].items()) or "none yet"
        return f"Total: {overview['total']}, Upcoming: {overview['upcoming']}, By status: {status_line}"

    @tool
    def get_system_overview() -> str:
        """Get system-wide stats: total patients, total doctors, busiest doctors, and
        specialties with no bookable doctor (staffing gaps)."""
        from core.database import session_scope
        from models.models import User

        with session_scope() as session:
            total_patients = session.query(User).filter(User.role == "patient").count()
            total_doctors = session.query(User).filter(User.role == "doctor").count()
        busiest = get_busiest_doctors(limit=5)
        gaps = get_staffing_gaps()
        busiest_line = ", ".join(f"{name} ({count})" for name, count in busiest) or "no upcoming appointments yet"
        gaps_line = ", ".join(gaps) if gaps else "none — full coverage"
        return (
            f"Total patients: {total_patients}, Total doctors: {total_doctors}\n"
            f"Busiest doctors (upcoming): {busiest_line}\n"
            f"Specialties with no bookable doctor: {gaps_line}"
        )

    @tool
    def book_appointment_for_patient(patient_name: str, doctor_name: str, date: str, time: str, reason: str = "") -> str:
        """Book an appointment on behalf of a named patient, with a named doctor, on a
        date (YYYY-MM-DD) and time (HH:MM, 24-hour). Always confirm patient, doctor,
        date, and time before calling this — do not guess any of them."""
        target_date = _parse_date(date)
        target_time = _parse_time(time)
        if not target_date:
            return f"Couldn't understand the date '{date}'. Ask for a clearer date (YYYY-MM-DD)."
        if not target_time:
            return f"Couldn't understand the time '{time}'. Ask for a clearer time (HH:MM)."

        patients = search_patients(patient_name, limit=5)
        if not patients:
            return f"No patient found matching '{patient_name}'."
        if len(patients) > 1:
            options = ", ".join(f"{p['full_name']} ({p['email']})" for p in patients)
            return f"Multiple patients match '{patient_name}': {options}. Please ask which one."

        doctor, err = _resolve_doctor(doctor_name)
        if err:
            return err

        result = _book_appointment(patients[0]["id"], doctor["id"], target_date, target_time, reason)
        return result.message

    @tool
    def cancel_appointment(patient_name: str = "", doctor_name: str = "", date: str = "", time: str = "") -> str:
        """Cancel any upcoming appointment system-wide. Provide whichever of
        patient_name, doctor_name, date (YYYY-MM-DD), or time (HH:MM) was specified to
        narrow it down. If multiple appointments still match, list them and ask which
        one instead of guessing."""
        from datetime import date as _date

        appts = get_all_appointments(status_filter="Booked", start_date=_date.today())
        if patient_name:
            appts = [a for a in appts if patient_name.lower() in a["patient_name"].lower()]
        if doctor_name:
            appts = [a for a in appts if doctor_name.lower() in a["doctor_name"].lower()]
        if date:
            d = _parse_date(date)
            if d:
                appts = [a for a in appts if a["scheduled_date"] == d]
        if time:
            t = _parse_time(time)
            if t:
                appts = [a for a in appts if a["start_time"] == t]
        if not appts:
            return "No matching upcoming appointment found to cancel."
        if len(appts) > 1:
            options = "; ".join(
                f"#{a['id']} {a['patient_name']} with Dr. {a['doctor_name']} on {a['scheduled_date']} at {a['start_time']}"
                for a in appts
            )
            return f"Multiple matching appointments found — ask which one: {options}"
        result = _cancel_appointment(appts[0]["id"])
        return result.message

    @tool
    def get_pharmacy_overview() -> str:
        """Get system-wide pharmacy stats: total medicines in catalog, out-of-stock
        and low-stock (5 or fewer units) counts, total orders by status, and total
        revenue from placed/completed orders."""
        meds = _list_medicines_raw(active_only=True)
        out_of_stock = [m for m in meds if m["stock"] == 0]
        low_stock = [m for m in meds if 0 < m["stock"] <= 5]

        orders = _get_all_orders()
        by_status = {}
        revenue = 0.0
        for o in orders:
            by_status[o["status"]] = by_status.get(o["status"], 0) + 1
            if o["status"] in ("placed", "completed"):
                revenue += o["total_amount"]

        status_line = ", ".join(f"{k}: {v}" for k, v in by_status.items()) or "no orders yet"
        low_line = ", ".join(f"{m['name']} ({m['stock']})" for m in low_stock) or "none"
        out_line = ", ".join(m["name"] for m in out_of_stock) or "none"

        return (
            f"Medicines in catalog: {len(meds)}\n"
            f"Out of stock: {out_line}\n"
            f"Low stock (<=5 units): {low_line}\n"
            f"Total orders: {len(orders)} ({status_line})\n"
            f"Revenue (placed + completed orders): ₹{revenue:.0f}"
        )

    @tool
    def search_medicine_stock(query: str = "", category: str = "") -> str:
        """Search the full medicine catalog (including inactive/hidden items) by name
        and/or category, showing current stock and price for each. Use this to answer
        questions about specific medicines' stock levels."""
        meds = _list_medicines_raw(category=category, search=query, active_only=False)
        if not meds:
            return "No medicines found matching that."
        return "\n".join(
            f"{m['name']} — {m['category']} — ₹{m['price']:.0f} — "
            f"{m['stock']} in stock{' (INACTIVE)' if not m.get('is_active', True) else ''}"
            for m in meds[:25]
        )

    @tool
    def list_recent_orders(status: str = "", patient_name: str = "") -> str:
        """List recent medicine orders system-wide. Optionally filter by status
        ('placed', 'completed', or 'cancelled') and/or by patient name (partial
        match)."""
        orders = _get_all_orders()
        if status:
            orders = [o for o in orders if o["status"] == status.lower()]
        if patient_name:
            orders = [o for o in orders if patient_name.lower() in o["patient_name"].lower()]
        if not orders:
            return "No orders match that."
        lines = []
        for o in orders[:20]:
            items_str = ", ".join(f"{i['name']} x{i['quantity']}" for i in o["items"])
            date_str = o["created_at"].strftime("%d %b %Y") if o["created_at"] else ""
            lines.append(
                f"#{o['id']} {o['patient_name']} — {items_str} — ₹{o['total_amount']:.0f} "
                f"— {o['status']} — {date_str}"
            )
        return "\n".join(lines)

    return [
        _list_doctors_tool(),
        list_upcoming_appointments,
        get_appointment_counts,
        get_system_overview,
        book_appointment_for_patient,
        cancel_appointment,
        get_pharmacy_overview,
        search_medicine_stock,
        list_recent_orders,
        _search_reference_tool(),
    ]