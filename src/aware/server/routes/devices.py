"""
Device routes.
"""

import secrets
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aware.db.engine import get_db
from aware.models import Device, Location, User
from aware.server.auth import get_current_user

router = APIRouter()


class DeviceCreate(BaseModel):
    """Device registration request."""

    name: str = Field(..., min_length=1, max_length=100)


class DeviceResponse(BaseModel):
    """Device response."""

    id: str
    name: str
    device_token: str
    last_seen_at: Optional[datetime]
    created_at: datetime
    last_location: Optional[dict] = None

    class Config:
        from_attributes = True


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    data: DeviceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a new device."""
    # Generate device token
    device_token = secrets.token_urlsafe(32)

    device = Device(
        user_id=current_user.id,
        name=data.name,
        device_token=device_token,
    )
    db.add(device)
    await db.flush()

    return {
        "id": str(device.id),
        "name": device.name,
        "device_token": device.device_token,
        "last_seen_at": device.last_seen_at,
        "created_at": device.created_at,
        "last_location": None,
    }


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """List all devices for the current user."""
    result = await db.execute(
        select(Device)
        .where(Device.user_id == current_user.id)
        .order_by(Device.created_at.desc())
    )
    devices = result.scalars().all()

    response = []
    for device in devices:
        # Get last location
        loc_result = await db.execute(
            select(Location)
            .where(Location.device_id == device.id)
            .order_by(Location.recorded_at.desc())
            .limit(1)
        )
        last_loc = loc_result.scalar_one_or_none()

        last_location = None
        if last_loc:
            last_location = {
                "latitude": last_loc.latitude,
                "longitude": last_loc.longitude,
                "city": last_loc.extra_data.get("city") if last_loc.extra_data else None,
                "country": last_loc.extra_data.get("country") if last_loc.extra_data else None,
                "recorded_at": last_loc.recorded_at.isoformat(),
            }

        response.append({
            "id": str(device.id),
            "name": device.name,
            "device_token": device.device_token,
            "last_seen_at": device.last_seen_at,
            "created_at": device.created_at,
            "last_location": last_location,
        })

    return response


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a specific device."""
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.user_id == current_user.id,
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Get last location
    loc_result = await db.execute(
        select(Location)
        .where(Location.device_id == device.id)
        .order_by(Location.recorded_at.desc())
        .limit(1)
    )
    last_loc = loc_result.scalar_one_or_none()

    last_location = None
    if last_loc:
        last_location = {
            "latitude": last_loc.latitude,
            "longitude": last_loc.longitude,
            "city": last_loc.extra_data.get("city") if last_loc.extra_data else None,
            "country": last_loc.extra_data.get("country") if last_loc.extra_data else None,
            "recorded_at": last_loc.recorded_at.isoformat(),
        }

    return {
        "id": str(device.id),
        "name": device.name,
        "device_token": device.device_token,
        "last_seen_at": device.last_seen_at,
        "created_at": device.created_at,
        "last_location": last_location,
    }


@router.delete("/{device_id}", status_code=status.HTTP_200_OK)
async def delete_device(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a device."""
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.user_id == current_user.id,
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    await db.delete(device)

    return {"detail": "Device deleted"}
