
import os
import smtplib
import logging
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def send_email(to_email, subject, message_text):
    sender = os.getenv("SMTP_EMAIL")
    password = os.getenv("SMTP_APP_PASSWORD")

    if not sender or not password or not to_email:
        logger.warning("Email skipped: configuration or recipient missing.")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to_email
    message.set_content(message_text)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(message)

        logger.info("Email sent successfully.")
        return True

    except Exception:
        logger.exception("Email notification failed.")
        return False
