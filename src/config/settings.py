import os
from pathlib import Path

from pydantic.v1 import BaseSettings

from dotenv import load_dotenv
load_dotenv()

class BaseAppSettings(BaseSettings):
    BASE_DIR: Path = Path(__file__).parent.parent
    PATH_TO_DB: str = os.getenv("DATABASE_URL", str(BASE_DIR / "database" / "source" / "theater.db"))
    PATH_TO_MOVIES_CSV: str = str(BASE_DIR / "database" / "seed_data" / "imdb_movies.csv")


class Settings(BaseAppSettings):
    ...


class TestingSettings(BaseAppSettings):
    ...
