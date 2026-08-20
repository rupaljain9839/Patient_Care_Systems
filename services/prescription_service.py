"""Doctor-issued prescriptions, in the fixed PDF format."""
from dataclasses import dataclass
from datetime import datetime, date

from core.database import session_scope
from core.pdf_generator import build_prescription_pdf
from models.models import Prescription, PrescriptionItem, Doctor, User


@dataclass
class ServiceResult:
    ok: bool
    message: str
    prescription_id: int = None


def _age_from_dob(dob):
    if not dob:
        return "—"
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def create_prescription(doctor_user_id: int, patient_id: int, diagnosis: str, notes: str, items: list) -> ServiceResult:
    """items: list of {medicine_name, dosage, frequency, duration, instructions}. Empty medicine_name rows are skipped."""
    valid_items = [i for i in items if i.get("medicine_name", "").strip()]
    if not valid_items:
        return ServiceResult(False, "Add at least one medicine.")

    with session_scope() as session:
        doctor = session.query(Doctor).filter(Doctor.user_id == doctor_user_id).first()
        if not doctor:
            return ServiceResult(False, "Only doctors can issue prescriptions.")

        prescription = Prescription(
            patient_id=patient_id,
            doctor_id=doctor.id,
            diagnosis=diagnosis or None,
            notes=notes or None,
            created_at=datetime.utcnow(),
        )
        session.add(prescription)
        session.flush()

        for item in valid_items:
            session.add(PrescriptionItem(
                prescription_id=prescription.id,
                medicine_name=item["medicine_name"].strip(),
                dosage=item.get("dosage", ""),
                frequency=item.get("frequency", ""),
                duration=item.get("duration", ""),
                instructions=item.get("instructions", ""),
            ))

        session.flush()
        return ServiceResult(True, "Prescription issued.", prescription.id)


def get_patient_prescriptions(patient_id: int):
    with session_scope() as session:
        rows = (
            session.query(Prescription)
            .filter(Prescription.patient_id == patient_id)
            .order_by(Prescription.created_at.desc())
            .all()
        )
        return [
            {
                "id": p.id,
                "doctor_name": p.doctor.user.full_name if p.doctor else "Unknown",
                "specialty": p.doctor.specialty.name if (p.doctor and p.doctor.specialty) else "General",
                "diagnosis": p.diagnosis or "—",
                "created_at": p.created_at,
                "item_count": len(p.items),
            }
            for p in rows
        ]


def get_doctor_prescriptions(doctor_user_id: int):
    with session_scope() as session:
        doctor = session.query(Doctor).filter(Doctor.user_id == doctor_user_id).first()
        if not doctor:
            return []
        rows = (
            session.query(Prescription)
            .filter(Prescription.doctor_id == doctor.id)
            .order_by(Prescription.created_at.desc())
            .all()
        )
        return [
            {
                "id": p.id,
                "patient_name": p.patient.full_name if p.patient else "Unknown",
                "diagnosis": p.diagnosis or "—",
                "created_at": p.created_at,
            }
            for p in rows
        ]


def get_patient_prescriptions_full(patient_id: int):
    """Full detail including medicine items — used by SmartCare AI to answer a
    patient's own questions about their prescriptions (unlike get_patient_prescriptions,
    which only returns summary counts for the UI list view)."""
    with session_scope() as session:
        rows = (
            session.query(Prescription)
            .filter(Prescription.patient_id == patient_id)
            .order_by(Prescription.created_at.desc())
            .all()
        )
        return [
            {
                "id": p.id,
                "doctor_name": p.doctor.user.full_name if p.doctor else "Unknown",
                "specialty": p.doctor.specialty.name if (p.doctor and p.doctor.specialty) else "General",
                "diagnosis": p.diagnosis or "—",
                "notes": p.notes or "",
                "created_at": p.created_at,
                "items": [
                    {
                        "medicine_name": i.medicine_name,
                        "dosage": i.dosage or "",
                        "frequency": i.frequency or "",
                        "duration": i.duration or "",
                        "instructions": i.instructions or "",
                    }
                    for i in p.items
                ],
            }
            for p in rows
        ]


def get_all_prescriptions():
    """Read-only oversight for admin — admin never writes prescriptions, only views them."""
    with session_scope() as session:
        rows = session.query(Prescription).order_by(Prescription.created_at.desc()).all()
        return [
            {
                "id": p.id,
                "patient_name": p.patient.full_name if p.patient else "Unknown",
                "doctor_name": p.doctor.user.full_name if p.doctor else "Unknown",
                "diagnosis": p.diagnosis or "—",
                "notes": p.notes or "",
                "created_at": p.created_at,
                "item_count": len(p.items),
                "items": [
                    {
                        "medicine_name": i.medicine_name,
                        "dosage": i.dosage,
                        "frequency": i.frequency,
                        "duration": i.duration,
                        "instructions": i.instructions,
                    }
                    for i in p.items
                ],
            }
            for p in rows
        ]


def generate_prescription_pdf(prescription_id: int) -> bytes:
    with session_scope() as session:
        p = session.query(Prescription).filter(Prescription.id == prescription_id).first()
        if not p:
            raise ValueError("Prescription not found.")

        data = {
            "patient_name": p.patient.full_name if p.patient else "Unknown",
            "patient_age": _age_from_dob(p.patient.dob) if p.patient else "—",
            "patient_gender": (p.patient.gender or "—") if p.patient else "—",
            "doctor_name": p.doctor.user.full_name if p.doctor else "Unknown",
            "specialty": p.doctor.specialty.name if (p.doctor and p.doctor.specialty) else "General",
            "date_str": p.created_at.strftime("%d %B %Y") if p.created_at else "",
            "diagnosis": p.diagnosis or "",
            "notes": p.notes or "",
            "items": [
                {
                    "medicine_name": i.medicine_name,
                    "dosage": i.dosage,
                    "frequency": i.frequency,
                    "duration": i.duration,
                    "instructions": i.instructions,
                }
                for i in p.items
            ],
        }
    return build_prescription_pdf(data)