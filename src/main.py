# main.py
"""Email-driven agent entrypoint."""

import argparse
import logging
import os

from playwright.sync_api import sync_playwright

from .models import DOC_TYPE_TO_TAB, Request
from .parser import parse_request
from .render import render_clarification_email, render_response_email
from .downloader import download_targets
from .zipper import make_zip
from .mailer import send_email
from .uarb_client import fetch_matter_metadata_and_counts, list_download_targets

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def _recipient(request: Request, reply_to: str) -> str:
    """Recipient for replies: requester_email or --reply_to."""
    return request.requester_email or reply_to


def _subject(matter_number: str, requested_type: str) -> str:
    """Email subject."""
    label = DOC_TYPE_TO_TAB.get(
        requested_type, requested_type.replace("_", " ").title()
    )
    return f"UARB {matter_number} – {label}"


def _send_or_dry_run(to: str, subject: str, body: str, attachment_path: str | None = None) -> None:
    """Send email, or if DRY_RUN=1: log, print subject/body/attachment."""
    if os.environ.get("DRY_RUN") == "1":
        log.info("DRY_RUN=1 – email not sent")
        print(f"\nSubject: {subject}\n")
        print(body)
        if attachment_path:
            print(f"\nAttachment: {attachment_path}")
        return
    try:
        send_email(to=to, subject=subject, body=body, attachment_path=attachment_path)
    except Exception as e:
        log.error("Failed to send email: %s", e)


def run(email_text: str, reply_to: str) -> None:
    """Run the agent pipeline: parse, fetch, download, zip, send email."""
    request, error = parse_request(email_text)

    if error:
        log.info("Parse failed: %s", error)
        body = render_clarification_email(error)
        print("\n--- Clarification email ---\n")
        print(body)
        print("\n--- End ---")
        _send_or_dry_run(to=reply_to, subject="UARB – Request clarification", body=body)
        return

    log.info(
        "Parsed: matter_number=%s, document_type=%s, requester_email=%s",
        request.matter_number,
        request.document_type,
        request.requester_email,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()

        summary = fetch_matter_metadata_and_counts(page, request.matter_number)
        if summary.not_found:
            log.info("Matter not found: %s", request.matter_number)
            body = render_clarification_email("Matter not found. Please verify the matter number.")
            print("\n--- Clarification email ---\n")
            print(body)
            print("\n--- End ---")
            _send_or_dry_run(
                to=reply_to,
                subject=f"UARB {request.matter_number} – Request clarification",
                body=body,
            )
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
            page, request.matter_number, request.document_type, limit=10
        )
        log.info("Download targets: %d items", len(targets))

        to_email = _recipient(request, reply_to)

        if not targets:
            body = render_response_email(
                summary=summary,
                requested_type=request.document_type,
                downloaded_count=0,
                requested_count=0,
                zip_filename=None,
                matter_number=request.matter_number,
            )
            print(f"No documents available for {request.matter_number} / {request.document_type}")
            _send_or_dry_run(
                to=to_email,
                subject=_subject(request.matter_number, request.document_type),
                body=body,
            )
            return

        for t in targets[:3]:
            log.info("  Target: name=%s, selector=%s", t.name, t.selector)
        if len(targets) > 3:
            log.info("  ... and %d more", len(targets) - 3)

        out_dir = os.path.join("output", request.matter_number, request.document_type)
        result = download_targets(
            page, request.matter_number, request.document_type, targets, out_dir
        )

    zip_path = os.path.join("output", request.matter_number, f"{request.document_type}.zip")
    make_zip(out_dir, zip_path)
    zip_filename = os.path.basename(zip_path)

    partial_success = result.failed > 0 and result.succeeded > 0
    body = render_response_email(
        summary=summary,
        requested_type=request.document_type,
        downloaded_count=result.succeeded,
        requested_count=result.requested,
        zip_filename=zip_filename,
        partial_success=partial_success,
        matter_number=request.matter_number,
    )

    log.info("Downloaded %d/%d, zipped at %s", result.succeeded, result.requested, zip_path)
    print(f"Downloaded {result.succeeded}/{result.requested}, zipped at {zip_path}")

    _send_or_dry_run(
        to=to_email,
        subject=_subject(request.matter_number, request.document_type),
        body=body,
        attachment_path=zip_path,
    )


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
