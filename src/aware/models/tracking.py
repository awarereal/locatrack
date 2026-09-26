"""
Tracking link model.
"""

import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aware.models.base import GUID, Base, TimestampMixin, generate_uuid


def generate_track_code() -> str:
    """Generate a short tracking code."""
    return secrets.token_urlsafe(8)


class TrackingLink(Base, TimestampMixin):
    """A tracking link that captures location when opened."""

    __tablename__ = "tracking_links"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Short code for URL
    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True, default=generate_track_code
    )

    # Optional label
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Link settings
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    single_use: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Captured location (filled when someone opens the link)
    captured_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Info about who opened it
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<TrackingLink {self.code}>"

    @property
    def is_captured(self) -> bool:
        """Check if location was captured."""
        return self.captured_at is not None

    @property
    def is_expired(self) -> bool:
        """Check if link has expired."""
        if not self.expires_at:
            return False
        from datetime import timezone as tz
        now = datetime.now(tz.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=tz.utc)
        return now > expires

    @property
    def is_valid(self) -> bool:
        """Check if link can still be used."""
        if not self.is_active:
            return False
        if self.is_expired:
            return False
        if self.single_use and self.is_captured:
            return False
        return True
