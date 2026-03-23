# -*- coding: utf-8 -*-
"""快手创作者平台相关配置"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.conf import (
    LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS, AUTH_MODE, CDP_ENDPOINT, CDP_DEBUG_PORT,
    get_platform_cookies_dir,
)

PROJECT_ROOT = _ROOT
BASE_DIR = Path(__file__).resolve().parent
COOKIES_DIR, CHROME_USER_DATA_DIR = get_platform_cookies_dir(PROJECT_ROOT, "kuaishou")
