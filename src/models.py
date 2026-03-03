# models.py
from pydantic import BaseModel

# Allowed document types (canonical) + synonyms in one place
# Restricted to exactly: Exhibits, Key Documents, Other Documents, Transcripts, Recordings
DOCUMENT_TYPES = [
    "exhibits",
    "key_documents",
    "other_documents",
    "transcripts",
    "recordings",
]

DOC_TYPE_SYNONYMS: dict[str, str] = {
    "exhibits": "exhibits",
    "exhibit": "exhibits",
    "key document": "key_documents",
    "key documents": "key_documents",
    "key docs": "key_documents",
    "key doc": "key_documents",
    "other doc": "other_documents",
    "other docs": "other_documents",
    "other documents": "other_documents",
    "transcripts": "transcripts",
    "transcript": "transcripts",
    "recordings": "recordings",
    "recording": "recordings",
}

# Map canonical type to tab label as shown on UARB (may need adjustment per site)
DOC_TYPE_TO_TAB: dict[str, str] = {
    "exhibits": "Exhibits",
    "key_documents": "Key Documents",
    "other_documents": "Other Documents",
    "transcripts": "Transcripts",
    "recordings": "Recordings",
}


class Request(BaseModel):
    """Parsed incoming email/request."""

    matter_number: str
    document_type: str | None = None
    requester_email: str | None = None


class MatterSummary(BaseModel):
    """Summary of a matter from UARB."""

    matter_id: str = ""
    title: str = ""
    counts: dict[str, int] = {}  # doc_type -> count per tab
    metadata: dict[str, str] = {}  # dates, category, amount, etc.
    not_found: bool = False


class DownloadTarget(BaseModel):
    """A single downloadable item (Go Get It target)."""

    name: str = ""
    selector: str = ""  # or id for Playwright to click
