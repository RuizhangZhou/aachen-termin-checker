"""Notification system module."""
import time
from mx_send import send_text


def log(msg):
    """Log a message."""
    print(time.strftime("[%Y-%m-%d %H:%M:%S]"), msg, flush=True)


def send_error_notification(error_msg, exception=None):
    """Send an error notification to Matrix."""
    try:
        if exception:
            full_msg = f"🚨 SuperC booking bot error: {error_msg}\n\nDetails: {str(exception)}"
        else:
            full_msg = f"🚨 SuperC booking bot error: {error_msg}"

        log(f"Sending error notification: {full_msg}")
        send_text(full_msg)
        log("Error notification sent to Matrix")
    except Exception as e:
        log(f"Failed to send error notification: {e}")
        # Record the original error even if Matrix notification fails
        log(f"Original error: {error_msg} - {exception}")


def send_success_notification(message):
    """Send a success notification to Matrix."""
    try:
        log(message)
        send_text(message)
        log("Matrix notification sent")
    except Exception as e:
        log(f"Failed to send Matrix notification: {e}")
        # Send an error notification when Matrix delivery fails
        send_error_notification("Matrix notification delivery failed", e)
