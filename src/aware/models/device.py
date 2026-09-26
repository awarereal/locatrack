"""
Device model.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aware.models.base import GUID, Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from aware.models.location import Location
    from aware.models.user import User


class Device(Base, TimestampMixin):
    """Registered device that can send location updates."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_token: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="devices")
    locations: Mapped[List["Location"]] = relationship(
        "Location", back_populates="device", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Device {self.name}>"
