#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按顺序上传到四个平台：抖音 → 小红书 → 快手 → 视频号
视频：桌面 3.mp4，标题/文案/标签自动生成
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from upload import upload
from common.utils import gen_desktop_content

_PLATFORM_CONFIG = {
    "douyin": {"title_max": 30, "tags_max": 99, "default_tags": ["生活记录", "日常分享", "美好时光", "vlog"]},
    "kuaishou": {"title_max": 15, "tags_max": 4, "default_tags": ["生活记录", "日常分享", "美好时光", "vlog"]},
    "shipinhao": {"title_max": 64, "tags_max": 10, "default_tags": ["生活记录", "日常分享", "美好时光", "vlog", "小确幸"]},
    "xiaohongshu": {"title_max": 20, "tags_max": 5, "default_tags": ["生活记录", "日常分享", "美好时光", "vlog", "小确幸"]},
}

# 顺序：先上传已稳定平台，抖音若连接失败可最后单独重试
ORDER = ["xiaohongshu", "kuaishou", "shipinhao", "douyin"]


def main():
    video_path = str(Path.home() / "Desktop" / "3.mp4")
    if len(sys.argv) > 1:
        video_path = sys.argv[1]

    path = Path(video_path)
    if not path.exists():
        print(f"❌ 视频不存在: {path}")
        sys.exit(1)

    cfg = _PLATFORM_CONFIG["douyin"]
    title, _, tags = gen_desktop_content(
        str(path), title_max=cfg["title_max"], tags_max=cfg["tags_max"], default_tags=cfg["default_tags"]
    )
    if not title or len(title) <= 1:
        title = "记录生活中的小确幸"
    # 文案：适合生活记录 / vlog 风格
    description = (
        "平凡日子里的小确幸，值得被好好记录 🌟 "
        "让每个瞬间都有仪式感，生活本该如此温柔。"
    )
    print("📝 生成内容（四平台共用）:")
    print(f"   标题: {title}")
    print(f"   文案: {description}")
    print(f"   标签: {', '.join(tags)}")
    print()

    for i, platform in enumerate(ORDER, 1):
        pcfg = _PLATFORM_CONFIG[platform]
        ptitle = title[: pcfg["title_max"]]
        ptags = tags[: pcfg["tags_max"]]
        names = {"douyin": "抖音", "xiaohongshu": "小红书", "kuaishou": "快手", "shipinhao": "视频号"}
        print(f"\n{'='*50}")
        print(f"[{i}/4] 正在上传到 {names[platform]}...")
        print(f"{'='*50}")

        ok = upload(
            platform=platform,
            video_path=str(path.resolve()),
            title=ptitle,
            description=description,
            tags=ptags,
        )
        if ok:
            print(f"✅ {names[platform]} 上传成功")
        else:
            print(f"❌ {names[platform]} 上传失败")
            sys.exit(1)

    print("\n🎉 四平台全部上传完成！")


if __name__ == "__main__":
    main()
