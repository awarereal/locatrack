"""
IP geolocation lookup.

Uses the ipwho.is API for geolocation data.
"""

import ipaddress
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from aware.config import settings


class IPLookupResult(BaseModel):
    """Result of an IP geolocation lookup."""

    ip: str
    success: bool = True
    error: Optional[str] = None

    # Location
    ip_type: Optional[str] = Field(None, alias="type")
    continent: Optional[str] = None
    continent_code: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None
    region_code: Optional[str] = None
    city: Optional[str] = None
    postal: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_eu: Optional[bool] = None
    borders: Optional[str] = None
    calling_code: Optional[str] = None
    capital: Optional[str] = None
    flag_emoji: Optional[str] = None

    # Connection
    asn: Optional[int] = None
    org: Optional[str] = None
    isp: Optional[str] = None
    domain: Optional[str] = None

    # Timezone
    timezone_id: Optional[str] = None
    timezone_abbr: Optional[str] = None
    utc_offset: Optional[str] = None
    current_time: Optional[str] = None
    is_dst: Optional[bool] = None


class MyIPResult(BaseModel):
    """Result of getting own IP address."""

    ip: Optional[str] = None
    error: Optional[str] = None


def validate_ip(ip: str) -> tuple[bool, Optional[str]]:
    """
    Validate an IP address.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        addr = ipaddress.ip_address(ip)
        # Check for private/reserved ranges
        if addr.is_private:
            return True, None  # Valid but will return "Reserved range" from API
        if addr.is_loopback:
            return False, "Loopback addresses cannot be geolocated"
        if addr.is_multicast:
            return False, "Multicast addresses cannot be geolocated"
        if addr.is_unspecified:
            return False, "Unspecified address (0.0.0.0) cannot be geolocated"
        return True, None
    except ValueError:
        return False, f"Invalid IP address format: {ip}"


async def lookup_ip(ip: str) -> IPLookupResult:
    """
    Look up geolocation information for an IP address.

    Args:
        ip: IP address to look up (IPv4 or IPv6)

    Returns:
        IPLookupResult with location data or error
    """
    # Validate IP format first
    is_valid, error = validate_ip(ip)
    if not is_valid:
        return IPLookupResult(ip=ip, success=False, error=error)

    try:
        async with httpx.AsyncClient(timeout=settings.ip_geolocation_timeout_seconds) as client:
            response = await client.get(f"{settings.ip_geolocation_api}/{ip}")
            response.raise_for_status()
            data = response.json()

        # Check API-level success
        if not data.get("success", True):
            return IPLookupResult(
                ip=ip,
                success=False,
                error=data.get("message", "Unknown API error"),
            )

        # Parse response
        return IPLookupResult(
            ip=data.get("ip", ip),
            success=True,
            ip_type=data.get("type"),
            continent=data.get("continent"),
            continent_code=data.get("continent_code"),
            country=data.get("country"),
            country_code=data.get("country_code"),
            region=data.get("region"),
            region_code=data.get("region_code"),
            city=data.get("city"),
            postal=data.get("postal"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            is_eu=data.get("is_eu"),
            borders=data.get("borders"),
            calling_code=data.get("calling_code"),
            capital=data.get("capital"),
            flag_emoji=data.get("flag", {}).get("emoji"),
            asn=data.get("connection", {}).get("asn"),
            org=data.get("connection", {}).get("org"),
            isp=data.get("connection", {}).get("isp"),
            domain=data.get("connection", {}).get("domain"),
            timezone_id=data.get("timezone", {}).get("id"),
            timezone_abbr=data.get("timezone", {}).get("abbr"),
            utc_offset=data.get("timezone", {}).get("utc"),
            current_time=data.get("timezone", {}).get("current_time"),
            is_dst=data.get("timezone", {}).get("is_dst"),
        )

    except httpx.TimeoutException:
        return IPLookupResult(
            ip=ip,
            success=False,
            error=f"Request timed out after {settings.ip_geolocation_timeout_seconds}s",
        )
    except httpx.HTTPStatusError as e:
        return IPLookupResult(
            ip=ip,
            success=False,
            error=f"HTTP error: {e.response.status_code}",
        )
    except httpx.RequestError as e:
        return IPLookupResult(
            ip=ip,
            success=False,
            error=f"Network error: {e}",
        )
    except Exception as e:
        return IPLookupResult(
            ip=ip,
            success=False,
            error=f"Unexpected error: {e}",
        )


async def get_my_ip() -> MyIPResult:
    """
    Get the current machine's public IP address.

    Returns:
        MyIPResult with IP or error
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try ipify first
            response = await client.get("https://api.ipify.org?format=json")
            response.raise_for_status()
            data = response.json()
            return MyIPResult(ip=data.get("ip"))

    except httpx.TimeoutException:
        return MyIPResult(error="Request timed out")
    except httpx.RequestError as e:
        return MyIPResult(error=f"Network error: {e}")
    except Exception as e:
        return MyIPResult(error=f"Unexpected error: {e}")
