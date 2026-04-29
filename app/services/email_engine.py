"""
Email Engine — Multi-provider email sending with Jinja2 templating,
sender rotation, and per-account rate limiting.
"""

import logging
import asyncio
from typing import Optional, Dict
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib
from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.email_account import EmailAccount, EmailProvider
from app.models.email_log import EmailLog, EmailStatus
from app.models.activity import Activity, ActivityChannel
from app.services.circuit_breaker import email_circuit

logger = logging.getLogger(__name__)


class EmailEngine:
    """
    Handles email sending via SMTP or SendGrid with:
    - Multi-provider support (Gmail, Outlook, SendGrid, custom SMTP)
    - Jinja2 template rendering with personalization
    - Per-account rate limiting
    - Sender rotation for bulk campaigns
    - Tracking pixel injection
    """

    @staticmethod
    def render_template(template_html: str, variables: Dict[str, str]) -> str:
        """Render an email template with personalization variables."""
        if not template_html:
            return ""
        
        # 1. Handle standard outreach format {variable}
        rendered = template_html
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            rendered = rendered.replace(placeholder, str(value or ""))
            
        # 2. Handle Jinja2 format {{ variable }}
        try:
            tpl = Template(rendered)
            return tpl.render(**variables)
        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            return rendered

    @staticmethod
    def inject_tracking_pixel(html: str, tracking_id: str) -> str:
        """Inject a 1x1 tracking pixel before </body> for open tracking."""
        pixel_url = f"{settings.tracking_base_url}/api/track/open/{tracking_id}"
        pixel_tag = f'<img src="{pixel_url}" width="1" height="1" style="display:none" alt="" />'

        if "</body>" in html:
            return html.replace("</body>", f"{pixel_tag}</body>")
        return html + pixel_tag

    @staticmethod
    def wrap_links_for_tracking(html: str, tracking_id: str) -> str:
        """Rewrite links to pass through tracking endpoint for click tracking."""
        import re
        import urllib.parse

        def replace_link(match):
            original_url = match.group(1)
            # Don't track tracking pixels or unsubscribe links
            if "track/open" in original_url or "unsubscribe" in original_url:
                return match.group(0)
            encoded = urllib.parse.quote(original_url, safe="")
            tracking_url = f"{settings.tracking_base_url}/api/track/click/{tracking_id}/{encoded}"
            return f'href="{tracking_url}"'

        return re.sub(r'href="([^"]+)"', replace_link, html)

    @staticmethod
    async def send_via_smtp(
        account: EmailAccount,
        to_email: str,
        subject: str,
        html_body: str,
    ) -> bool:
        """Send an email via SMTP."""
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{account.name} <{account.email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        # Determine SMTP settings by provider
        host = account.smtp_host or settings.SMTP_DEFAULT_HOST
        port = account.smtp_port or settings.SMTP_DEFAULT_PORT

        if account.provider == EmailProvider.GMAIL:
            host = "smtp.gmail.com"
            port = 587
        elif account.provider == EmailProvider.OUTLOOK:
            host = "smtp-mail.outlook.com"
            port = 587

        try:
            await aiosmtplib.send(
                msg,
                hostname=host,
                port=port,
                username=account.username or account.email,
                password=account.encrypted_password,  # Should be decrypted in production
                start_tls=True,
                timeout=30,
            )
            return True
        except Exception as e:
            logger.error(f"SMTP send failed for {account.email}: {e}")
            raise

    @staticmethod
    async def send_via_sendgrid(
        account: EmailAccount,
        to_email: str,
        subject: str,
        html_body: str,
    ) -> bool:
        """Send an email via SendGrid API."""
        import httpx

        api_key = account.sendgrid_api_key or settings.SENDGRID_API_KEY
        if not api_key:
            raise ValueError("SendGrid API key not configured")

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": account.email, "name": account.name},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_body}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if response.status_code not in (200, 201, 202):
                raise Exception(f"SendGrid error {response.status_code}: {response.text}")
            return True

    @classmethod
    async def send_email(
        cls,
        db: AsyncSession,
        account: EmailAccount,
        lead_id: int,
        to_email: str,
        subject: str,
        html_body: str,
        campaign_id: Optional[int] = None,
        personalization: Optional[Dict[str, str]] = None,
    ) -> EmailLog:
        """
        Send a single email through the circuit breaker with tracking.
        Returns the EmailLog record.
        """
        # Render personalization
        if personalization:
            html_body = cls.render_template(html_body, personalization)
            subject = cls.render_template(subject, personalization)

        # Create log entry
        email_log = EmailLog(
            lead_id=lead_id,
            campaign_id=campaign_id,
            sender_email=account.email,
            recipient_email=to_email,
            subject=subject,
            body_html=html_body,
            status=EmailStatus.QUEUED,
        )
        db.add(email_log)
        await db.flush()
        await db.refresh(email_log)

        # Inject tracking
        tracked_html = cls.inject_tracking_pixel(html_body, email_log.tracking_id)
        tracked_html = cls.wrap_links_for_tracking(tracked_html, email_log.tracking_id)

        try:
            # Send through circuit breaker
            if account.provider == EmailProvider.SENDGRID:
                send_func = cls.send_via_sendgrid
            else:
                send_func = cls.send_via_smtp

            await email_circuit.call(
                send_func, account, to_email, subject, tracked_html
            )

            email_log.status = EmailStatus.SENT
            email_log.sent_at = datetime.utcnow()

            # Update account counters
            account.sent_today += 1
            account.sent_this_hour += 1

            # Log activity
            activity = Activity(
                lead_id=lead_id,
                channel=ActivityChannel.EMAIL,
                action="email_sent",
                description=f"Email sent: {subject}",
                details={"tracking_id": email_log.tracking_id},
            )
            db.add(activity)

            logger.info(f"Email sent to {to_email} via {account.email}")

        except Exception as e:
            email_log.status = EmailStatus.FAILED
            email_log.error_message = str(e)
            logger.error(f"Email send failed to {to_email}: {e}")

        await db.flush()
        return email_log

    @staticmethod
    async def get_available_account(db: AsyncSession, account_id: Optional[int] = None) -> Optional[EmailAccount]:
        """
        Get an available email account, respecting rate limits.
        If account_id is specified, use that account. Otherwise rotate.
        """
        if account_id:
            result = await db.execute(
                select(EmailAccount).where(
                    EmailAccount.id == account_id,
                    EmailAccount.is_active == True,
                )
            )
            account = result.scalar_one_or_none()
            if account and account.sent_today < account.daily_limit:
                return account
            return None

        # Rotate: pick account with lowest sent_today that hasn't hit limit
        result = await db.execute(
            select(EmailAccount)
            .where(EmailAccount.is_active == True)
            .order_by(EmailAccount.sent_today.asc())
        )
        accounts = result.scalars().all()
        for account in accounts:
            if account.sent_today < account.daily_limit:
                return account

        return None
