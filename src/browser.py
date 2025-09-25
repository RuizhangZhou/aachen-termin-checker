"""
浏览器操作基础模块
"""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from .config import STORAGE_STATE
from .notifications import log


class BrowserManager:
    """浏览器管理器"""

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
    """接受网站 cookies"""
    for pat in ["Einverstanden", "Akzept", "Zustimmen", "Okay"]:
        try:
            page.get_by_role("button", name=re.compile(pat, re.I)).click(timeout=2500)
            return
        except PWTimeout:
            continue


def handle_modal_dialog(page):
    """处理模态对话框"""
    log("检测到模态对话框，尝试处理...")

    # 尝试点击各种可能的确认按钮
    confirm_patterns = [
        "Verstanden", "OK", "Schließen", "Weiter", "Bestätigen",
        "Ja", "Akzeptieren", "Fortfahren", "Continue"
    ]

    for pattern in confirm_patterns:
        try:
            # 尝试通过按钮文本点击
            button = page.locator(f'button:has-text("{pattern}")').first
            if button.is_visible(timeout=1000):
                button.click()
                log(f"已点击模态对话框确认按钮: {pattern}")
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    # 尝试点击模态对话框中的任意按钮
    try:
        modal_buttons = page.locator('.modal button, [role="dialog"] button, .dialog button').all()
        for button in modal_buttons:
            if button.is_visible():
                button.click()
                log("已点击模态对话框按钮")
                page.wait_for_timeout(1000)
                return True
    except Exception:
        pass

    # 尝试按 ESC 键关闭
    try:
        page.keyboard.press("Escape")
        log("已按 ESC 键尝试关闭模态对话框")
        page.wait_for_timeout(1000)
        return True
    except Exception:
        pass

    log("无法处理模态对话框")
    return False