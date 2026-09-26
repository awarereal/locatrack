"""
Sharing circle models.
"""

import secrets
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aware.models.base import GUID, Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from aware.models.user import User


def generate_invite_code() -> str:
    """Generate a random invite code."""
    return secrets.token_urlsafe(8).upper()[:12]


class Circle(Base, TimestampMixin):
    """Sharing circle - a group of users who share locations with each other."""

    __tablename__ = "circles"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="owned_circles")
    members: Mapped[List["CircleMember"]] = relationship(
        "CircleMember", back_populates="circle", cascade="all, delete-orphan"
    )
    invitations: Mapped[List["Invitation"]] = relationship(
        "Invitation", back_populates="circle", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Circle {self.name}>"


class CircleMember(Base, TimestampMixin):
    """Membership in a circle."""

    __tablename__ = "circle_members"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=generate_uuid
    )
    circle_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("circles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_sharing: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    circle: Mapped["Circle"] = relationship("Circle", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="circle_memberships")

    def __repr__(self) -> str:
        return f"<CircleMember circle={self.circle_id} user={self.user_id}>"


class Invitation(Base, TimestampMixin):
    """Invitation to join a circle."""

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=generate_uuid
    )
    circle_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("circles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True, default=generate_invite_code
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    circle: Mapped["Circle"] = relationship("Circle", back_populates="invitations")

    def __repr__(self) -> str:
        return f"<Invitation {self.code}>"

    @property
    def is_valid(self) -> bool:
        """Check if invitation is still valid."""
        from datetime import timezone

        now = datetime.now(timezone.utc)
        return (
            not self.is_expired
            and self.use_count < self.max_uses
        )

    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        from datetime import timezone

        now = datetime.now(timezone.utc)
        # Handle naive datetime
        expires = self.expires_at
        if expires.tzinfo is None:
            from datetime import timezone as tz
            expires = expires.replace(tzinfo=tz.utc)
        return now > expires
