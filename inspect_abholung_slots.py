#!/usr/bin/env python3
"""Inspect the Abholung Aufenthaltserlaubnis flow and dump available slots."""
from pathlib import Path

from src.browser import BrowserManager, handle_modal_dialog
from src.booking.navigation import goto_start, click_aufenthaltsangelegenheiten
from src.notifications import log, send_success_notification

ANLIEGEN_TEXT = "Abholung Aufenthaltserlaubnis"


def set_anliegen(page, name: str, count: int = 1) -> None:
    """Set the requested Anliegen via JavaScript to bypass visibility quirks."""
    locator = page.locator(f"input[data-tevis-cncname=\"{name}\"]").first
    if locator.count() == 0:
        raise RuntimeError(f"Option not found: {name}")

    locator.evaluate(
        "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }",
        str(count),
    )


def click_next(page, attempts: int = 3) -> None:
    """Click the Weiter button, handling modal dialogs if necessary."""
    for _ in range(attempts):
        handle_modal_dialog(page)
        button = page.get_by_role("button", name="Weiter")
        if button.count() == 0:
            raise RuntimeError("Could not find the Weiter button")
        try:
            button.click(timeout=3000)
            page.wait_for_timeout(1000)
            return
        except Exception:
            page.wait_for_timeout(1000)
    raise RuntimeError("Failed to click the Weiter button")


def collect_slots(page) -> list[dict[str, str]]:
    """Collect available slots as a list of {date, time}."""
    slots = []
    accordions = page.locator("#sugg_accordion > h3")
    for idx in range(accordions.count()):
        header = accordions.nth(idx)
        date_text = (header.text_content() or "").strip()
        panel_id = header.get_attribute("aria-controls")
        if not panel_id:
            continue
        panel = page.locator(f"#{panel_id}")
        buttons = panel.locator("button.suggest_btn:not([disabled])")
        for i in range(buttons.count()):
            time_text = (buttons.nth(i).text_content() or "").strip()
            if time_text:
                slots.append({"date": date_text, "time": time_text})
    return slots


def main() -> None:
    with BrowserManager(headless=True) as page:
        goto_start(page)
        click_aufenthaltsangelegenheiten(page)

        page.wait_for_load_state('networkidle')
        set_anliegen(page, ANLIEGEN_TEXT)
        page.wait_for_timeout(500)

        click_next(page)
        click_next(page)

        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)

        slots = collect_slots(page)
        if not slots:
            log("No available Abholung slots detected.")
        else:
            total = len(slots)
            log(f"Detected {total} Abholung slots:")
            preview_limit = 30
            for item in slots[:preview_limit]:
                log(f"- {item['date']} {item['time']}")
            if total > preview_limit:
                log(f"...omitted the remaining {total - preview_limit} slots")

            notify_limit = 10
            preview = ", ".join(f"{item['date']} {item['time']}" for item in slots[:notify_limit])
            message = (
                f"📋 Abholung test: found {total} available slots."
                + (f" First {notify_limit}: {preview}" if preview else "")
            )
            send_success_notification(message)

        # Dump a screenshot for visual confirmation
        page.screenshot(path="abholung_slots_headless.png", full_page=True)
        log(f"Saved screenshot: {Path('abholung_slots_headless.png').resolve()}")


if __name__ == "__main__":
    main()
