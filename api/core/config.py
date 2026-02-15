"""
MyMedic Core — Application Settings (HIPAA-Compliant Defaults)

Reads from environment variables / .env file.
All secrets MUST be overridden via env vars in production.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised configuration singleton."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────
    app_name: str = "MyMedic"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # ── Database ───────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://mymedic:changeme@localhost:5432/mymedic_db"

    @property
    def sqlalchemy_database_url(self) -> str:
        """Fixes Railway's 'postgres://' for SQLAlchemy asyncpg."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif "postgresql+asyncpg" not in url and url.startswith("postgresql://"):
             url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # ── JWT ────────────────────────────────────────────────────
    jwt_secret_key: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # ── OTP / 2FA ──────────────────────────────────────────────
    otp_secret_key: str = "CHANGE_ME"
    otp_issuer: str = "MyMedic"
    otp_digits: int = 6
    otp_interval: int = 30  # seconds

    # ── Payment Gateway (Paystack) ─────────────────────────────
    paystack_secret_key: str = "CHANGE_ME"
    paystack_public_key: str = "CHANGE_ME"

    # ── SMTP ───────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "MyMedic <noreply@mymedic.app>"


# Global singleton — imported by all modules.
settings = Settings()
