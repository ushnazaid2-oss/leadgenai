"""
WhatsApp CRUD — database access for WhatsApp logs.
"""

from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whatsapp_log import WhatsAppLog, WhatsAppDirection


async def get_whatsapp_logs(
    db: AsyncSession,
    lead_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 50,
) -> Tuple[List[WhatsAppLog], int]:
    query = select(WhatsAppLog)
    count_q = select(func.count(WhatsAppLog.id))
    if lead_id:
        query = query.where(WhatsAppLog.lead_id == lead_id)
        count_q = count_q.where(WhatsAppLog.lead_id == lead_id)
    if campaign_id:
        query = query.where(WhatsAppLog.campaign_id == campaign_id)
        count_q = count_q.where(WhatsAppLog.campaign_id == campaign_id)
    total = (await db.execute(count_q)).scalar() or 0
    offset = (page - 1) * per_page
    query = query.order_by(WhatsAppLog.created_at.asc()).offset(offset).limit(per_page)
    return (await db.execute(query)).scalars().all(), total


async def get_conversation(
    db: AsyncSession, lead_id: int
) -> List[WhatsAppLog]:
    """Get full conversation history for a lead."""
    result = await db.execute(
        select(WhatsAppLog)
        .where(WhatsAppLog.lead_id == lead_id)
        .order_by(WhatsAppLog.created_at.asc())
    )
    return result.scalars().all()
