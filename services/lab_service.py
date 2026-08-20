"""Lab test catalog (admin-managed), patient booking, and doctor-issued reports."""
from dataclasses import dataclass
from datetime import datetime, date

from core.database import session_scope
from core.pdf_generator import build_lab_report_pdf
from models.models import LabTest, LabTestBooking, LabReport, Doctor, User

CATEGORIES = ["Cardiac", "Blood", "Imaging", "Metabolic", "General", "Other"]


@dataclass
class ServiceResult:
    ok: bool
    message: str
    id: int = None


def _age_from_dob(dob):
    if not dob:
        return "—"
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ---------------------------------------------------------------- Catalog (admin)

def list_lab_tests(category: str = "", search: str = "", active_only: bool = True):
    with session_scope() as session:
        q = session.query(LabTest)
        if active_only:
            q = q.filter(LabTest.is_active.is_(True))
        if category and category != "All":
            q = q.filter(LabTest.category == category)
        if search:
            q = q.filter(LabTest.name.ilike(f"%{search}%"))
        q = q.order_by(LabTest.name)
        return [
            {"id": t.id, "name": t.name, "category": t.category or "General", "description": t.description or "",
             "price": float(t.price) if t.price is not None else 0.0, "is_active": t.is_active}
            for t in q.all()
        ]


def add_lab_test(name, category, description, price):
    if not name.strip():
        return ServiceResult(False, "Test name is required.")
    with session_scope() as session:
        session.add(LabTest(name=name.strip(), category=category, description=description, price=price, is_active=True))
        return ServiceResult(True, f"Added {name}.")


def update_lab_test(test_id, **fields):
    with session_scope() as session:
        t = session.query(LabTest).filter(LabTest.id == test_id).first()
        if not t:
            return ServiceResult(False, "Lab test not found.")
        for k, v in fields.items():
            if v is not None:
                setattr(t, k, v)
        return ServiceResult(True, "Updated.")


def delete_lab_test(test_id):
    with session_scope() as session:
        t = session.query(LabTest).filter(LabTest.id == test_id).first()
        if not t:
            return ServiceResult(False, "Not found.")
        session.delete(t)
        return ServiceResult(True, "Deleted.")


# ---------------------------------------------------------------- Booking (patient)

def book_lab_test(patient_id: int, lab_test_id: int, scheduled_date=None) -> ServiceResult:
    with session_scope() as session:
        test = session.query(LabTest).filter(LabTest.id == lab_test_id).first()
        if not test:
            return ServiceResult(False, "Test not found.")
        booking = LabTestBooking(
            patient_id=patient_id,
            lab_test_id=lab_test_id,
            status="pending",
            scheduled_date=scheduled_date,
            created_at=datetime.utcnow(),
        )
        session.add(booking)
        session.flush()
        return ServiceResult(True, f"Booked {test.name}.", booking.id)


def get_patient_bookings(patient_id: int):
    with session_scope() as session:
        rows = (
            session.query(LabTestBooking)
            .filter(LabTestBooking.patient_id == patient_id)
            .order_by(LabTestBooking.created_at.desc())
            .all()
        )
        return [
            {
                "id": b.id,
                "test_name": b.lab_test.name if b.lab_test else "Unknown",
                "status": b.status,
                "scheduled_date": b.scheduled_date,
                "created_at": b.created_at,
            }
            for b in rows
        ]


def get_all_bookings(status_filter: str = None):
    with session_scope() as session:
        q = session.query(LabTestBooking)
        if status_filter and status_filter != "All":
            q = q.filter(LabTestBooking.status == status_filter.lower())
        rows = q.order_by(LabTestBooking.created_at.desc()).all()
        return [
            {
                "id": b.id,
                "patient_id": b.patient_id,
                "patient_name": b.patient.full_name if b.patient else "Unknown",
                "test_name": b.lab_test.name if b.lab_test else "Unknown",
                "status": b.status,
                "created_at": b.created_at,
            }
            for b in rows
        ]


def get_pending_bookings_for_patient(patient_id: int):
    """For the doctor's 'link to a booking' dropdown when writing a report."""
    with session_scope() as session:
        rows = (
            session.query(LabTestBooking)
            .filter(LabTestBooking.patient_id == patient_id, LabTestBooking.status == "pending")
            .all()
        )
        return [{"id": b.id, "test_name": b.lab_test.name if b.lab_test else "Unknown"} for b in rows]


# ---------------------------------------------------------------- Reports (doctor)

def create_lab_report(doctor_user_id: int, patient_id: int, test_name: str, result_summary: str,
                       findings: str, recommendation: str, booking_id: int = None) -> ServiceResult:
    if not test_name.strip():
        return ServiceResult(False, "Test name is required.")

    with session_scope() as session:
        doctor = session.query(Doctor).filter(Doctor.user_id == doctor_user_id).first()
        if not doctor:
            return ServiceResult(False, "Only doctors can issue lab reports.")

        report = LabReport(
            patient_id=patient_id,
            doctor_id=doctor.id,
            booking_id=booking_id,
            test_name=test_name.strip(),
            result_summary=result_summary or None,
            findings=findings or None,
            recommendation=recommendation or None,
            created_at=datetime.utcnow(),
        )
        session.add(report)

        if booking_id:
            booking = session.query(LabTestBooking).filter(LabTestBooking.id == booking_id).first()
            if booking:
                booking.status = "completed"

        session.flush()
        return ServiceResult(True, "Lab report issued.", report.id)


def get_patient_reports(patient_id: int):
    with session_scope() as session:
        rows = (
            session.query(LabReport)
            .filter(LabReport.patient_id == patient_id)
            .order_by(LabReport.created_at.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "test_name": r.test_name,
                "doctor_name": r.doctor.user.full_name if r.doctor else "Unknown",
                "created_at": r.created_at,
            }
            for r in rows
        ]


def get_doctor_reports(doctor_user_id: int):
    with session_scope() as session:
        doctor = session.query(Doctor).filter(Doctor.user_id == doctor_user_id).first()
        if not doctor:
            return []
        rows = (
            session.query(LabReport)
            .filter(LabReport.doctor_id == doctor.id)
            .order_by(LabReport.created_at.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "patient_name": r.patient.full_name if r.patient else "Unknown",
                "test_name": r.test_name,
                "created_at": r.created_at,
            }
            for r in rows
        ]


def get_patient_reports_full(patient_id: int):
    """Full detail including result_summary/findings/recommendation — used by SmartCare
    AI to answer a patient's own questions about their lab reports (unlike
    get_patient_reports, which only returns the summary for the UI list view)."""
    with session_scope() as session:
        rows = (
            session.query(LabReport)
            .filter(LabReport.patient_id == patient_id)
            .order_by(LabReport.created_at.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "test_name": r.test_name,
                "doctor_name": r.doctor.user.full_name if r.doctor else "Unknown",
                "result_summary": r.result_summary or "",
                "findings": r.findings or "",
                "recommendation": r.recommendation or "",
                "created_at": r.created_at,
            }
            for r in rows
        ]


def get_all_reports():
    """Read-only oversight for admin — admin never writes lab reports, only views them."""
    with session_scope() as session:
        rows = session.query(LabReport).order_by(LabReport.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "patient_name": r.patient.full_name if r.patient else "Unknown",
                "doctor_name": r.doctor.user.full_name if r.doctor else "Unknown",
                "test_name": r.test_name,
                "result_summary": r.result_summary or "",
                "findings": r.findings or "",
                "recommendation": r.recommendation or "",
                "created_at": r.created_at,
            }
            for r in rows
        ]


def generate_lab_report_pdf(report_id: int) -> bytes:
    with session_scope() as session:
        r = session.query(LabReport).filter(LabReport.id == report_id).first()
        if not r:
            raise ValueError("Report not found.")

        data = {
            "patient_name": r.patient.full_name if r.patient else "Unknown",
            "patient_age": _age_from_dob(r.patient.dob) if r.patient else "—",
            "patient_gender": (r.patient.gender or "—") if r.patient else "—",
            "doctor_name": r.doctor.user.full_name if r.doctor else "Unknown",
            "specialty": r.doctor.specialty.name if (r.doctor and r.doctor.specialty) else "General",
            "date_str": r.created_at.strftime("%d %B %Y") if r.created_at else "",
            "test_name": r.test_name,
            "result_summary": r.result_summary or "",
            "findings": r.findings or "",
            "recommendation": r.recommendation or "",
        }
    return build_lab_report_pdf(data)