import asyncio
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape
import logging
import smtplib
import ssl
from typing import Protocol

from app.core.config import Settings, get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutboundEmail:
    recipient: str
    subject: str
    text_body: str
    html_body: str


class EmailBackend(Protocol):
    async def send(self, message: OutboundEmail) -> None: ...


class ConsoleEmailBackend:
    async def send(self, message: OutboundEmail) -> None:
        logger.info("Development email recipient=%s subject=%s\n%s", message.recipient, message.subject, message.text_body)


class SmtpEmailBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _send_sync(self, outbound: OutboundEmail) -> None:
        settings = self.settings
        if not settings.smtp_host or not settings.email_from:
            raise RuntimeError("SMTP_HOST and EMAIL_FROM are required")
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = outbound.recipient
        message["Subject"] = outbound.subject
        message.set_content(outbound.text_body)
        message.add_alternative(outbound.html_body, subtype="html")

        smtp_class = smtplib.SMTP_SSL if settings.smtp_use_tls else smtplib.SMTP
        context = ssl.create_default_context()
        kwargs = {"host": settings.smtp_host, "port": settings.smtp_port, "timeout": settings.smtp_timeout_seconds}
        if settings.smtp_use_tls:
            kwargs["context"] = context
        with smtp_class(**kwargs) as client:
            client.ehlo()
            if settings.smtp_starttls and not settings.smtp_use_tls:
                client.starttls(context=context)
                client.ehlo()
            if settings.smtp_user:
                client.login(settings.smtp_user, settings.smtp_password)
            client.send_message(message)

    async def send(self, message: OutboundEmail) -> None:
        await asyncio.to_thread(self._send_sync, message)


def get_email_backend(settings: Settings | None = None) -> EmailBackend:
    active_settings = settings or get_settings()
    if active_settings.email_provider == "smtp":
        return SmtpEmailBackend(active_settings)
    if active_settings.is_production:
        raise RuntimeError("EMAIL_PROVIDER must be smtp in production")
    return ConsoleEmailBackend()


async def send_verification_email(email: str, verification_url: str) -> None:
    settings = get_settings()
    safe_url = escape(verification_url, quote=True)
    message = OutboundEmail(
        recipient=email,
        subject=f"[{settings.email_subject_prefix}] 驗證您的 Email",
        text_body=f"請開啟以下連結完成 Email 驗證：\n\n{verification_url}\n\n此連結將在 24 小時後失效。",
        html_body=(
            "<p>請點擊下方連結完成 Email 驗證：</p>"
            f'<p><a href="{safe_url}">驗證 Email</a></p>'
            "<p>此連結將在 24 小時後失效。</p>"
        ),
    )
    try:
        await get_email_backend(settings).send(message)
    except Exception as exc:
        logger.exception("Verification email delivery failed", extra={"recipient": email})
        raise AppError("EMAIL_DELIVERY_FAILED", "Verification email could not be sent", 503) from exc
