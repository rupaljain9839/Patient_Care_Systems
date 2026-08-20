"""ORM table definitions matching the patient_care_db schema exactly."""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Date,
    Time,
    Numeric,
    Text,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(160), nullable=False)  # not DB-unique — enforced at app level
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # "patient" | "doctor" | "admin"
    gender = Column(String(20), nullable=True)
    dob = Column(Date, nullable=True)
    phone = Column(String(30), nullable=True)
    is_active = Column(Boolean, nullable=True, default=True)
    created_at = Column(DateTime, nullable=True)

    doctor_profile = relationship(
        "Doctor", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"


class Specialty(Base):
    __tablename__ = "specialties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    icon = Column(String(16), nullable=True)

    doctors = relationship("Doctor", back_populates="specialty")


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    specialty_id = Column(Integer, ForeignKey("specialties.id"), nullable=True)
    bio = Column(Text, nullable=True)
    experience_years = Column(Integer, nullable=True)
    consultation_fee = Column(Numeric(10, 2), nullable=True)
    avatar_url = Column(String(255), nullable=True)

    user = relationship("User", back_populates="doctor_profile")
    specialty = relationship("Specialty", back_populates="doctors")
    slots = relationship("DoctorSlot", back_populates="doctor", cascade="all, delete-orphan")


class DoctorSlot(Base):
    __tablename__ = "doctor_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday ... 6=Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_active = Column(Boolean, nullable=True, default=True)

    doctor = relationship("Doctor", back_populates="slots")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint("doctor_id", "scheduled_date", "start_time", name="uq_doctor_slot"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=True)
    status = Column(String(20), nullable=True)  # "booked" | "cancelled" | "completed"
    reason = Column(String(255), nullable=True)
    source = Column(String(20), nullable=True)  # "patient" | "chatbot" | "admin"
    created_at = Column(DateTime, nullable=True)

    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("Doctor", foreign_keys=[doctor_id])


class HealthRecord(Base):
    __tablename__ = "health_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recorded_at = Column(DateTime, nullable=True)
    heart_rate = Column(Integer, nullable=True)
    blood_pressure = Column(String(20), nullable=True)
    troponin = Column(Numeric(6, 3), nullable=True)
    ejection_fraction = Column(Integer, nullable=True)
    cardiac_output = Column(Numeric(5, 2), nullable=True)
    pulse_oximetry = Column(Integer, nullable=True)
    ecg_note = Column(String(120), nullable=True)
    diagnosis = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)


class Enquiry(Base):
    __tablename__ = "enquiries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    full_name = Column(String(120), nullable=False)
    phone = Column(String(30), nullable=False)
    preferred_time = Column(String(40), nullable=True)
    message = Column(Text, nullable=True)
    status = Column(String(20), nullable=True, default="new")
    created_at = Column(DateTime, nullable=True)

    patient = relationship("User", foreign_keys=[patient_id])


# ---------- Pharmacy: medicine catalog (FIXED: stock_quantity -> stock) ----------

class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    category = Column(String(60), nullable=True)
    strength = Column(String(40), nullable=True)  # e.g. "20 mg" — optional, unused by current UI
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    stock = Column(Integer, nullable=False, default=0)  # was stock_quantity
    icon = Column(String(16), nullable=True)
    image_url = Column(String(500), nullable=True)  # admin-managed product photo
    is_active = Column(Boolean, nullable=True, default=True)


# ---------- Prescriptions ----------

class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    diagnosis = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True)

    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("Doctor", foreign_keys=[doctor_id])
    items = relationship("PrescriptionItem", back_populates="prescription", cascade="all, delete-orphan")


class PrescriptionItem(Base):
    """FIXED: replaced dosage_instructions/quantity with the four fields the service
    layer and PDF generator actually use (dosage, frequency, duration, instructions)."""
    __tablename__ = "prescription_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False)
    medicine_name = Column(String(150), nullable=False)
    dosage = Column(String(60), nullable=True)
    frequency = Column(String(60), nullable=True)
    duration = Column(String(60), nullable=True)
    instructions = Column(String(255), nullable=True)

    prescription = relationship("Prescription", back_populates="items")


# ---------- Lab tests / bookings / reports ----------

class LabTest(Base):
    __tablename__ = "lab_tests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    category = Column(String(60), nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    description = Column(Text, nullable=True)
    icon = Column(String(16), nullable=True)
    is_active = Column(Boolean, nullable=True, default=True)


class LabTestBooking(Base):
    """FIXED: renamed booking_date -> scheduled_date and made it nullable, since
    patients can book without picking a date up front (book_lab_test defaults it to None)."""
    __tablename__ = "lab_test_bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lab_test_id = Column(Integer, ForeignKey("lab_tests.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)  # ordering doctor, if any
    scheduled_date = Column(Date, nullable=True)  # was booking_date, NOT NULL
    status = Column(String(20), nullable=True, default="booked")  # "pending" | "booked" | "completed" | "cancelled"
    created_at = Column(DateTime, nullable=True)

    patient = relationship("User", foreign_keys=[patient_id])
    lab_test = relationship("LabTest")
    doctor = relationship("Doctor", foreign_keys=[doctor_id])
    report = relationship("LabReport", back_populates="booking", uselist=False, cascade="all, delete-orphan")


class LabReport(Base):
    """FIXED: added patient_id, test_name, findings, recommendation (all used by
    lab_service.py and pdf_generator.py but missing from the previous version).
    booking_id is now optional, since create_lab_report() allows issuing a report
    without a prior booking."""
    __tablename__ = "lab_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    booking_id = Column(Integer, ForeignKey("lab_test_bookings.id"), nullable=True, unique=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    test_name = Column(String(150), nullable=False)
    result_summary = Column(String(255), nullable=True)
    findings = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True)

    patient = relationship("User", foreign_keys=[patient_id])
    booking = relationship("LabTestBooking", back_populates="report")
    doctor = relationship("Doctor", foreign_keys=[doctor_id])


# ---------- Medicine orders ----------

class MedicineOrder(Base):
    __tablename__ = "medicine_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)
    status = Column(String(20), nullable=True, default="placed")
    created_at = Column(DateTime, nullable=True)

    patient = relationship("User", foreign_keys=[patient_id])
    items = relationship("MedicineOrderItem", back_populates="order", cascade="all, delete-orphan")


class MedicineOrderItem(Base):
    __tablename__ = "medicine_order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("medicine_orders.id"), nullable=False)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=True)
    medicine_name = Column(String(150), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False, default=0)

    order = relationship("MedicineOrder", back_populates="items")
    medicine = relationship("Medicine")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(12), nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True)