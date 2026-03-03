# main.py
"""Email-driven agent entrypoint."""

import argparse
import logging

from .models import Request
from .parser import parse_request
from .render import render_clarification_email

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
    # TODO: fetch_matter_metadata_and_counts, list_download_targets, download, zip, send
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
