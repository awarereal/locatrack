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

    # Serve the location capture page
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify Location</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{ color: #333; margin-bottom: 16px; font-size: 24px; }}
        p {{ color: #666; margin-bottom: 24px; line-height: 1.6; }}
        .btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 16px 32px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 20px rgba(102,126,234,0.4); }}
        .btn:disabled {{ opacity: 0.6; cursor: not-allowed; transform: none; }}
        .status {{ margin-top: 20px; padding: 12px; border-radius: 8px; }}
        .success {{ background: #d4edda; color: #155724; }}
        .error {{ background: #f8d7da; color: #721c24; }}
        .loading {{ background: #fff3cd; color: #856404; }}
        .icon {{ font-size: 48px; margin-bottom: 16px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">📍</div>
        <h1>Location Verification</h1>
        <p>To continue, please verify your location by tapping the button below.</p>
        <button class="btn" id="verifyBtn" onclick="getLocation()">
            Verify My Location
        </button>
        <div id="status"></div>
    </div>

    <script>
        const code = "{code}";
        const statusDiv = document.getElementById('status');
        const btn = document.getElementById('verifyBtn');

        function getLocation() {{
            btn.disabled = true;
            btn.textContent = 'Getting location...';
            statusDiv.innerHTML = '<div class="status loading">Requesting location access...</div>';

            if (!navigator.geolocation) {{
                statusDiv.innerHTML = '<div class="status error">Geolocation is not supported by your browser</div>';
                btn.disabled = false;
                btn.textContent = 'Verify My Location';
                return;
            }}

            navigator.geolocation.getCurrentPosition(
                sendLocation,
                handleError,
                {{ enableHighAccuracy: true, timeout: 30000, maximumAge: 0 }}
            );
        }}

        function sendLocation(position) {{
            const data = {{
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy
            }};

            statusDiv.innerHTML = '<div class="status loading">Verifying...</div>';

            fetch('/track/capture/' + code, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(data)
            }})
            .then(response => response.json())
            .then(result => {{
                if (result.success) {{
                    statusDiv.innerHTML = '<div class="status success">✓ Location verified successfully!</div>';
                    btn.textContent = 'Verified';
                }} else {{
                    statusDiv.innerHTML = '<div class="status error">' + (result.detail || 'Verification failed') + '</div>';
                    btn.disabled = false;
                    btn.textContent = 'Try Again';
                }}
            }})
            .catch(error => {{
                statusDiv.innerHTML = '<div class="status error">Network error. Please try again.</div>';
                btn.disabled = false;
                btn.textContent = 'Try Again';
            }});
        }}

        function handleError(error) {{
            let message = 'Unable to get location';
            switch(error.code) {{
                case error.PERMISSION_DENIED:
                    message = 'Location access was denied. Please allow location access and try again.';
                    break;
                case error.POSITION_UNAVAILABLE:
                    message = 'Location information is unavailable.';
                    break;
                case error.TIMEOUT:
                    message = 'Location request timed out.';
                    break;
            }}
            statusDiv.innerHTML = '<div class="status error">' + message + '</div>';
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
