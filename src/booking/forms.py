"""
表单填写和验证码处理模块
"""
import re
from playwright.sync_api import TimeoutError as PWTimeout
from ..config import FIRST_NAME, LAST_NAME, EMAIL, PHONE, DATE_OF_BIRTH
from ..notifications import log


def proceed_until_personal(page, max_clicks=3):
    """继续点击直到到达个人信息页面"""
    clicks = 0
    while clicks < max_clicks:
        try:
            # 检查是否已经到达个人信息页面
            if page.locator('input[name*="vorname"], input[name*="firstname"], input[name*="first"]').count() > 0:
                log("已到达个人信息页面")
                return True

            # 尝试点击各种可能的"继续"按钮
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
            log(f"继续到个人信息页面时出错: {e}")
            break

    return clicks > 0


def fill_personal_data(page):
    """填写个人信息"""
    log("填写个人信息...")

    # 姓名字段
    name_fields = [
        ('input[name*="vorname"], input[name*="firstname"], input[name*="first"]', FIRST_NAME),
        ('input[name*="nachname"], input[name*="lastname"], input[name*="last"], input[name*="name"]', LAST_NAME),
        ('input[name*="email"], input[type="email"]', EMAIL),
        ('input[name*="telefon"], input[name*="phone"], input[name*="tel"]', PHONE),
        ('input[name*="geburt"], input[name*="birth"], input[name*="dob"]', DATE_OF_BIRTH)
    ]

    for selector, value in name_fields:
        if value:  # 只有当值不为空时才填写
            try:
                field = page.locator(selector).first
                if field.is_visible(timeout=2000):
                    field.clear()
                    field.fill(value)
                    log(f"已填写字段: {selector} = {value}")
            except Exception as e:
                log(f"填写字段 {selector} 时出错: {e}")

    log("个人信息填写完成")


def solve_captcha_human_in_loop(page):
    """人工解决验证码"""
    log("检测到验证码，需要人工解决...")

    # 截图以供人工查看
    try:
        page.screenshot(path='captcha_screenshot.png')
        log("已保存验证码截图: captcha_screenshot.png")
    except Exception as e:
        log(f"保存验证码截图失败: {e}")

    # 等待用户手动解决验证码
    log("请手动解决验证码，然后按任意键继续...")
    input("按回车键继续...")

    log("继续执行预约流程...")
    return True