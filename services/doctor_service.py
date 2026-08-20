"""Doctor directory and availability management."""
from core.database import session_scope
from models.models import Doctor, User, DoctorSlot

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _doctor_to_dict(d: Doctor) -> dict:
    return {
        "id": d.id,
        "user_id": d.user_id,
        "full_name": d.user.full_name,
        "specialty_id": d.specialty_id,
        "specialty": d.specialty.name if d.specialty else "General",
        "specialty_icon": d.specialty.icon if d.specialty else "🩺",
        "experience_years": d.experience_years or 0,
        "consultation_fee": float(d.consultation_fee) if d.consultation_fee is not None else 0.0,
        "bio": d.bio or "",
    }


def list_doctors(specialty_id=None, search: str = "", sort: str = "fee_asc"):
    with session_scope() as session:
        q = session.query(Doctor).join(User, Doctor.user_id == User.id).filter(User.is_active.is_(True))
        if specialty_id:
            q = q.filter(Doctor.specialty_id == specialty_id)
        if search:
            like = f"%{search}%"
            q = q.filter(User.full_name.ilike(like))

        if sort == "fee_asc":
            q = q.order_by(Doctor.consultation_fee.asc())
        elif sort == "fee_desc":
            q = q.order_by(Doctor.consultation_fee.desc())
        elif sort == "experience_desc":
            q = q.order_by(Doctor.experience_years.desc())
        else:
            q = q.order_by(User.full_name.asc())

        return [_doctor_to_dict(d) for d in q.all()]


def get_doctor(doctor_id: int):
    with session_scope() as session:
        d = session.query(Doctor).filter(Doctor.id == doctor_id).first()
        return _doctor_to_dict(d) if d else None


def get_doctor_slots(doctor_id: int):
    with session_scope() as session:
        rows = (
            session.query(DoctorSlot)
            .filter(DoctorSlot.doctor_id == doctor_id, DoctorSlot.is_active.is_(True))
            .order_by(DoctorSlot.day_of_week, DoctorSlot.start_time)
            .all()
        )
        return [
            {"id": r.id, "day_of_week": r.day_of_week, "start_time": r.start_time, "end_time": r.end_time}
            for r in rows
        ]


def format_availability_summary(doctor_id: int) -> str:
    """Groups this doctor's slots by identical (start,end) time range into a readable string,
    e.g. 'Morning · Mon, Wed, Fri · 09:00-13:00'."""
    slots = get_doctor_slots(doctor_id)
    if not slots:
        return "No availability set yet"

    groups = {}
    for s in slots:
        key = (s["start_time"], s["end_time"])
        groups.setdefault(key, []).append(s["day_of_week"])

    parts = []
    for (start, end), days in groups.items():
        day_labels = ", ".join(DAY_NAMES[d] for d in sorted(set(days)))
        session_label = "Morning" if start.hour < 12 else ("Afternoon" if start.hour < 17 else "Evening")
        parts.append(f"{session_label} · {day_labels} · {start.strftime('%H:%M')}-{end.strftime('%H:%M')}")
    return "; ".join(parts)


def add_doctor_slot(doctor_id: int, days_of_week: list, start_time, end_time):
    with session_scope() as session:
        for dow in days_of_week:
            session.add(
                DoctorSlot(doctor_id=doctor_id, day_of_week=dow, start_time=start_time, end_time=end_time, is_active=True)
            )


def delete_doctor_slot(slot_id: int):
    with session_scope() as session:
        session.query(DoctorSlot).filter(DoctorSlot.id == slot_id).delete()


def list_doctors_admin():
    """Full doctor listing for admin management — includes contact info and active status."""
    with session_scope() as session:
        rows = session.query(Doctor).all()
        return [
            {
                "id": d.id,
                "user_id": d.user_id,
                "full_name": d.user.full_name,
                "email": d.user.email,
                "phone": d.user.phone,
                "is_active": d.user.is_active,
                "specialty_id": d.specialty_id,
                "specialty": d.specialty.name if d.specialty else "General",
                "experience_years": d.experience_years or 0,
                "consultation_fee": float(d.consultation_fee) if d.consultation_fee is not None else 0.0,
                "bio": d.bio or "",
            }
            for d in rows
        ]


def update_doctor(doctor_id: int, specialty_id=None, experience_years=None, consultation_fee=None, bio=None, phone=None):
    with session_scope() as session:
        d = session.query(Doctor).filter(Doctor.id == doctor_id).first()
        if not d:
            return False, "Doctor not found."
        if specialty_id is not None:
            d.specialty_id = specialty_id
        if experience_years is not None:
            d.experience_years = experience_years
        if consultation_fee is not None:
            d.consultation_fee = consultation_fee
        if bio is not None:
            d.bio = bio
        if phone is not None:
            user = session.query(User).filter(User.id == d.user_id).first()
            if user:
                user.phone = phone
        return True, "Doctor updated."


def set_doctor_active(user_id: int, is_active: bool):
    with session_scope() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "User not found."
        user.is_active = is_active
        return True, "Doctor reactivated." if is_active else "Doctor deactivated."


def get_doctor_dependency_counts(doctor_id: int):
    """How many appointments/health records reference this doctor — determines whether
    a permanent delete is safe."""
    from models.models import Appointment, HealthRecord

    with session_scope() as session:
        appt_count = session.query(Appointment).filter(Appointment.doctor_id == doctor_id).count()
        record_count = session.query(HealthRecord).filter(HealthRecord.doctor_id == doctor_id).count()
        return appt_count, record_count


def delete_doctor_permanently(doctor_id: int):
    """Only succeeds if this doctor has zero appointments and zero health records —
    otherwise deleting would either orphan that history or fail on a DB constraint.
    Deactivation (set_doctor_active) is the safe default for doctors with any history."""
    appt_count, record_count = get_doctor_dependency_counts(doctor_id)
    if appt_count or record_count:
        return False, (
            f"Cannot delete — this doctor has {appt_count} appointment(s) and {record_count} "
            "vitals record(s) on file. Deactivate instead to hide them from booking without losing history."
        )

    with session_scope() as session:
        d = session.query(Doctor).filter(Doctor.id == doctor_id).first()
        if not d:
            return False, "Doctor not found."
        user = session.query(User).filter(User.id == d.user_id).first()
        if user:
            session.delete(user)  # cascades to Doctor -> DoctorSlot via the User.doctor_profile relationship
        return True, "Doctor permanently deleted."


def list_all_doctor_slots():
    """For the admin Availability tab — every slot across every doctor."""
    with session_scope() as session:
        rows = (
            session.query(DoctorSlot)
            .join(Doctor, DoctorSlot.doctor_id == Doctor.id)
            .join(User, Doctor.user_id == User.id)
            .order_by(User.full_name, DoctorSlot.day_of_week)
            .all()
        )
        return [
            {
                "id": r.id,
                "doctor_id": r.doctor_id,
                "doctor_name": r.doctor.user.full_name,
                "day_of_week": r.day_of_week,
                "day_name": DAY_FULL_NAMES[r.day_of_week],
                "start_time": r.start_time,
                "end_time": r.end_time,
            }
            for r in rows
        ]