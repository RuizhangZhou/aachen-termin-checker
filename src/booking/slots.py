"""
时间槽查找和预约模块
"""
import re
from playwright.sync_api import TimeoutError as PWTimeout
from ..notifications import log


def find_and_click_first_slot(page, monitor_only=False):
    """查找并点击第一个可用时间槽"""
    log("检查可用时间槽...")
    page.wait_for_timeout(2000)

    # 收集所有可用时间槽信息
    available_slots = []

    try:
        # 等待日历加载
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)

        # 查找所有可能的时间槽按钮
        slot_selectors = [
            'button:not([disabled]):has-text("Uhr")',
            'a[href*="slot"]:not(.disabled)',
            'button.available',
            'td.available button',
            '.calendar-slot:not(.disabled)',
            'button[data-time]:not([disabled])'
        ]

        for selector in slot_selectors:
            try:
                slots = page.locator(selector).all()
                for slot in slots:
                    if slot.is_visible():
                        slot_text = slot.text_content() or ""
                        if slot_text and (":" in slot_text or "uhr" in slot_text.lower()):
                            available_slots.append(slot_text.strip())

                            if not monitor_only:
                                # 如果不是仅监控模式，点击第一个可用时间槽
                                slot.click()
                                log(f"已点击时间槽: {slot_text}")
                                page.wait_for_timeout(2000)
                                return True
                break
            except Exception as e:
                log(f"检查时间槽选择器 {selector} 时出错: {e}")
                continue

    except Exception as e:
        log(f"查找时间槽时出错: {e}")

    if available_slots:
        log(f"发现 {len(available_slots)} 个可用时间槽: {available_slots[:5]}")
        return available_slots
    else:
        log("当前无可用时间。")
        return [] if monitor_only else False


def check_availability():
    """检查可用性的主函数（使用原始代码的简化逻辑）"""
    from ..browser import BrowserManager
    from ..config import ANLIEGEN, STANDORT
    from .navigation import goto_start, click_aufenthaltsangelegenheiten

    with BrowserManager(headless=True) as page:
        try:
            # 导航到起始页
            goto_start(page)

            # 点击 Aufenthaltsangelegenheiten
            click_aufenthaltsangelegenheiten(page)

            # 直接使用原始代码的简化逻辑
            log("查找RWTH选项...")

            # 等待页面加载完成
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)

            # 先滚动到页面底部确保所有元素都加载
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)

            target_input = page.locator(f'input[data-tevis-cncname="{ANLIEGEN}"]').first

            if target_input.count() == 0:
                log(f"未找到选项: {ANLIEGEN}")
                return []

            # 选择选项 - 使用 JavaScript 绕过可见性检查
            try:
                target_input.fill("1")
                log(f"已选择: {ANLIEGEN}")
            except Exception as e:
                log(f"常规填写失败，尝试JavaScript: {e}")
                # 使用 JavaScript 直接设置值
                page.evaluate(f"""
                    const input = document.querySelector('input[data-tevis-cncname="{ANLIEGEN}"]');
                    if (input) {{
                        input.value = '1';
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                """)
                log(f"通过JavaScript已选择: {ANLIEGEN}")

            page.wait_for_timeout(1000)

            # 点击继续按钮
            try:
                weiter_btn = page.get_by_role("button", name="Weiter")
                weiter_btn.click()
                log("成功点击Weiter按钮")
            except Exception as e:
                log(f"点击Weiter按钮失败: {e}")

            # 等待地点页面加载
            page.wait_for_timeout(2000)

            # 简化地点选择 - 选择第一个可用的
            try:
                first_location = page.locator('input[type="radio"], input[type="checkbox"]').first
                if first_location.count() > 0:
                    first_location.click()
                    log("已选择地点")
                    page.wait_for_timeout(1000)

                    # 点击继续
                    weiter_btn = page.get_by_role("button", name="Weiter")
                    weiter_btn.click()
                    log("成功点击地点页面Weiter按钮")
            except Exception as e:
                log(f"地点选择失败: {e}")

            # 检查可用时间槽
            available_slots = find_and_click_first_slot(page, monitor_only=True)
            return available_slots if available_slots else []

        except Exception as e:
            log(f"检查可用性时出错: {e}")
            return []