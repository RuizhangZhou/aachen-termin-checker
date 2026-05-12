"""Core browser helpers."""
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from .config import STORAGE_STATE
from .notifications import log


class BrowserManager:
    """Browser manager context helper."""

    def __init__(self, headless=True):
        self.headless = headless
        self.launch_attempts = 3
        self.playwright = None
        self.p = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        last_exc = None
        for attempt in range(1, self.launch_attempts + 1):
            try:
                self.playwright = sync_playwright()
                self.p = self.playwright.__enter__()
                self.browser = self.p.chromium.launch(
                    headless=self.headless,
                    args=["--disable-gpu"],
                )

                ctx_kwargs = {}
                if Path(STORAGE_STATE).exists():
                    ctx_kwargs["storage_state"] = STORAGE_STATE

                self.context = self.browser.new_context(**ctx_kwargs)
                self.page = self.context.new_page()
                self.page.set_default_timeout(15000)

                return self.page
            except Exception as exc:
                last_exc = exc
                brief = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
                log(
                    "Browser launch/setup attempt "
                    f"{attempt}/{self.launch_attempts} failed: {brief}"
                )
                self._cleanup(None, None, None)
                if attempt < self.launch_attempts:
                    time.sleep(2 * attempt)

        raise last_exc

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup(exc_type, exc_val, exc_tb)

    def _cleanup(self, exc_type, exc_val, exc_tb):
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
        self.page = None
        if self.playwright:
            try:
                self.playwright.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass
            self.playwright = None
            self.p = None


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
    modal_locators = '.modal-dialog, [role="dialog"], .modal.in'
    modal = page.locator(modal_locators).first
    has_modal = False
    try:
        has_modal = modal.count() > 0 and modal.is_visible(timeout=500)
    except Exception:
        has_modal = False

    if not has_modal:
        # Fallback: look for common OK buttons even if the dialog wrapper is missing
        try:
            ok_button = page.locator('button#OKButton, button.btn-ok, button:has-text("OK")').first
            has_modal = ok_button.is_visible(timeout=500)
        except Exception:
            has_modal = False

    if not has_modal:
        return False

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
