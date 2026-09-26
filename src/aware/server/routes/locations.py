"""
Location routes.
"""

import secrets
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aware.config import settings
from aware.db.engine import get_db
from aware.models import CircleMember, Device, Location, User
from aware.server.auth import get_current_user

router = APIRouter()


class LocationCreate(BaseModel):
    """Location submission request."""

    device_name: str = Field(..., min_length=1, max_length=100)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: Optional[float] = Field(None, ge=0)
    source: str = Field(default="unknown", max_length=20)
    metadata: Optional[dict[str, Any]] = None


class LocationResponse(BaseModel):
    """Location response."""

    id: str
    latitude: float
    longitude: float
    accuracy_meters: Optional[float]
    source: str
    metadata: Optional[dict]
    recorded_at: datetime
    device: Optional[dict] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_location(
    data: LocationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit a location update."""
    # Find or create device by name
    result = await db.execute(
        select(Device).where(
            Device.user_id == current_user.id,
            Device.name == data.device_name,
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        # Auto-create device
        device = Device(
            user_id=current_user.id,
            name=data.device_name,
            device_token=secrets.token_urlsafe(32),
        )
        db.add(device)
        await db.flush()

    # Update device last seen
    device.last_seen_at = datetime.now(timezone.utc)

    # Create location record
    location = Location(
        device_id=device.id,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy_meters=data.accuracy_meters,
        source=data.source,
        extra_data=data.metadata,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(location)

    return {"detail": "Location recorded", "id": str(location.id)}


@router.get("/me", response_model=List[LocationResponse])
async def get_my_locations(
    limit: int = Query(50, ge=1, le=1000),
    device: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get location history for current user."""
    # Get user's devices
    device_query = select(Device.id).where(Device.user_id == current_user.id)
    if device:
        device_query = device_query.where(Device.name == device)

    result = await db.execute(device_query)
    device_ids = [row[0] for row in result.all()]

    if not device_ids:
        return []

    # Get locations
    result = await db.execute(
        select(Location)
        .options(selectinload(Location.device))
        .where(Location.device_id.in_(device_ids))
        .order_by(Location.recorded_at.desc())
        .limit(limit)
    )
    locations = result.scalars().all()

    return [
        {
            "id": str(loc.id),
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "accuracy_meters": loc.accuracy_meters,
            "source": loc.source,
            "metadata": loc.extra_data,
            "recorded_at": loc.recorded_at,
            "device": {
                "id": str(loc.device.id),
                "name": loc.device.name,
            } if loc.device else None,
        }
        for loc in locations
    ]


@router.get("/live")
async def get_live_locations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get current locations of users sharing with you."""
    # Get circles the user is in
    result = await db.execute(
        select(CircleMember.circle_id).where(
            CircleMember.user_id == current_user.id
        )
    )
    circle_ids = [row[0] for row in result.all()]

    if not circle_ids:
        return []

    # Get all members of those circles who are sharing
    result = await db.execute(
        select(CircleMember)
        .options(selectinload(CircleMember.user))
        .where(
            CircleMember.circle_id.in_(circle_ids),
            CircleMember.is_sharing == True,
            CircleMember.user_id != current_user.id,  # Exclude self
        )
    )
    members = result.scalars().all()

    # Get unique user IDs
    user_ids = list(set(m.user_id for m in members))

    if not user_ids:
        return []

    # Get devices for each user
    result = await db.execute(
        select(Device).where(Device.user_id.in_(user_ids))
    )
    devices = result.scalars().all()

    # Get latest location for each device
    locations = []
    for device in devices:
        loc_result = await db.execute(
            select(Location)
            .where(Location.device_id == device.id)
            .order_by(Location.recorded_at.desc())
            .limit(1)
        )
        loc = loc_result.scalar_one_or_none()

        if loc:
            # Get user info
            user_result = await db.execute(
                select(User).where(User.id == device.user_id)
            )
            user = user_result.scalar_one_or_none()

            locations.append({
                "user": {
                    "id": str(user.id) if user else None,
                    "username": user.username if user else "Unknown",
                },
                "device": {
                    "id": str(device.id),
                    "name": device.name,
                },
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "accuracy_meters": loc.accuracy_meters,
                "city": loc.extra_data.get("city") if loc.extra_data else None,
                "country": loc.extra_data.get("country") if loc.extra_data else None,
                "recorded_at": loc.recorded_at.isoformat(),
            })

    return locations


@router.get("/shared")
async def get_shared_locations(
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get location history from users sharing with you."""
    # Similar to live but with history
    result = await db.execute(
        select(CircleMember.circle_id).where(
            CircleMember.user_id == current_user.id
        )
    )
    circle_ids = [row[0] for row in result.all()]

    if not circle_ids:
        return []

    # Get sharing members
    result = await db.execute(
        select(CircleMember.user_id).where(
            CircleMember.circle_id.in_(circle_ids),
            CircleMember.is_sharing == True,
            CircleMember.user_id != current_user.id,
        )
    )
    user_ids = list(set(row[0] for row in result.all()))

    if not user_ids:
        return []

    # Get devices
    result = await db.execute(
        select(Device.id).where(Device.user_id.in_(user_ids))
    )
    device_ids = [row[0] for row in result.all()]

    if not device_ids:
        return []

    # Get locations
    result = await db.execute(
        select(Location)
        .options(selectinload(Location.device))
        .where(Location.device_id.in_(device_ids))
        .order_by(Location.recorded_at.desc())
        .limit(limit)
    )
    locations = result.scalars().all()

    return [
        {
            "id": str(loc.id),
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "accuracy_meters": loc.accuracy_meters,
            "source": loc.source,
            "city": loc.extra_data.get("city") if loc.extra_data else None,
            "country": loc.extra_data.get("country") if loc.extra_data else None,
            "recorded_at": loc.recorded_at.isoformat(),
            "device": {
                "id": str(loc.device.id),
                "name": loc.device.name,
            } if loc.device else None,
        }
        for loc in locations
    ]
