import jwt
from datetime import datetime, timedelta, timezone

from config.dependencies import get_settings
from database.models.users import UserModel


settings = get_settings()

SECRET_KEY = settings.SECRET_TOKEN_KEY
ALGORITHM = "HS256"

def create_activation_token(user_id: int):
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }

    activation_token = jwt.encode(payload, SECRET_KEY, ALGORITHM)
    return activation_token
