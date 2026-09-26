"""
OSINT lookup routes.

These endpoints provide IP geolocation, phone parsing, and username search
functionality via the API.
"""

from typing import List

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from aware.lookups.ip_info import IPLookupResult, lookup_ip
from aware.lookups.phone import PhoneParseResult, parse_phone_number
from aware.lookups.username import UsernameResult, search_username

router = APIRouter()


class UsernameSearchRequest(BaseModel):
    """Username search request."""

    username: str
    timeout: float = 5.0


@router.get("/ip/{ip_address}")
async def lookup_ip_endpoint(ip_address: str) -> IPLookupResult:
    """
    Look up geolocation information for an IP address.

    Returns location, ISP, and timezone information.
    """
    result = await lookup_ip(ip_address)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "IP lookup failed",
        )

    return result


@router.get("/phone/{phone_number:path}")
async def lookup_phone_endpoint(
    phone_number: str,
    default_region: str = Query("US", description="Default region for parsing"),
) -> PhoneParseResult:
    """
    Parse and validate a phone number.

    Returns carrier, region, timezone, and format information.
    The phone number can include + for country code.
    """
    result = parse_phone_number(phone_number, default_region)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Phone parsing failed",
        )

    return result


@router.post("/username")
async def search_username_endpoint(
    data: UsernameSearchRequest,
) -> List[UsernameResult]:
    """
    Search for a username across social media platforms.

    Returns a list of platforms where the username was found.
    """
    results = await search_username(
        username=data.username,
        timeout=data.timeout,
    )

    return results
