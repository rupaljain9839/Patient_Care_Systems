"""Creates all tables (if missing) and seeds the admin user, default specialties,
and the SmartCare AI knowledge base.
Run this once before starting the app:
    python seed_data.py
Safe to run again later — nothing here duplicates existing data.
"""
from datetime import datetime

from core.config import settings
from core.database import init_db, session_scope
from core.security import hash_password
from models.models import User, Specialty

DEFAULT_SPECIALTIES = [
    ("Cardiology", "Heart and cardiovascular conditions", "🫀"),
    ("General Medicine", "General checkups and common illnesses", "🩺"),
    ("Pediatrics", "Care for infants, children, and teens", "🧒"),
    ("Dermatology", "Skin, hair, and nail conditions", "🧴"),
    ("Orthopedics", "Bones, joints, and muscles", "🦴"),
    ("Neurology", "Brain and nervous system", "🧠"),
]


def seed_admin():
    with session_scope() as session:
        existing = (
            session.query(User)
            .filter(User.email == settings.admin_email.lower().strip())
            .first()
        )
        if existing:
            print(f"Admin account already exists: {existing.email}")
            return

        admin = User(
            full_name=settings.admin_name,
            email=settings.admin_email.lower().strip(),
            password_hash=hash_password(settings.admin_password),
            role="admin",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        session.add(admin)
        print(f"Created admin account: {admin.email}")


def seed_specialties():
    with session_scope() as session:
        existing_names = {s.name for s in session.query(Specialty).all()}
        created = 0
        for name, description, icon in DEFAULT_SPECIALTIES:
            if name in existing_names:
                continue
            session.add(Specialty(name=name, description=description, icon=icon))
            created += 1
        print(f"Seeded {created} new specialties (skipped {len(DEFAULT_SPECIALTIES) - created} existing).")


def seed_knowledge_base():
    try:
        from ai.knowledge_base import seed_knowledge_base as seed_kb
        result = seed_kb()
        if result["seeded"]:
            print(f"Seeded {result['seeded']} knowledge base articles into Chroma.")
        else:
            print(f"Knowledge base already has {result['already_present']} articles — skipped.")
    except Exception as e:
        print(
            f"Skipped knowledge base seeding ({e}). "
            "This usually means chromadb / sentence-transformers aren't installed yet — "
            "see requirements.txt. SmartCare AI's retrieval step won't work until this succeeds, "
            "but the rest of the app is unaffected."
        )


def main():
    print("Creating tables (if they don't already exist)...")
    init_db()
    print("Seeding admin account...")
    seed_admin()
    print("Seeding default specialties...")
    seed_specialties()
    print("Seeding SmartCare AI knowledge base...")
    seed_knowledge_base()
    print("Done.")


if __name__ == "__main__":
    main()