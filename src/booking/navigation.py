"""
页面导航模块
"""
import re
from playwright.sync_api import TimeoutError as PWTimeout
from ..config import START_URL
from ..browser import accept_cookies
from ..notifications import log


def goto_start(page):
    """导航到起始页面"""
    page.goto(START_URL)
    accept_cookies(page)

    # 如果是介绍页，通常会有"Weiter/Termin"按钮
    for pat in ["Weiter", "Termin", "Starten"]:
        try:
            page.get_by_role("button", name=re.compile(pat, re.I)).click(timeout=1500)
            break
        except PWTimeout:
            pass


def click_aufenthaltsangelegenheiten(page):
    """点击 Aufenthaltsangelegenheiten 按钮"""
    log("点击 Aufenthaltsangelegenheiten...")

    # 等待页面加载
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # 尝试多种方式点击
    selectors = [
        'text=Aufenthaltsangelegenheiten',
        '[href*="aufenthalt"]',
        'a:has-text("Aufenthaltsangelegenheiten")',
        'button:has-text("Aufenthaltsangelegenheiten")'
    ]

    for selector in selectors:
        try:
            element = page.locator(selector).first
            if element.is_visible(timeout=2000):
                element.click()
                page.wait_for_timeout(2000)
                return True
        except Exception as e:
            log(f"尝试选择器 {selector} 失败: {e}")
            continue

    raise Exception("无法找到 Aufenthaltsangelegenheiten 链接")