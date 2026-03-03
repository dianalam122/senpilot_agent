# downloader.py
"""Download documents from UARB via Go Get It."""

import logging
import os
import re
import shutil
import time
import unicodedata

from playwright.sync_api import Page

from .models import DOC_TYPE_TO_TAB, DownloadResult, DownloadTarget
from .uarb_client import goto_matter

log = logging.getLogger(__name__)


def _open_modal(page: Page):
    """Select latest .v-window (modal) and wait for visible."""
    modals = page.locator(".v-window")
    modal = modals.last
    modal.wait_for(state="visible", timeout=10000)
    return modal


def _wait_for_content(page: Page, modal, timeout=12000) -> bool:
    """Wait for filename OR 'Your files are ready for download'. Return True if found."""
    deadline = time.time() + timeout
    file_re = r"text=/\.(pdf|docx?|xlsx?|zip)$/i"
    while time.time() < deadline:
        file_els = modal.locator(file_re)
        if file_els.count() > 0:
            return True
        ready = modal.get_by_text("Your files are ready for download", exact=False)
        if ready.count() > 0 and ready.first.is_visible():
            return True
        page.wait_for_timeout(300)
    return False


def _safe_filename(name: str) -> str:
    """Sanitize filename: remove/replace unsafe chars."""
    s = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    s = unicodedata.normalize("NFKC", s)
    return s.strip() or "document"


def download_targets(
    page: Page,
    matter_number: str,
    document_type: str,
    targets: list[DownloadTarget],
    out_dir: str,
) -> DownloadResult:
    """
    Navigate to matter, click tab, download each target via Go Get It.
    Retry once per file on failure. Return DownloadResult.
    """
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    log.info("Cleaned output directory: %s", out_dir)
    result = DownloadResult(requested=len(targets))

    frame, not_found = goto_matter(page, matter_number)
    if not frame or not_found:
        log.warning("goto_matter failed for %s", matter_number)
        result.failed = len(targets)
        return result

    tab_label = DOC_TYPE_TO_TAB.get(document_type, document_type)
    tab_loc = frame.get_by_role("tab", name=re.compile(tab_label, re.I))
    if tab_loc.count() == 0:
        tab_loc = frame.get_by_text(re.compile(tab_label, re.I))
    if tab_loc.count() == 0:
        tab_loc = frame.locator("button").filter(has_text=re.compile(tab_label, re.I))
    if tab_loc.count() > 0 and tab_loc.first.is_visible():
        tab_loc.first.click()
        log.info("Clicked tab: %s", tab_label)
        page.wait_for_timeout(800)
    else:
        log.warning("Tab %s not found", tab_label)
        result.failed = len(targets)
        return result

    go_get_it_links = frame.get_by_role("link", name=re.compile("Go Get It", re.I))
    go_get_it_btns = frame.get_by_role("button", name=re.compile("Go Get It", re.I))
    n_links = go_get_it_links.count()
    n_btns = go_get_it_btns.count()
    use_links = n_links >= n_btns and n_links > 0
    total_go_get_it = max(n_links, n_btns)

    for i, target in enumerate(targets[:10]):
        idx = int(target.selector) if target.selector.isdigit() else i
        if idx >= total_go_get_it:
            log.warning("Target index %d out of range (max %d); skipping", idx, total_go_get_it)
            result.failed += 1
            continue

        loc = go_get_it_links.nth(idx) if use_links else go_get_it_btns.nth(idx)

        # 1) Click row GO GET IT (force=True if needed)
        log.info("Clicking GO GET IT target %d/%d: %s", i + 1, len(targets), target.name or f"item_{i+1}")
        try:
            loc.click()
        except Exception:
            loc.click(force=True)

        # 2) Open modal (use .last for latest)
        try:
            modal = _open_modal(page)
        except Exception as e:
            log.warning("Download Files modal did not appear: %s", e)
            result.failed += 1
            continue
        log.info("Opened Download Files modal")

        try:
            # Wait for filename or "Your files are ready for download" (12s)
            if not _wait_for_content(page, modal, timeout=12000):
                _close_modal(modal)
                log.info("Content not ready, re-clicking GO GET IT and retrying")
                loc.click(force=True)
                try:
                    modal = _open_modal(page)
                except Exception as e:
                    log.warning("Modal did not reappear after retry: %s", e)
                    result.failed += 1
                    continue
                if not _wait_for_content(page, modal, timeout=12000):
                    page.screenshot(path=f"debug_modal_{i}.png")
                    log.info("Screenshot saved to debug_modal_%d.png", i)
                    try:
                        modal_text = modal.inner_text()
                        log.warning(
                            "Filename/ready not found after retry. Modal text (first 500 chars): %s",
                            modal_text[:500] if modal_text else "(empty)",
                        )
                    except Exception:
                        pass
                    result.failed += 1
                    continue

            # Locate filename elements, log count, use first
            file_els = modal.locator(r"text=/\.(pdf|docx?|xlsx?|zip)$/i")
            file_count = file_els.count()
            log.info("Filename elements found: %d", file_count)
            if file_count == 0:
                page.screenshot(path=f"debug_modal_{i}.png")
                log.info("Screenshot saved to debug_modal_%d.png", i)
                try:
                    modal_text = modal.inner_text()
                    log.warning(
                        "No filename element. Modal text (first 500 chars): %s",
                        modal_text[:500] if modal_text else "(empty)",
                    )
                except Exception:
                    pass
                result.failed += 1
                continue

            file_el = file_els.first

            # Log modal text snippet
            try:
                modal_text = modal.inner_text()
                log.info("Modal text snippet: %s", modal_text[:300] if modal_text else "(empty)")
            except Exception:
                pass

            path = None
            for attempt in range(2):
                try:
                    with page.expect_download(timeout=20000) as d:
                        el_text = file_el.inner_text().strip()
                        log.info("Clicking filename element: %s", el_text)
                        file_el.click(force=True)
                    download = d.value
                    suggested = download.suggested_filename or f"document_{i+1}"
                    base, ext = os.path.splitext(suggested)
                    if not ext:
                        ext = ".bin"
                    safe_base = _safe_filename(base)
                    stem = safe_base
                    out_path = os.path.join(out_dir, stem + ext)
                    n = 1
                    while os.path.exists(out_path):
                        out_path = os.path.join(out_dir, f"{safe_base}_{n}{ext}")
                        n += 1
                    download.save_as(out_path)
                    path = out_path
                    log.info("Saved file: %s", path)
                    break
                except Exception as e:
                    log.warning("Download failed (attempt %d): %s", attempt + 1, e)
                    if attempt == 0:
                        page.wait_for_timeout(500)

            if path:
                result.succeeded += 1
                result.saved_paths.append(path)
            else:
                result.failed += 1
        finally:
            _close_modal(modal)
            log.info("Closed modal")

    return result


def _close_modal(modal) -> None:
    """Close Download Files modal and wait for it to be hidden."""
    try:
        close_btn = modal.get_by_role("button", name=re.compile("Close", re.I)).first
        if close_btn.count() > 0:
            close_btn.click(force=True)
        modal.wait_for(state="hidden", timeout=10000)
    except Exception:
        pass
