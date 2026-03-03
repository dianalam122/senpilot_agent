# render.py
from .models import DOCUMENT_TYPES, DOC_TYPE_TO_TAB, MatterSummary


def render_clarification_email(reason: str, allowed_types: list[str] | None = None) -> str:
    """Render clarification/error email body."""
    allowed = allowed_types or DOCUMENT_TYPES
    types_list = "\n    • ".join(allowed)
    return f"""We couldn't process your request.

{reason}

Please resend with:
  • A valid matter number (e.g., M12205)
  • One document type from:
    • {types_list}

Thank you."""


def _format_doc_type_counts(counts: dict[str, int]) -> str:
    """Format counts for each of the 5 doc types."""
    lines = []
    for doc_type in DOCUMENT_TYPES:
        label = DOC_TYPE_TO_TAB.get(doc_type, doc_type.replace("_", " ").title())
        count = counts.get(doc_type, 0)
        lines.append(f"  • {label}: {count}")
    return "\n".join(lines) if lines else "  (no counts available)"


def render_response_email(
    summary: MatterSummary,
    requested_type: str,
    downloaded_count: int,
    requested_count: int = 0,
    zip_filename: str | None = None,
    partial_success: bool = False,
    matter_number: str | None = None,
) -> str:
    """Render polished response email body."""
    greeting = "Hello,\n\n"
    matter_id = summary.matter_id or matter_number or ""
    matter_line = f"Matter {matter_id}"
    if summary.title:
        matter_line += f" – {summary.title}"
    matter_line += "\n\n"

    metadata_block = ""
    if summary.metadata:
        metadata_block = "Key metadata:\n"
        for k, v in summary.metadata.items():
            metadata_block += f"  • {k}: {v}\n"
        metadata_block += "\n"

    counts_block = "Document counts by type:\n"
    counts_block += _format_doc_type_counts(summary.counts)
    counts_block += "\n\n"

    requested_label = DOC_TYPE_TO_TAB.get(
        requested_type, requested_type.replace("_", " ").title()
    )
    available_count = summary.counts.get(requested_type, 0)

    if downloaded_count == 0 and requested_count == 0:
        download_line = (
            f"Available in matter: {available_count}\n\n"
            f"No documents available for {requested_label} in this matter.\n\n"
        )
    elif partial_success and downloaded_count > 0:
        download_line = (
            f"Available in matter: {available_count}\n\n"
            f"Partial download: {downloaded_count}/{requested_count} files retrieved "
            "(requested up to 10). Some items may have failed.\n\n"
        )
    else:
        download_line = (
            f"Available in matter: {available_count}\n\n"
            f"Downloaded {downloaded_count}/{requested_count} (requested up to 10).\n\n"
        )

    attachment_line = f"Attached: {zip_filename}\n\n" if zip_filename else ""

    sign_off = "Best regards,\nUARB Document Service"

    return (
        greeting
        + matter_line
        + metadata_block
        + counts_block
        + download_line
        + attachment_line
        + sign_off
    )
