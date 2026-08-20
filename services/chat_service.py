"""Persists SmartCare AI conversations to the chat_messages table."""
from datetime import datetime

from core.database import session_scope
from models.models import ChatMessage


def save_message(user_id: int, role: str, content: str):
    with session_scope() as session:
        session.add(ChatMessage(user_id=user_id, role=role, content=content, created_at=datetime.utcnow()))


def get_history(user_id: int, limit: int = 50):
    with session_scope() as session:
        rows = (
            session.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        return [{"role": r.role, "content": r.content, "created_at": r.created_at} for r in rows]


def clear_history(user_id: int):
    with session_scope() as session:
        session.query(ChatMessage).filter(ChatMessage.user_id == user_id).delete()