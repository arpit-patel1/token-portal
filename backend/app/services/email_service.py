import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from loguru import logger

from app.core.config import settings

async def send_email_async(
    subject: str,
    recipient_to: str, # Single recipient for now, can be List[str]
    body_html: Optional[str] = None,
    body_text: Optional[str] = None,
) -> bool:
    """Asynchronously sends an email.
    
    For Gmail, ensure 'Less secure app access' is ON or use an App Password if 2FA is enabled.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD or not settings.EMAILS_FROM_EMAIL:
        logger.error("SMTP settings not configured. Cannot send email.")
        return False

    message = MIMEMultipart("alternative")
    message["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    message["To"] = recipient_to
    message["Subject"] = subject

    if body_text:
        message.attach(MIMEText(body_text, "plain"))
    if body_html:
        message.attach(MIMEText(body_html, "html"))
    
    if not message.get_payload():
        logger.error("Email body is empty. Cannot send email.")
        return False

    try:
        # Note: smtplib is synchronous. For a truly async email sending experience
        # in a high-load production app, consider libraries like aiosmtplib
        # or offloading to a background task queue (e.g., Celery).
        # For this MVP, synchronous smtplib within an async def is acceptable.
        
        # Ensure port is integer
        smtp_port = settings.SMTP_PORT if settings.SMTP_PORT else (587 if settings.SMTP_TLS else 25)

        server = smtplib.SMTP(settings.SMTP_HOST, smtp_port)
        if settings.SMTP_TLS:
            server.starttls() # Secure the connection
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAILS_FROM_EMAIL, recipient_to, message.as_string())
        server.quit()
        logger.info(f"Email sent to {recipient_to} with subject: {subject}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication Error sending email to {recipient_to}: {e}")
    except Exception as e:
        logger.error(f"Error sending email to {recipient_to}: {e}")
    return False

async def send_otp_email(email_to: str, otp: str) -> bool:
    """Sends a pre-formatted OTP email."""
    project_name = settings.PROJECT_NAME
    subject = f"Your OTP for {project_name}"
    body_html = f"""
    <html>
        <body>
            <p>Hi,</p>
            <p>Your One-Time Password (OTP) for {project_name} is: <strong>{otp}</strong></p>
            <p>This OTP is valid for {settings.OTP_EXPIRE_MINUTES} minutes.</p>
            <p>If you did not request this, please ignore this email.</p>
            <p>Thanks,<br/>The {project_name} Team</p>
        </body>
    </html>
    """
    body_text = f"Hi,\n\nYour One-Time Password (OTP) for {project_name} is: {otp}\n\nThis OTP is valid for {settings.OTP_EXPIRE_MINUTES} minutes.\n\nIf you did not request this, please ignore this email.\n\nThanks,\nThe {project_name} Team"

    return await send_email_async(
        subject=subject,
        recipient_to=email_to,
        body_html=body_html,
        body_text=body_text
    ) 