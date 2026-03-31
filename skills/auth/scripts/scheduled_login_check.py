#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时检查平台登录状态脚本
根据 login_check_config.json 配置执行登录检查
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.auth.scripts.platform_login import check_platform_login, auto_recover_session, close_connect_browser

def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent.parent / "login_check_config.json"
    if not config_path.exists():
        print(f"❌ 配置文件不存在：{config_path}")
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_all_platforms(config):
    """检查所有配置的平​​台登录状态"""
    results = []
    
    print('='*60)
    print(f'🦐 龙虾上传 - 定时登录状态检查')
    print(f'⏰ 检查时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*60)
    
    for platform in config.get("platforms", []):
        label_map = {
            'douyin': '抖音',
            'xiaohongshu': '小红书',
            'kuaishou': '快手',
            'shipinhao': '视频号'
        }
        label = label_map.get(platform, platform)
        
        # 检查登录状态（passive=False 会自动启动 Chrome）
        ok, msg = check_platform_login(platform, PROJECT_ROOT, passive=False)
        
        if ok:
            print(f'✅ {label}: 已登录')
            results.append({'platform': platform, 'status': 'ok', 'message': msg})
        else:
            print(f'❌ {label}: {msg}')
            results.append({'platform': platform, 'status': 'expired', 'message': msg})
            
            # 如果需要自动重试登录
            if config.get("auto_retry_login", True):
                print(f'   🔄 尝试自动恢复 {label} 会话...')
                success, recover_msg = auto_recover_session(platform, PROJECT_ROOT)
                if success:
                    print(f'   ✅ {label} 恢复成功')
                    results[-1]['recovered'] = True
                else:
                    print(f'   ❌ {label} 恢复失败：{recover_msg}')
                    results[-1]['recovered'] = False
        
        # 检查完关闭浏览器
        close_connect_browser(platform)
        print()
    
    print('='*60)
    
    # 汇总结果
    ok_count = sum(1 for r in results if r['status'] == 'ok')
    total = len(results)
    print(f'📊 结果汇总：{ok_count}/{total} 平台已登录')
    
    if ok_count < total:
        expired_platforms = [r['platform'] for r in results if r['status'] == 'expired']
        print(f'⚠️  需要重新登录的平台：{", ".join(expired_platforms)}')
    
    return results

def main():
    """主函数"""
    config = load_config()
    if not config:
        sys.exit(1)
    
    if not config.get("enabled", True):
        print("⏸️  定时检查已禁用")
        sys.exit(0)
    
    results = check_all_platforms(config)
    
    # 如果有平台登录失效且需要通知
    expired = [r for r in results if r['status'] == 'expired']
    if expired and config.get("notify_on_failure", True):
        print("\n📬 准备发送通知...")
        # 这里可以集成微信通知逻辑
        # 暂时先打印提示
        print("   （通知功能已预留，可集成到现有通知系统）")
    
    # 返回结果供 cron 使用
    print(json.dumps({
        'timestamp': datetime.now().isoformat(),
        'results': results,
        'summary': {
            'total': len(results),
            'ok': sum(1 for r in results if r['status'] == 'ok'),
            'expired': len(expired)
        }
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
