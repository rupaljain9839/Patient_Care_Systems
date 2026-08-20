"""Medicine catalog (admin-managed) and patient ordering."""
import os
from dataclasses import dataclass
from datetime import datetime

from core.database import session_scope
from models.models import Medicine, MedicineOrder, MedicineOrderItem, User

CATEGORIES = ["Cardiovascular", "Antibiotic", "Analgesic", "Diabetes", "Respiratory", "General", "Other"]

MEDICINE_IMAGES_DIR = os.path.join("static", "medicine_images")


@dataclass
class ServiceResult:
    ok: bool
    message: str


def _save_medicine_image(medicine_id: int, image_file) -> str:
    """image_file: a Streamlit UploadedFile (has .name and .getvalue()).
    Saves it to static/medicine_images/ and returns the relative path stored on Medicine.image_url."""
    os.makedirs(MEDICINE_IMAGES_DIR, exist_ok=True)
    ext = os.path.splitext(image_file.name)[1].lower() or ".png"
    filename = f"medicine_{medicine_id}{ext}"
    filepath = os.path.join(MEDICINE_IMAGES_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_file.getvalue())
    return f"medicine_images/{filename}"


def _med_to_dict(m: Medicine) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "category": m.category or "General",
        "description": m.description or "",
        "price": float(m.price) if m.price is not None else 0.0,
        "stock": m.stock or 0,
        "icon": m.icon or "💊",
        "image_url": m.image_url,
        "is_active": m.is_active,
    }


def list_medicines(category: str = "", search: str = "", active_only: bool = True):
    with session_scope() as session:
        q = session.query(Medicine)
        if active_only:
            q = q.filter(Medicine.is_active.is_(True))
        if category and category != "All":
            q = q.filter(Medicine.category == category)
        if search:
            q = q.filter(Medicine.name.ilike(f"%{search}%"))
        q = q.order_by(Medicine.name)
        return [_med_to_dict(m) for m in q.all()]


def add_medicine(name, category, description, price, stock, icon="💊", image_file=None):
    if not name.strip():
        return ServiceResult(False, "Medicine name is required.")
    with session_scope() as session:
        m = Medicine(
            name=name.strip(), category=category, description=description,
            price=price, stock=stock, icon=icon or "💊", is_active=True,
        )
        session.add(m)
        session.flush()  # need m.id for the image filename

        if image_file is not None:
            m.image_url = _save_medicine_image(m.id, image_file)

        return ServiceResult(True, f"Added {name}.")


def update_medicine(medicine_id, image_file=None, **fields):
    with session_scope() as session:
        m = session.query(Medicine).filter(Medicine.id == medicine_id).first()
        if not m:
            return ServiceResult(False, "Medicine not found.")
        for k, v in fields.items():
            if v is not None:
                setattr(m, k, v)
        if image_file is not None:
            m.image_url = _save_medicine_image(m.id, image_file)
        return ServiceResult(True, "Updated.")


def delete_medicine(medicine_id):
    with session_scope() as session:
        m = session.query(Medicine).filter(Medicine.id == medicine_id).first()
        if not m:
            return ServiceResult(False, "Not found.")
        session.delete(m)
        return ServiceResult(True, "Deleted.")


def place_order(patient_id: int, cart: dict) -> ServiceResult:
    """cart: {medicine_id: quantity}"""
    if not cart:
        return ServiceResult(False, "Cart is empty.")

    with session_scope() as session:
        total = 0.0
        items = []
        for medicine_id, qty in cart.items():
            m = session.query(Medicine).filter(Medicine.id == medicine_id).first()
            if not m:
                continue
            if m.stock < qty:
                return ServiceResult(False, f"Not enough stock for {m.name} (only {m.stock} left).")
            items.append((m, qty))
            total += float(m.price) * qty

        if not items:
            return ServiceResult(False, "No valid items in cart.")

        order = MedicineOrder(patient_id=patient_id, status="placed", total_amount=total, created_at=datetime.utcnow())
        session.add(order)
        session.flush()

        for m, qty in items:
            session.add(MedicineOrderItem(order_id=order.id, medicine_id=m.id, medicine_name=m.name, quantity=qty, unit_price=m.price))
            m.stock -= qty

        return ServiceResult(True, f"Order placed — ₹{total:.0f} total.")


def get_patient_orders(patient_id: int):
    with session_scope() as session:
        orders = (
            session.query(MedicineOrder)
            .filter(MedicineOrder.patient_id == patient_id)
            .order_by(MedicineOrder.created_at.desc())
            .all()
        )
        return [
            {
                "id": o.id,
                "status": o.status,
                "total_amount": float(o.total_amount),
                "created_at": o.created_at,
                "items": [{"name": i.medicine_name, "quantity": i.quantity, "unit_price": float(i.unit_price)} for i in o.items],
            }
            for o in orders
        ]


def cancel_order(patient_id: int, order_id: int) -> ServiceResult:
    with session_scope() as session:
        order = (
            session.query(MedicineOrder)
            .filter(MedicineOrder.id == order_id, MedicineOrder.patient_id == patient_id)
            .first()
        )
        if not order:
            return ServiceResult(False, "Order not found.")
        if order.status != "placed":
            return ServiceResult(False, f"This order is already {order.status} and can't be cancelled.")

        for item in order.items:
            if item.medicine:
                item.medicine.stock += item.quantity

        order.status = "cancelled"
        return ServiceResult(True, f"Order #{order.id} cancelled — stock restored.")


def get_all_orders():
    with session_scope() as session:
        orders = session.query(MedicineOrder).order_by(MedicineOrder.created_at.desc()).all()
        return [
            {
                "id": o.id,
                "patient_name": o.patient.full_name if o.patient else "Unknown",
                "status": o.status,
                "total_amount": float(o.total_amount),
                "created_at": o.created_at,
                "items": [{"name": i.medicine_name, "quantity": i.quantity, "unit_price": float(i.unit_price)} for i in o.items],
            }
            for o in orders
        ]