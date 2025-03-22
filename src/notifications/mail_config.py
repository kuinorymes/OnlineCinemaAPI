from pathlib import Path

from fastapi_mail import ConnectionConfig

from config.dependencies import get_settings


settings = get_settings()


mail_config = ConnectionConfig(
    MAIL_USERNAME=settings.EMAIL_ADDRESS,
    MAIL_PASSWORD=settings.EMAIL_PASSWORD,
    MAIL_FROM=settings.EMAIL_ADDRESS,
    MAIL_PORT=settings.EMAIL_PORT,
    MAIL_SERVER=settings.SMTP_SERVER,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    TEMPLATE_FOLDER=Path(__file__).parent / "templates"
)
