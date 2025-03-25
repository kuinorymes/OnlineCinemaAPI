import os
from pathlib import Path

from pydantic import SecretStr, EmailStr
from pydantic.v1 import BaseSettings

from dotenv import load_dotenv

load_dotenv()


class BaseAppSettings(BaseSettings):
    BASE_DIR: Path = Path(__file__).parent.parent
    PATH_TO_DB: str = os.getenv(
        "DATABASE_URL", str(BASE_DIR / "database" / "source" / "theater.db")
    )
    PATH_TO_MOVIES_CSV: str = str(
        BASE_DIR / "database" / "seed_data" / "imdb_movies.csv"
    )

    EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD")
    SMTP_SERVER: str = os.getenv("SMTP_SERVER")
    EMAIL_PORT: int = os.getenv("EMAIL_PORT")

    SECRET_ACCESS_TOKEN_KEY: str = os.getenv("SECRET_ACCESS_TOKEN_KEY")
    SECRET_REFRESH_TOKEN_KEY: str = os.getenv("SECRET_REFRESH_TOKEN_KEY")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM")

    LOGIN_DAYS_VALID: int = 7

    BASE_URL: str = "http://127.0.0.1:8000"

    API_VERSION: str = "/api/v1"

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_BACKEND_URL: str = "redis://localhost:6379/0"

    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME")

    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST")
    POSTGRES_DB_PORT: int = os.getenv("POSTGRES_DB_PORT")

    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY")

    # STRIPE_SUCCESS_URL: str = "http://localhost:8000/payment/success"
    # STRIPE_CANCEL_URL = "http://localhost:8000/payment/cancel"


class Settings(BaseAppSettings):
    pass


class TestingSettings(BaseAppSettings):
    pass
