"""Page navigation helpers."""
import re
from playwright.sync_api import TimeoutError as PWTimeout
from ..config import START_URL
from ..browser import accept_cookies
from ..notifications import log


def goto_start(page):
    """Navigate to the start page."""
    page.goto(START_URL)
    accept_cookies(page)

    # Intro pages often expose a "Weiter/Termin" button
    for pat in ["Weiter", "Termin", "Starten"]:
        try:
            page.get_by_role("button", name=re.compile(pat, re.I)).click(timeout=1500)
            break
        except PWTimeout:
            pass


def click_aufenthaltsangelegenheiten(page):
    """Click the current Ausländerbehörde entry point."""
    log("Opening the Ausländerbehörde entry point...")

    # Wait for the page to stabilise
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)

    try:
        body_text = page.locator("body").inner_text(timeout=2000)
    except Exception:
        body_text = ""

    if "Auswahl des Anliegens" in body_text:
        log("Already on the Anliegen selection page")
        return True

    try:
        department_buttons = page.locator("button.select_mdt_btn")
        if department_buttons.count() == 1:
            button = department_buttons.first
            if button.is_visible(timeout=2000):
                label = (button.inner_text() or "").strip()
                button.click()
                log(f"Clicked single department button: {label}")
                page.wait_for_timeout(2000)
                return True
    except Exception as exc:
        log(f"Failed to use the single department shortcut: {exc}")

    # Try multiple selectors to maximise compatibility across TEVIS variants.
    selectors = [
        'button:has-text("Ausländer- und Staatsangehörigkeitsbehörde")',
        'button:has-text("Ausländerbehörde")',
        'button:has-text("Ausländer")',
        'text=Aufenthaltsangelegenheiten',
        '[href*="aufenthalt"]',
        'a:has-text("Aufenthaltsangelegenheiten")',
        'button:has-text("Aufenthaltsangelegenheiten")',
    ]

    for selector in selectors:
        try:
            element = page.locator(selector).first
            if element.is_visible(timeout=2000):
                element.click()
                page.wait_for_timeout(2000)
                return True
        except Exception as e:
            log(f"Failed using selector {selector}: {e}")
            continue

    raise Exception("Could not find the Ausländerbehörde entry point")
