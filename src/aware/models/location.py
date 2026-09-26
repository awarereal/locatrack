"""
Location model.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from aware.models.base import GUID, Base, generate_uuid

if TYPE_CHECKING:
    from aware.models.device import Device


class Location(Base):
    """Location record from a device."""

    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=generate_uuid
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Coordinates
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Source of location (ip, gps, manual)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")

    # Additional data (city, country, etc.)
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Timestamp
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="locations")

    def __repr__(self) -> str:
        return f"<Location {self.latitude}, {self.longitude}>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "device_id": str(self.device_id),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy_meters": self.accuracy_meters,
            "source": self.source,
            "extra_data": self.extra_data,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }
