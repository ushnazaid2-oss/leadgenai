"""
Leads API — CRUD endpoints for lead management and CSV import.
All endpoints require authentication.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.lead import (
    LeadCreate, LeadUpdate, LeadResponse, LeadListResponse, CSVImportResponse
)
from app.crud.leads import (
    create_lead, get_lead_by_id, get_lead_by_email,
    get_leads, update_lead, delete_lead,
)
from app.services.csv_importer import CSVImporter
from app.middleware.rate_limiter import limiter

router = APIRouter(prefix="/api/leads", tags=["Leads"])


@router.get("/niches", response_model=list[str])
async def list_unique_niches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a list of all unique niches across all leads."""
    from sqlalchemy import select
    from app.models.lead import Lead
    query = select(Lead.niche).distinct().where(Lead.niche != None)
    result = await db.execute(query)
    return [n for n in result.scalars().all() if n]


@router.post("/", response_model=LeadResponse, status_code=201)
async def create_new_lead(
    data: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new lead manually."""
    # Check duplicate email
    existing = await get_lead_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lead with email {data.email} already exists",
        )

    lead = await create_lead(
        db=db,
        name=data.name,
        email=data.email,
        company=data.company,
        phone=data.phone,
        niche=data.niche,
        notes=data.notes,
    )
    return lead


@router.get("/", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    niche: Optional[str] = None,
    is_hot_lead: Optional[bool] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List leads with pagination, filtering, and search."""
    leads, total = await get_leads(
        db, page=page, per_page=per_page,
        status=status, niche=niche,
        is_hot_lead=is_hot_lead, search=search,
    )
    return LeadListResponse(
        total=total, page=page, per_page=per_page, leads=leads
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_single_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single lead by ID."""
    lead = await get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_existing_lead(
    lead_id: int,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a lead's information."""
    update_data = data.model_dump(exclude_unset=True)
    lead = await update_lead(db, lead_id, **update_data)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.delete("/{lead_id}", status_code=204)
async def delete_existing_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a lead."""
    success = await delete_lead(db, lead_id)
    if not success:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.commit()


@router.post("/import/csv", response_model=CSVImportResponse)
async def import_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import leads from a CSV file."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400, detail="Only CSV files are accepted"
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    importer = CSVImporter(db)
    report = await importer.import_csv(content, file.filename)
    return CSVImportResponse(**report)
