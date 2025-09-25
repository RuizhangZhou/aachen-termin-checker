#!/usr/bin/env python3
"""
Aachen Termin Bot 主入口
使用重构后的模块化架构
"""

# 添加 src 目录到 Python 路径
import sys
from pathlib import Path

# 添加 src 目录到 sys.path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# 导入并运行主程序
from src.main import main

if __name__ == "__main__":
    main()