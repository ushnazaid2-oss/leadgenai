"""
Lead CRUD operations — database access layer for leads.
"""

from typing import Optional, List, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.activity import Activity, ActivityChannel


async def create_lead(
    db: AsyncSession,
    name: str,
    email: str,
    company: Optional[str] = None,
    phone: Optional[str] = None,
    niche: Optional[str] = None,
    source: LeadSource = LeadSource.MANUAL,
    notes: Optional[str] = None,
) -> Lead:
    """Create a new lead."""
    lead = Lead(
        name=name,
        email=email,
        company=company,
        phone=phone,
        niche=niche,
        source=source,
        notes=notes,
    )
    db.add(lead)
    await db.flush()
    await db.refresh(lead)

    # Log activity
    activity = Activity(
        lead_id=lead.id,
        channel=ActivityChannel.SYSTEM,
        action="lead_created",
        description=f"Lead created via {source.value}",
    )
    db.add(activity)
    return lead


async def get_lead_by_id(db: AsyncSession, lead_id: int) -> Optional[Lead]:
    """Get a single lead by ID."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    return result.scalar_one_or_none()


async def get_lead_by_email(db: AsyncSession, email: str) -> Optional[Lead]:
    """Get a lead by email address."""
    result = await db.execute(select(Lead).where(Lead.email == email))
    return result.scalar_one_or_none()


async def get_leads(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    niche: Optional[str] = None,
    is_hot_lead: Optional[bool] = None,
    search: Optional[str] = None,
) -> Tuple[List[Lead], int]:
    """Get paginated leads with optional filtering."""
    query = select(Lead)
    count_query = select(func.count(Lead.id))

    # Apply filters
    if status:
        query = query.where(Lead.status == status)
        count_query = count_query.where(Lead.status == status)
    if niche:
        query = query.where(Lead.niche == niche)
        count_query = count_query.where(Lead.niche == niche)
    if is_hot_lead is not None:
        query = query.where(Lead.is_hot_lead == is_hot_lead)
        count_query = count_query.where(Lead.is_hot_lead == is_hot_lead)
    if search:
        search_filter = or_(
            Lead.name.ilike(f"%{search}%"),
            Lead.company.ilike(f"%{search}%"),
            Lead.email.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(Lead.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    leads = result.scalars().all()

    return leads, total


async def update_lead(
    db: AsyncSession, lead_id: int, **kwargs
) -> Optional[Lead]:
    """Update lead fields."""
    lead = await get_lead_by_id(db, lead_id)
    if lead is None:
        return None

    for key, value in kwargs.items():
        if value is not None and hasattr(lead, key):
            setattr(lead, key, value)

    await db.flush()
    await db.refresh(lead)
    return lead


async def delete_lead(db: AsyncSession, lead_id: int) -> bool:
    """Delete a lead by ID."""
    lead = await get_lead_by_id(db, lead_id)
    if lead is None:
        return False
    await db.delete(lead)
    return True


async def get_lead_ids_by_filter(
    db: AsyncSession,
    lead_ids: Optional[List[int]] = None,
    filters: Optional[dict] = None,
) -> List[int]:
    """Get lead IDs matching criteria — used by campaign launchers."""
    query = select(Lead.id)

    if lead_ids:
        query = query.where(Lead.id.in_(lead_ids))

    if filters:
        if "niche" in filters:
            query = query.where(Lead.niche == filters["niche"])
        if "status" in filters:
            query = query.where(Lead.status == filters["status"])
        if "is_hot_lead" in filters:
            query = query.where(Lead.is_hot_lead == filters["is_hot_lead"])

    result = await db.execute(query)
    return [row[0] for row in result.all()]
