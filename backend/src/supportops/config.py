"""Configuration is loaded explicitly; importing this module reads no secrets."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url, URL


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    database_url: str | None = field(default=None, repr=False)
    jwt_secret: str | None = field(default=None, repr=False)
    jwt_issuer: str = "supportops-api"
    jwt_audience: str = "supportops-web"
    access_token_minutes: int = 15

    def __post_init__(self):
        if self.database_url:
            if make_url(self.database_url).drivername != "postgresql+psycopg":
                raise ValueError("DATABASE_URL must use postgresql+psycopg")
        if self.jwt_secret is not None and len(self.jwt_secret.encode()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes")
        if not self.jwt_issuer or not self.jwt_audience:
            raise ValueError("JWT issuer and audience must be nonempty")
        if not 1 <= self.access_token_minutes <= 30:
            raise ValueError("ACCESS_TOKEN_MINUTES must be between 1 and 30")


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    database_url = os.getenv("DATABASE_URL")
    if not database_url and os.getenv("POSTGRES_PASSWORD"):
        database_url = URL.create(
            "postgresql+psycopg",
            username=os.getenv("POSTGRES_USER", "supportops"),
            password=os.environ["POSTGRES_PASSWORD"],
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "supportops"),
        ).render_as_string(hide_password=False)
    return Settings(
        database_url=database_url,
        jwt_secret=os.getenv("JWT_SECRET") or None,
        jwt_issuer=os.getenv("JWT_ISSUER", "supportops-api"),
        jwt_audience=os.getenv("JWT_AUDIENCE", "supportops-web"),
        access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "15")),
    )
