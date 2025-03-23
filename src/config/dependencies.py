import os

from fastapi import Depends

from config.settings import BaseAppSettings, TestingSettings, Settings
from security.interfaces import JWTAuthManagerInterface
from security.jwt_manager import JWTAuthManager


def get_settings() -> BaseAppSettings:
    environment = os.getenv("ENVIRONMENT", "developing")
    if environment == "testing":
        return TestingSettings()
    return Settings()


def get_jwt_auth_manager(
    settings: BaseAppSettings = Depends(get_settings),
) -> JWTAuthManagerInterface:
    """
    Create and return a JWT authentication manager instance.

    This function uses the provided application settings to instantiate a JWTAuthManager, which implements
    the JWTAuthManagerInterface. The manager is configured with secret keys for access and refresh tokens
    as well as the JWT signing algorithm specified in the settings.

    Args:
        settings (BaseAppSettings, optional): The application settings instance.
        Defaults to the output of get_settings().

    Returns:
        JWTAuthManagerInterface: An instance of JWTAuthManager configured with
        the appropriate secret keys and algorithm.
    """
    return JWTAuthManager(
        secret_key_access=settings.SECRET_ACCESS_TOKEN_KEY,
        secret_key_refresh=settings.SECRET_REFRESH_TOKEN_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
