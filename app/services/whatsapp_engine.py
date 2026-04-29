"""
WhatsApp Engine — Meta Cloud API integration for bulk messaging and auto-reply.
"""

import logging
import httpx
from typing import Optional, List, Dict
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.whatsapp_log import WhatsAppLog, WhatsAppStatus, WhatsAppDirection
from app.models.lead import Lead
from app.models.activity import Activity, ActivityChannel
from app.services.circuit_breaker import whatsapp_circuit

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = settings.WHATSAPP_API_URL
PHONE_NUMBER_ID = settings.WHATSAPP_PHONE_NUMBER_ID
ACCESS_TOKEN = settings.WHATSAPP_ACCESS_TOKEN


class WhatsAppEngine:
    """Handles Meta WhatsApp Cloud API interactions."""

    @staticmethod
    def _get_headers() -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _build_template_payload(
        recipient_phone: str,
        template_name: str,
        language_code: str = "en_US",
        parameters: Optional[List[Dict]] = None,
    ) -> dict:
        """Build a WhatsApp template message payload."""
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone.replace("+", ""),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if parameters:
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": p.get("value", "")}
                        for p in parameters
                    ],
                }
            ]
        return payload

    @classmethod
    async def send_template_message(
        cls,
        db: AsyncSession,
        lead: Lead,
        template_name: str,
        parameters: Optional[List[Dict]] = None,
        campaign_id: Optional[int] = None,
    ) -> WhatsAppLog:
        """Send a WhatsApp template message to a lead."""
        if not lead.phone:
            raise ValueError(f"Lead {lead.id} has no phone number")

        log = WhatsAppLog(
            lead_id=lead.id,
            campaign_id=campaign_id,
            template_name=template_name,
            direction=WhatsAppDirection.OUTBOUND,
            status=WhatsAppStatus.QUEUED,
        )
        db.add(log)
        await db.flush()
        await db.refresh(log)

        payload = cls._build_template_payload(
            lead.phone, template_name, parameters=parameters
        )

        async def _send():
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages",
                    json=payload,
                    headers=cls._get_headers(),
                )
                if response.status_code not in (200, 201):
                    raise Exception(
                        f"WhatsApp API error {response.status_code}: {response.text}"
                    )
                return response.json()

        try:
            result = await whatsapp_circuit.call(_send)
            wa_msg_id = result.get("messages", [{}])[0].get("id")
            log.whatsapp_message_id = wa_msg_id
            log.status = WhatsAppStatus.SENT
            log.sent_at = datetime.utcnow()

            activity = Activity(
                lead_id=lead.id,
                channel=ActivityChannel.WHATSAPP,
                action="whatsapp_sent",
                description=f"WhatsApp template '{template_name}' sent",
                details={"message_id": wa_msg_id, "template": template_name},
            )
            db.add(activity)
            logger.info(f"WhatsApp sent to {lead.phone}: {wa_msg_id}")

        except Exception as e:
            log.status = WhatsAppStatus.FAILED
            log.error_message = str(e)
            logger.error(f"WhatsApp send failed to {lead.phone}: {e}")

        await db.flush()
        return log

    @classmethod
    async def process_incoming_webhook(
        cls,
        db: AsyncSession,
        webhook_data: dict,
    ):
        """Process an incoming WhatsApp message from the Meta webhook."""
        try:
            entries = webhook_data.get("entry", [])
            for entry in entries:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    for msg in messages:
                        from_phone = msg.get("from")
                        msg_type = msg.get("type")
                        body = ""
                        if msg_type == "text":
                            body = msg.get("text", {}).get("body", "")

                        # Find matching lead by phone
                        from sqlalchemy import select
                        from app.models.lead import Lead
                        result = await db.execute(
                            select(Lead).where(
                                Lead.phone.like(f"%{from_phone[-10:]}")
                            )
                        )
                        lead = result.scalar_one_or_none()

                        if lead:
                            # Log inbound message
                            inbound_log = WhatsAppLog(
                                lead_id=lead.id,
                                message_body=body,
                                direction=WhatsAppDirection.INBOUND,
                                status=WhatsAppStatus.DELIVERED,
                                whatsapp_message_id=msg.get("id"),
                            )
                            db.add(inbound_log)

                            # Log activity
                            activity = Activity(
                                lead_id=lead.id,
                                channel=ActivityChannel.WHATSAPP,
                                action="whatsapp_received",
                                description=f"Received: {body[:100]}",
                            )
                            db.add(activity)

                        # Auto-reply based on keywords
                        if body and lead:
                            await cls._check_auto_reply(lead.phone, body)

            await db.flush()

        except Exception as e:
            logger.error(f"Webhook processing error: {e}")

    @classmethod
    async def _check_auto_reply(cls, phone: str, message: str):
        """Simple keyword-based auto-reply handler."""
        msg_lower = message.lower()
        auto_replies = {
            "price": "Thanks for your interest! Our pricing starts at $99/month. Reply DEMO to schedule a call.",
            "demo": "Great! Please visit https://calendly.com/demo to book your free demo.",
            "stop": "You have been unsubscribed. Reply START to re-subscribe.",
            "help": "How can we help? Reply with: PRICE, DEMO, or talk to a human.",
        }
        for keyword, reply_text in auto_replies.items():
            if keyword in msg_lower:
                await cls._send_text_reply(phone, reply_text)
                break

    @classmethod
    async def _send_text_reply(cls, to_phone: str, text: str):
        """Send a free-form text reply (only within 24h window)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone.replace("+", ""),
            "type": "text",
            "text": {"body": text},
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(
                    f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages",
                    json=payload,
                    headers=cls._get_headers(),
                )
        except Exception as e:
            logger.error(f"Auto-reply failed: {e}")
