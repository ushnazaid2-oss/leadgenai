"""
Call Celery Tasks — background workers for bulk calling campaigns.
"""

import logging
import time
from app.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.call_tasks.run_call_campaign",
    queue="calls",
    max_retries=2,
    default_retry_delay=180,
    rate_limit="3/m",
    acks_late=True,
)
def run_call_campaign(
    self, campaign_id: int, lead_ids: list,
    from_number: str = None, call_script: str = "",
):
    """Celery task: Execute bulk AI calling campaign."""
    import asyncio
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.models.lead import Lead
    from app.models.campaign import Campaign, CampaignStatus
    from app.models.call_log import CallLog, CallOutcome
    from app.services.voice_agent import VoiceAgent
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

            initiated = 0
            failed = 0

            for lead_id in lead_ids:
                # Rate limiting: max concurrent calls
                time.sleep(10)  # 10 seconds between calls

                lead = db.execute(
                    select(Lead).where(Lead.id == lead_id)
                ).scalar_one_or_none()
                if not lead or not lead.phone:
                    failed += 1
                    continue

                # Create call log
                call_log = CallLog(
                    lead_id=lead.id,
                    campaign_id=campaign_id,
                    from_number=from_number or settings.TWILIO_DEFAULT_FROM_NUMBER,
                    to_number=lead.phone,
                    call_script_used=call_script,
                    started_at=datetime.utcnow(),
                )
                db.add(call_log)
                db.commit()
                db.refresh(call_log)

                try:
                    result = asyncio.run(
                        VoiceAgent.initiate_call(
                            to_number=lead.phone,
                            from_number=from_number,
                            call_script=call_script,
                            lead_id=lead.id,
                            campaign_id=campaign_id,
                        )
                    )
                    call_log.twilio_call_sid = result.get("call_sid")
                    initiated += 1
                except Exception as e:
                    call_log.outcome = CallOutcome.FAILED
                    call_log.error_message = str(e)
                    failed += 1
                    logger.error(f"Call failed for lead {lead_id}: {e}")

                db.commit()
                self.update_state(
                    state="PROGRESS",
                    meta={"initiated": initiated, "failed": failed, "total": len(lead_ids)},
                )

            campaign.sent_count = initiated
            campaign.failed_count = failed
            campaign.status = CampaignStatus.COMPLETED
            db.commit()

            return {"campaign_id": campaign_id, "initiated": initiated, "failed": failed}

        except Exception as e:
            logger.error(f"Call campaign {campaign_id} failed: {e}")
            if campaign:
                campaign.status = CampaignStatus.FAILED
                db.commit()
            raise self.retry(exc=e, countdown=180 * (2 ** self.request.retries))
