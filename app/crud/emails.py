"""
Email CRUD operations — database access for email logs and accounts.
"""

from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_log import EmailLog, EmailStatus
from app.models.email_account import EmailAccount, EmailProvider


async def create_email_account(
    db: AsyncSession, name: str, email: str, provider: str,
    smtp_host: Optional[str] = None, smtp_port: int = 587,
    username: Optional[str] = None, password: Optional[str] = None,
    sendgrid_api_key: Optional[str] = None,
    daily_limit: int = 500, hourly_limit: int = 50,
) -> EmailAccount:
    account = EmailAccount(
        name=name, email=email, provider=EmailProvider(provider),
        smtp_host=smtp_host, smtp_port=smtp_port, username=username,
        encrypted_password=password, sendgrid_api_key=sendgrid_api_key,
        daily_limit=daily_limit, hourly_limit=hourly_limit,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account


async def get_email_accounts(db: AsyncSession) -> List[EmailAccount]:
    result = await db.execute(select(EmailAccount).order_by(EmailAccount.created_at.desc()))
    return result.scalars().all()


async def get_email_logs(
    db: AsyncSession, campaign_id: Optional[int] = None,
    lead_id: Optional[int] = None, status: Optional[str] = None,
    page: int = 1, per_page: int = 50,
) -> Tuple[List[EmailLog], int]:
    query = select(EmailLog)
    count_query = select(func.count(EmailLog.id))
    if campaign_id:
        query = query.where(EmailLog.campaign_id == campaign_id)
        count_query = count_query.where(EmailLog.campaign_id == campaign_id)
    if lead_id:
        query = query.where(EmailLog.lead_id == lead_id)
        count_query = count_query.where(EmailLog.lead_id == lead_id)
    if status:
        query = query.where(EmailLog.status == status)
        count_query = count_query.where(EmailLog.status == status)
    total = (await db.execute(count_query)).scalar()
    offset = (page - 1) * per_page
    query = query.order_by(EmailLog.created_at.desc()).offset(offset).limit(per_page)
    return (await db.execute(query)).scalars().all(), total


async def get_email_stats(db: AsyncSession, campaign_id: Optional[int] = None) -> dict:
    total_q = select(func.count(EmailLog.id))
    if campaign_id:
        total_q = total_q.where(EmailLog.campaign_id == campaign_id)
    total = (await db.execute(total_q)).scalar() or 0
    stats = {}
    for s in ["sent", "delivered", "opened", "clicked", "bounced", "failed"]:
        q = select(func.count(EmailLog.id)).where(EmailLog.status == s)
        if campaign_id:
            q = q.where(EmailLog.campaign_id == campaign_id)
        stats[s] = (await db.execute(q)).scalar() or 0
    sent_total = max(stats["sent"] + stats["delivered"] + stats["opened"] + stats["clicked"], 1)
    return {
        "total_sent": total, "delivered": stats["delivered"],
        "opened": stats["opened"], "clicked": stats["clicked"],
        "bounced": stats["bounced"], "failed": stats["failed"],
        "open_rate": round(stats["opened"] / sent_total * 100, 2),
        "click_rate": round(stats["clicked"] / sent_total * 100, 2),
        "bounce_rate": round(stats["bounced"] / sent_total * 100, 2),
    }
