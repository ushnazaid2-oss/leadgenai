"""
WhatsApp API — endpoints for sending messages, broadcasts, and webhook handling.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.whatsapp import WhatsAppSend, WhatsAppBroadcast, WhatsAppLogResponse
from app.crud.leads import get_lead_by_id, get_lead_ids_by_filter
from app.crud.whatsapp import get_whatsapp_logs, get_conversation
from app.services.whatsapp_engine import WhatsAppEngine
from app.tasks.whatsapp_tasks import send_whatsapp_broadcast
from app.config import settings

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])


@router.post("/send")
async def send_whatsapp_message(
    data: WhatsAppSend,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a WhatsApp template message to a single lead."""
    if not settings.FEATURE_WHATSAPP_ENABLED:
        raise HTTPException(status_code=403, detail="WhatsApp module is disabled")
    lead = await get_lead_by_id(db, data.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.phone:
        raise HTTPException(status_code=400, detail="Lead has no phone number")

    log = await WhatsAppEngine.send_template_message(
        db, lead, data.template_name, data.parameters
    )
    return {"status": log.status.value, "message_id": log.whatsapp_message_id}


@router.post("/broadcast")
async def broadcast_whatsapp(
    data: WhatsAppBroadcast,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Launch a bulk WhatsApp broadcast campaign via Celery."""
    if not settings.FEATURE_WHATSAPP_ENABLED:
        raise HTTPException(status_code=403, detail="WhatsApp module is disabled")

    lead_ids = await get_lead_ids_by_filter(db, data.lead_ids, data.filters)
    if not lead_ids:
        raise HTTPException(status_code=400, detail="No leads match the criteria")

    task = send_whatsapp_broadcast.delay(
        data.campaign_id, lead_ids, data.template_name, data.parameters
    )
    return {"task_id": task.id, "lead_count": len(lead_ids), "status": "queued"}


@router.get("/conversations/{lead_id}")
async def get_lead_conversation(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full WhatsApp conversation history for a lead."""
    lead = await get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    messages = await get_conversation(db, lead_id)
    return {
        "lead_id": lead_id,
        "lead_name": lead.name,
        "messages": [WhatsAppLogResponse.model_validate(m) for m in messages],
    }


@router.get("/logs", response_model=list[WhatsAppLogResponse])
async def list_whatsapp_logs(
    lead_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get WhatsApp message logs."""
    logs, _ = await get_whatsapp_logs(db, lead_id, campaign_id, page, per_page)
    return logs


@router.get("/webhook")
async def verify_webhook(request: Request):
    """Meta webhook verification challenge."""
    params = dict(request.query_params)
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN
    ):
        return int(params.get("hub.challenge", 0))
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive incoming WhatsApp messages and delivery status updates."""
    data = await request.json()
    await WhatsAppEngine.process_incoming_webhook(db, data)
    return {"status": "ok"}
