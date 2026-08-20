"""Vitals / health record logic — matches the health_records table."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.database import session_scope
from models.models import User, HealthRecord, Doctor


@dataclass
class ServiceResult:
    ok: bool
    message: str


def search_patients(query: str, limit: int = 10):
    """Search patients by name or email — used by doctors to pick who they're recording vitals for."""
    query = (query or "").strip()
    with session_scope() as session:
        q = session.query(User).filter(User.role == "patient")
        if query:
            like = f"%{query}%"
            q = q.filter((User.full_name.ilike(like)) | (User.email.ilike(like)))
        rows = q.order_by(User.full_name).limit(limit).all()
        return [{"id": u.id, "full_name": u.full_name, "email": u.email} for u in rows]


def add_health_record(
    patient_id: int,
    doctor_user_id: int,
    heart_rate: Optional[int] = None,
    blood_pressure: str = "",
    troponin: Optional[float] = None,
    ejection_fraction: Optional[int] = None,
    cardiac_output: Optional[float] = None,
    pulse_oximetry: Optional[int] = None,
    ecg_note: str = "",
    diagnosis: str = "",
    notes: str = "",
) -> ServiceResult:
    with session_scope() as session:
        doctor_profile = session.query(Doctor).filter(Doctor.user_id == doctor_user_id).first()
        if doctor_profile is None:
            return ServiceResult(False, "Only doctors can record vitals.")

        patient = session.query(User).filter(User.id == patient_id, User.role == "patient").first()
        if patient is None:
            return ServiceResult(False, "Patient not found.")

        record = HealthRecord(
            patient_id=patient_id,
            recorded_at=datetime.utcnow(),
            heart_rate=heart_rate,
            blood_pressure=blood_pressure or None,
            troponin=troponin,
            ejection_fraction=ejection_fraction,
            cardiac_output=cardiac_output,
            pulse_oximetry=pulse_oximetry,
            ecg_note=ecg_note or None,
            diagnosis=diagnosis or None,
            notes=notes or None,
            doctor_id=doctor_profile.id,
        )
        session.add(record)
        session.flush()
        return ServiceResult(True, "Vitals recorded successfully.")


def get_latest_vitals(patient_id: int) -> Optional[dict]:
    with session_scope() as session:
        record = (
            session.query(HealthRecord)
            .filter(HealthRecord.patient_id == patient_id)
            .order_by(HealthRecord.recorded_at.desc())
            .first()
        )
        if record is None:
            return None
        return {
            "recorded_at": record.recorded_at,
            "heart_rate": record.heart_rate,
            "blood_pressure": record.blood_pressure,
            "troponin": float(record.troponin) if record.troponin is not None else None,
            "ejection_fraction": record.ejection_fraction,
            "cardiac_output": float(record.cardiac_output) if record.cardiac_output is not None else None,
            "pulse_oximetry": record.pulse_oximetry,
            "ecg_note": record.ecg_note,
            "diagnosis": record.diagnosis,
            "notes": record.notes,
        }


def get_vitals_history(patient_id: int, limit: int = 50):
    with session_scope() as session:
        rows = (
            session.query(HealthRecord)
            .filter(HealthRecord.patient_id == patient_id)
            .order_by(HealthRecord.recorded_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "recorded_at": r.recorded_at,
                "heart_rate": r.heart_rate,
                "blood_pressure": r.blood_pressure,
                "troponin": float(r.troponin) if r.troponin is not None else None,
                "ejection_fraction": r.ejection_fraction,
                "cardiac_output": float(r.cardiac_output) if r.cardiac_output is not None else None,
                "pulse_oximetry": r.pulse_oximetry,
                "diagnosis": r.diagnosis,
            }
            for r in rows
        ]


def get_doctor_patient_conditions(doctor_user_id: int):
    """Each patient this doctor has recorded vitals for, with their latest diagnosis —
    powers the doctor portal's 'Patient conditions' tab."""
    with session_scope() as session:
        doctor = session.query(Doctor).filter(Doctor.user_id == doctor_user_id).first()
        if not doctor:
            return []

        records = (
            session.query(HealthRecord)
            .filter(HealthRecord.doctor_id == doctor.id)
            .order_by(HealthRecord.recorded_at.desc())
            .all()
        )
        seen = set()
        result = []
        for r in records:
            if r.patient_id in seen:
                continue
            seen.add(r.patient_id)
            patient = session.query(User).filter(User.id == r.patient_id).first()
            result.append({
                "patient_name": patient.full_name if patient else "Unknown",
                "diagnosis": r.diagnosis or "No diagnosis recorded",
                "recorded_at": r.recorded_at,
            })
        return result


def get_admin_vitals_overview():
    """Aggregate stats for the admin analytics section."""
    with session_scope() as session:
        total_records = session.query(HealthRecord).count()
        rows = (
            session.query(HealthRecord)
            .filter(HealthRecord.heart_rate.isnot(None))
            .order_by(HealthRecord.recorded_at.asc())
            .all()
        )
        heart_rate_series = [
            {"date": r.recorded_at.date().isoformat() if r.recorded_at else "unknown", "heart_rate": r.heart_rate}
            for r in rows
        ]
        return {"total_records": total_records, "heart_rate_series": heart_rate_series}