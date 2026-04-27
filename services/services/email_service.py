import smtplib
from email.mime.text import MIMEText

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_SENDER = "bianzino@gmail.com"
EMAIL_PASSWORD = "twhz eqvj zneo xafh"


def send_otp_email(to_email: str, code: str):
    subject = "Codice accesso ConsulentIA AI"
    body = f"Il tuo codice è: {code}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
