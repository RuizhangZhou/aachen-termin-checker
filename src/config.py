"""
配置管理模块
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 预约系统配置
START_URL = os.getenv("TERMIN_URL", "https://termine.staedteregion-aachen.de/auslaenderamt/")
ANLIEGEN = os.getenv("ANLIEGEN_TEXT", "")
STANDORT = os.getenv("STANDORT_TEXT", "")
AUTO_BOOK = os.getenv("AUTO_BOOK", "false").lower() == "true"
LOCK_FILE = os.getenv("BOOK_ONCE_LOCK", "booked.lock")
STORAGE_STATE = os.getenv("STORAGE_STATE", "state.json")

# 个人信息配置
FIRST_NAME = os.getenv("APPLICANT_FIRST", "")
LAST_NAME = os.getenv("APPLICANT_LAST", "")
EMAIL = os.getenv("APPLICANT_EMAIL", "")
PHONE = os.getenv("APPLICANT_PHONE", "")
DATE_OF_BIRTH = os.getenv("APPLICANT_DOB", "")

# Matrix 通知配置
MATRIX_HOMESERVER = os.getenv("MATRIX_HOMESERVER", "")
MATRIX_ACCESS_TOKEN = os.getenv("MATRIX_ACCESS_TOKEN", "")
MATRIX_ROOM_ID = os.getenv("MATRIX_ROOM_ID", "")