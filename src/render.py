# render.py
from .models import DOCUMENT_TYPES, MatterSummary, Request


def render_clarification_email(reason: str, allowed_types: list[str] | None = None) -> str:
    """Render clarification/error email body."""
    allowed = allowed_types or DOCUMENT_TYPES
    types_list = "\n  - ".join(allowed)
    return f"""We couldn't process your request.

{reason}

Please resend with:
  - A valid matter number (e.g., M12205)
  - One document type from:
  - {types_list}

Thank you."""


def render_response_email(summary: MatterSummary, requested_type: str, downloaded_count: int) -> str:
    """Render success email body (stub for later)."""
    # TODO: Implement when MatterSummary has counts/metadata
    return f"Re: Matter {summary.matter_id}\n\nDownloaded {downloaded_count} documents (type: {requested_type})."
