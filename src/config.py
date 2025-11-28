"""Configuration management module."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Booking system configuration
START_URL = os.getenv("TERMIN_URL", "https://termine.staedteregion-aachen.de/auslaenderamt/")
ANLIEGEN = os.getenv("ANLIEGEN_TEXT", "")
STANDORT = os.getenv("STANDORT_TEXT", "")
AUTO_BOOK = os.getenv("AUTO_BOOK", "false").lower() == "true"
LOCK_FILE = os.getenv("BOOK_ONCE_LOCK", "booked.lock")
STORAGE_STATE = os.getenv("STORAGE_STATE", "state.json")
SEND_MONITOR_SCREENSHOT = os.getenv("SEND_MONITOR_SCREENSHOT", "false").lower() == "true"

# Applicant information configuration
FIRST_NAME = os.getenv("APPLICANT_FIRST", "")
LAST_NAME = os.getenv("APPLICANT_LAST", "")
EMAIL = os.getenv("APPLICANT_EMAIL", "")
PHONE = os.getenv("APPLICANT_PHONE", "")
DATE_OF_BIRTH = os.getenv("APPLICANT_DOB", "")

# Matrix notification configuration
MATRIX_HOMESERVER = os.getenv("MATRIX_HOMESERVER", "")
MATRIX_ACCESS_TOKEN = os.getenv("MATRIX_ACCESS_TOKEN", "")
MATRIX_ROOM_ID = os.getenv("MATRIX_ROOM_ID", "")
