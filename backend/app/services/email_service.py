"""Email service using aiosmtplib + Jinja2 templates."""
from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "email"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=True,
)


class EmailService:
    """Sends transactional and report emails."""

    async def send(
        self,
        *,
        to: list[str] | str,
        subject: str,
        html: str,
        text: str | None = None,
    ) -> None:
        recipients = [to] if isinstance(to, str) else to
        if not recipients:
            return

        msg = EmailMessage()
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        if text:
            msg.set_content(text)
            msg.add_alternative(html, subtype="html")
        else:
            msg.set_content(html, subtype="html")

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                use_tls=settings.SMTP_TLS,
            )
            log.info("email.sent", to=recipients, subject=subject)
        except Exception:  # noqa: BLE001
            log.exception("email.send_failed", to=recipients, subject=subject)

    async def render_template(self, template_name: str, **context: object) -> str:
        template = _env.get_template(template_name)
        return await template.render_async(**context)

    async def send_template(
        self,
        *,
        to: list[str] | str,
        subject: str,
        template_name: str,
        context: dict,
    ) -> None:
        html = await self.render_template(template_name, **context)
        await self.send(to=to, subject=subject, html=html)


_email_service = EmailService()


def get_email_service() -> EmailService:
    return _email_service
