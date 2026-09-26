"""
Phone number intelligence and tracking.

IMPORTANT: Getting GPS location from a phone number requires them to click a link.
This module provides:
1. Phone number OSINT (carrier, location, social presence)
2. Integration with tracking links for actual GPS capture
3. Ready-to-send messages for WhatsApp/SMS/Telegram
"""

import asyncio
import re
from typing import Any, Optional
from urllib.parse import quote_plus, quote

import httpx
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from pydantic import BaseModel


class PhoneOSINTResult(BaseModel):
    """Comprehensive phone OSINT result."""

    original: str
    success: bool = True
    error: Optional[str] = None

    # Validation
    valid: bool = False
    possible: bool = False

    # Parsed info
    country_code: Optional[int] = None
    national_number: Optional[str] = None
    region_code: Optional[str] = None
    country: Optional[str] = None
    carrier: Optional[str] = None
    line_type: Optional[str] = None
    timezone: Optional[str] = None

    # Formatted
    international: Optional[str] = None
    national: Optional[str] = None
    e164: Optional[str] = None

    # Online presence
    whatsapp: Optional[bool] = None
    telegram: Optional[bool] = None
    viber: Optional[bool] = None

    # OSINT links
    google_dorks: list[dict[str, str]] = []
    lookup_services: list[dict[str, str]] = []

    # Tracking (for GPS capture)
    tracking_link: Optional[str] = None
    tracking_code: Optional[str] = None
    send_via: list[dict[str, str]] = []


def _get_number_type(num_type: int) -> str:
    types = {
        phonenumbers.PhoneNumberType.FIXED_LINE: "Fixed Line",
        phonenumbers.PhoneNumberType.MOBILE: "Mobile",
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Mobile/Fixed",
        phonenumbers.PhoneNumberType.TOLL_FREE: "Toll Free",
        phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium",
        phonenumbers.PhoneNumberType.VOIP: "VoIP",
        phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Personal",
    }
    return types.get(num_type, "Unknown")


async def _check_messaging_platforms(clean_number: str, e164: str) -> dict:
    """Check if number is registered on messaging platforms."""
    results = {"whatsapp": None, "telegram": None, "viber": None}

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        # WhatsApp - check if number opens chat
        try:
            resp = await client.head(f"https://api.whatsapp.com/send?phone={clean_number}")
            results["whatsapp"] = resp.status_code == 200
        except:
            pass

        # Telegram - check if number has profile
        try:
            resp = await client.get(f"https://t.me/+{clean_number}")
            results["telegram"] = resp.status_code == 200 and "tgme_page" in resp.text
        except:
            pass

    return results


def _generate_dorks(phone: str, e164: str) -> list[dict]:
    """Generate Google search queries."""
    clean = re.sub(r"[^\d]", "", phone)
    return [
        {"name": "General", "url": f"https://www.google.com/search?q={quote_plus(phone)}"},
        {"name": "E164", "url": f"https://www.google.com/search?q={quote_plus(e164)}"},
        {"name": "Facebook", "url": f"https://www.google.com/search?q=site:facebook.com+{quote_plus(phone)}"},
        {"name": "LinkedIn", "url": f"https://www.google.com/search?q=site:linkedin.com+{quote_plus(phone)}"},
        {"name": "Leaks", "url": f"https://www.google.com/search?q={quote_plus(phone)}+leak+OR+breach"},
    ]


def _generate_lookup_links(clean: str, e164: str) -> list[dict]:
    """Generate links to lookup services."""
    return [
        {"name": "Truecaller", "url": f"https://www.truecaller.com/search/{clean}"},
        {"name": "Sync.me", "url": f"https://sync.me/search/?number={quote_plus(e164)}"},
        {"name": "WhitePages", "url": f"https://www.whitepages.com/phone/{clean}"},
        {"name": "NumLookup", "url": f"https://www.numlookup.com/search?number={quote_plus(e164)}"},
        {"name": "SpyDialer", "url": f"https://www.spydialer.com/results.aspx?phone={clean}"},
        {"name": "ThatsThem", "url": f"https://thatsthem.com/phone/{clean}"},
    ]


def _generate_send_links(clean: str, e164: str, tracking_url: str) -> list[dict]:
    """Generate ready-to-send tracking link messages."""
    # Message templates - designed to get clicks
    msg = tracking_url

    return [
        {
            "platform": "WhatsApp",
            "url": f"https://wa.me/{clean}?text={quote(msg)}",
            "icon": "📱",
        },
        {
            "platform": "SMS",
            "url": f"sms:{e164}?body={quote(msg)}",
            "icon": "💬",
        },
        {
            "platform": "Telegram",
            "url": f"https://t.me/+{clean}",
            "message": msg,
            "icon": "✈️",
        },
        {
            "platform": "Copy Link",
            "url": tracking_url,
            "icon": "📋",
        },
    ]


async def phone_osint(
    phone_number: str,
    default_region: str = "US",
    deep_scan: bool = True,
    tracking_url: Optional[str] = None,
    tracking_code: Optional[str] = None,
) -> PhoneOSINTResult:
    """
    Phone number OSINT lookup with optional tracking link integration.

    Args:
        phone_number: Number to look up
        default_region: Default country code
        deep_scan: Check online platforms
        tracking_url: Pre-created tracking link URL
        tracking_code: Tracking link code
    """
    result = PhoneOSINTResult(original=phone_number)

    try:
        parsed = phonenumbers.parse(phone_number, default_region)

        result.valid = phonenumbers.is_valid_number(parsed)
        result.possible = phonenumbers.is_possible_number(parsed)
        result.country_code = parsed.country_code
        result.national_number = str(parsed.national_number)
        result.region_code = phonenumbers.region_code_for_number(parsed)

        # Location/carrier from number
        try:
            result.country = geocoder.description_for_number(parsed, "en")
        except:
            pass

        try:
            result.carrier = carrier.name_for_number(parsed, "en") or None
        except:
            pass

        result.line_type = _get_number_type(phonenumbers.number_type(parsed))

        try:
            tz = timezone.time_zones_for_number(parsed)
            result.timezone = tz[0] if tz else None
        except:
            pass

        # Format number
        result.international = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        result.national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        result.e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

        clean = re.sub(r"[^\d]", "", result.e164)

        # Generate OSINT links
        result.google_dorks = _generate_dorks(phone_number, result.e164)
        result.lookup_services = _generate_lookup_links(clean, result.e164)

        # Check messaging platforms
        if deep_scan and result.valid:
            try:
                presence = await _check_messaging_platforms(clean, result.e164)
                result.whatsapp = presence.get("whatsapp")
                result.telegram = presence.get("telegram")
                result.viber = presence.get("viber")
            except:
                pass

        # Add tracking link integration
        if tracking_url:
            result.tracking_link = tracking_url
            result.tracking_code = tracking_code
            result.send_via = _generate_send_links(clean, result.e164, tracking_url)

        return result

    except phonenumbers.NumberParseException as e:
        result.success = False
        result.error = f"Invalid number: {e}"
        return result
    except Exception as e:
        result.success = False
        result.error = str(e)
        return result


def parse_phone_number(phone_number: str, default_region: str = "US") -> PhoneOSINTResult:
    """Sync wrapper."""
    return asyncio.run(phone_osint(phone_number, default_region, deep_scan=False))
