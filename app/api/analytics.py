"""
Analytics API — dashboard summary, pipeline, timeline, and export endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.analytics import (
    PipelineResponse, ChannelStatsResponse, TimelineResponse, DashboardSummary,
)
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await AnalyticsService.get_dashboard_summary(db)


@router.get("/pipeline", response_model=PipelineResponse)
async def pipeline_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await AnalyticsService.get_pipeline(db)


@router.get("/channels", response_model=ChannelStatsResponse)
async def channel_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await AnalyticsService.get_channel_stats(db)


@router.get("/timeline", response_model=TimelineResponse)
async def timeline(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await AnalyticsService.get_timeline(db, days)


@router.get("/export/excel")
async def export_excel(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await AnalyticsService.export_to_excel(db)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=leads_report.xlsx"},
    )


@router.get("/export/pdf")
async def export_pdf(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await AnalyticsService.export_to_pdf(db)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=leads_report.pdf"},
    )
