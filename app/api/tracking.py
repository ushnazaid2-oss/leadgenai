"""
Tracking API — handles email open pixel and click redirect endpoints.
These are PUBLIC (no auth) since they're called by email clients.
"""

import base64
from fastapi import APIRouter, Depends
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import urllib.parse

from app.database import get_db
from app.services.tracking import TrackingService

router = APIRouter(prefix="/api/track", tags=["Tracking"])

# 1x1 transparent GIF bytes
TRANSPARENT_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


@router.get("/open/{tracking_id}")
async def track_open(tracking_id: str, db: AsyncSession = Depends(get_db)):
    """
    Email open tracking pixel.
    Returns a 1x1 transparent GIF and records the open event.
    Called automatically when an email is opened and images are loaded.
    """
    await TrackingService.record_open(db, tracking_id)
    return Response(
        content=TRANSPARENT_GIF,
        media_type="image/gif",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/click/{tracking_id}/{encoded_url:path}")
async def track_click(
    tracking_id: str,
    encoded_url: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Email click tracking redirect.
    Logs the click event then redirects to the original URL.
    """
    try:
        original_url = urllib.parse.unquote(encoded_url)
    except Exception:
        original_url = encoded_url

    await TrackingService.record_click(db, tracking_id, original_url)
    return RedirectResponse(url=original_url, status_code=302)
