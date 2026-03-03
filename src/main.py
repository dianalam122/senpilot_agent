# main.py
"""Email-driven agent entrypoint."""

import argparse
import logging

from .models import Request
from .parser import parse_request
from .render import render_clarification_email
from .uarb_client import fetch_matter_metadata_and_counts, list_download_targets

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def run(email_text: str, reply_to: str | None) -> None:
    """Run the agent pipeline (M1: parse only, print clarification if invalid)."""
    request, error = parse_request(email_text)

    if error:
        log.info("Parse failed: %s", error)
        body = render_clarification_email(error)
        print("\n--- Clarification email ---\n")
        print(body)
        print("\n--- End ---")
        return

    log.info(
        "Parsed: matter_number=%s, document_type=%s, requester_email=%s",
        request.matter_number,
        request.document_type,
        request.requester_email,
    )

    summary = fetch_matter_metadata_and_counts(request.matter_number)
    if summary.not_found:
        log.info("Matter not found: %s", request.matter_number)
        body = render_clarification_email("Matter not found. Please verify the matter number.")
        print("\n--- Clarification email ---\n")
        print(body)
        print("\n--- End ---")
        return

    log.info(
        "Matter found: title=%s, counts=%s, metadata=%s",
        summary.title[:60] if summary.title else "",
        summary.counts,
        summary.metadata,
    )

    if request.document_type:
        targets = list_download_targets(
            request.matter_number, request.document_type, limit=10
        )
        log.info("Download targets: %d items", len(targets))
        for t in targets[:3]:  # log first 3
            log.info("  Target: name=%s, selector=%s", t.name, t.selector)
        if len(targets) > 3:
            log.info("  ... and %d more", len(targets) - 3)

    # TODO: download_targets, make_zip, send_email
    print(f"Valid request: {request.matter_number} / {request.document_type}")


def main() -> None:
    parser = argparse.ArgumentParser(description="UARB document request agent")
    parser.add_argument("--email_text_file", required=True, help="Path to .txt file with email body")
    parser.add_argument("--reply_to", required=True, help="Recipient email for reply")
    args = parser.parse_args()

    path = args.email_text_file
    try:
        with open(path, encoding="utf-8") as f:
            email_text = f.read()
    except OSError as e:
        log.error("Could not read %s: %s", path, e)
        return

    run(email_text, args.reply_to)


if __name__ == "__main__":
    main()
