"""Phone number normalisation to E.164."""
from __future__ import annotations

import phonenumbers

# Values carriers/Twilio use for withheld caller ID.
_HIDDEN = {"", "anonymous", "restricted", "unknown", "private", "+266696687", "+86282452253"}


def is_hidden(raw: str | None) -> bool:
    return (raw or "").strip().lower() in _HIDDEN


def normalize(raw: str | None, default_region: str = "ES") -> str | None:
    """Return E.164 or None when the number is hidden or unparseable."""
    if is_hidden(raw):
        return None
    try:
        parsed = phonenumbers.parse(raw.strip(), default_region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def region_for_language(language: str) -> str:
    return "PT" if language.lower().startswith("pt") else "ES"
