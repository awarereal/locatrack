"""
Phone number parsing and validation.

Uses the phonenumbers library for offline parsing.
"""

from typing import Optional

import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from pydantic import BaseModel


class PhoneParseResult(BaseModel):
    """Result of parsing a phone number."""

    original: str
    success: bool = True
    error: Optional[str] = None

    # Validity
    is_valid: bool = False
    is_possible: bool = False

    # Parsed components
    country_code: Optional[int] = None
    national_number: Optional[int] = None
    region_code: Optional[str] = None

    # Location info
    location: Optional[str] = None
    carrier: Optional[str] = None
    timezone: Optional[str] = None

    # Number type
    number_type: Optional[str] = None

    # Formatted versions
    international_format: Optional[str] = None
    national_format: Optional[str] = None
    e164_format: Optional[str] = None
    rfc3966_format: Optional[str] = None


def _get_number_type_name(number_type: int) -> str:
    """Convert phonenumbers type constant to readable name."""
    type_names = {
        phonenumbers.PhoneNumberType.FIXED_LINE: "Fixed Line",
        phonenumbers.PhoneNumberType.MOBILE: "Mobile",
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed Line or Mobile",
        phonenumbers.PhoneNumberType.TOLL_FREE: "Toll Free",
        phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium Rate",
        phonenumbers.PhoneNumberType.SHARED_COST: "Shared Cost",
        phonenumbers.PhoneNumberType.VOIP: "VoIP",
        phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Personal Number",
        phonenumbers.PhoneNumberType.PAGER: "Pager",
        phonenumbers.PhoneNumberType.UAN: "UAN",
        phonenumbers.PhoneNumberType.VOICEMAIL: "Voicemail",
        phonenumbers.PhoneNumberType.UNKNOWN: "Unknown",
    }
    return type_names.get(number_type, "Unknown")


def parse_phone_number(
    phone_number: str,
    default_region: str = "US",
) -> PhoneParseResult:
    """
    Parse and validate a phone number.

    Args:
        phone_number: Phone number string (with or without country code)
        default_region: Default region code if not specified in number

    Returns:
        PhoneParseResult with parsed information or error
    """
    try:
        # Parse the number
        parsed = phonenumbers.parse(phone_number, default_region)

        # Check validity
        is_valid = phonenumbers.is_valid_number(parsed)
        is_possible = phonenumbers.is_possible_number(parsed)

        # Get region code
        region_code = phonenumbers.region_code_for_number(parsed)

        # Get location description
        try:
            location = geocoder.description_for_number(parsed, "en")
        except Exception:
            location = None

        # Get carrier info
        try:
            carrier_name = carrier.name_for_number(parsed, "en")
        except Exception:
            carrier_name = None

        # Get timezone
        try:
            tz_list = timezone.time_zones_for_number(parsed)
            tz_str = ", ".join(tz_list) if tz_list else None
        except Exception:
            tz_str = None

        # Get number type
        number_type = phonenumbers.number_type(parsed)
        type_name = _get_number_type_name(number_type)

        # Format in various ways
        try:
            international_format = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )
        except Exception:
            international_format = None

        try:
            national_format = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.NATIONAL
            )
        except Exception:
            national_format = None

        try:
            e164_format = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
        except Exception:
            e164_format = None

        try:
            rfc3966_format = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.RFC3966
            )
        except Exception:
            rfc3966_format = None

        return PhoneParseResult(
            original=phone_number,
            success=True,
            is_valid=is_valid,
            is_possible=is_possible,
            country_code=parsed.country_code,
            national_number=parsed.national_number,
            region_code=region_code,
            location=location or None,
            carrier=carrier_name or None,
            timezone=tz_str,
            number_type=type_name,
            international_format=international_format,
            national_format=national_format,
            e164_format=e164_format,
            rfc3966_format=rfc3966_format,
        )

    except phonenumbers.NumberParseException as e:
        return PhoneParseResult(
            original=phone_number,
            success=False,
            error=f"Parse error: {e}",
        )
    except Exception as e:
        return PhoneParseResult(
            original=phone_number,
            success=False,
            error=f"Unexpected error: {e}",
        )
