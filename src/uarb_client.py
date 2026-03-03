# uarb_client.py
"""Playwright client for UARB Nova Scotia WebDirect."""

import logging
import platform
import re

from playwright.sync_api import Frame, Locator, Page, sync_playwright

from .models import DOCUMENT_TYPES, DOC_TYPE_TO_TAB, DownloadTarget, MatterSummary

log = logging.getLogger(__name__)

UARB_URL = "https://uarb.novascotia.ca/fmi/webd/UARB15"


def _pick_nearest_search_button(card_locator: Locator, field_locator: Locator) -> Locator | None:
    """
    Within card, pick the visible Search button with smallest vertical distance to field.
    Returns the chosen Locator or None. Excludes navbar (button must be inside card).
    """
    try:
        field_box = field_locator.first.bounding_box()
    except Exception:
        field_box = None
    search_btns = card_locator.get_by_role("button", name=re.compile("Search", re.I))
    n = search_btns.count()
    if n == 0:
        return None
    if n == 1:
        return search_btns.first
    candidates: list[tuple[float, Locator]] = []
    for i in range(n):
        btn = search_btns.nth(i)
        try:
            if not btn.is_visible():
                continue
            box = btn.bounding_box()
            if not box or not field_box:
                candidates.append((0.0, btn))
                continue
            field_center_y = field_box["y"] + field_box["height"] / 2
            btn_center_y = box["y"] + box["height"] / 2
            dist = abs(btn_center_y - field_center_y)
            candidates.append((dist, btn))
        except Exception:
            candidates.append((float("inf"), btn))
    if not candidates:
        return search_btns.first
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _get_working_frame(page: Page) -> Frame:
    """
    Detect if the app is inside an iframe and return the frame to operate on.
    Debug: log frame URLs and textbox counts per frame.
    """
    page.wait_for_load_state("domcontentloaded")

    frames = page.frames
    for i, frame in enumerate(frames):
        url = frame.url
        n_textboxes = frame.get_by_role("textbox").count()
        log.info("Frame %d: url=%s, textboxes=%d", i, url or "(main)", n_textboxes)

    # Prefer main frame if it has textboxes
    if page.main_frame.get_by_role("textbox").count() > 0:
        log.info("Using main frame")
        return page.main_frame

    # Look for iframe that contains the app (has "Go Directly to Matter" placeholder or textboxes)
    for frame in page.frames[1:]:
        try:
            n = frame.get_by_role("textbox").count()
            if n > 0:
                # Check if this frame has the matter input
                try:
                    inp = frame.get_by_placeholder("Go Directly to Matter")
                    if inp.count() > 0:
                        log.info("Using iframe with url=%s (has Go Directly to Matter)", frame.url)
                        return frame
                except Exception:
                    pass
                # First iframe with textboxes as fallback
                log.info("Using iframe with url=%s (has %d textboxes)", frame.url, n)
                return frame
        except Exception as e:
            log.debug("Frame %s: %s", frame.url, e)

    log.info("Defaulting to main frame")
    return page.main_frame


def goto_matter(page: Page, matter_number: str) -> tuple[Frame | None, bool]:
    """
    Load page, find frame, find "Go Directly to Matter" textbox, fill, submit.
    Returns (working_frame, not_found) where not_found=True if matter search returned no results.
    """
    # Attach diagnostic listeners before navigation
    page.on("console", lambda msg: log.info("CONSOLE[%s]: %s", msg.type, msg.text))
    page.on("pageerror", lambda err: log.error("PAGEERROR: %s", err))
    page.on("requestfailed", lambda req: log.warning("REQFAILED: %s - %s", req.url, req.failure))
    page.on(
        "response",
        lambda res: log.warning("RESPONSE %d: %s", res.status, res.url)
        if (res.status < 200 or res.status >= 400) else None,
    )

    log.info("Navigating to %s", UARB_URL)
    page.goto(UARB_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(15000)

    page.screenshot(path="debug_uarb_15s.png", full_page=True)
    log.info("Screenshot saved to debug_uarb_15s.png")
    with open("debug_page_15s.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    log.info("Page HTML saved to debug_page_15s.html")

    # Debug: iframe count and first iframe details
    n_iframes = page.locator("iframe").count()
    log.info("iframe count: %d", n_iframes)
    if n_iframes > 0:
        first_iframe = page.locator("iframe").first
        try:
            src = first_iframe.get_attribute("src") or "(none)"
            elem_id = first_iframe.get_attribute("id") or "(none)"
            elem_class = first_iframe.get_attribute("class") or "(none)"
            elem_name = first_iframe.get_attribute("name") or "(none)"
            log.info("First iframe: src=%s, id=%s, class=%s, name=%s",
                     src, elem_id, elem_class, elem_name)
            outer = first_iframe.evaluate("el => el.outerHTML") or ""
            log.info("First iframe outerHTML (truncated): %s", outer[:500])
        except Exception as e:
            log.debug("Could not get first iframe attributes: %s", e)

    # Re-log frame URLs after wait
    for i, f in enumerate(page.frames):
        log.info("Frame %d URL (after 15s wait): %s", i, f.url or "(main)")

    # Save main page HTML
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    log.info("Page HTML saved to debug_page.html")

    # Debug: DOM element counts
    n_inputs = page.locator("input").count()
    n_textareas = page.locator("textarea").count()
    n_contenteditable = page.locator("[contenteditable=\"true\"]").count()
    log.info("Main frame: <input>=%d, <textarea>=%d, [contenteditable=true]=%d, <iframe>=%d",
             n_inputs, n_textareas, n_contenteditable, n_iframes)

    page.wait_for_load_state("domcontentloaded", timeout=10000)

    # 1) card = Go Directly to Matter card: must include "Go Directly to Matter" AND visible text /eg\s*M0?\d+/i
    eg_pattern = re.compile(r"eg\s*M0?\d+", re.I)
    header = page.get_by_text("Go Directly to Matter", exact=False).first
    if header.count() == 0:
        log.warning("UI_LOCATION_FAILED: Could not find 'Go Directly to Matter' heading")
        page.screenshot(path="debug_uarb.png", full_page=True)
        return None, True
    card = None
    for i in range(1, 10):
        anc = header.locator(f"xpath=ancestor::*[self::div or self::section][{i}]")
        if anc.count() == 0:
            break
        try:
            anc_text = anc.first.inner_text()
            has_heading = "Go Directly to Matter" in anc_text
            has_eg = bool(eg_pattern.search(anc_text))
            if has_heading and has_eg and anc.get_by_role("button", name=re.compile("Search", re.I)).count() > 0:
                card = anc
                break
        except Exception:
            pass
    if card is None or card.count() == 0:
        card = header.locator("xpath=ancestor::*[self::div or self::section][1]")
    if card.count() == 0:
        card = header.locator("xpath=ancestor::*[1]")

    try:
        card_text = card.first.inner_text()
        log.info("Card text includes 'Go Directly to Matter': %s, eg placeholder: %s",
                 "Go Directly to Matter" in card_text, bool(eg_pattern.search(card_text)))
    except Exception:
        pass

    # 2) Field: click 'eg M01234' text then keyboard.type; fallback to first focusable in card
    eg_text = card.get_by_text(eg_pattern).first
    field_clicked = False
    if eg_text.count() > 0 and eg_text.first.is_visible():
        try:
            eg_text.click()
            field_clicked = True
            log.info("Clicked 'eg M01234' placeholder text")
        except Exception:
            pass
    if not field_clicked:
        focusable = card.locator("input, textarea, [tabindex='0'], [contenteditable='true']").first
        if focusable.count() > 0 and focusable.first.is_visible():
            try:
                focusable.click()
                field_clicked = True
                log.info("Clicked first focusable element in card")
            except Exception:
                pass
    if not field_clicked:
        log.warning("UI_LOCATION_FAILED: Could not focus matter input (eg text or focusable)")
        page.screenshot(path="debug_uarb.png", full_page=True)
        return None, True

    select_all = "Meta+a" if platform.system() == "Darwin" else "Control+a"
    page.keyboard.press(select_all)
    page.keyboard.press("Backspace")
    page.keyboard.type(matter_number)
    log.info("Entered matter %s (cleared + typed)", matter_number)

    # 3) search_btn = within card, pick nearest Search button
    field_for_btn = card.get_by_text(eg_pattern).first
    if field_for_btn.count() == 0:
        field_for_btn = card.locator("input, textarea, [tabindex='0']").first
    search_btn = _pick_nearest_search_button(card, field_for_btn)
    log.info("Search buttons in card: 1 chosen (nearest to field)")

    # 4) Click Search button
    if search_btn and search_btn.count() > 0:
        search_btn.click()
        log.info("Clicked Search button (nearest to field)")
    else:
        log.warning("UI_LOCATION_FAILED: No Search button in card, pressing Enter")
        page.keyboard.press("Enter")

    frame = page.main_frame

    # 5) Wait for tab buttons (Label - N pattern); success if >= 5
    tab_buttons_loc = frame.locator("button").filter(has_text=re.compile(r".+\s-\s\d+"))
    try:
        tab_buttons_loc.nth(4).wait_for(state="visible", timeout=15000)
        log.info("Tab buttons visible (>=5) (search success)")
        return frame, False
    except Exception:
        pass

    # Fallback: check for matter heading in body
    page.wait_for_load_state("domcontentloaded", timeout=5000)
    page_text = ""
    try:
        page_text = page.locator("body").first.inner_text()
    except Exception:
        pass
    page_text_lower = page_text.lower()

    matter_heading = re.search(r"matter\s+no\.?\s*[:\s]*[Mm]\d{4,}", page_text, re.I)
    tabs_by_role = tab_buttons_loc.count() >= 5
    if matter_heading or tabs_by_role:
        log.info("Search success: matter_heading=%s, tabs_by_role=%s", bool(matter_heading), tabs_by_role)
        return frame, False

    # Not-found only if explicit message (do not treat UI location failures as matter not found)
    not_found_patterns = ["no records found", "no results", "matter not found"]
    for pat in not_found_patterns:
        if pat in page_text_lower:
            log.info("Matter not found: '%s' detected", pat)
            return frame, True

    # Page still on search screen
    still_on_search = "Go Directly to Matter" in page_text and not tabs_by_role
    if still_on_search:
        log.warning("Page remains on search screen; treating as not found")
        return frame, True

    log.info("Page changed; assuming success")
    return frame, False


def fetch_matter_metadata_and_counts(matter_number: str) -> MatterSummary:
    """
    Open UARB, search matter, scrape title + metadata + counts per doc type.
    Returns MatterSummary with not_found=True if matter not found.
    """
    counts = {dt: 0 for dt in DOCUMENT_TYPES}
    metadata: dict[str, str] = {}
    title = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()

        try:
            frame, not_found = goto_matter(page, matter_number)
            if not frame or not_found:
                return MatterSummary(
                    matter_id=matter_number,
                    title="",
                    counts=counts,
                    metadata={"error": "Could not navigate or matter not found"},
                    not_found=True,
                )

            # Scrape title - look for prominent heading or matter title area (use frame)
            title_selectors = ["h1", "h2", '[class*="title" i]', '[class*="matter" i]', "td"]
            for sel in title_selectors:
                els = frame.locator(sel).all()
                for el in els[:20]:  # limit scan
                    try:
                        t = el.inner_text().strip()
                        if matter_number.upper() in t.upper() and len(t) < 200:
                            title = t
                            log.info("Found title via %s: %s", sel, title[:80])
                            break
                        if t and 10 < len(t) < 150 and not title:
                            title = t
                    except Exception:
                        pass
                if title:
                    break

            if not title:
                title = f"Matter {matter_number}"
                log.info("No explicit title found, using: %s", title)

            # Scrape metadata (dates, category, amount) - look for label: value pairs
            meta_pattern = re.compile(
                r"(date|category|amount|status|filed|filing)\s*[:：]\s*(.+?)",
                re.IGNORECASE,
            )
            for el in frame.locator("td, span, div, label, p").all()[:100]:
                try:
                    text = el.inner_text().strip()
                    m = meta_pattern.search(text)
                    if m:
                        metadata[m.group(1).lower()] = m.group(2).strip()[:100]
                except Exception:
                    pass

            if metadata:
                log.info("Metadata found: %s", metadata)

            # Tab discovery: buttons with "Label - N" pattern
            tab_buttons = frame.locator("button").filter(has_text=re.compile(r".+\s-\s\d+"))
            count = tab_buttons.count()
            log.info("Tab buttons count: %d", count)

            _TAB_COUNT_REGEX = re.compile(r"^(.*?)\s*-\s*(\d+)\s*$")
            _LABEL_TO_DOC_TYPE = [
                ("exhibit", "exhibits"),
                ("key", "key_documents"),
                ("other", "other_documents"),
                ("transcript", "transcripts"),
                ("record", "recordings"),
            ]

            discovered_tab_texts: list[str] = []
            for i in range(min(count, 20)):
                try:
                    txt = tab_buttons.nth(i).inner_text().strip()
                    txt = " ".join(txt.split())
                    discovered_tab_texts.append(txt)
                    m = _TAB_COUNT_REGEX.match(txt)
                    if not m:
                        continue
                    label = m.group(1).strip()
                    count_val = int(m.group(2))
                    label_lower = label.lower()
                    for keyword, doc_type in _LABEL_TO_DOC_TYPE:
                        if keyword in label_lower:
                            counts[doc_type] = count_val
                            break
                except Exception as e:
                    log.debug("Tab button %d: %s", i, e)

            log.info("Discovered tab button texts: %s", discovered_tab_texts)
            log.info("Extracted counts per canonical type: %s", counts)

            return MatterSummary(
                matter_id=matter_number,
                title=title,
                counts=counts,
                metadata=metadata,
                not_found=False,
            )

        except Exception as e:
            log.error("Navigation/scrape error: %s", e, exc_info=True)
            return MatterSummary(
                matter_id=matter_number,
                title="",
                counts=counts,
                metadata={"error": str(e)},
                not_found=True,
            )
        finally:
            browser.close()


def list_download_targets(
    matter_number: str, document_type: str, limit: int = 10
) -> list[DownloadTarget]:
    """
    Navigate to matter, select tab by document_type, collect up to limit
    items with "Go Get It". Return targets with name + selector for download.
    """
    targets: list[DownloadTarget] = []
    tab_label = DOC_TYPE_TO_TAB.get(document_type, document_type)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()

        try:
            frame, not_found = goto_matter(page, matter_number)
            if not frame or not_found:
                log.warning("Could not navigate to matter %s", matter_number)
                return []

            # Navigate to tab (robust locators)
            tab_loc = frame.get_by_role("tab", name=re.compile(tab_label, re.I))
            if tab_loc.count() == 0:
                tab_loc = frame.get_by_text(tab_label, exact=True)
            if tab_loc.count() == 0:
                tab_loc = frame.get_by_text(re.compile(tab_label, re.I))

            if tab_loc.count() > 0 and tab_loc.first.is_visible():
                tab_loc.first.click()
                log.info("Clicked tab: %s", tab_label)
                page.wait_for_timeout(800)
            else:
                log.warning("Tab %s not found", tab_label)
                return []

            # Collect "Go Get It" using get_by_role (no brittle CSS)
            go_get_it_links = frame.get_by_role("link", name="Go Get It")
            go_get_it_btns = frame.get_by_role("button", name="Go Get It")
            locs = list(go_get_it_links.all()) or list(go_get_it_btns.all())
            log.info("Go Get It elements found: %d (links=%d, buttons=%d)",
                     len(locs), go_get_it_links.count(), go_get_it_btns.count())

            for i, loc in enumerate(locs[:limit]):
                try:
                    name = loc.inner_text().strip() or f"document_{i + 1}"
                    # Store index for downloader to use frame.get_by_role(...).nth(i)
                    targets.append(DownloadTarget(name=name, selector=str(i)))
                except Exception as e:
                    log.debug("Could not get name for item %d: %s", i, e)

            log.info("Collected %d download targets for %s", len(targets), document_type)
            return targets

        except Exception as e:
            log.error("list_download_targets error: %s", e, exc_info=True)
            return []
        finally:
            browser.close()
