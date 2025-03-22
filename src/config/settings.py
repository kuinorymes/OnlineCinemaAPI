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

    SECRET_TOKEN_KEY: str = os.getenv("SECRET_TOKEN_KEY")

    BASE_URL: str = "http://127.0.0.1:8000"


class Settings(BaseAppSettings):
    pass


class TestingSettings(BaseAppSettings):
    pass
