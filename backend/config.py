"""Explicit settings; never use a predictable signing key in production."""

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str = field(repr=False)
    environment: str = "development"
    jwt_expire_minutes: int = 60
    cors_origins: tuple[str, ...] = ("http://localhost:5500", "http://127.0.0.1:5500")
    upload_dir: Path = field(default_factory=lambda: ROOT / "uploads")
    auth_rate_limit: int = 20
    auth_rate_window: int = 300
    max_body_bytes: int = 12 * 1024 * 1024
    serve_frontend: bool = True

    def __post_init__(self):
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test or production")
        if len(self.jwt_secret.encode()) < 32 or any(
            word in self.jwt_secret.lower() for word in ("doi-chuoi", "dev-secret", "change-me")
        ):
            raise ValueError("JWT_SECRET must be a random secret of at least 32 bytes")
        dialect = make_url(self.database_url).get_backend_name()
        if dialect not in {"sqlite", "postgresql", "postgres"}:
            raise ValueError("Unsupported database dialect")
        if self.environment == "production" and dialect not in {"postgresql", "postgres"}:
            raise ValueError("Production requires PostgreSQL")
        if not 1 <= self.jwt_expire_minutes <= 1440:
            raise ValueError("JWT_EXPIRE_MINUTES must be between 1 and 1440")
        if "*" in self.cors_origins:
            raise ValueError("Explicit CORS origins are required")
        for origin in self.cors_origins:
            url = urlsplit(origin)
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username
                or url.password
                or url.path
                or url.query
                or url.fragment
            ):
                raise ValueError("CORS origins must be HTTP(S) origins without credentials or paths")
            _ = url.port
        for name, value, maximum in (
            ("auth_rate_limit", self.auth_rate_limit, 10000),
            ("auth_rate_window", self.auth_rate_window, 86400),
            ("max_body_bytes", self.max_body_bytes, 100 * 1024 * 1024),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"Invalid {name}")

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env", override=False)
        environment = os.getenv("APP_ENV", "development")
        if environment not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test or production")
        serve_frontend = os.getenv("SERVE_FRONTEND", "false" if environment == "production" else "true")
        if serve_frontend.lower() not in {"true", "false"}:
            raise ValueError("SERVE_FRONTEND must be true or false")
        secret = os.getenv("JWT_SECRET", "")
        if not secret:
            if environment == "production":
                raise ValueError("JWT_SECRET is required in production")
            secret_file = ROOT / ".local-secret"
            try:
                with secret_file.open("x", encoding="ascii") as file:
                    file.write(secrets.token_urlsafe(48))
                secret_file.chmod(0o600)
            except FileExistsError:
                pass
            secret = secret_file.read_text(encoding="ascii").strip()
        return cls(
            database_url=os.getenv("DATABASE_URL") or f"sqlite:///{(ROOT / 'luxstay.db').as_posix()}",
            jwt_secret=secret,
            environment=environment,
            jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "60")),
            cors_origins=tuple(
                x.strip()
                for x in os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",")
                if x.strip()
            ),
            upload_dir=Path(os.getenv("UPLOAD_DIR", str(ROOT / "uploads"))).resolve(),
            auth_rate_limit=int(os.getenv("AUTH_RATE_LIMIT", "20")),
            auth_rate_window=int(os.getenv("AUTH_RATE_WINDOW", "300")),
            max_body_bytes=int(os.getenv("MAX_BODY_BYTES", str(12 * 1024 * 1024))),
            serve_frontend=serve_frontend.lower() == "true",
        )
