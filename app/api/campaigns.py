"""
Campaigns API — CRUD endpoints for campaign management.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse
from app.crud.campaigns import create_campaign, get_campaigns, get_campaign_by_id, update_campaign

router = APIRouter(prefix="/api/campaigns", tags=["Campaigns"])


@router.post("/", response_model=CampaignResponse, status_code=201)
async def create_new_campaign(
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = await create_campaign(
        db, data.name, data.type, data.template_name, data.subject, data.body, data.niche_filter,
    )
    return campaign


@router.post("/{campaign_id}/start")
async def start_campaign_task(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from app.models.campaign import Campaign, CampaignType
    from app.models.lead import Lead
    from app.tasks.email_tasks import send_bulk_emails
    from app.tasks.whatsapp_tasks import send_whatsapp_broadcast
    from app.tasks.call_tasks import run_call_campaign

    # 1. Fetch Campaign
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # 2. Fetch Targeted Leads
    query = select(Lead.id)
    if campaign.niche_filter:
        niches = [n.strip() for n in campaign.niche_filter.split(',') if n.strip()]
        if niches:
            query = query.where(Lead.niche.in_(niches))
    
    lead_ids = (await db.execute(query)).scalars().all()
    if not lead_ids:
        raise HTTPException(status_code=400, detail="No leads found for this campaign filter")

    # 3. Update Campaign status
    campaign.status = "active"
    await db.flush()

    # 4. Trigger Worker Task
    if campaign.type == CampaignType.EMAIL:
        task = send_bulk_emails.delay(campaign.id, list(lead_ids))
    elif campaign.type == CampaignType.WHATSAPP:
        # Use campaign body as template name for WA if template_name is null
        tpl = campaign.template_name or campaign.body or "business_intro"
        task = send_whatsapp_broadcast.delay(campaign.id, list(lead_ids), tpl)
    elif campaign.type == CampaignType.CALL:
        task = run_call_campaign.delay(campaign.id, list(lead_ids), call_script=campaign.body)
    
    campaign.celery_task_id = task.id
    return {"message": "Campaign started", "task_id": task.id, "leads_targeted": len(lead_ids)}


@router.get("/", response_model=list[CampaignResponse])
async def list_campaigns(
    type: Optional[str] = None, status: Optional[str] = None,
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaigns, _ = await get_campaigns(db, type, status, page, per_page)
    return campaigns


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_single_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_existing_campaign(
    campaign_id: int, data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_data = data.model_dump(exclude_unset=True)
    campaign = await update_campaign(db, campaign_id, **update_data)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.delete("/{campaign_id}", status_code=204)
async def delete_existing_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a campaign."""
    from app.crud.campaigns import delete_campaign
    success = await delete_campaign(db, campaign_id)
    if not success:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await db.commit()
