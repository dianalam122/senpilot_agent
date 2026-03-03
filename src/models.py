# models.py
from pydantic import BaseModel

# Allowed document types (canonical) + synonyms in one place
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
    "transcript": "transcrips",
    "recordings": "recordings",
    "recording": "recordings",
}


class Request(BaseModel):
    """Parsed incoming email/request."""

    matter_number: str
    document_type: str | None = None
    requester_email: str | None = None


class MatterSummary(BaseModel):
    """Summary of a matter from external system (stub for later)."""

    matter_id: str = ""
    title: str = ""
    status: str = ""
