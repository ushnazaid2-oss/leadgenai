"""
Tracking service — handles open pixel and click redirect tracking.
"""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_log import EmailLog, EmailStatus
from app.models.lead import Lead, LeadStatus
from app.models.activity import Activity, ActivityChannel

logger = logging.getLogger(__name__)


class TrackingService:
    """Handles email open and click tracking events."""

    @staticmethod
    async def record_open(db: AsyncSession, tracking_id: str) -> bool:
        """Record an email open event from tracking pixel."""
        result = await db.execute(
            select(EmailLog).where(EmailLog.tracking_id == tracking_id)
        )
        email_log = result.scalar_one_or_none()

        if email_log is None:
            logger.warning(f"Tracking ID not found: {tracking_id}")
            return False

        # Only record first open
        if email_log.opened_at is None:
            email_log.opened_at = datetime.utcnow()
            email_log.status = EmailStatus.OPENED

            # Update lead status if still at "contacted"
            lead_result = await db.execute(
                select(Lead).where(Lead.id == email_log.lead_id)
            )
            lead = lead_result.scalar_one_or_none()
            if lead and lead.status in (LeadStatus.NEW, LeadStatus.CONTACTED):
                lead.status = LeadStatus.OPENED

            # Log activity
            activity = Activity(
                lead_id=email_log.lead_id,
                channel=ActivityChannel.EMAIL,
                action="email_opened",
                description=f"Opened: {email_log.subject}",
                details={"tracking_id": tracking_id},
            )
            db.add(activity)

            logger.info(f"Open tracked: {tracking_id} (lead {email_log.lead_id})")

        return True

    @staticmethod
    async def record_click(
        db: AsyncSession, tracking_id: str, original_url: str
    ) -> bool:
        """Record an email link click event."""
        result = await db.execute(
            select(EmailLog).where(EmailLog.tracking_id == tracking_id)
        )
        email_log = result.scalar_one_or_none()

        if email_log is None:
            logger.warning(f"Tracking ID not found for click: {tracking_id}")
            return False

        # Record click
        if email_log.clicked_at is None:
            email_log.clicked_at = datetime.utcnow()
            email_log.status = EmailStatus.CLICKED

        # Log activity
        activity = Activity(
            lead_id=email_log.lead_id,
            channel=ActivityChannel.EMAIL,
            action="email_link_clicked",
            description=f"Clicked link in: {email_log.subject}",
            details={"tracking_id": tracking_id, "url": original_url},
        )
        db.add(activity)

        logger.info(f"Click tracked: {tracking_id} → {original_url}")
        return True
