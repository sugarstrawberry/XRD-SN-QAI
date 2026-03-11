#!/usr/bin/env python3
"""
材料数据质量评价系统 - 命令行接口
提供XRD和S-N数据质量评价的CLI功能
"""

import sys
import os

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(current_dir, 'src'))
sys.path.insert(0, current_dir)

# 导入CLI解析器
try:
    from src.cli.cli_parser import main
except ImportError:
    print("❌ 导入失败，请确保在pythonProject目录下运行")
    print(f"当前目录: {os.getcwd()}")
    print(f"脚本目录: {current_dir}")
    sys.exit(1)

if __name__ == '__main__':
    main()