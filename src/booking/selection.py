"""
选择事项和地点模块
"""
import re
from playwright.sync_api import TimeoutError as PWTimeout
from ..browser import handle_modal_dialog
from ..notifications import log


def select_anliegen(page, text, count=1):
    """选择事项"""
    log(f"正在查找选项: {text}")

    # 等待页面加载完成
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # 滚动到页面底部确保所有元素都加载
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)

    # 截图供调试
    page.screenshot(path='debug_select_anliegen.png', full_page=True)
    log("已保存页面截图: debug_select_anliegen.png")

    # 查找所有input，遍历匹配
    inputs = page.locator('input[data-tevis-cncname]').all()
    log(f"找到 {len(inputs)} 个选项")

    # 列出所有选项供调试
    for i, inp in enumerate(inputs):
        try:
            cnc_name = inp.get_attribute('data-tevis-cncname')
            log(f"选项 {i}: {cnc_name}")
        except:
            pass

    found = False
    for i, inp in enumerate(inputs):
        try:
            cnc_name = inp.get_attribute('data-tevis-cncname')
            if cnc_name and text == cnc_name:  # 使用精确匹配
                # 滚动到该元素
                inp.scroll_into_view_if_needed()
                inp.fill(str(count))
                log(f"成功选择: {cnc_name}，数量: {count}")
                found = True
                break
        except Exception as e:
            log(f"处理选项 {i} 时出错: {e}")
            continue

    if not found:
        error_msg = f"未找到选项: {text}"
        from ..notifications import send_error_notification
        send_error_notification(f"选择事项失败 - {error_msg}")
        raise Exception(error_msg)

    # 在点击Weiter之前处理可能的模态对话框
    max_attempts = 5
    for attempt in range(max_attempts):
        # 处理模态对话框
        handle_modal_dialog(page)
        page.wait_for_timeout(500)

        try:
            # 尝试点击Weiter按钮
            weiter_btn = page.get_by_role("button", name=re.compile("Weiter", re.I))
            if weiter_btn.is_visible() and weiter_btn.is_enabled():
                weiter_btn.click(timeout=3000)
                log("成功点击Weiter按钮")
                break
        except PWTimeout:
            if attempt < max_attempts - 1:
                log(f"Weiter按钮点击失败，尝试第{attempt + 2}次...")
                # 尝试用JavaScript强制点击
                try:
                    page.evaluate("""
                        const weiterBtn = document.getElementById('WeiterButton') ||
                                         document.querySelector('input[value="Weiter"]') ||
                                         document.querySelector('button[title*="Weiter"]');
                        if (weiterBtn) {
                            weiterBtn.click();
                        }
                    """)
                    log("已通过JavaScript点击Weiter按钮")
                    break
                except Exception as e:
                    log(f"JavaScript点击失败: {e}")
            else:
                log("所有Weiter按钮点击尝试都失败了")
                break

    log("已强制处理模态对话框并提交表单")


def select_standort(page, text):
    """选择地点"""
    log("选择地点...")
    page.wait_for_timeout(2000)

    # 检测并处理可能的模态对话框
    handle_modal_dialog(page)

    # 等待页面加载
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # 查找地点选项
    inputs = page.locator('input[type="radio"], input[type="checkbox"]').all()
    log(f"找到 {len(inputs)} 个地点选项")

    found = False
    for inp in inputs:
        try:
            # 获取关联的标签文本
            label_text = ""
            inp_id = inp.get_attribute('id')
            if inp_id:
                try:
                    label = page.locator(f'label[for="{inp_id}"]')
                    if label.count() > 0:
                        label_text = label.text_content() or ""
                except:
                    pass

            # 如果没有找到标签，尝试获取父元素文本
            if not label_text:
                try:
                    parent_text = inp.locator('xpath=..').text_content() or ""
                    label_text = parent_text
                except:
                    pass

            log(f"检查地点选项: {label_text}")
            if text.lower() in label_text.lower():
                log(f"已选择地点: {label_text}")
                inp.click()
                page.wait_for_timeout(1000)
                found = True
                break
        except Exception as e:
            log(f"选择地点时出错: {e}")
            continue

    if not found:
        # 如果没有找到匹配的地点，尝试选择第一个可用选项
        log("未找到匹配的地点，尝试选择第一个选项")
        try:
            first_input = page.locator('input[type="radio"], input[type="checkbox"]').first
            if first_input.is_visible():
                first_input.click()
                log("已选择第一个地点选项")
                found = True
        except Exception as e:
            log(f"选择第一个地点选项失败: {e}")

    if not found:
        raise Exception(f"未找到匹配的地点选项: {text}")

    # 点击继续按钮
    page.wait_for_timeout(2000)
    try:
        weiter_button = page.get_by_role("button", name="Weiter")
        if weiter_button.is_visible(timeout=3000):
            weiter_button.click()
            log("成功点击Weiter按钮")
        else:
            # 尝试其他可能的按钮
            buttons = page.locator('input[type="submit"], button[type="submit"]').all()
            for btn in buttons:
                if btn.is_visible():
                    btn.click()
                    log("已点击提交按钮")
                    break
    except Exception as e:
        log(f"点击Weiter按钮失败: {e}")