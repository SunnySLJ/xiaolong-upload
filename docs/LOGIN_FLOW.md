# 上传与登录流程（权威文档）

本文档是项目中登录与上传流程的唯一说明，覆盖目录、入口、登录链路、上传链路与稳定性约定。

## 1. 当前推荐入口

- 单平台统一入口：`upload.py`
- 四平台顺序入口（抖音优先）：`scripts/upload_xhs_ks_sph_generated.py`
- 四平台登录助手：`scripts/platform_login.py`
- 平台 connect 脚本：
  - `scripts/upload_douyin_connect.ps1`
  - `scripts/upload_xiaohongshu_connect.ps1`
  - `scripts/upload_kuaishou_connect.ps1`
  - `scripts/upload_shipinhao_connect.ps1`

## 2. 目录结构（精简后）

```text
xiaolong-upload/
├── common/                        # 共享配置、浏览器连接、工具函数
├── platforms/                     # 四平台实现
│   ├── douyin_upload/
│   ├── xhs_upload/
│   ├── ks_upload/
│   └── shipinhao_upload/
├── scripts/
│   ├── upload_xhs_ks_sph_generated.py   # 批量顺序上传（抖音优先）
│   ├── upload_douyin_connect.ps1
│   ├── upload_xiaohongshu_connect.ps1
│   ├── upload_kuaishou_connect.ps1
│   ├── upload_shipinhao_connect.ps1
│   ├── platform_login.py
│   ├── upload_desktop.py
│   ├── open_chrome_for_upload.ps1
│   └── run_upload.bat
├── docs/
│   └── LOGIN_FLOW.md
├── upload.py                      # 统一 CLI 路由
├── README.md
└── STRUCTURE.md
```

## 3. AUTH_MODE（环境变量）

| 模式 | 说明 | Cookie 文件 |
|------|------|-------------|
| `profile` | 使用固定 Chrome 用户目录，登录态持久化（推荐） | 不需要 |
| `cookie` | 每次新开 Chrome，通过 cookie 文件保存/加载 | 需要 |
| `connect` | 连接已打开的 Chrome（remote debugging） | 不需要 |

## 4. 登录链路（connect 模式）

1. `upload_*_connect.ps1` 检查对应调试端口（如抖音 9224）是否监听。  
2. 若未监听，启动 Chrome 并指定：
   - `--remote-debugging-port=<port>`
   - `--user-data-dir=<cookies/chrome_connect_xxx>`
3. 设置环境变量：
   - `AUTH_MODE=connect`
   - `CDP_DEBUG_PORT=<port>`
   - `CDP_ENDPOINT=http://127.0.0.1:<port>`
4. 调用 `python upload.py --platform <platform> ...`
5. 平台 `api.py` 执行 `*_setup()`：
   - 已登录：直接复用 tab
   - 未登录：引导扫码登录后继续

## 5. 上传链路（统一模型）

1. `upload.py` 根据 `--platform` 分发到各平台 `api.py`。  
2. 平台 `api.py` 调用平台 `main.py`：
   - 打开/复用发布页
   - 填写标题、文案、标签/话题
   - 点击发布
3. connect 脚本按退出码处理浏览器：
   - 成功后延时关闭（默认 10 秒）
   - 失败时可保留浏览器用于排查

## 5.1 统一发布接口（对外暴露）

登录完成后的发布只允许走一个统一入口：

- CLI：`python upload.py --platform <platform> <video_path> [title] [description] [tags]`
- Python：`from upload import upload`

平台内部实际映射：

- 抖音：`platforms.douyin_upload.api.upload_to_douyin`
- 小红书：`platforms.xhs_upload.upload.upload`
- 快手：`platforms.ks_upload.upload.upload`
- 视频号：`platforms.shipinhao_upload.api.upload_to_shipinhao`

调用方、skill、外部项目都不直接拼平台内部模块，统一走 `upload.py`。

详细要求见：

- `docs/PUBLISH_REQUIREMENTS.md`

## 5.2 登录前置规则（必须遵守）

1. 四个平台的登录信息都会过期，不能假设“上次登录过，这次也一定能发”。
2. 在真正上传视频前，必须先检查该平台当前是否还能复用登录态。
3. 若登录不可复用：
   - 先明确提醒用户该平台需要重新登录。
   - 指向 `scripts/platform_login.py --platform <platform>` 或平台专用 connect 登录流程。
4. 批量上传时，若某个平台当前登录不可复用：
   - 跳过该平台，不阻塞其他平台继续上传。
   - 汇报里必须明确标为“跳过（需先登录）”。
5. 单平台上传时，若用户未要求立刻人工登录，先回传“需要登录”而不是假装已开始发布。

登录检查示例：

```bash
python scripts/platform_login.py --platform shipinhao --check-only
```

备注：当前项目里 `scripts/platform_login.py` 的登录检查/补登录入口暂时只支持视频号，旧的抖音、小红书、快手检查示例不再适用。

若需要打开专用登录窗口并等待用户完成登录：

```bash
python scripts/platform_login.py --platform shipinhao
```

若用户无法连接桌面电脑，可由脚本生成二维码截图，再交给 OpenClaw 发到微信，并等待登录完成：

```bash
python scripts/platform_login.py --platform shipinhao --notify-wechat
```

说明：

- 二维码/截图由登录脚本生成
- 发送到微信这一步由 OpenClaw 执行
- 登录是否完成仍以浏览器页面检测结果为准

## 5.3 登录后确认再发布（必须遵守）

1. `auth` 只负责登录，不因“登录成功”自动触发发布。
2. 若用户要求“登录之后还是需要确认发布”，则登录成功后必须停在“已登录、可发布”状态。
3. 只有在用户明确说“继续发布/现在发布”后，才调用统一发布接口：

```bash
python upload.py --platform <platform> <video_path> <title> <description> <tags>
```

4. 登录成功后的标准回传口径应为：
   - 平台已登录
   - 登录信息已写入对应 `cookies/chrome_connect_*`
   - 当前尚未开始发布，等待用户确认

## 6. 各平台对比

| 项目 | 抖音 | 小红书 | 快手 | 视频号 |
|------|------|--------|------|--------|
| try_connect | ✅ | ❌ | ❌ | ✅ |
| cookie_auth 返回 | (bool, browser) | (bool, browser, tab) | (bool, browser, tab) | (bool, browser, tab) |
| cookie_gen 返回 | (browser, tab) | (browser, tab, was_reused) | (browser, tab) | (browser, tab) |
| setup 返回 (browser, tab) | ✅ | ✅ | ✅ | ✅ |
| 登录检测方式 | 轮询 15s | 轮询 15s | 轮询 15s | 轮询 15s |
| profile 前缀 | dy | xhs | ks | sph |

## 7. 关键稳定性约定

1. 复用发布页 tab  
   - 登录成功后返回 `(browser, tab)`，上传流程优先复用该 tab，不重复开新 tab。

2. connect 模式纯连接  
   - `common/browser.py` 在 connect 模式必须使用 `uc.start(host, port)` 纯连接，不额外启动 Chrome。

3. 复用浏览器时不 stop  
   - `was_reused=True` 时不要调用 `browser.stop()`，避免关闭用户已有 Chrome。

4. 批量脚本串行执行  
   - `upload_xhs_ks_sph_generated.py` 按平台串行，便于失败定位与单平台重试。

5. 编码统一 UTF-8  
   - connect 脚本统一设置 `PYTHONIOENCODING=utf-8`，降低中文参数编码问题。
6. 上传前必须做登录检查  
   - 批量入口 `scripts/upload_all_platforms.py` 已接入登录前置检查；登录不可复用时会提醒并跳过该平台。
   - Windows 串行脚本 `scripts/upload_xhs_ks_sph_generated.py` 也已接入同样逻辑；登录不可复用时会提醒并跳过该平台。

## 8. 发布页 URL

| 平台 | 发布页 URL |
|------|------------|
| 抖音 | https://creator.douyin.com/creator-micro/content/upload |
| 小红书 | https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video |
| 快手 | https://cp.kuaishou.com/article/publish/video |
| 视频号 | https://channels.weixin.qq.com/platform/post/create |

## 9. 外部 Cookie 替换上传

支持“你提供 cookie -> 替换当前登录态 -> 校验 -> 上传”：

1. 准备 cookie JSON（建议 Chrome 导出数组格式）。
2. 运行 `scripts/import_cookie_and_upload.ps1`。
3. 脚本会自动：
   - 启动/连接对应平台调试 Chrome
   - 清理现有 cookie 并导入你的 cookie
   - 刷新发布页并检查是否仍处于登录页
   - 校验通过后继续调用平台上传脚本

仅校验 cookie 是否可用（不上传）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/import_cookie_and_upload.ps1 -Platform douyin -CookieFile "C:\path\dy_cookie.json" -ValidateOnly
```

校验通过后直接上传：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/import_cookie_and_upload.ps1 -Platform douyin -CookieFile "C:\path\dy_cookie.json" -VideoPath "C:\Users\你\Desktop\2.mp4" -Title "今日份生活小记录" -Description "把今天的片段收进这支小视频里" -Tags "生活记录,日常分享"
```

## 10. 四平台 Cookie 获取（你拿不到 cookie 时）

如果你无法手工导出 cookie，可直接从当前 connect 浏览器导出：

- 抖音：`scripts/export_douyin_cookie.ps1`
- 小红书：`scripts/export_xiaohongshu_cookie.ps1`
- 快手：`scripts/export_kuaishou_cookie.ps1`
- 视频号：`scripts/export_shipinhao_cookie.ps1`

示例（抖音）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/export_douyin_cookie.ps1
```

默认导出路径：

- 抖音：`cookies/douyin/cookie_exported.json`
- 小红书：`cookies/xiaohongshu/cookie_exported.json`
- 快手：`cookies/kuaishou/cookie_exported.json`
- 视频号：`cookies/shipinhao/cookie_exported.json`

导出后先做可用性校验（以抖音为例）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/import_cookie_and_upload.ps1 -Platform douyin -CookieFile "C:\Users\你\Desktop\shuang\xiaolong-upload\cookies\douyin\cookie_exported.json" -ValidateOnly
```

## 11. 给其他项目复用的登录脚本

`scripts/platform_login.py` 是刻意做成单文件、可复制的登录脚本。

用途：

1. 独立检查某个平台当前登录是否还能复用。
2. 若不能复用，自动打开该平台专用 connect Chrome 并等待用户完成登录。
3. 其他项目后续只要复用同一套 `cookies/chrome_connect_*` 目录和端口，就可以直接拿这份登录信息去上传。

当前四个平台固定映射：

- 抖音：`9224` + `cookies/chrome_connect_dy`
- 小红书：`9223` + `cookies/chrome_connect_xhs`
- 快手：`9225` + `cookies/chrome_connect_ks`
- 视频号：`9226` + `cookies/chrome_connect_sph`

建议其他项目接入规则：

1. 上传前先调用 `python platform_login.py --platform <platform> --check-only`
2. 返回非 0 时，不直接上传，先让用户登录
3. 登录完成后再进入上传流程
4. 若是批量任务，该平台登录失败就跳过，不拖死整批任务
