"""Patient 'Send Enquiry' feature — a lightweight callback-request form,
separate from full appointment booking. Admins work through these from the
Admin Console."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.database import session_scope
from models.models import Enquiry, User

PREFERRED_TIME_OPTIONS = ["Morning (9am–12pm)", "Afternoon (12pm–4pm)", "Evening (4pm–8pm)", "Anytime"]
STATUS_OPTIONS = ["new", "contacted", "resolved"]


@dataclass
class ServiceResult:
    ok: bool
    message: str


def submit_enquiry(patient_id: int, name: str, phone: str, preferred_time: str, message: str = "") -> ServiceResult:
    if not name.strip() or not phone.strip():
        return ServiceResult(False, "Name and phone number are required.")

    with session_scope() as session:
        enquiry = Enquiry(
            patient_id=patient_id,
            full_name=name.strip(),
            phone=phone.strip(),
            preferred_time=preferred_time,
            message=message.strip() or None,
            status="new",
            created_at=datetime.utcnow(),
        )
        session.add(enquiry)
        session.flush()
        return ServiceResult(True, "Your enquiry has been submitted. Our team will call you back soon.")


def get_patient_enquiries(patient_id: int, limit: int = 20):
    with session_scope() as session:
        rows = (
            session.query(Enquiry)
            .filter(Enquiry.patient_id == patient_id)
            .order_by(Enquiry.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": e.id,
                "name": e.full_name,
                "phone": e.phone,
                "preferred_time": e.preferred_time,
                "message": e.message,
                "status": e.status or "new",
                "created_at": e.created_at,
            }
            for e in rows
        ]


def get_all_enquiries(status_filter: Optional[str] = None, limit: int = 200):
    """For the admin console. status_filter should be one of STATUS_OPTIONS, or None/'all' for everything."""
    with session_scope() as session:
        q = session.query(Enquiry, User).join(User, Enquiry.patient_id == User.id)
        if status_filter and status_filter != "all":
            q = q.filter(Enquiry.status == status_filter)
        rows = q.order_by(Enquiry.created_at.desc()).limit(limit).all()
        return [
            {
                "id": e.id,
                "patient_name": user.full_name,
                "patient_email": user.email,
                "name": e.full_name,
                "phone": e.phone,
                "preferred_time": e.preferred_time or "—",
                "message": e.message or "—",
                "status": e.status or "new",
                "created_at": e.created_at,
            }
            for e, user in rows
        ]


def update_enquiry_status(enquiry_id: int, status: str) -> ServiceResult:
    if status not in STATUS_OPTIONS:
        return ServiceResult(False, "Invalid status.")
    with session_scope() as session:
        enquiry = session.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
        if enquiry is None:
            return ServiceResult(False, "Enquiry not found.")
        enquiry.status = status
        return ServiceResult(True, "Status updated.")