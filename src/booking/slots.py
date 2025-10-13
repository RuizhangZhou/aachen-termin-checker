"""Slot discovery and booking helpers."""
from typing import List, Tuple
from playwright.sync_api import Locator
from ..notifications import log


def _extract_slots_from_calendar(page) -> List[Tuple[str, str, Locator]]:
    """Parse the booking calendar and return a list of (date, time, button)."""
    slots: List[Tuple[str, str, Locator]] = []

    accordion_headers = page.locator("#sugg_accordion > h3")
    header_count = accordion_headers.count()
    if header_count == 0:
        return slots

    for idx in range(header_count):
        header = accordion_headers.nth(idx)
        date_text = (header.text_content() or "").strip()
        panel_id = header.get_attribute("aria-controls")
        if not panel_id:
            continue

        panel = page.locator(f"#{panel_id}")
        buttons = panel.locator("button.suggest_btn:not([disabled])")
        button_count = buttons.count()

        for btn_idx in range(button_count):
            button = buttons.nth(btn_idx)
            time_text = (button.text_content() or button.get_attribute("title") or "").strip()
            if not time_text:
                continue
            slots.append((date_text, time_text, button))

    return slots


def find_and_click_first_slot(page, monitor_only=False):
    """Find and optionally click the first available slot."""
    log("Checking available slots...")
    page.wait_for_timeout(2000)

    try:
        # Wait for the slot accordion to load
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)

        parsed_slots = _extract_slots_from_calendar(page)

        if parsed_slots:
            formatted_slots = [f"{date} {time}".strip() for date, time, _ in parsed_slots]

            if monitor_only:
                log(f"Found {len(formatted_slots)} available slots: {formatted_slots[:5]}")
                return formatted_slots

            # Click the first available slot
            first_date, first_time, first_button = parsed_slots[0]
            slot_label = f"{first_date} {first_time}".strip()
            try:
                first_button.click()
                log(f"Clicked slot: {slot_label}")
                page.wait_for_timeout(2000)
                return True
            except Exception as e:
                log(f"Error while clicking slot {slot_label}: {e}")
                page.wait_for_timeout(1000)
                parsed_slots = []  # continue with fallback logic

        if not parsed_slots:
            # Fall back to legacy selectors to cover potential page variants
            slot_selectors = [
                'button:not([disabled]):has-text("Uhr")',
                'button.suggest_btn:not([disabled])',
                'a[href*="slot"]:not(.disabled)',
                'button.available',
                'td.available button',
                '.calendar-slot:not(.disabled)',
                'button[data-time]:not([disabled])'
            ]

            fallback_slots = []
            for selector in slot_selectors:
                try:
                    slots = page.locator(selector).all()
                    for slot in slots:
                        if slot.is_visible():
                            slot_text = slot.text_content() or ""
                            if slot_text and (":" in slot_text or "uhr" in slot_text.lower()):
                                slot_label = slot_text.strip()
                                fallback_slots.append(slot_label)
                                if not monitor_only:
                                    slot.click()
                                    log(f"Clicked slot: {slot_label}")
                                    page.wait_for_timeout(2000)
                                    return True
                    if fallback_slots:
                        break
                except Exception as e:
                    log(f"Error while checking slot selector {selector}: {e}")
                    continue

            if fallback_slots:
                log(f"Found {len(fallback_slots)} available slots: {fallback_slots[:5]}")
                return fallback_slots if monitor_only else True

    except Exception as e:
        log(f"Error while discovering slots: {e}")

    log("No slots currently available.")
    return [] if monitor_only else False


def check_availability():
    """Check availability using the simplified legacy flow."""
    from ..browser import BrowserManager
    from ..config import ANLIEGEN, STANDORT
    from .navigation import goto_start, click_aufenthaltsangelegenheiten

    with BrowserManager(headless=True) as page:
        try:
            # Navigate to the start page
            goto_start(page)

            # Click the Aufenthaltsangelegenheiten entrypoint
            click_aufenthaltsangelegenheiten(page)

            # Use the simplified legacy logic directly
            log("Searching for the RWTH option...")

            # Wait for the page to load fully
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)

            # Scroll to the bottom to ensure everything loads
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)

            target_input = page.locator(f'input[data-tevis-cncname="{ANLIEGEN}"]').first

            if target_input.count() == 0:
                log(f"Option not found: {ANLIEGEN}")
                return []

            # Select the option - use JavaScript if visibility blocks interaction
            try:
                target_input.fill("1")
                log(f"Selected: {ANLIEGEN}")
            except Exception as e:
                log(f"Standard fill failed, trying JavaScript: {e}")
                # Use JavaScript to set the value directly
                page.evaluate(f"""
                    const input = document.querySelector('input[data-tevis-cncname="{ANLIEGEN}"]');
                    if (input) {{
                        input.value = '1';
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                """)
                log(f"Selected via JavaScript: {ANLIEGEN}")

            page.wait_for_timeout(1000)

            # Click the continue button
            try:
                weiter_btn = page.get_by_role("button", name="Weiter")
                weiter_btn.click()
                log("Successfully clicked the Weiter button")
            except Exception as e:
                log(f"Failed to click the Weiter button: {e}")

            # Wait for the location page to load
            page.wait_for_timeout(2000)

            # Simplified location selection - choose the first available option
            try:
                first_location = page.locator('input[type="radio"], input[type="checkbox"]').first
                if first_location.count() > 0:
                    first_location.click()
                    log("Selected a location")
                    page.wait_for_timeout(1000)

                    # Continue to the slot calendar
                    weiter_btn = page.get_by_role("button", name="Weiter")
                    weiter_btn.click()
                    log("Clicked the Weiter button on the location page")
            except Exception as e:
                log(f"Failed to select a location: {e}")

            # Check the availability calendar again
            available_slots = find_and_click_first_slot(page, monitor_only=True)
            return available_slots if available_slots else []

        except Exception as e:
            log(f"Error while checking availability: {e}")
            return []
