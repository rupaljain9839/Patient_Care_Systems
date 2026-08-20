"""Outgoing email via plain SMTP (stdlib smtplib — no extra pip dependency).
Currently used for exactly one thing: emailing a newly created doctor their
login credentials, on a branded HTML template matching the app's theme.
"""
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.config import settings


@dataclass
class EmailResult:
    ok: bool
    message: str


def _credentials_email_html(doctor_name: str, login_email: str, password: str, specialty: str) -> str:
    return f"""
<div style="font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; background:#F6F8FF; padding:2rem 1rem;">
  <div style="max-width:520px; margin:0 auto; background:white; border-radius:20px; overflow:hidden;
              box-shadow:0 10px 30px rgba(8,14,50,0.12);">

    <div style="background:linear-gradient(135deg, #5B6EF5 0%, #22C1DC 100%); padding:1.8rem 2rem; text-align:center;">
      <div style="color:white; font-size:1.3rem; font-weight:800;">{settings.app_name}</div>
      <div style="color:#EAF0FF; font-size:0.85rem; margin-top:0.2rem;">AI-powered smart healthcare platform</div>
    </div>

    <div style="padding:2rem;">
      <p style="color:#1B2350; font-size:1.05rem;">Hi Dr. {doctor_name},</p>
      <p style="color:#4A5578; font-size:0.95rem; line-height:1.6;">
        An account has been created for you on {settings.app_name}
        {f"in the <b>{specialty}</b> department" if specialty else ""}.
        You can use the credentials below to log in.
      </p>

      <div style="background:#F4F6FF; border:1px solid #DCE1FF; border-radius:14px; padding:1.2rem 1.4rem; margin:1.4rem 0;">
        <div style="color:#7C86A8; font-size:0.78rem; font-weight:700; letter-spacing:0.04em;">LOGIN EMAIL</div>
        <div style="color:#1B2350; font-size:1rem; font-weight:700; font-family:monospace; margin-bottom:0.9rem;">{login_email}</div>
        <div style="color:#7C86A8; font-size:0.78rem; font-weight:700; letter-spacing:0.04em;">TEMPORARY PASSWORD</div>
        <div style="color:#1B2350; font-size:1rem; font-weight:700; font-family:monospace;">{password}</div>
      </div>

      <p style="color:#B23B3B; background:#FDEEEE; border:1px solid #F3C9C9; border-radius:10px;
                padding:0.7rem 1rem; font-size:0.85rem;">
        For security, please log in and change this password as soon as possible.
      </p>

      <p style="color:#7C86A8; font-size:0.8rem; margin-top:1.8rem;">
        This is a system-generated email from {settings.app_name}. If you weren't expecting this,
        please contact your administrator.
      </p>
    </div>
  </div>
</div>
"""


def send_doctor_credentials_email(to_email: str, doctor_name: str, login_email: str, password: str, specialty: str = "") -> EmailResult:
    if not settings.email_configured:
        return EmailResult(
            False,
            "Email isn't configured — set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in .env to enable this.",
        )
    if not to_email:
        return EmailResult(False, "No personal email address was provided.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your {settings.app_name} login credentials"
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to_email

    html = _credentials_email_html(doctor_name, login_email, password, specialty)
    plain = (
        f"Hi Dr. {doctor_name},\n\n"
        f"An account has been created for you on {settings.app_name}.\n\n"
        f"Login email: {login_email}\n"
        f"Temporary password: {password}\n\n"
        "For security, please don't share the credentials with anyone.\n"
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, [to_email], msg.as_string())
        return EmailResult(True, f"Credentials emailed to {to_email}.")
    except Exception as e:
        return EmailResult(False, f"Couldn't send the email: {e}")