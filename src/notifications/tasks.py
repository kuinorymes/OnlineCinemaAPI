from fastapi_mail import MessageSchema, MessageType, FastMail
from jinja2 import Environment, select_autoescape, PackageLoader

from notifications.mail_config import mail_config


templates = Environment(
    loader=PackageLoader("notifications"), autoescape=select_autoescape(["html", "xml"])
)


async def send_register_activate_email(email, activation_link):

    template = templates.get_template("welcome_activate.html")
    html_content = template.render(
        email=email,
        activation_link=activation_link,
    )

    message = MessageSchema(
        subject="Welcome",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html,
    )
    fast_mail = FastMail(mail_config)
    await fast_mail.send_message(message)


async def send_reset_password_email(email, reset_link):

    template = templates.get_template("reset_password.html")
    html_content = template.render(
        email=email,
        reset_link=reset_link,
    )

    message = MessageSchema(
        subject="Reset Password",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html,
    )
    fast_mail = FastMail(mail_config)
    await fast_mail.send_message(message)


async def send_reset_password_email_complete(email, login_link):

    template = templates.get_template("reset_password_complete.html")
    html_content = template.render(
        email=email,
        reset_link=login_link,
    )

    message = MessageSchema(
        subject="Password has been changed",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html,
    )
    fast_mail = FastMail(mail_config)
    await fast_mail.send_message(message)