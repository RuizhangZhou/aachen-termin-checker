"""Main entry module."""
import sys
from pathlib import Path

from .browser import BrowserManager
import json
import time
from datetime import datetime, timezone

from .config import (
    AUTO_BOOK,
    LOCK_FILE,
    ANLIEGEN,
    STANDORT,
    MONITOR_STATE_FILE,
    ALERT_CHANGE_ONLY,
    ALERT_MIN_INTERVAL_MINUTES,
)
from .notifications import log, send_error_notification, send_success_notification
from .booking.navigation import goto_start, click_aufenthaltsangelegenheiten
from .booking.selection import select_anliegen, select_standort
from .booking.slots import find_and_click_first_slot, check_availability
from .booking.forms import proceed_until_personal, fill_personal_data, solve_captcha_human_in_loop


def run_once(headless=True):
    """Execute the full booking workflow."""
    try:
        with BrowserManager(headless=headless) as page:
            # Navigate to the start page
            goto_start(page)

            # Click the Aufenthaltsangelegenheiten entry
            click_aufenthaltsangelegenheiten(page)

            # Step 2: select the service
            select_anliegen(page, ANLIEGEN, count=1)

            # Step 3: select the location
            select_standort(page, STANDORT)

            # Step 4: pick a slot
            if not find_and_click_first_slot(page):
                log("No slots currently available.")
                return False

            # Notify only when auto-booking is disabled
            if not AUTO_BOOK:
                send_success_notification("⚠️ Found available slots, but auto-booking is disabled. Please complete the booking manually.")
                return True

            # Avoid duplicate bookings by checking for the lock file
            if Path(LOCK_FILE).exists():
                log("Lock file detected; skipping booking to avoid duplicates")
                return True

            # Step 5: continue to the personal information page
            if not proceed_until_personal(page):
                send_error_notification("Unable to reach the personal information page")
                return False

            # Step 6: fill in personal data
            fill_personal_data(page)

            # Step 7: handle a captcha if present
            if page.locator('img[src*="captcha"], canvas, #captcha').count() > 0:
                if not solve_captcha_human_in_loop(page):
                    send_error_notification("Captcha handling failed")
                    return False

            # Final submission
            try:
                submit_button = page.get_by_role("button", name="Buchen")
                if submit_button.is_visible(timeout=5000):
                    submit_button.click()
                    page.wait_for_timeout(3000)

                    # Create the lock file to prevent duplicate bookings
                    Path(LOCK_FILE).touch()

                    send_success_notification("🎉 Booking confirmed! The automated flow completed successfully.")
                    log("Booking workflow completed")
                    return True
                else:
                    send_error_notification("Unable to locate the final submission button")
                    return False

            except Exception as e:
                send_error_notification("Error during final submission", e)
                return False

    except Exception as e:
        log(f"Booking workflow failed: {e}")
        send_error_notification("Error occurred while executing the booking workflow", e)
        return False


def monitor_mode():
    """Monitor mode with alert throttling and state-change detection."""
    state_path = Path(__file__).resolve().parent.parent / MONITOR_STATE_FILE

    # Load previous state
    last_state = "none"  # "none" or "some"
    last_alert_ts = 0
    try:
        if state_path.exists():
            data = json.loads(state_path.read_text(encoding="utf-8"))
            last_state = data.get("last_state", "none")
            last_alert_ts = int(data.get("last_alert_ts", 0))
    except Exception as exc:
        log(f"Failed to read monitor state: {exc}")

    now_ts = int(time.time())
    cooldown = max(0, int(ALERT_MIN_INTERVAL_MINUTES) * 60)

    slots = check_availability()
    has_slots = bool(slots)

    # Decide whether to send
    should_send = False
    reason = ""

    if has_slots:
        if last_state != "some":
            should_send = True
            reason = "state change: none->some"
        elif cooldown and (now_ts - last_alert_ts) >= cooldown:
            should_send = True
            reason = f"cooldown elapsed: >= {ALERT_MIN_INTERVAL_MINUTES} min"
        elif not ALERT_CHANGE_ONLY and (now_ts - last_alert_ts) >= cooldown:
            # Fallback path if someone disables change-only but keeps cooldown
            should_send = True
            reason = f"periodic reminder after {ALERT_MIN_INTERVAL_MINUTES} min"

    if has_slots and should_send:
        preview = ", ".join(slots[:5])
        message = (
            f"⚠️ Appointment slots detected for SuperC Auslandsamt: {preview}. Please book immediately."
        )
        log(f"Sending alert ({reason})")
        send_success_notification(message)
        last_alert_ts = now_ts
        last_state = "some"
    elif has_slots and not should_send:
        log("Slots detected but throttled (no->yes not triggered or cooldown not elapsed)")
        last_state = "some"
    else:
        log("No slots currently available.")
        last_state = "none"

    # Persist state (only the minimal fields we need)
    try:
        state = {"last_state": last_state, "last_alert_ts": int(last_alert_ts)}
        state_path.write_text(json.dumps(state), encoding="utf-8")
    except Exception as exc:
        log(f"Failed to write monitor state: {exc}")


def main():
    """Entry point."""
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
            # Monitor mode: check availability and send notifications
            monitor_mode()
        else:
            # Default mode: run the full booking workflow
            ok = run_once(headless=True)
            if not ok:
                send_error_notification("Full booking workflow failed to complete")
                sys.exit(2)

    except KeyboardInterrupt:
        log("Execution interrupted by user")
        sys.exit(0)
    except Exception as e:
        log(f"Program execution error: {e}")
        send_error_notification("Program encountered an error", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
