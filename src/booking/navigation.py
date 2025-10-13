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
    """Click the Aufenthaltsangelegenheiten entry."""
    log("Clicking Aufenthaltsangelegenheiten...")

    # Wait for the page to stabilise
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Try multiple selectors to maximise compatibility
    selectors = [
        'text=Aufenthaltsangelegenheiten',
        '[href*="aufenthalt"]',
        'a:has-text("Aufenthaltsangelegenheiten")',
        'button:has-text("Aufenthaltsangelegenheiten")'
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

    raise Exception("Could not find the Aufenthaltsangelegenheiten link")
