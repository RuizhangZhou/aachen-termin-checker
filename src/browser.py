"""Core browser helpers."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from .config import STORAGE_STATE
from .notifications import log


class BrowserManager:
    """Browser manager context helper."""

    def __init__(self, headless=True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        self.playwright = sync_playwright()
        self.p = self.playwright.__enter__()
        self.browser = self.p.chromium.launch(headless=self.headless)

        ctx_kwargs = {}
        if Path(STORAGE_STATE).exists():
            ctx_kwargs["storage_state"] = STORAGE_STATE

        self.context = self.browser.new_context(**ctx_kwargs)
        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)

        return self.page

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.__exit__(exc_type, exc_val, exc_tb)


def accept_cookies(page):
    """Accept site cookies when banners appear."""
    for pat in ["Einverstanden", "Akzept", "Zustimmen", "Okay"]:
        try:
            page.get_by_role("button", name=re.compile(pat, re.I)).click(timeout=2500)
            return
        except PWTimeout:
            continue


def handle_modal_dialog(page):
    """Handle modal dialogs that block progress."""
    log("Modal dialog detected, attempting to handle it...")

    # Try to click through common confirmation buttons
    confirm_patterns = [
        "Verstanden", "OK", "Schließen", "Weiter", "Bestätigen",
        "Ja", "Akzeptieren", "Fortfahren", "Continue"
    ]

    for pattern in confirm_patterns:
        try:
            # First attempt to click via button text
            button = page.locator(f'button:has-text("{pattern}")').first
            if button.is_visible(timeout=1000):
                button.click()
                log(f"Clicked modal confirmation button: {pattern}")
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    # Fall back to clicking any button inside the modal
    try:
        modal_buttons = page.locator('.modal button, [role="dialog"] button, .dialog button').all()
        for button in modal_buttons:
            if button.is_visible():
                button.click()
                log("Clicked a button inside the modal dialog")
                page.wait_for_timeout(1000)
                return True
    except Exception:
        pass

    # Finally, try hitting Escape to dismiss it
    try:
        page.keyboard.press("Escape")
        log("Pressed Escape to dismiss the modal dialog")
        page.wait_for_timeout(1000)
        return True
    except Exception:
        pass

    log("Unable to handle the modal dialog")
    return False
