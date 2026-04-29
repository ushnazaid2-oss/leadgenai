"""
Campaigns CRUD — database access for campaigns.
"""
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.lead import Lead


async def create_campaign(
    db: AsyncSession, name: str, type: str,
    template_name: Optional[str] = None, subject: Optional[str] = None,
    body: Optional[str] = None, niche_filter: Optional[str] = None,
) -> Campaign:
    # Calculate target count based on filter
    query = select(func.count(Lead.id))
    if niche_filter:
        niches = [n.strip() for n in niche_filter.split(',') if n.strip()]
        if niches:
            query = query.where(Lead.niche.in_(niches))
    target_count = (await db.execute(query)).scalar() or 0

    campaign = Campaign(
        name=name, type=CampaignType(type),
        template_name=template_name, niche_filter=niche_filter,
        subject=subject, body=body, target_count=target_count,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign


async def get_campaigns(
    db: AsyncSession, type: Optional[str] = None,
    status: Optional[str] = None, page: int = 1, per_page: int = 50,
) -> tuple:
    query = select(Campaign)
    count_q = select(func.count(Campaign.id))
    if type:
        query = query.where(Campaign.type == type)
        count_q = count_q.where(Campaign.type == type)
    if status:
        query = query.where(Campaign.status == status)
        count_q = count_q.where(Campaign.status == status)
    total = (await db.execute(count_q)).scalar() or 0
    offset = (page - 1) * per_page
    query = query.order_by(Campaign.created_at.desc()).offset(offset).limit(per_page)
    return (await db.execute(query)).scalars().all(), total


async def get_campaign_by_id(db: AsyncSession, campaign_id: int) -> Optional[Campaign]:
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    return result.scalar_one_or_none()


async def update_campaign(db: AsyncSession, campaign_id: int, **kwargs) -> Optional[Campaign]:
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        return None
    for k, v in kwargs.items():
        if v is not None and hasattr(campaign, k):
            setattr(campaign, k, v)
    await db.flush()
    await db.refresh(campaign)
    return campaign


async def delete_campaign(db: AsyncSession, campaign_id: int) -> bool:
    from sqlalchemy import delete
    from app.models.email_log import EmailLog
    from app.models.whatsapp_log import WhatsAppLog
    from app.models.call_log import CallLog

    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        return False
    
    # Force delete all logs
    await db.execute(delete(EmailLog).where(EmailLog.campaign_id == campaign_id))
    await db.execute(delete(WhatsAppLog).where(WhatsAppLog.campaign_id == campaign_id))
    await db.execute(delete(CallLog).where(CallLog.campaign_id == campaign_id))
    
    await db.delete(campaign)
    await db.flush()
    return True
