"""
通知系统模块
"""
import time
from mx_send import send_text


def log(msg):
    """记录日志信息"""
    print(time.strftime("[%Y-%m-%d %H:%M:%S]"), msg, flush=True)


def send_error_notification(error_msg, exception=None):
    """发送错误通知到Matrix"""
    try:
        if exception:
            full_msg = f"🚨 SuperC 预约程序出错：{error_msg}\n\n错误详情：{str(exception)}"
        else:
            full_msg = f"🚨 SuperC 预约程序出错：{error_msg}"

        log(f"发送错误通知: {full_msg}")
        send_text(full_msg)
        log("已发送错误通知到Matrix")
    except Exception as e:
        log(f"发送错误通知失败: {e}")
        # 即使Matrix通知失败也要记录原始错误
        log(f"原始错误: {error_msg} - {exception}")


def send_success_notification(message):
    """发送成功通知到Matrix"""
    try:
        log(message)
        send_text(message)
        log("已发送Matrix通知")
    except Exception as e:
        log(f"发送Matrix通知失败: {e}")
        # 如果Matrix通知失败，发送错误通知
        send_error_notification("Matrix通知发送失败", e)