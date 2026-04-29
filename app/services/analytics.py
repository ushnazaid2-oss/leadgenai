"""
Analytics service — pipeline metrics, channel stats, exports.
"""
import io
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadStatus
from app.models.email_log import EmailLog
from app.models.whatsapp_log import WhatsAppLog
from app.models.call_log import CallLog
from app.models.campaign import Campaign, CampaignStatus

logger = logging.getLogger(__name__)


class AnalyticsService:

    @staticmethod
    async def get_pipeline(db: AsyncSession) -> dict:
        stages = []
        total_q = select(func.count(Lead.id))
        total = (await db.execute(total_q)).scalar() or 0
        for status in LeadStatus:
            q = select(func.count(Lead.id)).where(Lead.status == status)
            count = (await db.execute(q)).scalar() or 0
            stages.append({
                "stage": status.value,
                "count": count,
                "percentage": round(count / max(total, 1) * 100, 1),
            })
        return {"stages": stages, "total_leads": total}

    @staticmethod
    async def get_channel_stats(db: AsyncSession) -> dict:
        email_total = (await db.execute(select(func.count(EmailLog.id)))).scalar() or 0
        email_success = (await db.execute(
            select(func.count(EmailLog.id)).where(EmailLog.status.in_(["sent", "delivered", "opened", "clicked"]))
        )).scalar() or 0
        wa_total = (await db.execute(select(func.count(WhatsAppLog.id)))).scalar() or 0
        wa_success = (await db.execute(
            select(func.count(WhatsAppLog.id)).where(WhatsAppLog.status.in_(["sent", "delivered", "read"]))
        )).scalar() or 0
        call_total = (await db.execute(select(func.count(CallLog.id)))).scalar() or 0
        call_connected = (await db.execute(
            select(func.count(CallLog.id)).where(CallLog.outcome.in_(["interested", "not_interested", "follow_up"]))
        )).scalar() or 0

        return {"channels": [
            {"channel": "email", "total_sent": email_total,
             "success_rate": round(email_success / max(email_total, 1) * 100, 1), "response_rate": 0},
            {"channel": "whatsapp", "total_sent": wa_total,
             "success_rate": round(wa_success / max(wa_total, 1) * 100, 1), "response_rate": 0},
            {"channel": "call", "total_sent": call_total,
             "success_rate": round(call_connected / max(call_total, 1) * 100, 1), "response_rate": 0},
        ]}

    @staticmethod
    async def get_dashboard_summary(db: AsyncSession) -> dict:
        total_leads = (await db.execute(select(func.count(Lead.id)))).scalar() or 0
        hot_leads = (await db.execute(
            select(func.count(Lead.id)).where(Lead.is_hot_lead == True)
        )).scalar() or 0
        today = datetime.utcnow().date()
        new_today = (await db.execute(
            select(func.count(Lead.id)).where(func.date(Lead.created_at) == today)
        )).scalar() or 0
        emails_sent = (await db.execute(select(func.count(EmailLog.id)))).scalar() or 0
        wa_sent = (await db.execute(select(func.count(WhatsAppLog.id)))).scalar() or 0
        calls_made = (await db.execute(select(func.count(CallLog.id)))).scalar() or 0
        converted = (await db.execute(
            select(func.count(Lead.id)).where(Lead.status == LeadStatus.CONVERTED)
        )).scalar() or 0
        active_campaigns = (await db.execute(
            select(func.count(Campaign.id)).where(Campaign.status == CampaignStatus.ACTIVE)
        )).scalar() or 0

        return {
            "total_leads": total_leads, "hot_leads": hot_leads,
            "new_leads_today": new_today, "emails_sent": emails_sent,
            "whatsapp_sent": wa_sent, "calls_made": calls_made,
            "conversion_rate": round(converted / max(total_leads, 1) * 100, 2),
            "active_campaigns": active_campaigns,
        }

    @staticmethod
    async def get_timeline(db: AsyncSession, days: int = 30) -> dict:
        data = []
        for i in range(days - 1, -1, -1):
            day = (datetime.utcnow() - timedelta(days=i)).date()
            emails = (await db.execute(
                select(func.count(EmailLog.id)).where(func.date(EmailLog.created_at) == day)
            )).scalar() or 0
            wa = (await db.execute(
                select(func.count(WhatsAppLog.id)).where(func.date(WhatsAppLog.created_at) == day)
            )).scalar() or 0
            calls = (await db.execute(
                select(func.count(CallLog.id)).where(func.date(CallLog.created_at) == day)
            )).scalar() or 0
            converted = (await db.execute(
                select(func.count(Lead.id)).where(
                    and_(Lead.status == LeadStatus.CONVERTED, func.date(Lead.updated_at) == day)
                )
            )).scalar() or 0
            data.append({
                "date": str(day), "emails_sent": emails,
                "whatsapp_sent": wa, "calls_made": calls, "leads_converted": converted,
            })
        return {"data": data, "period": f"{days}d"}

    @staticmethod
    async def export_to_excel(db: AsyncSession) -> bytes:
        import pandas as pd
        result = await db.execute(select(Lead).order_by(Lead.created_at.desc()))
        leads = result.scalars().all()
        rows = [{
            "Name": l.name, "Company": l.company, "Email": l.email,
            "Phone": l.phone, "Niche": l.niche, "Status": l.status.value if l.status else "",
            "Hot Lead": l.is_hot_lead, "Source": l.source.value if l.source else "",
            "Created": str(l.created_at),
        } for l in leads]
        df = pd.DataFrame(rows)
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, sheet_name="Leads")
        buffer.seek(0)
        return buffer.read()

    @staticmethod
    async def export_to_pdf(db: AsyncSession) -> bytes:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        result = await db.execute(select(Lead).order_by(Lead.created_at.desc()))
        leads = result.scalars().all()
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        w, h = A4
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, h - 50, "Lead Generation AI — Report")
        c.setFont("Helvetica", 10)
        c.drawString(50, h - 70, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}")
        y = h - 100
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, y, "Name")
        c.drawString(180, y, "Company")
        c.drawString(300, y, "Email")
        c.drawString(450, y, "Status")
        y -= 15
        c.setFont("Helvetica", 8)
        for lead in leads[:100]:
            if y < 50:
                c.showPage()
                y = h - 50
            c.drawString(50, y, (lead.name or "")[:20])
            c.drawString(180, y, (lead.company or "")[:18])
            c.drawString(300, y, (lead.email or "")[:25])
            c.drawString(450, y, lead.status.value if lead.status else "")
            y -= 12
        c.save()
        buffer.seek(0)
        return buffer.read()
