"""Appointment booking and management. Slots are generated on the fly from
DoctorSlot weekly availability, minus whatever's already booked for that date."""
from datetime import datetime, date, timedelta
from dataclasses import dataclass

from core.database import session_scope
from models.models import Appointment, Doctor, DoctorSlot, User

SLOT_MINUTES = 30


@dataclass
class BookingResult:
    ok: bool
    message: str


def _generate_day_slots(doctor_id: int, target_date: date):
    weekday = target_date.weekday()  # Monday=0 ... Sunday=6, matches DoctorSlot.day_of_week
    with session_scope() as session:
        slot_defs = (
            session.query(DoctorSlot)
            .filter(DoctorSlot.doctor_id == doctor_id, DoctorSlot.day_of_week == weekday, DoctorSlot.is_active.is_(True))
            .all()
        )
        ranges = [(s.start_time, s.end_time) for s in slot_defs]

        booked_rows = (
            session.query(Appointment.start_time)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.scheduled_date == target_date,
                Appointment.status != "cancelled",
            )
            .all()
        )
        booked_times = {b[0] for b in booked_rows}

    slots = []
    for start, end in ranges:
        cur = datetime.combine(target_date, start)
        end_dt = datetime.combine(target_date, end)
        while cur < end_dt:
            t = cur.time()
            slots.append({"time": t, "booked": t in booked_times})
            cur += timedelta(minutes=SLOT_MINUTES)
    return slots


def get_available_slots(doctor_id: int, target_date: date):
    return [s["time"] for s in _generate_day_slots(doctor_id, target_date) if not s["booked"]]


def get_slot_summary(doctor_id: int, target_date: date):
    """Returns (total_slots, free_slots) for the 'X of Y slots free' caption."""
    slots = _generate_day_slots(doctor_id, target_date)
    return len(slots), len([s for s in slots if not s["booked"]])


def book_appointment(patient_id: int, doctor_id: int, target_date: date, start_time, reason: str = "") -> BookingResult:
    if target_date < date.today():
        return BookingResult(False, "Cannot book an appointment in the past.")

    with session_scope() as session:
        existing = (
            session.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.scheduled_date == target_date,
                Appointment.start_time == start_time,
                Appointment.status != "cancelled",
            )
            .first()
        )
        if existing:
            return BookingResult(False, "That slot was just booked by someone else — please pick another.")

        end_dt = datetime.combine(target_date, start_time) + timedelta(minutes=SLOT_MINUTES)
        session.add(
            Appointment(
                patient_id=patient_id,
                doctor_id=doctor_id,
                scheduled_date=target_date,
                start_time=start_time,
                end_time=end_dt.time(),
                status="booked",
                reason=reason or None,
                source="patient",
                created_at=datetime.utcnow(),
            )
        )
        return BookingResult(True, "Appointment booked successfully.")


def _appt_to_dict(a: Appointment) -> dict:
    return {
        "id": a.id,
        "patient_id": a.patient_id,
        "patient_name": a.patient.full_name if a.patient else "Unknown",
        "doctor_id": a.doctor_id,
        "doctor_name": a.doctor.user.full_name if a.doctor else "Unknown",
        "specialty": a.doctor.specialty.name if (a.doctor and a.doctor.specialty) else "General",
        "scheduled_date": a.scheduled_date,
        "start_time": a.start_time,
        "end_time": a.end_time,
        "status": a.status,
        "reason": a.reason,
    }


def get_patient_appointments(patient_id: int, upcoming_only: bool = False):
    with session_scope() as session:
        q = session.query(Appointment).filter(Appointment.patient_id == patient_id)
        if upcoming_only:
            q = q.filter(Appointment.scheduled_date >= date.today(), Appointment.status != "cancelled")
        q = q.order_by(Appointment.scheduled_date.asc(), Appointment.start_time.asc())
        return [_appt_to_dict(a) for a in q.all()]


def get_patient_appointments_in_range(patient_id: int, start_date: date, end_date: date):
    with session_scope() as session:
        rows = (
            session.query(Appointment)
            .filter(
                Appointment.patient_id == patient_id,
                Appointment.scheduled_date >= start_date,
                Appointment.scheduled_date <= end_date,
                Appointment.status != "cancelled",
            )
            .order_by(Appointment.start_time.asc())
            .all()
        )
        return [_appt_to_dict(a) for a in rows]


def get_next_appointment(patient_id: int):
    appts = get_patient_appointments(patient_id, upcoming_only=True)
    return appts[0] if appts else None


def cancel_appointment(appointment_id: int, patient_id: int = None) -> BookingResult:
    """If patient_id is given, only cancels if it belongs to that patient (patient self-service).
    If patient_id is None, cancels regardless (admin/doctor use)."""
    with session_scope() as session:
        q = session.query(Appointment).filter(Appointment.id == appointment_id)
        if patient_id is not None:
            q = q.filter(Appointment.patient_id == patient_id)
        appt = q.first()
        if not appt:
            return BookingResult(False, "Appointment not found.")
        appt.status = "cancelled"
        return BookingResult(True, "Appointment cancelled.")


def update_appointment_status(appointment_id: int, new_status: str) -> BookingResult:
    with session_scope() as session:
        appt = session.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appt:
            return BookingResult(False, "Appointment not found.")
        appt.status = new_status
        return BookingResult(True, f"Status updated to {new_status}.")


def get_doctor_appointments(doctor_user_id: int, upcoming_only: bool = True):
    with session_scope() as session:
        doctor = session.query(Doctor).filter(Doctor.user_id == doctor_user_id).first()
        if not doctor:
            return []
        q = session.query(Appointment).filter(Appointment.doctor_id == doctor.id)
        if upcoming_only:
            q = q.filter(Appointment.scheduled_date >= date.today(), Appointment.status != "cancelled")
        q = q.order_by(Appointment.scheduled_date.asc(), Appointment.start_time.asc())
        return [_appt_to_dict(a) for a in q.all()]


def get_all_appointments(status_filter: str = None, start_date: date = None, end_date: date = None):
    """For the admin 'All appointments' tab."""
    with session_scope() as session:
        q = session.query(Appointment)
        if status_filter and status_filter != "All":
            q = q.filter(Appointment.status == status_filter.lower())
        if start_date:
            q = q.filter(Appointment.scheduled_date >= start_date)
        if end_date:
            q = q.filter(Appointment.scheduled_date <= end_date)
        q = q.order_by(Appointment.scheduled_date.desc(), Appointment.start_time.desc())
        return [_appt_to_dict(a) for a in q.all()]


def get_busiest_doctors(limit: int = 6):
    """Top doctors by upcoming appointment count — for the admin analytics 'Busiest doctors' chart."""
    with session_scope() as session:
        rows = (
            session.query(Appointment)
            .filter(Appointment.scheduled_date >= date.today(), Appointment.status != "cancelled")
            .all()
        )
        counts = {}
        for a in rows:
            name = a.doctor.user.full_name if a.doctor else "Unknown"
            counts[name] = counts.get(name, 0) + 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]


def get_staffing_gaps():
    """Specialties with zero doctors who have any bookable availability — a proactive
    insight for admins, since a specialty with no bookable hours means patients silently
    can't book anyone in it."""
    from models.models import Specialty

    with session_scope() as session:
        specialties = session.query(Specialty).all()
        gaps = []
        for sp in specialties:
            doctors = session.query(Doctor).filter(Doctor.specialty_id == sp.id).all()
            has_slot = any(
                session.query(DoctorSlot).filter(DoctorSlot.doctor_id == d.id, DoctorSlot.is_active.is_(True)).count() > 0
                for d in doctors
            )
            if not has_slot:
                gaps.append(sp.name)
        return gaps


def get_doctor_stats(doctor_user_id: int):
    """Today / upcoming / completed / unique-patient counts for a doctor's own dashboard."""
    with session_scope() as session:
        doctor = session.query(Doctor).filter(Doctor.user_id == doctor_user_id).first()
        if not doctor:
            return {"today": 0, "upcoming": 0, "completed": 0, "unique_patients": 0}

        today_count = (
            session.query(Appointment)
            .filter(Appointment.doctor_id == doctor.id, Appointment.scheduled_date == date.today(), Appointment.status != "cancelled")
            .count()
        )
        upcoming_count = (
            session.query(Appointment)
            .filter(Appointment.doctor_id == doctor.id, Appointment.scheduled_date >= date.today(), Appointment.status != "cancelled")
            .count()
        )
        completed_count = (
            session.query(Appointment)
            .filter(Appointment.doctor_id == doctor.id, Appointment.status == "completed")
            .count()
        )
        unique_patients = (
            session.query(Appointment.patient_id)
            .filter(Appointment.doctor_id == doctor.id, Appointment.status != "cancelled")
            .distinct()
            .count()
        )
        return {
            "today": today_count,
            "upcoming": upcoming_count,
            "completed": completed_count,
            "unique_patients": unique_patients,
        }


def get_doctor_appointments_in_range(doctor_user_id: int, start_date: date, end_date: date):
    """For the doctor's own weekly calendar — all their appointments in a date range."""
    with session_scope() as session:
        doctor = session.query(Doctor).filter(Doctor.user_id == doctor_user_id).first()
        if not doctor:
            return []
        rows = (
            session.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor.id,
                Appointment.scheduled_date >= start_date,
                Appointment.scheduled_date <= end_date,
                Appointment.status != "cancelled",
            )
            .order_by(Appointment.start_time.asc())
            .all()
        )
        return [_appt_to_dict(a) for a in rows]


def get_admin_appointment_overview():
    """Aggregate stats for the admin Analytics tab."""
    with session_scope() as session:
        total = session.query(Appointment).filter(Appointment.status != "cancelled").count()
        upcoming = (
            session.query(Appointment)
            .filter(Appointment.scheduled_date >= date.today(), Appointment.status != "cancelled")
            .count()
        )
        rows = session.query(Appointment).filter(Appointment.status != "cancelled").all()

        per_day = {}
        by_status = {}
        by_specialty = {}
        for a in rows:
            d_key = a.scheduled_date.isoformat()
            per_day[d_key] = per_day.get(d_key, 0) + 1
            status_key = a.status or "booked"
            by_status[status_key] = by_status.get(status_key, 0) + 1
            specialty_key = a.doctor.specialty.name if (a.doctor and a.doctor.specialty) else "General"
            by_specialty[specialty_key] = by_specialty.get(specialty_key, 0) + 1

        return {
            "total": total,
            "upcoming": upcoming,
            "per_day": per_day,
            "by_status": by_status,
            "by_specialty": by_specialty,
        }