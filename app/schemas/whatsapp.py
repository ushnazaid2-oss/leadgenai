"""
WhatsApp schemas — request/response models for WhatsApp operations.
"""

from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel


class WhatsAppSend(BaseModel):
    lead_id: int
    template_name: str
    parameters: Optional[List[Dict[str, str]]] = None  # Template variables


class WhatsAppBroadcast(BaseModel):
    campaign_id: int
    template_name: str
    parameters: Optional[List[Dict[str, str]]] = None
    lead_ids: Optional[List[int]] = None
    filters: Optional[dict] = None


class WhatsAppLogResponse(BaseModel):
    id: int
    lead_id: int
    campaign_id: Optional[int] = None
    template_name: Optional[str] = None
    message_body: Optional[str] = None
    direction: str
    status: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WhatsAppConversation(BaseModel):
    lead_id: int
    lead_name: str
    messages: List[WhatsAppLogResponse]


class WhatsAppAutoReplyRule(BaseModel):
    keyword: str
    response_template: str
    is_active: bool = True
