# -*- coding: utf-8 -*-
"""抖音创作者平台相关配置"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.conf import (
    LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS, get_platform_cookies_dir,
)

# 抖音固定使用 connect 模式，登录态复用 auth skill 打开的 chrome_connect_dy/
AUTH_MODE = "connect"
CDP_ENDPOINT = "http://127.0.0.1:9224"
CDP_DEBUG_PORT = 9224

PROJECT_ROOT = _ROOT
BASE_DIR = Path(__file__).resolve().parent
COOKIES_DIR, CHROME_USER_DATA_DIR = get_platform_cookies_dir(PROJECT_ROOT, "douyin")
