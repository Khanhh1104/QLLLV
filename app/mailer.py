import os
import ssl
import smtplib
from email.message import EmailMessage


def configured():
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def send_mail(to, subject, body):
    if not configured():
        raise RuntimeError("Chưa cấu hình SMTP")
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    host = os.environ["SMTP_HOST"]
    use_ssl = os.getenv("SMTP_SSL", "false").lower() == "true"
    port = int(os.getenv("SMTP_PORT", "465" if use_ssl else "587"))
    connection = (
        smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context())
        if use_ssl
        else smtplib.SMTP(host, port, timeout=15)
    )
    with connection as client:
        if not use_ssl and os.getenv("SMTP_STARTTLS", "true").lower() == "true":
            client.starttls(context=ssl.create_default_context())
        if os.getenv("SMTP_USER"):
            client.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        client.send_message(message)
