"""
Call CRUD — database access for call logs.
"""
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.call_log import CallLog


async def get_call_logs(
    db: AsyncSession, lead_id: Optional[int] = None,
    campaign_id: Optional[int] = None, outcome: Optional[str] = None,
    page: int = 1, per_page: int = 50,
) -> Tuple[List[CallLog], int]:
    query = select(CallLog)
    count_q = select(func.count(CallLog.id))
    if lead_id:
        query = query.where(CallLog.lead_id == lead_id)
        count_q = count_q.where(CallLog.lead_id == lead_id)
    if campaign_id:
        query = query.where(CallLog.campaign_id == campaign_id)
        count_q = count_q.where(CallLog.campaign_id == campaign_id)
    if outcome:
        query = query.where(CallLog.outcome == outcome)
        count_q = count_q.where(CallLog.outcome == outcome)
    total = (await db.execute(count_q)).scalar() or 0
    offset = (page - 1) * per_page
    query = query.order_by(CallLog.created_at.desc()).offset(offset).limit(per_page)
    return (await db.execute(query)).scalars().all(), total


async def get_call_stats(db: AsyncSession, campaign_id: Optional[int] = None) -> dict:
    base = select(func.count(CallLog.id))
    if campaign_id:
        base = base.where(CallLog.campaign_id == campaign_id)
    total = (await db.execute(base)).scalar() or 0
    stats = {}
    for o in ["interested", "not_interested", "follow_up", "no_answer", "voicemail", "failed"]:
        q = select(func.count(CallLog.id)).where(CallLog.outcome == o)
        if campaign_id:
            q = q.where(CallLog.campaign_id == campaign_id)
        stats[o] = (await db.execute(q)).scalar() or 0
    avg_q = select(func.avg(CallLog.duration_seconds))
    if campaign_id:
        avg_q = avg_q.where(CallLog.campaign_id == campaign_id)
    avg_dur = (await db.execute(avg_q)).scalar() or 0
    hot_q = select(func.count(CallLog.id)).where(CallLog.is_hot_lead == True)
    if campaign_id:
        hot_q = hot_q.where(CallLog.campaign_id == campaign_id)
    hot = (await db.execute(hot_q)).scalar() or 0
    connected = total - stats.get("no_answer", 0) - stats.get("failed", 0)
    return {
        "total_calls": total, "connected": connected,
        "interested": stats.get("interested", 0),
        "not_interested": stats.get("not_interested", 0),
        "follow_up": stats.get("follow_up", 0),
        "no_answer": stats.get("no_answer", 0),
        "avg_duration": round(avg_dur, 1), "hot_leads": hot,
        "conversion_rate": round(stats.get("interested", 0) / max(connected, 1) * 100, 2),
    }


async def update_call_log(db: AsyncSession, call_sid: str, **kwargs) -> Optional[CallLog]:
    result = await db.execute(select(CallLog).where(CallLog.twilio_call_sid == call_sid))
    cl = result.scalar_one_or_none()
    if not cl:
        return None
    for k, v in kwargs.items():
        if v is not None and hasattr(cl, k):
            setattr(cl, k, v)
    await db.flush()
    return cl
