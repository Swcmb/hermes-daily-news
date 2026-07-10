# conftest.py — pytest 配置,确保 tests 能导入 lib 包
import sys
import os

# 将项目根目录加入 sys.path,使 lib.parsers 可被导入
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
