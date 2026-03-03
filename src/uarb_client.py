# uarb_client.py
from .models import MatterSummary

# TODO: Playwright navigation to https://uarb.novascotia.ca/fmi/webd/UARB15


def fetch_matter_metadata_and_counts(matter_number: str) -> MatterSummary:
    """Fetch matter summary: title, counts per tab, metadata (dates/category/amount)."""
    # TODO: Navigate, search matter, scrape tabs and counts
    return MatterSummary(matter_id=matter_number, title="", status="")


def list_download_targets(matter_number: str, document_type: str, limit: int = 10) -> list:
    """List up to `limit` items for document type (Go Get It targets)."""
    # TODO: Navigate to matter, select tab by document_type, collect targets
    return []
