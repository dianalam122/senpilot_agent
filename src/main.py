# main.py
"""Email-driven agent entrypoint."""

import argparse
import logging
import os

from playwright.sync_api import sync_playwright

from .models import Request
from .parser import parse_request
from .render import render_clarification_email
from .downloader import download_targets
from .zipper import make_zip
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

    if not request.document_type:
        print(f"Valid request: {request.matter_number} (no doc type)")
        return

    targets = list_download_targets(
        request.matter_number, request.document_type, limit=10
    )
    log.info("Download targets: %d items", len(targets))
    if not targets:
        print(f"No documents available for {request.matter_number} / {request.document_type}")
        return

    for t in targets[:3]:
        log.info("  Target: name=%s, selector=%s", t.name, t.selector)
    if len(targets) > 3:
        log.info("  ... and %d more", len(targets) - 3)

    out_dir = os.path.join("output", request.matter_number, request.document_type)
    os.makedirs(out_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()
        result = download_targets(
            page, request.matter_number, request.document_type, targets, out_dir
        )
        browser.close()

    zip_path = os.path.join("output", request.matter_number, f"{request.document_type}.zip")
    make_zip(out_dir, zip_path)

    log.info("Downloaded %d/%d, zipped at %s", result.succeeded, result.requested, zip_path)
    print(f"Downloaded {result.succeeded}/{result.requested}, zipped at {zip_path}")


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
