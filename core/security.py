"""Password hashing and the strong-password policy."""
import re

import bcrypt

_UPPER = re.compile(r"[A-Z]")
_DIGIT = re.compile(r"[0-9]")
_SPECIAL = re.compile(r"""[!@#$%^&*(),.?":{}|<>_\-\[\]/\\+=;'`~]""")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def validate_password(password: str):
    """Return (ok, message). Enforces uppercase, number and special character."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not _UPPER.search(password):
        return False, "Password must contain at least one uppercase letter."
    if not _DIGIT.search(password):
        return False, "Password must contain at least one number."
    if not _SPECIAL.search(password):
        return False, "Password must contain at least one special character (e.g. @ # $ !)."
    return True, "Strong password."