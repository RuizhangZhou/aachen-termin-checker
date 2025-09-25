"""
主入口模块
"""
import sys
from pathlib import Path

from .browser import BrowserManager
from .config import AUTO_BOOK, LOCK_FILE, ANLIEGEN, STANDORT
from .notifications import log, send_error_notification, send_success_notification
from .booking.navigation import goto_start, click_aufenthaltsangelegenheiten
from .booking.selection import select_anliegen, select_standort
from .booking.slots import find_and_click_first_slot, check_availability
from .booking.forms import proceed_until_personal, fill_personal_data, solve_captcha_human_in_loop


def run_once(headless=True):
    """执行完整的预约流程"""
    try:
        with BrowserManager(headless=headless) as page:
            # 导航到起始页
            goto_start(page)

            # 点击 Aufenthaltsangelegenheiten
            click_aufenthaltsangelegenheiten(page)

            # Schritt 2: 事项
            select_anliegen(page, ANLIEGEN, count=1)

            # Schritt 3: 地点
            select_standort(page, STANDORT)

            # Schritt 4: 日历
            if not find_and_click_first_slot(page):
                log("当前无可用时间。")
                return False

            # 如果找到时间槽但不自动预约，则只通知
            if not AUTO_BOOK:
                send_success_notification("⚠️ 发现可用时间槽，但未启用自动预约。请手动完成预约。")
                return True

            # 检查是否已经预约过（避免重复预约）
            if Path(LOCK_FILE).exists():
                log("检测到锁定文件，跳过预约以避免重复")
                return True

            # Schritt 5: 继续到个人信息页面
            if not proceed_until_personal(page):
                send_error_notification("无法进入个人信息页面")
                return False

            # Schritt 6: 填写个人信息
            fill_personal_data(page)

            # Schritt 7: 处理可能的验证码
            if page.locator('img[src*="captcha"], canvas, #captcha').count() > 0:
                if not solve_captcha_human_in_loop(page):
                    send_error_notification("验证码处理失败")
                    return False

            # 最终提交
            try:
                submit_button = page.get_by_role("button", name="Buchen")
                if submit_button.is_visible(timeout=5000):
                    submit_button.click()
                    page.wait_for_timeout(3000)

                    # 创建锁定文件以防止重复预约
                    Path(LOCK_FILE).touch()

                    send_success_notification("🎉 预约成功！已自动完成预约流程。")
                    log("预约流程完成")
                    return True
                else:
                    send_error_notification("找不到最终提交按钮")
                    return False

            except Exception as e:
                send_error_notification("最终提交时出错", e)
                return False

    except Exception as e:
        log(f"预约流程执行失败：{e}")
        send_error_notification("预约流程执行过程中出现错误", e)
        return False


def monitor_mode():
    """监控模式：检查可用性并发送通知"""
    slots = check_availability()
    if slots:
        message = f"⚠️ SuperC Auslandsamt 的 termin 发现可约：{', '.join(slots[:5])}，请立即手动预约。"
        send_success_notification(message)
    else:
        log("当前无可用时间。")


def main():
    """主函数"""
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
            # 监控模式：检查可用性并发送通知
            monitor_mode()
        else:
            # 常规模式：完整预约流程
            ok = run_once(headless=True)
            if not ok:
                send_error_notification("完整预约流程执行失败")
                sys.exit(2)

    except KeyboardInterrupt:
        log("程序被用户中断")
        sys.exit(0)
    except Exception as e:
        log(f"程序执行出错: {e}")
        send_error_notification("程序执行异常", e)
        sys.exit(1)


if __name__ == "__main__":
    main()