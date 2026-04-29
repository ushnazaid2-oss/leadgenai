"""
Analytics schemas — response models for dashboard charts and exports.
"""

from typing import Optional, List, Dict
from pydantic import BaseModel


class PipelineStage(BaseModel):
    stage: str
    count: int
    percentage: float


class PipelineResponse(BaseModel):
    stages: List[PipelineStage]
    total_leads: int


class ChannelStats(BaseModel):
    channel: str
    total_sent: int
    success_rate: float
    response_rate: float


class ChannelStatsResponse(BaseModel):
    channels: List[ChannelStats]


class TimelineDataPoint(BaseModel):
    date: str
    emails_sent: int
    whatsapp_sent: int
    calls_made: int
    leads_converted: int


class TimelineResponse(BaseModel):
    data: List[TimelineDataPoint]
    period: str  # "7d", "30d", "90d"


class DashboardSummary(BaseModel):
    total_leads: int
    hot_leads: int
    new_leads_today: int
    emails_sent: int
    whatsapp_sent: int
    calls_made: int
    conversion_rate: float
    active_campaigns: int


class ExportRequest(BaseModel):
    format: str = "excel"  # excel or pdf
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    channels: Optional[List[str]] = None
    statuses: Optional[List[str]] = None
