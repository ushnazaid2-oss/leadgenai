"""
Call schemas — request/response models for AI voice calling.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class CallInitiate(BaseModel):
    lead_id: int
    from_number: Optional[str] = None  # Twilio number; None = use default
    call_script: Optional[str] = None  # Override default script


class CallCampaignLaunch(BaseModel):
    campaign_id: int
    from_number: Optional[str] = None
    call_script: str
    lead_ids: Optional[List[int]] = None
    filters: Optional[dict] = None


class CallScriptUpdate(BaseModel):
    name: str
    script: str
    system_prompt: Optional[str] = None


class CallLogResponse(BaseModel):
    id: int
    lead_id: int
    campaign_id: Optional[int] = None
    twilio_call_sid: Optional[str] = None
    from_number: str
    to_number: str
    duration_seconds: int
    outcome: Optional[str] = None
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    is_hot_lead: bool
    scheduled_meeting: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TwilioNumberResponse(BaseModel):
    phone_number: str
    friendly_name: str
    country: str
    capabilities: dict


class CallStatsResponse(BaseModel):
    total_calls: int
    connected: int
    interested: int
    not_interested: int
    follow_up: int
    no_answer: int
    avg_duration: float
    hot_leads: int
    conversion_rate: float
