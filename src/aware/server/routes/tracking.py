"""
Tracking link routes.

Generate links that capture location when opened.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aware.db.engine import get_db
from aware.models import TrackingLink, User
from aware.server.auth import get_current_user

router = APIRouter()


class TrackingLinkCreate(BaseModel):
    """Create tracking link request."""

    label: Optional[str] = Field(None, max_length=100)
    expires_hours: Optional[int] = Field(None, ge=1, le=720)  # Max 30 days
    single_use: bool = True


class TrackingLinkResponse(BaseModel):
    """Tracking link response."""

    id: str
    code: str
    url: str
    label: Optional[str]
    single_use: bool
    expires_at: Optional[datetime]
    is_active: bool
    captured_at: Optional[datetime]
    latitude: Optional[float]
    longitude: Optional[float]
    accuracy_meters: Optional[float]
    ip_address: Optional[str]
    created_at: datetime


class LocationCapture(BaseModel):
    """Location capture from browser."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0)


@router.post("", response_model=TrackingLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_tracking_link(
    data: TrackingLinkCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new tracking link."""

    expires_at = None
    if data.expires_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=data.expires_hours)

    link = TrackingLink(
        user_id=current_user.id,
        label=data.label,
        expires_at=expires_at,
        single_use=data.single_use,
    )
    db.add(link)
    await db.flush()

    # Build URL
    base_url = str(request.base_url).rstrip("/")
    url = f"{base_url}/t/{link.code}"

    return {
        "id": str(link.id),
        "code": link.code,
        "url": url,
        "label": link.label,
        "single_use": link.single_use,
        "expires_at": link.expires_at,
        "is_active": link.is_active,
        "captured_at": link.captured_at,
        "latitude": link.latitude,
        "longitude": link.longitude,
        "accuracy_meters": link.accuracy_meters,
        "ip_address": link.ip_address,
        "created_at": link.created_at,
    }


@router.get("", response_model=List[TrackingLinkResponse])
async def list_tracking_links(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """List all tracking links for current user."""

    result = await db.execute(
        select(TrackingLink)
        .where(TrackingLink.user_id == current_user.id)
        .order_by(TrackingLink.created_at.desc())
    )
    links = result.scalars().all()

    base_url = str(request.base_url).rstrip("/")

    return [
        {
            "id": str(link.id),
            "code": link.code,
            "url": f"{base_url}/t/{link.code}",
            "label": link.label,
            "single_use": link.single_use,
            "expires_at": link.expires_at,
            "is_active": link.is_active,
            "captured_at": link.captured_at,
            "latitude": link.latitude,
            "longitude": link.longitude,
            "accuracy_meters": link.accuracy_meters,
            "ip_address": link.ip_address,
            "created_at": link.created_at,
        }
        for link in links
    ]


@router.delete("/{code}")
async def delete_tracking_link(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a tracking link."""

    result = await db.execute(
        select(TrackingLink).where(
            TrackingLink.code == code,
            TrackingLink.user_id == current_user.id,
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracking link not found",
        )

    await db.delete(link)

    return {"detail": "Tracking link deleted"}


# Public endpoint - the tracking page
@router.get("/page/{code}", response_class=HTMLResponse)
async def tracking_page(
    code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """
    Serve the tracking page that captures location.

    This is what the user's friend sees when they open the link.
    """

    result = await db.execute(
        select(TrackingLink).where(TrackingLink.code == code)
    )
    link = result.scalar_one_or_none()

    if not link:
        return HTMLResponse(
            content="<html><body><h1>Link not found</h1></body></html>",
            status_code=404,
        )

    if not link.is_valid:
        return HTMLResponse(
            content="<html><body><h1>This link has expired</h1></body></html>",
            status_code=410,
        )

    # Serve the location capture page - clean minimal design
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Continue</title>
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:-apple-system,system-ui,sans-serif;background:#000;color:#fff;min-height:100vh;display:flex;align-items:center;justify-content:center}}
        .c{{max-width:320px;width:100%;padding:24px;text-align:center}}
        h1{{font-size:20px;font-weight:500;margin-bottom:12px}}
        p{{font-size:14px;color:#888;margin-bottom:32px}}
        button{{background:#fff;color:#000;border:none;padding:14px 28px;border-radius:99px;font-size:15px;font-weight:500;cursor:pointer;width:100%}}
        button:active{{transform:scale(0.98)}}
        button:disabled{{opacity:0.4;cursor:default;transform:none}}
        .s{{margin-top:24px;font-size:13px}}
        .ok{{color:#34c759}}
        .er{{color:#ff453a}}
        .ld{{color:#888}}
    </style>
</head>
<body>
    <div class="c">
        <h1>Allow location access</h1>
        <p>Tap continue to proceed</p>
        <button id="b" onclick="go()">Continue</button>
        <div class="s" id="s"></div>
    </div>
<script>
const c="{code}",s=document.getElementById('s'),b=document.getElementById('b');
function go(){{b.disabled=1;b.textContent='Loading...';s.className='s ld';s.textContent='';
if(!navigator.geolocation){{s.className='s er';s.textContent='Not supported';b.disabled=0;b.textContent='Continue';return}}
navigator.geolocation.getCurrentPosition(ok,er,{{enableHighAccuracy:1,timeout:30000,maximumAge:0}})}}
function ok(p){{fetch('/track/capture/'+c,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy:p.coords.accuracy}})}}).then(r=>r.json()).then(r=>{{if(r.success){{s.className='s ok';s.textContent='Done';b.textContent='✓'}}else{{s.className='s er';s.textContent='Failed';b.disabled=0;b.textContent='Retry'}}}}).catch(e=>{{s.className='s er';s.textContent='Error';b.disabled=0;b.textContent='Retry'}})}}
function er(e){{s.className='s er';s.textContent=e.code==1?'Denied':'Failed';b.disabled=0;b.textContent='Retry'}}
</script>
</body>
</html>'''

    return HTMLResponse(content=html)


# Public endpoint - receive the captured location
@router.post("/capture/{code}")
async def capture_location(
    code: str,
    data: LocationCapture,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive and store the captured location."""

    result = await db.execute(
        select(TrackingLink).where(TrackingLink.code == code)
    )
    link = result.scalar_one_or_none()

    if not link:
        return {"success": False, "detail": "Link not found"}

    if not link.is_valid:
        return {"success": False, "detail": "Link expired or already used"}

    # Get client info
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")

    # Store the captured location
    link.captured_at = datetime.now(timezone.utc)
    link.latitude = data.latitude
    link.longitude = data.longitude
    link.accuracy_meters = data.accuracy
    link.ip_address = client_ip
    link.user_agent = user_agent

    # If single use, deactivate
    if link.single_use:
        link.is_active = False

    return {"success": True, "message": "Location captured"}
