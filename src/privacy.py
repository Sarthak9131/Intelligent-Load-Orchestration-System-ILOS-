"""Conservative masking helpers for identifiers in prompts and logs."""

import re
from collections.abc import Mapping
from typing import Any

REDACTED_NAME = "[REDACTED_NAME]"
REDACTED_SSN = "[REDACTED_SSN]"
REDACTED_DOB = "[REDACTED_DOB]"
REDACTED_ADDRESS = "[REDACTED_ADDRESS]"
REDACTED_PHONE = "[REDACTED_PHONE]"
REDACTED_EMAIL = "[REDACTED_EMAIL]"

_JSON_FIELDS = {
    "name": re.compile(
        r'("(?:applicant_name|patient_name|member_name|full_name|name)"\s*:\s*)"([^"]*)"',
        re.IGNORECASE,
    ),
    "ssn": re.compile(
        r'("(?:ssn|social_security_number)"\s*:\s*)"([^"]*)"', re.IGNORECASE
    ),
    "dob": re.compile(
        r'("(?:dob|date_of_birth|birth_date)"\s*:\s*)"([^"]*)"', re.IGNORECASE
    ),
    "address": re.compile(
        r'("(?:address|street_address|mailing_address)"\s*:\s*)"([^"]*)"',
        re.IGNORECASE,
    ),
    "phone": re.compile(
        r'("(?:phone|phone_number|mobile|telephone)"\s*:\s*)"([^"]*)"',
        re.IGNORECASE,
    ),
    "email": re.compile(
        r'("(?:email|email_address)"\s*:\s*)"([^"]*)"', re.IGNORECASE
    ),
}
_TOKENS = {
    "name": REDACTED_NAME,
    "ssn": REDACTED_SSN,
    "dob": REDACTED_DOB,
    "address": REDACTED_ADDRESS,
    "phone": REDACTED_PHONE,
    "email": REDACTED_EMAIL,
}
_LABELED_FIELDS = (
    (
        re.compile(
            r"(?im)(\b(?:applicant|patient|member|full)\s+name\b|\bname\b)"
            r"(\s*[:=]\s*)([^\r\n,;]+)"
        ),
        REDACTED_NAME,
        "name",
    ),
    (
        re.compile(
            r"(?im)(\b(?:social\s+security\s+number|ssn)\b)(\s*[:=]\s*)"
            r"([^\r\n,;]+)"
        ),
        REDACTED_SSN,
        "ssn",
    ),
    (
        re.compile(r"(?im)(\b(?:date\s+of\s+birth|dob)\b)(\s*[:=]\s*)([^\r\n,;]+)"),
        REDACTED_DOB,
        "dob",
    ),
    (
        re.compile(
            r"(?im)(\b(?:street\s+address|mailing\s+address|address)\b)"
            r"(\s*[:=]\s*)([^\r\n]+)"
        ),
        REDACTED_ADDRESS,
        "address",
    ),
    (
        re.compile(
            r"(?im)(\b(?:phone|phone\s+number|mobile|telephone)\b)"
            r"(\s*[:=]\s*)([^\r\n,;]+)"
        ),
        REDACTED_PHONE,
        "phone",
    ),
    (
        re.compile(r"(?im)(\b(?:email|email\s+address)\b)(\s*[:=]\s*)([^\r\n,;]+)"),
        REDACTED_EMAIL,
        "email",
    ),
)


def mask_pii(value: str) -> str:
    """Mask labeled names, SSNs, birth dates, addresses, phones, and emails."""
    masked = value
    names = _extract_names(masked)
    for key, pattern in _JSON_FIELDS.items():
        masked = pattern.sub(
            lambda match, replacement=_TOKENS[key]: (
                f'{match.group(1)}"{replacement}"'
            ),
            masked,
        )
    for pattern, replacement, _ in _LABELED_FIELDS:
        masked = pattern.sub(
            lambda match, token=replacement: (
                f"{match.group(1)}{match.group(2)}{token}"
            ),
            masked,
        )
    for name in sorted(names, key=len, reverse=True):
        if name and name not in _TOKENS.values():
            masked = re.sub(re.escape(name), REDACTED_NAME, masked, flags=re.IGNORECASE)
    masked = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", REDACTED_SSN, masked)
    masked = re.sub(
        r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)?\d{2}\b",
        REDACTED_DOB,
        masked,
    )
    masked = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        REDACTED_EMAIL,
        masked,
        flags=re.IGNORECASE,
    )
    masked = re.sub(
        r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)",
        REDACTED_PHONE,
        masked,
    )
    return masked


def mask_sensitive_data(value: Any) -> Any:
    """Recursively mask string values in structured log and audit payloads."""
    if isinstance(value, str):
        return mask_pii(value)
    if isinstance(value, Mapping):
        field_tokens = {
            "name": REDACTED_NAME,
            "applicant_name": REDACTED_NAME,
            "patient_name": REDACTED_NAME,
            "member_name": REDACTED_NAME,
            "full_name": REDACTED_NAME,
            "ssn": REDACTED_SSN,
            "social_security_number": REDACTED_SSN,
            "dob": REDACTED_DOB,
            "date_of_birth": REDACTED_DOB,
            "birth_date": REDACTED_DOB,
            "address": REDACTED_ADDRESS,
            "street_address": REDACTED_ADDRESS,
            "mailing_address": REDACTED_ADDRESS,
            "phone": REDACTED_PHONE,
            "phone_number": REDACTED_PHONE,
            "mobile": REDACTED_PHONE,
            "telephone": REDACTED_PHONE,
            "email": REDACTED_EMAIL,
            "email_address": REDACTED_EMAIL,
        }
        return {
            key: (
                field_tokens[str(key).lower()]
                if str(key).lower() in field_tokens and item is not None
                else mask_sensitive_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [mask_sensitive_data(item) for item in value]
    return value


def _extract_names(value: str) -> list[str]:
    names = []
    for pattern in (
        _JSON_FIELDS["name"],
        _LABELED_FIELDS[0][0],
    ):
        for match in pattern.finditer(value):
            candidate = match.group(match.lastindex or 1).strip()
            if pattern is _JSON_FIELDS["name"]:
                candidate = match.group(2).strip()
            else:
                candidate = match.group(3).strip()
            if candidate and candidate not in _TOKENS.values():
                names.append(candidate.strip('"\''))
    return names
