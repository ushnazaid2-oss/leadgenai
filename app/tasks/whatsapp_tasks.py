"""
WhatsApp Celery Tasks — background workers for bulk broadcasts.
"""

import logging
import time
from app.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.whatsapp_tasks.send_whatsapp_broadcast",
    queue="whatsapp",
    max_retries=3,
    default_retry_delay=120,
    rate_limit="5/m",
    acks_late=True,
)
def send_whatsapp_broadcast(
    self, campaign_id: int, lead_ids: list,
    template_name: str, parameters: list = None,
):
    """Celery task: Broadcast WhatsApp template to a list of leads."""
    import asyncio
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.models.lead import Lead
    from app.models.campaign import Campaign, CampaignStatus
    from app.models.whatsapp_log import WhatsAppLog, WhatsAppStatus, WhatsAppDirection
    from app.models.activity import Activity, ActivityChannel
    from app.services.whatsapp_engine import WhatsAppEngine
    from datetime import datetime

    sync_url = settings.DATABASE_URL.replace("+aiosqlite", "").replace("aiosqlite:///", "sqlite:///")
    engine = create_engine(sync_url)

    with Session(engine) as db:
        try:
            campaign = db.execute(
                select(Campaign).where(Campaign.id == campaign_id)
            ).scalar_one_or_none()
            if not campaign:
                return {"error": "Campaign not found"}

            campaign.status = CampaignStatus.ACTIVE
            campaign.celery_task_id = self.request.id
            db.commit()

            sent = 0
            failed = 0

            for lead_id in lead_ids:
                # Rate limiting: delay between messages
                time.sleep(settings.WHATSAPP_BATCH_DELAY_SECONDS)

                lead = db.execute(
                    select(Lead).where(Lead.id == lead_id)
                ).scalar_one_or_none()

                if not lead or not lead.phone:
                    failed += 1
                    continue

                payload = WhatsAppEngine._build_template_payload(
                    lead.phone, template_name, parameters=parameters
                )

                log = WhatsAppLog(
                    lead_id=lead.id,
                    campaign_id=campaign_id,
                    template_name=template_name,
                    direction=WhatsAppDirection.OUTBOUND,
                    status=WhatsAppStatus.QUEUED,
                )
                db.add(log)
                db.commit()

                try:
                    import httpx
                    response = httpx.post(
                        f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
                        json=payload,
                        headers=WhatsAppEngine._get_headers(),
                        timeout=30,
                    )
                    if response.status_code in (200, 201):
                        log.status = WhatsAppStatus.SENT
                        log.sent_at = datetime.utcnow()
                        sent += 1
                    else:
                        log.status = WhatsAppStatus.FAILED
                        log.error_message = response.text
                        failed += 1
                except Exception as e:
                    log.status = WhatsAppStatus.FAILED
                    log.error_message = str(e)
                    failed += 1
                    logger.error(f"WhatsApp failed for lead {lead_id}: {e}")

                db.commit()
                self.update_state(
                    state="PROGRESS",
                    meta={"sent": sent, "failed": failed, "total": len(lead_ids)},
                )

            campaign.sent_count = sent
            campaign.success_count = sent
            campaign.failed_count = failed
            campaign.status = CampaignStatus.COMPLETED
            db.commit()

            return {"campaign_id": campaign_id, "sent": sent, "failed": failed}

        except Exception as e:
            logger.error(f"WhatsApp campaign {campaign_id} failed: {e}")
            if campaign:
                campaign.status = CampaignStatus.FAILED
                db.commit()
            raise self.retry(exc=e, countdown=120 * (2 ** self.request.retries))
