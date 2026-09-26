"""
Phone number OSINT lookup.

Comprehensive phone intelligence gathering using multiple sources.
Similar to PhoneInfoga approach - gathers all publicly available info.
"""

import asyncio
import re
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from pydantic import BaseModel


class PhoneOSINTResult(BaseModel):
    """Comprehensive phone OSINT result."""

    # Input
    original: str
    success: bool = True
    error: Optional[str] = None

    # Basic parsing
    valid: bool = False
    possible: bool = False
    country_code: Optional[int] = None
    national_number: Optional[str] = None
    region_code: Optional[str] = None
    country: Optional[str] = None

    # Carrier/operator info
    carrier: Optional[str] = None
    line_type: Optional[str] = None
    timezone: Optional[str] = None

    # Formatted versions
    international: Optional[str] = None
    national: Optional[str] = None
    e164: Optional[str] = None

    # OSINT results
    google_dorks: list[dict[str, str]] = []
    social_links: list[dict[str, str]] = []
    reputation: Optional[dict[str, Any]] = None
    online_presence: list[dict[str, Any]] = []

    # NumVerify API result (if available)
    numverify: Optional[dict[str, Any]] = None


def _get_number_type_name(number_type: int) -> str:
    """Convert phonenumbers type constant to readable name."""
    type_names = {
        phonenumbers.PhoneNumberType.FIXED_LINE: "Fixed Line",
        phonenumbers.PhoneNumberType.MOBILE: "Mobile",
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed/Mobile",
        phonenumbers.PhoneNumberType.TOLL_FREE: "Toll Free",
        phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium Rate",
        phonenumbers.PhoneNumberType.SHARED_COST: "Shared Cost",
        phonenumbers.PhoneNumberType.VOIP: "VoIP",
        phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Personal",
        phonenumbers.PhoneNumberType.PAGER: "Pager",
        phonenumbers.PhoneNumberType.UAN: "UAN",
        phonenumbers.PhoneNumberType.VOICEMAIL: "Voicemail",
        phonenumbers.PhoneNumberType.UNKNOWN: "Unknown",
    }
    return type_names.get(number_type, "Unknown")


def _generate_google_dorks(phone: str, e164: str, national: str) -> list[dict[str, str]]:
    """Generate Google dork search queries for the phone number."""
    # Clean versions for searching
    clean = re.sub(r"[^\d]", "", phone)

    dorks = [
        {
            "name": "General Search",
            "query": f'"{phone}"',
            "url": f"https://www.google.com/search?q={quote_plus(phone)}",
        },
        {
            "name": "E164 Format",
            "query": f'"{e164}"',
            "url": f"https://www.google.com/search?q={quote_plus(e164)}",
        },
        {
            "name": "Digits Only",
            "query": f'"{clean}"',
            "url": f"https://www.google.com/search?q={quote_plus(clean)}",
        },
        {
            "name": "Facebook",
            "query": f'site:facebook.com "{phone}"',
            "url": f"https://www.google.com/search?q=site:facebook.com+{quote_plus(phone)}",
        },
        {
            "name": "LinkedIn",
            "query": f'site:linkedin.com "{phone}"',
            "url": f"https://www.google.com/search?q=site:linkedin.com+{quote_plus(phone)}",
        },
        {
            "name": "Twitter/X",
            "query": f'site:twitter.com OR site:x.com "{phone}"',
            "url": f"https://www.google.com/search?q=site:twitter.com+OR+site:x.com+{quote_plus(phone)}",
        },
        {
            "name": "Instagram",
            "query": f'site:instagram.com "{phone}"',
            "url": f"https://www.google.com/search?q=site:instagram.com+{quote_plus(phone)}",
        },
        {
            "name": "Documents",
            "query": f'filetype:pdf OR filetype:doc "{phone}"',
            "url": f"https://www.google.com/search?q=filetype:pdf+OR+filetype:doc+{quote_plus(phone)}",
        },
        {
            "name": "Disposable Check",
            "query": f'"{phone}" (disposable OR temporary OR burner)',
            "url": f"https://www.google.com/search?q={quote_plus(phone)}+(disposable+OR+temporary+OR+burner)",
        },
        {
            "name": "Data Breach",
            "query": f'"{phone}" (leak OR breach OR dump OR pastebin)',
            "url": f"https://www.google.com/search?q={quote_plus(phone)}+(leak+OR+breach+OR+dump)",
        },
    ]

    return dorks


def _generate_social_links(phone: str, e164: str) -> list[dict[str, str]]:
    """Generate direct social media search links."""
    clean = re.sub(r"[^\d]", "", phone)
    encoded = quote_plus(phone)

    return [
        {
            "platform": "Facebook",
            "url": f"https://www.facebook.com/search/top?q={encoded}",
        },
        {
            "platform": "Sync.me",
            "url": f"https://sync.me/search/?number={quote_plus(e164)}",
        },
        {
            "platform": "Truecaller",
            "url": f"https://www.truecaller.com/search/{clean}",
        },
        {
            "platform": "CallerID Test",
            "url": f"https://calleridtest.com/results/?number={clean}",
        },
        {
            "platform": "SpyDialer",
            "url": f"https://www.spydialer.com/results.aspx?phone={clean}",
        },
        {
            "platform": "WhitePages",
            "url": f"https://www.whitepages.com/phone/{clean}",
        },
        {
            "platform": "ThatsThem",
            "url": f"https://thatsthem.com/phone/{clean}",
        },
        {
            "platform": "NumLookup",
            "url": f"https://www.numlookup.com/search?number={quote_plus(e164)}",
        },
        {
            "platform": "Telegram",
            "url": f"https://t.me/{clean}",
        },
        {
            "platform": "WhatsApp",
            "url": f"https://wa.me/{clean}",
        },
        {
            "platform": "Viber",
            "url": f"viber://chat?number={quote_plus(e164)}",
        },
    ]


async def _check_numverify(phone: str) -> Optional[dict]:
    """Check NumVerify API (free tier)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # NumVerify free API (limited)
            response = await client.get(
                f"http://apilayer.net/api/validate",
                params={
                    "access_key": "",  # Would need API key
                    "number": phone,
                },
            )
            if response.status_code == 200:
                return response.json()
    except Exception:
        pass
    return None


async def _check_reputation(phone: str) -> dict:
    """Check phone reputation from various sources."""
    reputation = {
        "spam_reports": 0,
        "fraud_score": None,
        "sources_checked": [],
    }

    clean = re.sub(r"[^\d]", "", phone)

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check various free reputation sources
        checks = []

        # 800notes (scrape-based)
        try:
            resp = await client.get(
                f"https://800notes.com/{clean}",
                follow_redirects=True,
            )
            if resp.status_code == 200 and "spam" in resp.text.lower():
                reputation["spam_reports"] += 1
            reputation["sources_checked"].append("800notes")
        except Exception:
            pass

    return reputation


async def _check_online_presence(phone: str, e164: str) -> list[dict]:
    """Check if phone is registered on various services."""
    presence = []
    clean = re.sub(r"[^\d]", "", phone)

    async with httpx.AsyncClient(timeout=8.0) as client:
        # Check WhatsApp (via API endpoint)
        try:
            # This checks if the number exists on WhatsApp
            resp = await client.get(
                f"https://wa.me/{clean}",
                follow_redirects=False,
            )
            presence.append({
                "service": "WhatsApp",
                "registered": resp.status_code != 404,
                "url": f"https://wa.me/{clean}",
            })
        except Exception:
            pass

        # Check Telegram
        try:
            resp = await client.get(
                f"https://t.me/{clean}",
                follow_redirects=True,
            )
            presence.append({
                "service": "Telegram",
                "registered": "tgme_page_title" in resp.text if resp.status_code == 200 else False,
                "url": f"https://t.me/{clean}",
            })
        except Exception:
            pass

    return presence


async def phone_osint(
    phone_number: str,
    default_region: str = "US",
    deep_scan: bool = True,
) -> PhoneOSINTResult:
    """
    Comprehensive phone number OSINT lookup.

    Args:
        phone_number: Phone number string (with or without country code)
        default_region: Default region code if not specified
        deep_scan: Whether to perform online lookups (slower)

    Returns:
        PhoneOSINTResult with all gathered intelligence
    """
    result = PhoneOSINTResult(original=phone_number)

    try:
        # Parse the number
        parsed = phonenumbers.parse(phone_number, default_region)

        # Basic validation
        result.valid = phonenumbers.is_valid_number(parsed)
        result.possible = phonenumbers.is_possible_number(parsed)
        result.country_code = parsed.country_code
        result.national_number = str(parsed.national_number)
        result.region_code = phonenumbers.region_code_for_number(parsed)

        # Get country name
        try:
            result.country = geocoder.description_for_number(parsed, "en")
        except Exception:
            pass

        # Carrier info
        try:
            result.carrier = carrier.name_for_number(parsed, "en") or None
        except Exception:
            pass

        # Line type
        number_type = phonenumbers.number_type(parsed)
        result.line_type = _get_number_type_name(number_type)

        # Timezone
        try:
            tz_list = timezone.time_zones_for_number(parsed)
            result.timezone = ", ".join(tz_list) if tz_list else None
        except Exception:
            pass

        # Format versions
        result.international = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
        result.national = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.NATIONAL
        )
        result.e164 = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )

        # Generate OSINT links
        result.google_dorks = _generate_google_dorks(
            phone_number, result.e164, result.national
        )
        result.social_links = _generate_social_links(phone_number, result.e164)

        # Deep scan - online lookups
        if deep_scan and result.valid:
            try:
                # Run online checks concurrently
                reputation_task = _check_reputation(result.e164)
                presence_task = _check_online_presence(result.e164, result.e164)

                reputation, presence = await asyncio.gather(
                    reputation_task,
                    presence_task,
                    return_exceptions=True,
                )

                if isinstance(reputation, dict):
                    result.reputation = reputation
                if isinstance(presence, list):
                    result.online_presence = presence

            except Exception:
                pass

        return result

    except phonenumbers.NumberParseException as e:
        result.success = False
        result.error = f"Invalid phone number: {e}"
        return result
    except Exception as e:
        result.success = False
        result.error = f"Error: {e}"
        return result


# Sync wrapper for CLI
def parse_phone_number(phone_number: str, default_region: str = "US") -> PhoneOSINTResult:
    """Synchronous wrapper for phone OSINT."""
    return asyncio.run(phone_osint(phone_number, default_region, deep_scan=False))
