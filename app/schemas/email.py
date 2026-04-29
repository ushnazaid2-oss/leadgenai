"""
Email schemas — request/response models for email operations.
"""

from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, EmailStr


class EmailSend(BaseModel):
    lead_id: int
    sender_account_id: Optional[int] = None
    subject: str
    body_html: str
    personalization: Optional[Dict[str, str]] = None  # {name}, {company}, {service}


class EmailCampaignLaunch(BaseModel):
    campaign_id: int
    sender_account_id: Optional[int] = None  # None = rotate across all active
    subject: str
    body_html: str
    lead_ids: Optional[List[int]] = None
    filters: Optional[dict] = None


class EmailAccountCreate(BaseModel):
    name: str
    email: EmailStr
    provider: str  # gmail, outlook, sendgrid, custom_smtp
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = 587
    username: Optional[str] = None
    password: Optional[str] = None
    sendgrid_api_key: Optional[str] = None
    daily_limit: int = 500
    hourly_limit: int = 50


class EmailAccountUpdate(BaseModel):
    name: Optional[str] = None
    daily_limit: Optional[int] = None
    hourly_limit: Optional[int] = None
    is_active: Optional[bool] = None


class EmailAccountResponse(BaseModel):
    id: int
    name: str
    email: str
    provider: str
    is_active: bool
    daily_limit: int
    hourly_limit: int
    sent_today: int
    sent_this_hour: int
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailLogResponse(BaseModel):
    id: int
    lead_id: int
    campaign_id: Optional[int] = None
    sender_email: str
    recipient_email: str
    subject: str
    status: str
    tracking_id: str
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailStatsResponse(BaseModel):
    total_sent: int
    delivered: int
    opened: int
    clicked: int
    bounced: int
    failed: int
    open_rate: float
    click_rate: float
    bounce_rate: float
