"""Registration and authentication logic — matches the patient_care_db schema
(no separate patient/doctor profile tables; doctors link straight into `doctors`)."""
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

from core.database import session_scope
from core.security import hash_password, verify_password, validate_password
from models.models import User, Doctor, Specialty


@dataclass
class AuthResult:
    ok: bool
    message: str
    user_id: Optional[int] = None
    role: Optional[str] = None


def email_exists(email: str) -> bool:
    with session_scope() as session:
        return session.query(User).filter(User.email == email.lower().strip()).first() is not None


def list_specialties():
    """Returns [(id, name), ...] for populating dropdowns."""
    with session_scope() as session:
        rows = session.query(Specialty).order_by(Specialty.name).all()
        return [(s.id, s.name) for s in rows]


def register_patient(
    full_name: str,
    email: str,
    password: str,
    phone: str = "",
    gender: str = "",
    dob: Optional[date] = None,
) -> AuthResult:
    email = email.lower().strip()

    ok, msg = validate_password(password)
    if not ok:
        return AuthResult(False, msg)

    if email_exists(email):
        return AuthResult(False, "An account with this email already exists.")

    with session_scope() as session:
        user = User(
            full_name=full_name.strip(),
            email=email,
            password_hash=hash_password(password),
            role="patient",
            gender=gender or None,
            dob=dob,
            phone=phone or None,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        session.add(user)
        session.flush()
        return AuthResult(True, "Patient account created successfully.", user.id, "patient")


def register_doctor(
    full_name: str,
    email: str,
    password: str,
    phone: str = "",
    gender: str = "",
    dob: Optional[date] = None,
    specialty_id: Optional[int] = None,
    bio: str = "",
    experience_years: int = 0,
    consultation_fee: float = 0.0,
) -> AuthResult:
    email = email.lower().strip()

    ok, msg = validate_password(password)
    if not ok:
        return AuthResult(False, msg)

    if email_exists(email):
        return AuthResult(False, "An account with this email already exists.")

    with session_scope() as session:
        user = User(
            full_name=full_name.strip(),
            email=email,
            password_hash=hash_password(password),
            role="doctor",
            gender=gender or None,
            dob=dob,
            phone=phone or None,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        session.add(user)
        session.flush()  # need user.id for the doctors row

        doctor = Doctor(
            user_id=user.id,
            specialty_id=specialty_id,
            bio=bio or None,
            experience_years=experience_years,
            consultation_fee=consultation_fee,
            avatar_url=None,
        )
        session.add(doctor)
        session.flush()
        return AuthResult(True, "Doctor account created successfully.", user.id, "doctor")


def authenticate(email: str, password: str) -> AuthResult:
    email = email.lower().strip()

    with session_scope() as session:
        user = session.query(User).filter(User.email == email).first()

        if user is None or not verify_password(password, user.password_hash):
            return AuthResult(False, "Invalid email or password.")

        if user.is_active is False:
            return AuthResult(False, "This account has been deactivated. Contact an administrator.")

        return AuthResult(True, "Login successful.", user.id, user.role)


def get_user_summary(user_id: int) -> Optional[dict]:
    """Lightweight dict for storing in st.session_state (avoids detached ORM objects)."""
    with session_scope() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user is None:
            return None
        return {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "phone": user.phone,
        }