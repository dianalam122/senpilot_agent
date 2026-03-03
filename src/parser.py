# parser.py
import re
from .models import Request, DOCUMENT_TYPES, DOC_TYPE_SYNONYMS

MATTER_RE = re.compile(r"\bM\d{4,6}\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def parse_request(email_text: str) -> tuple[Request | None, str | None]:
    """
    Parse email text into Request. Returns (Request, None) if valid,
    (None, error_message) if missing/invalid/ambiguous (for clarification email).
    """
    text = email_text.strip()
    if not text:
        return None, "Email body is empty. Please include a matter number (e.g., M12205) and document type."

    # Extract matter number
    matters = MATTER_RE.findall(text)
    if not matters:
        return None, (
            "No matter number found. Please include a matter number in the format M##### (e.g., M12205)."
        )
    if len(matters) > 1:
        return None, (
            f"Multiple matter numbers found ({', '.join(set(m.lower() for m in matters))}). "
            "Please request documents for one matter at a time."
        )
    matter_number = matters[0].upper()

    # Extract document type via synonym lookup
    text_lower = text.lower()
    found_types: set[str] = set()
    for phrase, canonical in DOC_TYPE_SYNONYMS.items():
        if phrase in text_lower:
            found_types.add(canonical)

    if len(found_types) > 1:
        return None, (
            f"Multiple document types detected ({', '.join(sorted(found_types))}). "
            f"Please specify one. Allowed: {', '.join(DOCUMENT_TYPES)}."
        )
    if len(found_types) == 0:
        return None, (
            "No document type specified. Please indicate which documents you need. "
            f"Allowed types: {', '.join(DOCUMENT_TYPES)}."
        )
    document_type = found_types.pop()

    # Extract requester email (first occurrence)
    emails = EMAIL_RE.findall(text)
    requester_email = emails[0] if emails else None

    return Request(
        matter_number=matter_number,
        document_type=document_type,
        requester_email=requester_email,
    ), None
