"""Service and location selection helpers."""
import re
from playwright.sync_api import TimeoutError as PWTimeout
from ..browser import handle_modal_dialog
from ..notifications import log


def select_anliegen(page, text, count=1):
    """Select the requested service."""
    log(f"Searching for option: {text}")

    # Wait for the page to finish loading
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Scroll to the bottom to ensure lazy-loaded elements appear
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)

    # Capture a screenshot for debugging
    page.screenshot(path='debug_select_anliegen.png', full_page=True)
    log("Saved page screenshot: debug_select_anliegen.png")

    # Find all inputs and iterate to match the requested option
    inputs = page.locator('input[data-tevis-cncname]').all()
    log(f"Found {len(inputs)} options")

    # List all options for debugging
    for i, inp in enumerate(inputs):
        try:
            cnc_name = inp.get_attribute('data-tevis-cncname')
            log(f"Option {i}: {cnc_name}")
        except:
            pass

    found = False
    for i, inp in enumerate(inputs):
        try:
            cnc_name = inp.get_attribute('data-tevis-cncname')
            if cnc_name and text == cnc_name:  # use exact match
                # Scroll to the element
                inp.scroll_into_view_if_needed()
                inp.fill(str(count))
                log(f"Selected {cnc_name} with count {count}")
                found = True
                break
        except Exception as e:
            log(f"Error processing option {i}: {e}")
            continue

    if not found:
        error_msg = f"Option not found: {text}"
        from ..notifications import send_error_notification
        send_error_notification(f"Failed to select service - {error_msg}")
        raise Exception(error_msg)

    # Handle potential modal dialogs before clicking Weiter
    max_attempts = 5
    for attempt in range(max_attempts):
        # Dismiss modal dialogs if they appear
        handle_modal_dialog(page)
        page.wait_for_timeout(500)

        try:
            # Try clicking the Weiter button
            weiter_btn = page.get_by_role("button", name=re.compile("Weiter", re.I))
            if weiter_btn.is_visible() and weiter_btn.is_enabled():
                weiter_btn.click(timeout=3000)
                log("Successfully clicked the Weiter button")
                break
        except PWTimeout:
            if attempt < max_attempts - 1:
                log(f"Weiter button click failed, attempt {attempt + 2}...")
                # Try to force the click via JavaScript
                try:
                    page.evaluate("""
                        const weiterBtn = document.getElementById('WeiterButton') ||
                                         document.querySelector('input[value="Weiter"]') ||
                                         document.querySelector('button[title*="Weiter"]');
                        if (weiterBtn) {
                            weiterBtn.click();
                        }
                    """)
                    log("Clicked the Weiter button via JavaScript")
                    break
                except Exception as e:
                    log(f"JavaScript click failed: {e}")
            else:
                log("All attempts to click the Weiter button failed")
                break

    log("Handled modal dialogs and submitted the form")


def select_standort(page, text):
    """Select the location."""
    log("Selecting location...")
    page.wait_for_timeout(2000)

    # Check for and dismiss modal dialogs
    handle_modal_dialog(page)

    # Wait for the page to load
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Locate the available site options
    inputs = page.locator('input[type="radio"], input[type="checkbox"]').all()
    log(f"Found {len(inputs)} location options")

    found = False
    for inp in inputs:
        try:
            # Get the associated label text
            label_text = ""
            inp_id = inp.get_attribute('id')
            if inp_id:
                try:
                    label = page.locator(f'label[for="{inp_id}"]')
                    if label.count() > 0:
                        label_text = label.text_content() or ""
                except:
                    pass

            # If there is no label, fall back to the parent element text
            if not label_text:
                try:
                    parent_text = inp.locator('xpath=..').text_content() or ""
                    label_text = parent_text
                except:
                    pass

            log(f"Inspecting location option: {label_text}")
            if text.lower() in label_text.lower():
                log(f"Selected location: {label_text}")
                inp.click()
                page.wait_for_timeout(1000)
                found = True
                break
        except Exception as e:
            log(f"Error while selecting location: {e}")
            continue

    if not found:
        # No match found; fall back to the first available option
        log("No matching location found, selecting the first option")
        try:
            first_input = page.locator('input[type="radio"], input[type="checkbox"]').first
            if first_input.is_visible():
                first_input.click()
                log("Selected the first location option")
                found = True
        except Exception as e:
            log(f"Failed to select the first location option: {e}")

    if not found:
        raise Exception(f"No matching location option found: {text}")

    # Click the continue/submit button
    page.wait_for_timeout(2000)
    try:
        weiter_button = page.get_by_role("button", name="Weiter")
        if weiter_button.is_visible(timeout=3000):
            weiter_button.click()
            log("Successfully clicked the Weiter button")
        else:
            # Try other submit buttons
            buttons = page.locator('input[type="submit"], button[type="submit"]').all()
            for btn in buttons:
                if btn.is_visible():
                    btn.click()
                    log("Clicked a submit button")
                    break
    except Exception as e:
        log(f"Failed to click the Weiter button: {e}")
