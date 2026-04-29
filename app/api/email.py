"""
Email API + Tracking endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.email import (
    EmailSend, EmailCampaignLaunch, EmailAccountCreate,
    EmailAccountResponse, EmailLogResponse, EmailStatsResponse,
    EmailAccountUpdate,
)
from app.schemas.campaign import TaskStatusResponse
from app.crud.emails import (
    create_email_account, get_email_accounts, get_email_logs, get_email_stats,
)
from app.crud.leads import get_lead_by_id, get_lead_ids_by_filter
from app.services.email_engine import EmailEngine
from app.tasks.email_tasks import send_bulk_emails
from app.config import settings

router = APIRouter(prefix="/api/email", tags=["Email"])


@router.post("/send")
async def send_single_email(
    data: EmailSend,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a single email to a lead."""
    if not settings.FEATURE_EMAIL_ENABLED:
        raise HTTPException(status_code=403, detail="Email module is disabled")

    lead = await get_lead_by_id(db, data.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    account = await EmailEngine.get_available_account(db, data.sender_account_id)
    if not account:
        raise HTTPException(status_code=400, detail="No available email account found. Please connect an account first.")

    personalization = data.personalization or {
        "name": lead.name, "company": lead.company or "",
    }

    email_log = await EmailEngine.send_email(
        db, account, lead.id, lead.email, data.subject,
        data.body_html, personalization=personalization,
    )
    return {"status": email_log.status.value, "tracking_id": email_log.tracking_id}


@router.post("/campaign")
async def launch_email_campaign(
    data: EmailCampaignLaunch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Launch a bulk email campaign via Celery."""
    if not settings.FEATURE_EMAIL_ENABLED:
        raise HTTPException(status_code=403, detail="Email module is disabled")

    lead_ids = await get_lead_ids_by_filter(db, data.lead_ids, data.filters)
    if not lead_ids:
        raise HTTPException(status_code=400, detail="No leads match the criteria")

    task = send_bulk_emails.delay(data.campaign_id, lead_ids, data.sender_account_id)
    return {"task_id": task.id, "lead_count": len(lead_ids), "status": "queued"}


@router.get("/accounts", response_model=list[EmailAccountResponse])
async def list_email_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all sender email accounts."""
    return await get_email_accounts(db)


@router.post("/accounts", response_model=EmailAccountResponse, status_code=201)
async def add_email_account(
    data: EmailAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new sender email account."""
    account = await create_email_account(
        db, data.name, data.email, data.provider,
        data.smtp_host, data.smtp_port, data.username,
        data.password, data.sendgrid_api_key,
        data.daily_limit, data.hourly_limit,
    )
    return account


@router.put("/accounts/{account_id}", response_model=EmailAccountResponse)
async def update_email_account_endpoint(
    account_id: int,
    data: EmailAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an email account (e.g. name)."""
    from app.models.email_account import EmailAccount
    from sqlalchemy import select
    result = await db.execute(select(EmailAccount).where(EmailAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if hasattr(account, k):
            setattr(account, k, v)
    
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_email_account_endpoint(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an email account."""
    from app.models.email_account import EmailAccount
    from sqlalchemy import select
    result = await db.execute(select(EmailAccount).where(EmailAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    await db.delete(account)
    await db.commit()
    return {"message": "Account deleted"}


@router.get("/logs", response_model=list[EmailLogResponse])
async def list_email_logs(
    campaign_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get email activity logs."""
    logs, total = await get_email_logs(db, campaign_id, lead_id, status, page, per_page)
    return logs


@router.get("/stats", response_model=EmailStatsResponse)
async def email_statistics(
    campaign_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get email performance statistics."""
    return await get_email_stats(db, campaign_id)


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Check Celery task status for a campaign."""
    from app.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    return TaskStatusResponse(
        task_id=task_id,
        status=result.state,
        progress=result.info.get("sent") if isinstance(result.info, dict) else None,
        total=result.info.get("total") if isinstance(result.info, dict) else None,
        result=result.info if result.state == "SUCCESS" else None,
    )
