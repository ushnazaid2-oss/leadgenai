"""
Email Celery Tasks — background workers for bulk email campaigns.
Implements retry with exponential backoff and rate limiting.
"""

import logging
import time
from app.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.email_tasks.send_bulk_emails",
    queue="email",
    max_retries=3,
    default_retry_delay=60,
    rate_limit="10/m",
    acks_late=True,
)
def send_bulk_emails(self, campaign_id: int, lead_ids: list, sender_account_id: int = None):
    """
    Celery task: Send emails to a list of leads for a campaign.
    Runs synchronously inside the worker (uses sync DB session).
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.models.lead import Lead
    from app.models.campaign import Campaign, CampaignStatus
    from app.models.email_account import EmailAccount
    from app.models.email_log import EmailLog, EmailStatus
    from app.models.activity import Activity, ActivityChannel
    from app.services.email_engine import EmailEngine
    import asyncio

    # Sync DB for Celery workers
    sync_url = settings.DATABASE_URL.replace("+aiosqlite", "").replace("aiosqlite:///", "sqlite:///")
    engine = create_engine(sync_url)

    with Session(engine) as db:
        try:
            # Get campaign
            campaign = db.execute(
                select(Campaign).where(Campaign.id == campaign_id)
            ).scalar_one_or_none()

            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return {"error": "Campaign not found"}

            campaign.status = CampaignStatus.ACTIVE
            campaign.celery_task_id = self.request.id
            db.commit()

            sent_count = 0
            failed_count = 0

            for idx, lead_id in enumerate(lead_ids):
                # Rate limiting: respect per-second send rate
                time.sleep(1.0 / max(settings.EMAIL_RATE_PER_SECOND, 1))

                lead = db.execute(
                    select(Lead).where(Lead.id == lead_id)
                ).scalar_one_or_none()

                if not lead:
                    failed_count += 1
                    continue

                # Get available sender account
                if sender_account_id:
                    account = db.execute(
                        select(EmailAccount).where(EmailAccount.id == sender_account_id)
                    ).scalar_one_or_none()
                else:
                    # Rotate: pick account with lowest sent_today
                    account = db.execute(
                        select(EmailAccount)
                        .where(EmailAccount.is_active == True)
                        .order_by(EmailAccount.sent_today.asc())
                    ).scalars().first()

                if not account:
                    logger.warning("No available email account")
                    failed_count += 1
                    continue

                # Check rate limits
                if account.sent_today >= account.daily_limit:
                    logger.warning(f"Account {account.email} hit daily limit")
                    failed_count += 1
                    continue

                # Render personalization
                personalization = {
                    "name": lead.name,
                    "company": lead.company or "your company",
                    "email": lead.email,
                    "niche": lead.niche or "",
                }

                subject = EmailEngine.render_template(
                    campaign.subject or "Hello {name}", personalization
                )
                body = EmailEngine.render_template(
                    campaign.body or "", personalization
                )

                # Create email log
                email_log = EmailLog(
                    lead_id=lead.id,
                    campaign_id=campaign_id,
                    sender_email=account.email,
                    recipient_email=lead.email,
                    subject=subject,
                    body_html=body,
                    status=EmailStatus.QUEUED,
                )
                db.add(email_log)
                db.commit()
                db.refresh(email_log)

                # Inject tracking
                tracked_body = EmailEngine.inject_tracking_pixel(body, email_log.tracking_id)
                tracked_body = EmailEngine.wrap_links_for_tracking(tracked_body, email_log.tracking_id)

                try:
                    # Send email (sync wrapper for async)
                    if account.provider.value == "sendgrid":
                        asyncio.run(EmailEngine.send_via_sendgrid(
                            account, lead.email, subject, tracked_body
                        ))
                    else:
                        asyncio.run(EmailEngine.send_via_smtp(
                            account, lead.email, subject, tracked_body
                        ))

                    email_log.status = EmailStatus.SENT
                    email_log.sent_at = __import__("datetime").datetime.utcnow()
                    account.sent_today += 1
                    sent_count += 1

                    # Log activity
                    activity = Activity(
                        lead_id=lead.id,
                        channel=ActivityChannel.EMAIL,
                        action="email_sent",
                        description=f"Campaign email: {subject}",
                    )
                    db.add(activity)

                except Exception as e:
                    email_log.status = EmailStatus.FAILED
                    email_log.error_message = str(e)
                    failed_count += 1
                    logger.error(f"Failed to send to {lead.email}: {e}")

                db.commit()

                # Update task progress
                self.update_state(
                    state="PROGRESS",
                    meta={"sent": sent_count, "failed": failed_count, "total": len(lead_ids)},
                )

            # Finalize campaign
            campaign.sent_count = sent_count
            campaign.success_count = sent_count
            campaign.failed_count = failed_count
            campaign.status = CampaignStatus.COMPLETED
            db.commit()

            result = {
                "campaign_id": campaign_id,
                "total": len(lead_ids),
                "sent": sent_count,
                "failed": failed_count,
            }
            logger.info(f"Email campaign {campaign_id} completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Email campaign {campaign_id} failed: {e}")
            if campaign:
                campaign.status = CampaignStatus.FAILED
                db.commit()
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
