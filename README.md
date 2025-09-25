# Aachen Termin Bot

自动预约亚琛外管局（Ausländeramt）预约时间的工具。

## 重构架构

### 目录结构
```
├── src/                    # 源代码目录
│   ├── config.py          # 配置管理（环境变量、参数）
│   ├── notifications.py   # 通知系统（Matrix、日志）
│   ├── browser.py         # 浏览器基础操作
│   ├── booking/           # 预约功能模块
│   │   ├── navigation.py  # 页面导航
│   │   ├── selection.py   # 事项和地点选择
│   │   ├── slots.py       # 时间槽查找
│   │   └── forms.py       # 表单处理和验证码
│   └── main.py            # 主业务逻辑
├── main.py                # 程序入口
├── mx_send.py             # Matrix 消息发送（原有）
├── run_monitor.sh         # 定时运行脚本
└── .env                   # 配置文件
```

### 使用方法

1. **监控模式**（推荐）：
   ```bash
   python main.py --monitor
   ```
   仅检查可用性，发现预约时间时发送通知。

2. **完整预约模式**：
   ```bash
   python main.py
   ```
   执行完整预约流程（需要 `AUTO_BOOK=true`）。

### 定时任务

通过 cron 每 10 分钟检查一次：
```cron
*/10 * * * * /root/aachen-termin-bot/run_monitor.sh >> /root/aachen-termin-bot/cron.log 2>&1
```

### 配置文件 (.env)

```bash
# 预约系统配置
TERMIN_URL="https://termine.staedteregion-aachen.de/auslaenderamt/"
ANLIEGEN_TEXT="RWTH Mitarbeitende & Forschende bzw. PhD"
STANDORT_TEXT="Aachen Arkaden"
AUTO_BOOK=false

# 个人信息
APPLICANT_FIRST=Your_First_Name
APPLICANT_LAST=Your_Last_Name
APPLICANT_EMAIL=your@email.com
APPLICANT_PHONE=+49123456789
APPLICANT_DOB=01.01.1990

# Matrix 通知
export MATRIX_HOMESERVER=https://your-matrix-server.com
export MATRIX_ACCESS_TOKEN=your_token_here
export MATRIX_ROOM_ID=!room_id:server.com
```

### 重构优势

- **模块化**：功能分离，易于维护
- **安全性**：配置集中管理，敏感信息不硬编码
- **可测试性**：每个模块可独立测试
- **可扩展性**：添加新功能更容易
- **代码重用**：模块间可以复用功能
- **智能兼容性**：自动处理网页元素可见性问题

### 状态

✅ **重构完成**：新架构已经过测试，功能完全正常
✅ **定时任务正常**：每10分钟自动检查，使用重构后的代码
ℹ️ **历史版本**：旧版 `aachen_termin.py` 可在 Git 历史中查看
