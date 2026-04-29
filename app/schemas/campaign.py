"""
Campaign schemas — request/response models for campaign management.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class CampaignCreate(BaseModel):
    name: str
    type: str  # email, whatsapp, call
    template_name: Optional[str] = None
    niche_filter: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    lead_ids: Optional[List[int]] = None
    filters: Optional[dict] = None  # Filter leads by niche, status, etc.


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    template_name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class CampaignResponse(BaseModel):
    id: int
    name: str
    type: str
    status: str
    template_name: Optional[str] = None
    niche_filter: Optional[str] = None
    subject: Optional[str] = None
    target_count: int
    sent_count: int
    success_count: int
    failed_count: int
    celery_task_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    total: int
    campaigns: List[CampaignResponse]


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # pending, running, completed, failed
    progress: Optional[int] = None
    total: Optional[int] = None
    result: Optional[dict] = None
