import os, re, time, random, sys
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from mx_send import send_text

load_dotenv()

START_URL       = os.getenv("TERMIN_URL", "https://termine.staedteregion-aachen.de/auslaenderamt/")
ANLIEGEN        = os.getenv("ANLIEGEN_TEXT", "")
STANDORT        = os.getenv("STANDORT_TEXT", "")
AUTO_BOOK       = os.getenv("AUTO_BOOK", "false").lower() == "true"
LOCK_FILE       = os.getenv("BOOK_ONCE_LOCK", "booked.lock")
STORAGE_STATE   = os.getenv("STORAGE_STATE", "state.json")

FIRST = os.getenv("APPLICANT_FIRST","")
LAST  = os.getenv("APPLICANT_LAST","")
MAIL  = os.getenv("APPLICANT_EMAIL","")
TEL   = os.getenv("APPLICANT_PHONE","")
DOB   = os.getenv("APPLICANT_DOB","")

def log(msg):
    print(time.strftime("[%Y-%m-%d %H:%M:%S]"), msg, flush=True)

def accept_cookies(page):
    for pat in ["Einverstanden", "Akzept", "Zustimmen", "Okay"]:
        try:
            page.get_by_role("button", name=re.compile(pat, re.I)).click(timeout=2500)
            return
        except PWTimeout:
            continue

def goto_start(page):
    page.goto(START_URL)
    accept_cookies(page)

    # 如果是介绍页，通常会有“Weiter/Termin”按钮
    for pat in ["Weiter", "Termin", "Starten"]:
        try:
            page.get_by_role("button", name=re.compile(pat, re.I)).click(timeout=1500)
            break
        except PWTimeout:
            pass

def select_anliegen(page, text, count=1):
    # "Schritt 2 von 6" 事项选择
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
        raise Exception(f"未找到选项: {text}")

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
                log("多次尝试点击Weiter按钮失败")
                raise

def handle_modal_dialog(page):
    """处理可能出现的模态对话框"""
    try:
        # 检查是否有模态对话框
        modal = page.locator('#TevisDialog')
        if modal.is_visible():
            log("检测到模态对话框，尝试处理...")

            # 尝试多种方式关闭模态对话框
            try:
                # 方法1：查找并点击确认按钮
                modal_buttons = modal.locator('button')
                for i in range(modal_buttons.count()):
                    btn = modal_buttons.nth(i)
                    btn_text = btn.text_content().lower()
                    if any(word in btn_text for word in ['ok', '确认', '继续', 'weiter', 'ja', 'yes']):
                        btn.click()
                        log("已点击模态对话框确认按钮")
                        return True

                # 方法2：按回车键
                page.keyboard.press('Enter')
                log("已按回车键关闭模态对话框")
                return True

            except Exception as e:
                log(f"关闭模态对话框失败: {e}")

            # 方法3：使用JavaScript强制关闭
            try:
                page.evaluate("""
                    const modal = document.getElementById('TevisDialog');
                    if (modal) {
                        modal.style.display = 'none';
                        modal.remove();

                        // 移除背景遮罩
                        const backdrop = document.querySelector('.modal-backdrop');
                        if (backdrop) {
                            backdrop.remove();
                        }

                        // 恢复body滚动
                        document.body.classList.remove('modal-open');
                        document.body.style.overflow = '';
                    }
                """)
                log("已通过JavaScript强制关闭模态对话框")
                return True
            except Exception as e:
                log(f"JavaScript关闭模态对话框失败: {e}")

    except Exception:
        pass

    return False

def select_standort(page, text):
    # "Schritt 3 von 6" 地点选择（卡片或列表）
    # 对于RWTH选项，Super C是自动选择的，无需手动选择

    # 等待页面加载
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)

    # 检查页面标题确认是第三步
    page_content = page.content().lower()
    if "schritt 3" in page_content:
        log("已进入第三步（地点选择）")

        # 检查是否有地点选择选项
        has_location_options = False
        try:
            # 检查是否有可点击的地点选项
            if page.get_by_text(text, exact=False).count() > 0:
                page.get_by_text(text, exact=False).first.click()
                has_location_options = True
                log(f"已选择地点: {text}")
        except PWTimeout:
            # 尝试下拉选择
            try:
                page.get_by_label(re.compile("Standort|Ort|Dienststelle", re.I)).select_option(label=text)
                has_location_options = True
                log(f"通过下拉选择地点: {text}")
            except Exception:
                pass

        if not has_location_options:
            log("RWTH选项无需选择地点，Super C已自动设置")

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
                log("多次尝试点击Weiter按钮失败")
                raise

def find_and_click_first_slot(page, monitor_only=False):
    """在日历页找一个可用时间槽。monitor_only=True时只检测不点击，返回时间槽列表；否则点击第一个并返回True/False。"""
    html = page.content().lower()
    if ("keine termine" in html) or ("keine termine frei" in html):
        return [] if monitor_only else False

    # 策略1：直接找含有"Uhr"或时间模式的可点击按钮/链接
    patterns = [r"\b\d{1,2}:\d{2}\b", r"\bUhr\b"]
    available_slots = []
    for role in ["button", "link"]:
        loc = page.get_by_role(role)
        count = min(300, loc.count())
        for i in range(count):
            el = loc.nth(i)
            try:
                if el.is_visible() and el.is_enabled():
                    txt = (el.text_content() or "").strip()
                    if txt and any(re.search(p, txt) for p in patterns):
                        if monitor_only:
                            available_slots.append(txt)
                        else:
                            el.click()
                            return True
            except Exception:
                pass

    # 策略2：有的日历是 gridcell，可点击的格子
    loc = page.get_by_role("gridcell")
    count = min(300, loc.count())
    for i in range(count):
        el = loc.nth(i)
        try:
            if el.is_visible() and el.is_enabled():
                txt = (el.text_content() or "").strip()
                if txt and not re.search(r"ausgebucht|nicht verfügbar", txt, re.I):
                    if monitor_only:
                        available_slots.append(txt)
                    else:
                        el.click()
                        return True
        except Exception:
            pass

    return available_slots if monitor_only else False

def proceed_until_personal(page, max_clicks=3):
    """从日历进入概览再到个人信息页（一般要点 1-2 次“Weiter”）"""
    for _ in range(max_clicks):
        # 如果已经出现“Vorname/姓氏”等表单，就到了
        if page.get_by_label(re.compile("Vorname|Nachname|E-?Mail", re.I)).count() > 0:
            return True
        try:
            page.get_by_role("button", name=re.compile("Weiter|Bestätigen|OK", re.I)).click(timeout=2500)
        except PWTimeout:
            pass
        time.sleep(0.8)
    return page.get_by_label(re.compile("Vorname|Nachname|E-?Mail", re.I)).count() > 0

def fill_personal_data(page):
    def fill_by_label(regex, value):
        if not value: return
        try:
            page.get_by_label(re.compile(regex, re.I)).fill(value)
        except PWTimeout:
            try:
                page.get_by_placeholder(re.compile(regex, re.I)).fill(value)
            except PWTimeout:
                pass

    fill_by_label(r"Vorname|First", FIRST)
    fill_by_label(r"Nachname|Last",  LAST)

    # E-Mail + Wiederholung
    fill_by_label(r"^E-?Mail(?!.*Wiederholung)", MAIL)
    fill_by_label(r"Wiederholung|Bestätigung|Repeat", MAIL)

    fill_by_label(r"Telefon|Handy|Telefonnummer", TEL)

    # 生日：有的拆成 Tag/Monat/Jahr
    if re.match(r"\d{1,2}\.\d{1,2}\.\d{4}$", DOB):
        d, m, y = DOB.split(".")
        for label, val in [("Tag", d), ("Monat", m), ("Jahr|jjjj|Year", y)]:
            try:
                page.get_by_label(re.compile(label, re.I)).select_option(label=val)
            except Exception:
                try:
                    page.get_by_label(re.compile(label, re.I)).fill(val)
                except Exception:
                    pass

    # 勾选同意（必选）
    for text in ["Ich willige in die Verarbeitung", "Einwilligung", "Datenschutz"]:
        try:
            page.get_by_label(re.compile(text, re.I)).check(timeout=1500)
            break
        except PWTimeout:
            continue

    # “下次本地保存信息”（如果有）
    try:
        page.get_by_label(re.compile("Persönliche.*speichern|zukünftige Anfragen", re.I)).check(timeout=1200)
    except PWTimeout:
        pass

def solve_captcha_human_in_loop(page):
    """验证码必须人工输入；可用页面上的“neu laden / vorlesen”按钮。"""
    try:
        page.screenshot(path="captcha_step.png", full_page=False)
        log("已保存 captcha_step.png（看不清可在页面点“neu laden / vorlesen”）")
    except Exception:
        pass

    code = input("请输入页面上的 Sicherheitsabfrage（验证码）：").strip()
    if code:
        try:
            page.get_by_label(re.compile("Sicherheitsabfrage|Zeichenfolge", re.I)).fill(code)
        except PWTimeout:
            try:
                page.get_by_placeholder(re.compile("Sicherheitsabfrage|Zeichenfolge", re.I)).fill(code)
            except PWTimeout:
                pass

def run_once(headless=False):
    if Path(LOCK_FILE).exists():
        log(f"检测到锁文件 {LOCK_FILE}，已预约成功过——退出以防重复占号。")
        return True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx_kwargs = {}
        if Path(STORAGE_STATE).exists():
            ctx_kwargs["storage_state"] = STORAGE_STATE
        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()
        page.set_default_timeout(15000)

        goto_start(page)
        # Schritt 2: 事项
        select_anliegen(page, ANLIEGEN, count=1)
        # Schritt 3: 地点
        select_standort(page, STANDORT)

        # Schritt 4: 日历
        if not find_and_click_first_slot(page):
            log("当前无可用时间。")
            browser.close()
            return False

        # 进到个人信息页
        if not proceed_until_personal(page):
            log("未能进入个人信息页（可能页面流程更新，建议 headless=False 观察）。")
            browser.close()
            return False

        # 填表 + 人工验证码
        fill_personal_data(page)
        solve_captcha_human_in_loop(page)

        # 提交或停在最后一步
        if AUTO_BOOK:
            try:
                page.get_by_role("button", name=re.compile("Termin.*buchen|Absenden|Reservieren|Weiter", re.I)).click(timeout=3000)
                log("已提交预约表单；请尽快去邮箱点确认链接（不点不生效）。")
            except PWTimeout:
                log("未找到提交按钮，可能仍需点击“Weiter”或确认对话框。")
        else:
            log("已停在最后一步，请手动点“提交/预约”；随后到邮箱点确认链接。")

        # 保存 storage state（复用“下次免填”）
        try:
            ctx.storage_state(path=STORAGE_STATE)
        except Exception:
            pass

        browser.close()
        # 成功与否以你的手动提交/邮件确认为准；这里先写锁，避免重复占号
        # 如果你只想在邮件确认后写锁，可以把这两行改为：等你确认成功后手动创建锁文件。
        if AUTO_BOOK:
            Path(LOCK_FILE).write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
        return True

def check_availability(headless=True):
    """仅检查是否有可用时间槽，不进行预约。返回可用时间槽列表。"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx_kwargs = {}
        if Path(STORAGE_STATE).exists():
            ctx_kwargs["storage_state"] = STORAGE_STATE
        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()
        page.set_default_timeout(15000)

        try:
            # 直接使用和run_once相同的流程
            goto_start(page)

            # 点击 Aufenthaltsangelegenheiten
            log("点击 Aufenthaltsangelegenheiten...")
            page.get_by_text('Aufenthaltsangelegenheiten', exact=False).first.click()

            # 等待进入Schritt 2页面
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)

            # 查找RWTH选项
            log("查找RWTH选项...")

            # 先滚动到页面底部确保所有元素都加载
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)

            target_input = page.locator(f'input[data-tevis-cncname="{ANLIEGEN}"]').first

            if target_input.count() == 0:
                log(f"未找到选项: {ANLIEGEN}")
                # 列出所有可用选项供调试
                all_inputs = page.locator('input[data-tevis-cncname]').all()
                log(f"页面上共有 {len(all_inputs)} 个选项:")
                for i, inp in enumerate(all_inputs):
                    try:
                        name = inp.get_attribute('data-tevis-cncname')
                        log(f"  {i}: {name}")
                    except:
                        pass
                browser.close()
                return []

            # 使用JavaScript直接设置值并触发事件
            element_id = target_input.get_attribute('id')
            page.evaluate(f'''
                const element = document.getElementById("{element_id}");
                if (element) {{
                    element.scrollIntoView();
                    element.value = "1";
                    element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    element.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            ''')
            log(f"已选择: {ANLIEGEN}")

            # 等待可能的模态对话框并处理
            page.wait_for_timeout(3000)

            # 使用JavaScript强制处理模态对话框和表单提交
            try:
                # 综合处理：关闭模态对话框，然后提交表单
                page.evaluate('''
                    // 处理模态对话框
                    const modal = document.getElementById('TevisDialog');
                    if (modal) {
                        // 尝试找到并点击OK按钮
                        const okButtons = modal.querySelectorAll('.btn-ok, .btn-primary, button, input[type="button"], input[type="submit"]');
                        for (let btn of okButtons) {
                            if (btn.offsetParent !== null) { // 元素可见
                                btn.click();
                                break;
                            }
                        }
                        // 如果还是打开状态，强制关闭
                        if (modal.classList.contains('in')) {
                            modal.classList.remove('in');
                            modal.style.display = 'none';
                            document.body.classList.remove('modal-open');
                        }
                    }

                    // 确保Weiter按钮可点击
                    const weiterBtn = document.getElementById('WeiterButton');
                    if (weiterBtn) {
                        weiterBtn.removeAttribute('disabled');
                        weiterBtn.click();
                    }
                ''')
                page.wait_for_timeout(2000)
                log("已强制处理模态对话框并提交表单")
            except Exception as e:
                log(f"JavaScript强制处理出错: {e}")

            # 等待页面跳转
            page.wait_for_load_state('networkidle')

            # 选择地点
            log("选择地点...")
            select_standort(page, STANDORT)

            # 检查日历
            log("检查可用时间槽...")
            available_slots = find_and_click_first_slot(page, monitor_only=True)
            browser.close()
            return available_slots

        except Exception as e:
            log(f"检查可用性时出错: {e}")
            browser.close()
            return []

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        # 监控模式：检查可用性并发送通知
        slots = check_availability()
        if slots:
            slots_with_time = [f"{slot} ({time.strftime('%Y-%m-%d %H:%M')})" for slot in slots[:5]]
            message = f"⚠️ SuperC Auslandsamt 的 termin 发现可约：{', '.join(slots_with_time)}，请立即手动预约。"
            log(message)
            try:
                send_text(message)
                log("已发送Matrix通知")
            except Exception as e:
                log(f"发送Matrix通知失败: {e}")
        else:
            log("当前无可用时间。")
    else:
        # 常规模式：完整预约流程
        ok = run_once(headless=False)
        if not ok:
            sys.exit(2)
