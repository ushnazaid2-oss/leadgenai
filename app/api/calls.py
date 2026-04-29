"""
Calls API — AI voice calling endpoints and Twilio webhooks.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json, urllib.parse

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.call import CallInitiate, CallCampaignLaunch, CallLogResponse, CallStatsResponse
from app.crud.leads import get_lead_by_id, get_lead_ids_by_filter
from app.crud.calls import get_call_logs, get_call_stats, update_call_log
from app.services.voice_agent import VoiceAgent
from app.tasks.call_tasks import run_call_campaign
from app.config import settings

router = APIRouter(prefix="/api/calls", tags=["Calls"])

# In-memory conversation state (for Phase 1; use Redis in production)
_conversations: dict = {}


@router.post("/initiate")
async def initiate_call(
    data: CallInitiate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Initiate a single AI call to a lead."""
    if not settings.FEATURE_CALLS_ENABLED:
        raise HTTPException(status_code=403, detail="Calls module is disabled")
    lead = await get_lead_by_id(db, data.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.phone:
        raise HTTPException(status_code=400, detail="Lead has no phone number")

    from app.models.call_log import CallLog
    call_log = CallLog(
        lead_id=lead.id, from_number=data.from_number or settings.TWILIO_DEFAULT_FROM_NUMBER,
        to_number=lead.phone, call_script_used=data.call_script, started_at=datetime.utcnow(),
    )
    db.add(call_log)
    await db.flush()

    result = await VoiceAgent.initiate_call(
        to_number=lead.phone, from_number=data.from_number,
        call_script=data.call_script, lead_id=lead.id,
    )
    call_log.twilio_call_sid = result.get("call_sid")
    await db.flush()
    return {"call_sid": result["call_sid"], "status": "initiated"}


@router.post("/campaign")
async def launch_call_campaign(
    data: CallCampaignLaunch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Launch a bulk calling campaign via Celery."""
    if not settings.FEATURE_CALLS_ENABLED:
        raise HTTPException(status_code=403, detail="Calls module is disabled")
    lead_ids = await get_lead_ids_by_filter(db, data.lead_ids, data.filters)
    if not lead_ids:
        raise HTTPException(status_code=400, detail="No leads match")
    task = run_call_campaign.delay(data.campaign_id, lead_ids, data.from_number, data.call_script)
    return {"task_id": task.id, "lead_count": len(lead_ids), "status": "queued"}


@router.get("/numbers")
async def list_numbers(current_user: User = Depends(get_current_user)):
    """List available Twilio phone numbers."""
    return await VoiceAgent.list_available_numbers()


@router.get("/logs", response_model=list[CallLogResponse])
async def list_call_logs(
    lead_id: Optional[int] = None, campaign_id: Optional[int] = None,
    outcome: Optional[str] = None, page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logs, _ = await get_call_logs(db, lead_id, campaign_id, outcome, page, per_page)
    return logs


@router.get("/stats", response_model=CallStatsResponse)
async def call_statistics(
    campaign_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_call_stats(db, campaign_id)


# --- Twilio Webhooks (public, called by Twilio) ---

@router.post("/twilio-voice-webhook", response_class=PlainTextResponse)
async def twilio_voice_webhook(request: Request):
    """Called by Twilio when call connects. Returns initial greeting TwiML."""
    params = dict(request.query_params)
    script = urllib.parse.unquote(params.get("script", ""))
    lead_id = params.get("lead_id", "0")
    call_sid = (await request.form()).get("CallSid", "")

    _conversations[call_sid] = {"history": [], "script": script, "lead_id": lead_id, "turn": 0}
    twiml = VoiceAgent.build_initial_greeting(script or None)
    return PlainTextResponse(content=twiml, media_type="application/xml")


@router.post("/twilio-gather-response", response_class=PlainTextResponse)
async def twilio_gather_response(request: Request):
    """Process speech gathered by Twilio and respond with AI-generated TwiML."""
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult", "")
    call_sid = form_data.get("CallSid", "")

    conv = _conversations.get(call_sid, {"history": [], "script": "", "turn": 0})
    conv["turn"] += 1
    conv["history"].append({"role": "user", "content": speech_result})

    # End call after 10 turns or end signals
    end_signals = ["goodbye", "not interested", "stop calling", "bye", "no thanks"]
    should_end = conv["turn"] >= 10 or any(s in speech_result.lower() for s in end_signals)

    import asyncio
    ai_response = await VoiceAgent.process_speech_input(
        speech_result, conv["history"], conv.get("script")
    )
    conv["history"].append({"role": "assistant", "content": ai_response})
    _conversations[call_sid] = conv

    twiml = VoiceAgent.build_response_twiml(ai_response, should_continue=not should_end)
    return PlainTextResponse(content=twiml, media_type="application/xml")


@router.post("/twilio-status")
async def twilio_status_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Twilio call status updates and finalize call logs."""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "")
    duration = int(form_data.get("CallDuration", 0))

    if call_status == "completed" and call_sid in _conversations:
        conv = _conversations.pop(call_sid, {})
        transcript = "\n".join(
            f"{'Lead' if m['role'] == 'user' else 'Agent'}: {m['content']}"
            for m in conv.get("history", [])
        )
        # Classify outcome
        classification = await VoiceAgent.classify_call_outcome(transcript)
        await update_call_log(
            db, call_sid,
            duration_seconds=duration, transcript=transcript,
            outcome=classification.get("outcome", "follow_up"),
            ai_summary=classification.get("summary", ""),
            is_hot_lead=classification.get("is_hot_lead", False),
            ended_at=datetime.utcnow(),
        )
    elif call_status in ("no-answer", "busy", "failed"):
        await update_call_log(
            db, call_sid, outcome="no_answer" if call_status != "failed" else "failed",
            duration_seconds=duration, ended_at=datetime.utcnow(),
        )

    return {"status": "ok"}
