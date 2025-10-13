"""Form entry and captcha handling module."""
import re
from playwright.sync_api import TimeoutError as PWTimeout
from ..config import FIRST_NAME, LAST_NAME, EMAIL, PHONE, DATE_OF_BIRTH
from ..notifications import log


def proceed_until_personal(page, max_clicks=3):
    """Continue clicking until the personal information page is reached."""
    clicks = 0
    while clicks < max_clicks:
        try:
            # Check whether we already reached the personal information page
            if page.locator('input[name*="vorname"], input[name*="firstname"], input[name*="first"]').count() > 0:
                log("Reached the personal information page")
                return True

            # Try clicking any button that might mean "continue"
            continue_patterns = ["Weiter", "Fortfahren", "Bestätigen", "Buchen"]
            for pattern in continue_patterns:
                try:
                    button = page.get_by_role("button", name=re.compile(pattern, re.I))
                    if button.is_visible(timeout=2000):
                        button.click()
                        page.wait_for_timeout(2000)
                        clicks += 1
                        break
                except PWTimeout:
                    continue
            else:
                break
        except Exception as e:
            log(f"Error while navigating to the personal information page: {e}")
            break

    return clicks > 0


def fill_personal_data(page):
    """Fill in personal information."""
    log("Filling personal information...")

    # Fields to populate
    name_fields = [
        ('input[name*="vorname"], input[name*="firstname"], input[name*="first"]', FIRST_NAME),
        ('input[name*="nachname"], input[name*="lastname"], input[name*="last"], input[name*="name"]', LAST_NAME),
        ('input[name*="email"], input[type="email"]', EMAIL),
        ('input[name*="telefon"], input[name*="phone"], input[name*="tel"]', PHONE),
        ('input[name*="geburt"], input[name*="birth"], input[name*="dob"]', DATE_OF_BIRTH)
    ]

    for selector, value in name_fields:
        if value:  # only populate when a value is provided
            try:
                field = page.locator(selector).first
                if field.is_visible(timeout=2000):
                    field.clear()
                    field.fill(value)
                    log(f"Filled field: {selector} = {value}")
            except Exception as e:
                log(f"Error while filling field {selector}: {e}")

    log("Completed personal information entry")


def solve_captcha_human_in_loop(page):
    """Allow a human to solve the captcha and resume afterwards."""
    log("Captcha detected, manual resolution required...")

    # Capture a screenshot for manual review
    try:
        page.screenshot(path='captcha_screenshot.png')
        log("Saved captcha screenshot: captcha_screenshot.png")
    except Exception as e:
        log(f"Failed to save captcha screenshot: {e}")

    # Wait for the user to solve the captcha manually
    log("Please solve the captcha manually, then press Enter to continue...")
    input("Press Enter to continue...")

    log("Resuming the booking workflow...")
    return True
