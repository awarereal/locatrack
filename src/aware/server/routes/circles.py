"""
Sharing circle routes.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aware.db.engine import get_db
from aware.models import Circle, CircleMember, Device, Invitation, Location, User
from aware.server.auth import get_current_user

router = APIRouter()


class CircleCreate(BaseModel):
    """Circle creation request."""

    name: str = Field(..., min_length=1, max_length=100)


class CircleResponse(BaseModel):
    """Circle response."""

    id: str
    name: str
    is_owner: bool
    is_sharing: bool
    member_count: int
    created_at: datetime


class InviteCreate(BaseModel):
    """Invite creation request."""

    expires_hours: int = Field(default=24, ge=1, le=720)  # Max 30 days
    max_uses: int = Field(default=1, ge=1, le=100)


class InviteResponse(BaseModel):
    """Invite response."""

    code: str
    expires_at: datetime
    max_uses: int
    use_count: int


class JoinRequest(BaseModel):
    """Join circle request."""

    code: str


class SharingUpdate(BaseModel):
    """Sharing status update."""

    is_sharing: bool


class MemberResponse(BaseModel):
    """Circle member response."""

    username: str
    is_owner: bool
    is_sharing: bool
    last_location: Optional[dict] = None


@router.post("", response_model=CircleResponse, status_code=status.HTTP_201_CREATED)
async def create_circle(
    data: CircleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new sharing circle."""
    # Check for duplicate name
    result = await db.execute(
        select(Circle).where(
            Circle.owner_id == current_user.id,
            Circle.name == data.name,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A circle with this name already exists",
        )

    # Create circle
    circle = Circle(
        name=data.name,
        owner_id=current_user.id,
    )
    db.add(circle)
    await db.flush()

    # Add owner as member
    member = CircleMember(
        circle_id=circle.id,
        user_id=current_user.id,
        is_sharing=True,
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)

    return {
        "id": str(circle.id),
        "name": circle.name,
        "is_owner": True,
        "is_sharing": True,
        "member_count": 1,
        "created_at": circle.created_at,
    }


@router.get("", response_model=List[CircleResponse])
async def list_circles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """List circles the user is a member of."""
    result = await db.execute(
        select(CircleMember)
        .options(selectinload(CircleMember.circle))
        .where(CircleMember.user_id == current_user.id)
    )
    memberships = result.scalars().all()

    circles = []
    for membership in memberships:
        circle = membership.circle

        # Count members
        count_result = await db.execute(
            select(func.count(CircleMember.id)).where(
                CircleMember.circle_id == circle.id
            )
        )
        member_count = count_result.scalar() or 0

        circles.append({
            "id": str(circle.id),
            "name": circle.name,
            "is_owner": circle.owner_id == current_user.id,
            "is_sharing": membership.is_sharing,
            "member_count": member_count,
            "created_at": circle.created_at,
        })

    return circles


@router.post("/{circle_name}/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    circle_name: str,
    data: InviteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create an invite for a circle."""
    # Find circle by name where user is owner
    result = await db.execute(
        select(Circle).where(
            Circle.name == circle_name,
            Circle.owner_id == current_user.id,
        )
    )
    circle = result.scalar_one_or_none()

    if not circle:
        # Check if user is member (can still invite in some implementations)
        result = await db.execute(
            select(Circle)
            .join(CircleMember)
            .where(
                Circle.name == circle_name,
                CircleMember.user_id == current_user.id,
            )
        )
        circle = result.scalar_one_or_none()

        if not circle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Circle not found",
            )

        if circle.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the circle owner can create invites",
            )

    # Create invitation
    expires_at = datetime.now(timezone.utc) + timedelta(hours=data.expires_hours)
    invitation = Invitation(
        circle_id=circle.id,
        created_by_id=current_user.id,
        expires_at=expires_at,
        max_uses=data.max_uses,
    )
    db.add(invitation)
    await db.flush()

    return {
        "code": invitation.code,
        "expires_at": invitation.expires_at,
        "max_uses": invitation.max_uses,
        "use_count": invitation.use_count,
    }


@router.post("/join")
async def join_circle(
    data: JoinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Join a circle using an invite code."""
    # Find invitation
    result = await db.execute(
        select(Invitation)
        .options(selectinload(Invitation.circle))
        .where(Invitation.code == data.code)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code",
        )

    if not invitation.is_valid:
        if invitation.is_expired:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite code has expired",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite code has reached maximum uses",
        )

    # Check if already a member
    result = await db.execute(
        select(CircleMember).where(
            CircleMember.circle_id == invitation.circle_id,
            CircleMember.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already a member of this circle",
        )

    # Add as member
    member = CircleMember(
        circle_id=invitation.circle_id,
        user_id=current_user.id,
        is_sharing=True,
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)

    # Increment use count
    invitation.use_count += 1

    return {
        "detail": "Joined circle successfully",
        "circle": {
            "id": str(invitation.circle.id),
            "name": invitation.circle.name,
        },
    }


@router.delete("/{circle_name}/leave")
async def leave_circle(
    circle_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Leave a circle."""
    # Find circle
    result = await db.execute(
        select(Circle).where(Circle.name == circle_name)
    )
    circle = result.scalar_one_or_none()

    if not circle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Circle not found",
        )

    # Can't leave if owner
    if circle.owner_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner cannot leave circle. Delete it instead.",
        )

    # Find membership
    result = await db.execute(
        select(CircleMember).where(
            CircleMember.circle_id == circle.id,
            CircleMember.user_id == current_user.id,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not a member of this circle",
        )

    await db.delete(membership)

    return {"detail": "Left circle"}


@router.patch("/{circle_name}/sharing")
async def update_sharing(
    circle_name: str,
    data: SharingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update sharing status in a circle."""
    # Find circle
    result = await db.execute(
        select(Circle).where(Circle.name == circle_name)
    )
    circle = result.scalar_one_or_none()

    if not circle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Circle not found",
        )

    # Find membership
    result = await db.execute(
        select(CircleMember).where(
            CircleMember.circle_id == circle.id,
            CircleMember.user_id == current_user.id,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not a member of this circle",
        )

    membership.is_sharing = data.is_sharing

    return {
        "detail": "Sharing updated",
        "is_sharing": membership.is_sharing,
    }


@router.get("/{circle_name}/members", response_model=List[MemberResponse])
async def list_members(
    circle_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """List members of a circle."""
    # Find circle
    result = await db.execute(
        select(Circle).where(Circle.name == circle_name)
    )
    circle = result.scalar_one_or_none()

    if not circle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Circle not found",
        )

    # Check if user is member
    result = await db.execute(
        select(CircleMember).where(
            CircleMember.circle_id == circle.id,
            CircleMember.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this circle",
        )

    # Get all members
    result = await db.execute(
        select(CircleMember)
        .options(selectinload(CircleMember.user))
        .where(CircleMember.circle_id == circle.id)
    )
    members = result.scalars().all()

    response = []
    for member in members:
        # Get last location if sharing
        last_location = None
        if member.is_sharing:
            device_result = await db.execute(
                select(Device).where(Device.user_id == member.user_id).limit(1)
            )
            device = device_result.scalar_one_or_none()

            if device:
                loc_result = await db.execute(
                    select(Location)
                    .where(Location.device_id == device.id)
                    .order_by(Location.recorded_at.desc())
                    .limit(1)
                )
                loc = loc_result.scalar_one_or_none()

                if loc:
                    last_location = {
                        "city": loc.extra_data.get("city") if loc.extra_data else None,
                        "recorded_at": loc.recorded_at.isoformat(),
                    }

        response.append({
            "username": member.user.username,
            "is_owner": circle.owner_id == member.user_id,
            "is_sharing": member.is_sharing,
            "last_location": last_location,
        })

    return response


@router.delete("/{circle_name}")
async def delete_circle(
    circle_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a circle (owner only)."""
    result = await db.execute(
        select(Circle).where(
            Circle.name == circle_name,
            Circle.owner_id == current_user.id,
        )
    )
    circle = result.scalar_one_or_none()

    if not circle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Circle not found or you don't own it",
        )

    await db.delete(circle)

    return {"detail": "Circle deleted"}
