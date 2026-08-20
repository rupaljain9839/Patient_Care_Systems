"""Central configuration. All secrets and the Groq model are read from .env."""
import os
from functools import lru_cache
from urllib.parse import quote_plus
from dotenv import load_dotenv

# override=True forces values in .env to win over any stale OS/terminal
# environment variables of the same name (e.g. a leftover `set DB_NAME=...`
# from an earlier session). Without this, load_dotenv() silently skips
# any variable that's already set in the environment.
load_dotenv(override=True)


class Settings:
    def __init__(self) -> None:
        # ---- Database (MySQL) ----
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = os.getenv("DB_PORT", "3306")
        self.db_name = os.getenv("DB_NAME", "smartcare")
        self.db_user = os.getenv("DB_USER", "root")
        self.db_password = os.getenv("DB_PASSWORD", "")

        # ---- LLM (Groq via LangChain) ----
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        # Model selection lives ONLY in .env, as requested.
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))

        # ---- Embeddings / Vector store ----
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
        self.chroma_dir = os.getenv("CHROMA_DIR", ".chroma")
        self.kb_collection = os.getenv("KB_COLLECTION", "smartcare_health_kb")

        # ---- Bootstrap admin (created by seed_data.py) ----
        self.admin_name = os.getenv("ADMIN_NAME", "System Administrator")
        self.admin_email = os.getenv("ADMIN_EMAIL", "admin@smartcare.local")
        self.admin_password = os.getenv("ADMIN_PASSWORD", "Admin@123")

        # ---- App ----
        self.app_name = os.getenv(
            "APP_NAME", "Patient Care Management System for Healthcare Services (PCMS-HS)"
        )

        # ---- Outgoing email (SMTP) — used to send new doctors their login
        # credentials. Works with Gmail (use an App Password, not your real
        # password — see https://myaccount.google.com/apppasswords), Outlook,
        # or any standard SMTP provider (SendGrid, Mailgun, your institution's
        # mail server, etc.).
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_user)
        self.smtp_from_name = os.getenv("SMTP_FROM_NAME", "PCMS-HS")

    @property
    def database_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()