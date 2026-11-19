"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes", "on"}

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = _int_env("DB_PORT", 3306)
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "civicfix")

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "complaints")
    MAX_UPLOAD_BYTES = _int_env("MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_BYTES + (1024 * 1024)

    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
    ALLOWED_IMAGE_MIME_TYPES = {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
    }

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    PERMANENT_SESSION_LIFETIME = 7 * 24 * 60 * 60

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = _int_env("SMTP_PORT", 587)
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "CivicFix <no-reply@civicfix.local>")

    @staticmethod
    def db_config(database: bool = True) -> dict:
        config = {
            "host": Config.DB_HOST,
            "port": Config.DB_PORT,
            "user": Config.DB_USER,
            "password": Config.DB_PASSWORD,
            "charset": "utf8mb4",
            "collation": "utf8mb4_unicode_ci",
            "use_pure": True,
        }
        if database:
            config["database"] = Config.DB_NAME
        return config
