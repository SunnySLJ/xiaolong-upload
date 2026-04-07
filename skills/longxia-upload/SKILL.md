---
name: longxia-upload
description: 龙虾上传技能。当用户提到“上传到抖音/小红书/快手/视频号”“多平台发布”“继续上传”“重传”“cookie 登录/导入 cookie/导出 cookie”时必须使用。覆盖 Windows PowerShell connect 模式与 macOS/Python 直连模式，处理 Chrome 调试端口、cookie 复用、重传排障，并回传明确发布结果（成功/失败原因）。
---

# 龙虾上传 (Longxia Upload) Skill

本技能用于在 Windows 或 macOS 环境下，将本地视频自动化上传到抖音、小红书、快手、视频号创作者平台，并支持 cookie 导入/导出复用登录态。

## 项目路径

- 项目根目录必须使用当前机器上的真实路径。
- 优先使用环境变量 `OPENCLAW_UPLOAD_ROOT`；不要继续使用旧机器目录。
- 技能目录：当前仓库内 `skills/longxia-upload/`

## 支持平台

| 平台 | 上传脚本 | 导出 cookie 脚本 | 端口 |
|------|----------|-------------------|------|
| 抖音 | `scripts/upload_douyin_connect.ps1` | `scripts/export_douyin_cookie.ps1` | 9224 |
| 小红书 | `scripts/upload_xiaohongshu_connect.ps1` | `scripts/export_xiaohongshu_cookie.ps1` | 9223 |
| 快手 | `scripts/upload_kuaishou_connect.ps1` | `scripts/export_kuaishou_cookie.ps1` | 9225 |
| 视频号 | `scripts/upload_shipinhao_connect.ps1` | `scripts/export_shipinhao_cookie.ps1` | 9226 |

## 平台入口选择

1. Windows 优先使用项目内 PowerShell connect 脚本。
2. macOS 优先使用根入口 `upload.py` 配合 `${OPENCLAW_PYTHON:-python3.12}`。
3. 若浏览器复用失败，再切换到 `AUTH_MODE=connect` 并手动拉起带远程调试端口的 Chrome。
4. 只有确认用户目标视频路径后才执行上传；不要默认替换成别的视频。
5. 若用户要求“登录后仍要确认再发布”，则在登录完成后停住，等用户明确确认后再调统一发布接口。
6. 若用户只是要“检查登录/先补登录”，不要直接调用发布流程；优先用 `upload.py --login-only` 或 `auth` skill 单独完成登录。
7. 只要用户没有明确说“现在就发布/继续上传/直接发”，就禁止从登录检查自动跳到发布。
8. 凡是补登录或登录验收，一次只处理一个平台；不要并行拉起多个平台登录页。

## Python 环境约束

- 优先使用仓库内 `.venv/bin/python3.12`。
- 若仓库内没有 `.venv/bin/python3.12`，再使用当前机器可用的 `python3.12`。
- 严禁继续依赖旧机器特有的固定解释器路径。

## 标准执行流程

### 1) 单平台上传（默认）

在项目根目录执行（推荐）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\upload_douyin_connect.ps1" "C:\Users\爽爽\Desktop\2.mp4" "今日份生活小记录" "文案" "标签1,标签2"
```

其他平台同理替换脚本名。

macOS 快手直传示例：

```bash
${OPENCLAW_PYTHON:-python3.12} upload.py --platform kuaishou "<video_path>" "记录生活小确幸" "把今天的片段剪成短视频，记录平凡里的小美好。喜欢的话点个赞～" "生活记录,日常分享,美好时光,vlog"
```

### 2) 四平台顺序上传（顺序：抖音 -> 快手 -> 视频号 -> 小红书）

```bash
${OPENCLAW_PYTHON:-python3.12} scripts/upload_xhs_ks_sph_generated.py "<video_path>"
```

说明：

- 批量发布时必须逐个平台串行处理。
- 发布前的登录检查使用“被动检查”：只判断当前 connect 会话能否直接复用。
- 不要为了检查登录态，预先打开 4 个平台页面；只有轮到该平台真正发布时，才进入对应发布页。
- 若某个平台登录失效，则跳过该平台并继续后续平台。
- `upload_all.py` 与 `scripts/upload_xhs_ks_sph_generated.py` 都必须遵守同样规则：检查失败后不自动恢复会话、不自动打开登录页，直接跳过当前平台。

### 3) cookie 导入后上传（推荐给“拿到 cookie 不想扫码”的场景）

先校验 cookie：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\import_cookie_and_upload.ps1" -Platform douyin -CookieFile "C:\path\dy_cookie.json" -ValidateOnly
```

校验通过后上传：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\import_cookie_and_upload.ps1" -Platform douyin -CookieFile "C:\path\dy_cookie.json" -VideoPath "C:\Users\爽爽\Desktop\2.mp4" -Title "今日份生活小记录" -Description "文案" -Tags "生活记录,日常分享"
```

### 4) cookie 导出（拿不到 cookie 时）

```powershell
# 抖音
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\export_douyin_cookie.ps1"
# 小红书
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\export_xiaohongshu_cookie.ps1"
# 快手
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\export_kuaishou_cookie.ps1"
# 视频号
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\export_shipinhao_cookie.ps1"
```

## 执行原则（必须遵守）

1. **先确认目标平台与视频路径**，再执行脚本。
2. **上传前必须先检查该平台登录是否还能复用**，不能默认沿用上次登录态。
   - 这里的“检查”默认指被动检查，只查看当前会话/端口/标签页是否可直接复用。
   - 发布流程里不要为了检查额外打开新标签页、恢复多个平台页面或并发拉起多个登录页。
3. 若平台当前无法复用登录：
   - 明确提醒用户需要重新登录
   - 指向 `${OPENCLAW_PYTHON:-python3.12} scripts/platform_login.py --platform <platform>` 或对应平台 connect 登录流程
   - 批量任务里直接跳过该平台，不阻塞其他平台
   - Windows 串行脚本 `scripts/upload_xhs_ks_sph_generated.py` 也应遵守同样规则
2. **每次回传结果必须包含**：
   - 是否发布成功
   - 关键日志节点（进入发布页/上传完毕/发布成功）
   - 最终退出码
3. 出现“卡住”时，不做模糊判断，优先读终端日志文件确认真实状态。
4. 若用户说“页面没打开/没反应”，先检查对应端口是否监听，再重启该平台调试 Chrome。
5. 不擅自删用户业务文件；清理仅限缓存或用户明确要求删除的项。
6. 遇到“好像没发出去”时，先读平台日志，不要只看浏览器表象。快手重点看 `logs/kuaishou.log`。
7. 若日志显示“已点击发布”但最终不是“视频发布成功”，必须明确告诉用户这是“发布流程已触发但未确认成功”，不能算成功。
8. 若平台因登录失效被跳过，必须明确告诉用户：
   - 哪个平台被跳过
   - 为什么跳过
   - 用哪个命令去重新登录
9. 真正发布时统一走根入口 `upload.py`，不要在 skill 外层直接拼平台内部模块调用。
10. 凡是“检查登录状态”“看看是否失效”“先重新登录”“先补登录”这类请求：
   - 第一动作只能是 `auth` 检查或 `upload.py --login-only`
   - 回传结果后必须停住
   - 必须等待用户明确确认“开始发布”后，才能调用真正上传命令
11. 若用户说“把几个平台都登一下”，也必须串行执行：一次一个平台，完成登录验收后再开始下一个。

## 对外发布接口

统一发布接口：

```bash
${OPENCLAW_PYTHON:-python3.12} upload.py --platform <platform> <video_path> <title> <description> <tags>
```

Python 调用：

```python
from upload import upload
```

平台参数固定为：

- `douyin`
- `xiaohongshu`
- `kuaishou`
- `shipinhao`

若用户先让系统做登录，再决定要不要发，skill 的标准行为是：

1. 先调用 `auth` 完成登录。
2. 回传“已登录，可发布，等待确认”。
3. 用户明确确认后，再调用 `upload.py` 开始发布。

若直接走统一入口但用户不想立刻发布，使用：

```bash
${OPENCLAW_PYTHON:-python3.12} upload.py --platform <platform> <video_path> --login-only
```

说明：

- `upload.py` 默认会在登录成功后继续发布
- `--login-only` 会在登录完成后停住
- 当前项目里的公共“登录检查/补登录”入口暂时只支持视频号；下面四平台模板里只有视频号检查命令仍然有效

强制规则：

- “登录检查”和“真正发布”视为两个独立动作
- 没有用户明确确认发布前，不得自动执行第二个动作

## 四平台确认发布模板

### 抖音

```bash
${OPENCLAW_PYTHON:-python3.12} upload.py --platform douyin "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"
```

### 小红书

```bash
${OPENCLAW_PYTHON:-python3.12} upload.py --platform xiaohongshu "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"
```

### 快手

```bash
${OPENCLAW_PYTHON:-python3.12} upload.py --platform kuaishou "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"
```

### 视频号

```bash
${OPENCLAW_PYTHON:-python3.12} scripts/platform_login.py --platform shipinhao --check-only
${OPENCLAW_PYTHON:-python3.12} upload.py --platform shipinhao "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"
```

## 环境要求

- Python 3.10+
- Google Chrome
- 依赖：`pip install -r requirements.txt`

推荐解释器：

- 仓库内 `.venv/bin/python3.12`
- 或 `${OPENCLAW_PYTHON:-python3.12}`

## 常见故障与处理

1. `COOKIE_COUNT: 0`
   - 多数是登录发生在非目标调试窗口；重启目标端口浏览器后重新登录再导出。
2. `COOKIE_NOT_VALID`
   - 先跑 `-ValidateOnly`，若失败再让用户在对应端口窗口重新登录。
3. `ConnectionRefusedError / WinError 1225`
   - 端口进程丢失或浏览器被关；先重启对应端口 Chrome 再重试。
4. Shell 报 `Aborted`
   - 常见于等待命令而非主任务失败；以主任务日志 `exit_code` 为准。
5. `python3` 版本低于 3.10
   - `nodriver` 无法运行；macOS 上优先改用 `.venv/bin/python3.12` 或 `${OPENCLAW_PYTHON:-python3.12}`。
6. `Failed to connect to browser`
   - 先区分是“复用当前 Chrome 失败”还是“connect 模式 attach 失败”。
   - 如果调试端口未监听，先手动拉起 Chrome。
   - 如果端口已监听但脚本仍连接失败，优先用授权/非沙箱方式执行 attach。

## 快手重传排障流程

适用场景：用户说“快手上传有问题”“帮我再传一次”“页面像是卡住了”。

1. 先读 `logs/kuaishou.log` 最近 200 行，确认上一轮卡在哪一步。
2. 重点区分三类状态：
   - `Step 1 失败: 未找到上传 input`：页面结构波动，直接重试可能恢复。
   - `Step 5 完成: 已点击「发布」` 但没有 `视频发布成功`：只能算“已触发发布”，不能算成功。
   - `视频发布成功`：本轮已成功，不要重复上传。
3. 在 macOS 上先确认解释器：
   - `python3 -V` 若低于 3.10，不要继续用它。
   - 改用 `.venv/bin/python3.12` 或 `${OPENCLAW_PYTHON:-python3.12}`。
4. 如果普通 profile 模式报 `Failed to connect to browser`：
   - 手动拉起专用 Chrome：
   - `open -na "Google Chrome" --args --remote-debugging-port=9225 --user-data-dir="${OPENCLAW_UPLOAD_ROOT:-<repo-root>}/cookies/chrome_connect_ks" --start-maximized https://cp.kuaishou.com/article/publish/video`
   - 再用 connect 模式上传：
   - `AUTH_MODE=connect CDP_DEBUG_PORT=9225 CDP_ENDPOINT=http://127.0.0.1:9225 ${OPENCLAW_PYTHON:-python3.12} upload.py --platform kuaishou "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"`
5. 若在受限环境中 connect 模式仍失败，优先怀疑本地调试端口访问受限；需要用有权限的执行方式重跑。
6. 成功判定必须以日志出现 `视频发布成功` 为准。

## 四平台标准重传模板

适用场景：用户说“再上传一次”“刚才可能没成功”“某个平台重新发一下”。

### 抖音

1. 先读 `logs/douyin.log` 最近 100 行。
2. 成功链路通常应包含：
   - `成功进入发布页面!`
   - `视频上传完毕`
   - `文案+话题已填充`
   - `视频发布成功`
3. 若出现 `复用 Chrome 失败 (coroutine raised StopIteration)`，不要直接判失败；继续看后面是否已切到新浏览器并最终发布成功。
4. Windows 优先命令：
   - `powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\upload_douyin_connect.ps1" "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"`
5. 成功判定：
   - 必须看到 `视频发布成功`。
6. 上传前先做登录检查：
   - 当前公共登录检查入口暂不支持抖音，禁止继续引用 `scripts/platform_login.py --platform douyin --check-only`
   - 若用户需要补登录，明确说明“当前项目的检查入口只支持视频号”，不要伪造抖音检查结果。

### 小红书

1. 先读 `logs/xiaohongshu.log` 最近 100 行。
2. 成功链路通常应包含：
   - `Step 0: 打开发布页...`
   - `Step 1 完成: 已发送文件`
   - `视频上传完毕`
   - `Step 3 完成: 标题已填充`
   - `Step 4 完成: 文案+话题已填充`
   - `视频发布成功`
3. 若停在 `Step 5 完成: 已点击发布` 但没有后续成功标记，只能算“已触发发布”，不能直接报成功。
4. Windows 优先命令：
   - `powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\upload_xiaohongshu_connect.ps1" "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"`
5. 成功判定：
   - 必须看到 `视频发布成功`。
6. 上传前先做登录检查：
   - 当前公共登录检查入口暂不支持小红书，禁止继续引用 `scripts/platform_login.py --platform xiaohongshu --check-only`
   - 若用户需要补登录，明确说明“当前项目的检查入口只支持视频号”，不要伪造小红书检查结果。

### 快手

1. 先读 `logs/kuaishou.log` 最近 200 行。
2. 成功链路通常应包含：
   - `Step 1 完成: 已发送文件`
   - `Step 2 完成: 视频上传完毕`
   - `Step 4 完成: 文案+话题已填充`
   - `Step 5 完成: 已点击「发布」`
   - `视频发布成功`
3. 若出现 `Step 1 失败: 未找到上传 input`，优先重试。
4. 若出现 `发布流程已触发，请稍后到创作者中心确认`，不能算成功，必须告诉用户只是“触发了发布流程”。
5. Windows 优先命令：
   - `powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\upload_kuaishou_connect.ps1" "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"`
6. macOS 优先命令：
   - `${OPENCLAW_PYTHON:-python3.12} upload.py --platform kuaishou "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"`
7. 成功判定：
   - 必须看到 `视频发布成功`。
8. 上传前先做登录检查：
   - 当前公共登录检查入口暂不支持快手，禁止继续引用 `scripts/platform_login.py --platform kuaishou --check-only`
   - 若用户需要补登录，明确说明“当前项目的检查入口只支持视频号”，不要伪造快手检查结果。

### 视频号

1. 先读 `logs/shipinhao.log` 最近 150 行。
2. 视频号最常见的阻塞不是上传控件，而是登录态失效。先找这些标记：
   - `检测到登录页，需要微信扫码登录`
   - `检测到登录页，cookie/会话已失效`
   - `登录二维码已截图`
   - `请打开图片用微信扫码登录`
3. 如果日志已出现：
   - `检测到已登录，正在保存...`
   - `已在发表页，准备进入上传流程`
   说明扫码已完成，可以继续重传或继续当前流程。
4. 若一直循环到登录页，不要盲目重试上传，先处理微信扫码。
5. Windows 优先命令：
   - `powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\upload_shipinhao_connect.ps1" "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"`
6. 成功判定：
   - 先以日志确认已脱离登录页并进入发表页；若后续跑到发布阶段，再以最终发布成功日志为准。
7. 当前仓库已加规则：
   - 视频号一旦进入“需要登录”，会优先拉起固定的 `9226 + cookies/chrome_connect_sph` 专用 Chrome。
   - 因此后续扫码登录应优先沉淀到 `cookies/chrome_connect_sph`，而不是只留在 `cookies/shipinhao/sph_default`。
8. 若用户反馈“OpenClaw 本地再跑视频号上传还是让我登录”，优先检查两件事：
   - 是否错误探测了全局默认调试端口 `9222`，而不是视频号专用 `9226`
   - 是否 `9226` 根本没有成功拉起，导致代码退回了旧的 profile 流程
9. 当前已修复的代码行为：
   - `try_connect_existing_chrome()` 固定优先探测 `9226`
   - `shipinhao_setup()` 在走 profile 校验前，会先 `ensure_connect_login_chrome()` 并预检 `chrome_connect_sph`
   - macOS 上拉起视频号专用 Chrome 改为 `open -na "Google Chrome" --args ...`，比直接起 Chrome 二进制更稳
10. 上传前先做登录检查：
   - `python scripts/platform_login.py --platform shipinhao --check-only`
   - 若检查失败，提醒用户登录并跳过当前平台。

## 登录脚本复用规则

`scripts/platform_login.py` 是给当前项目和其他项目共用的单文件登录脚本。

用法：

```bash
python scripts/platform_login.py --platform shipinhao
python scripts/platform_login.py --platform shipinhao --check-only
```

要求：

1. 当前脚本对外只保留视频号登录检查/补登录入口。
2. 其他项目若要复用当前登录信息，必须沿用视频号这一组端口和目录：
   - 视频号 `9226` + `cookies/chrome_connect_sph`
3. 其他项目先完成登录，再拿这套登录信息去上传。
4. 若 `--check-only` 返回失败，不直接上传；批量任务里跳过该平台。

## 视频号复用失败专项排障

适用场景：用户说“明明登录过了，但 OpenClaw 再跑视频号还是让我登录”。

1. 先看 `logs/shipinhao.log` 最近 200 行。
2. 若看到：
   - `connect Chrome 启动超时，继续走默认登录流程`
   - `检测到登录页，cookie/会话已失效`
   说明不是单纯 cookie 没写入，而是专用 `9226` 会话没有被成功保活。
3. 若看到：
   - `已连接视频号专用 connect Chrome`
   - `视频号 connect 目录已就绪`
   但后续又要求登录，优先怀疑本轮执行没有复用 `9226`，而是退回到了旧 profile。
4. 修复原则：
   - 视频号永远优先复用 `9226 + cookies/chrome_connect_sph`
   - 不能先做 profile 校验再决定是否 connect
   - 不能复用全局默认调试端口 `9222`
5. 成功判定：
   - 不只是目录存在，还要看到日志里真正进入发表页或发布成功。

## 重传时的统一汇报格式

每次执行完成后，回传给用户的结果至少包含：

1. 平台名。
2. 视频路径。
3. 本轮使用的入口命令类型：
   - Windows PowerShell connect
   - macOS `python3.11`
   - macOS `AUTH_MODE=connect`
4. 关键日志节点：
   - 进入发布页
   - 上传完毕
   - 点击发布
   - 最终成功或失败原因
5. 明确结论：
   - `已发布成功`
   - `仅触发发布，未确认成功`
   - `未进入上传流程`
   - `卡在登录，需扫码`

## 本次已验证的快手案例

- 时间：`2026-03-27`
- 视频：`<video_path>`
- 文案：
  - 标题：`记录生活小确幸`
  - 描述：`把今天的片段剪成短视频，记录平凡里的小美好。喜欢的话点个赞～`
  - 标签：`生活记录,日常分享,美好时光,vlog`
- 真实故障链路：
  - 默认 `python3` 是 `3.9.6`，不满足 `nodriver` 要求。
  - 直接 profile 模式启动时，`nodriver` 报 `Failed to connect to browser`。
  - Chrome 调试端口 `9225` 实际可监听，但受限执行环境下 attach 不稳定。
- 解决方式：
  - 改用 `.venv/bin/python3.12` 或 `${OPENCLAW_PYTHON:-python3.12}`
  - 手动打开带 `9225` 调试端口的 Chrome
  - 用 `AUTH_MODE=connect` 重跑快手上传
- 最终结果：
  - 日志在 `2026-03-27 10:55:07` 出现 `视频发布成功`

## 本次已记录的视频号复用问题

- 时间：`2026-03-27`
- 现象：
  - 用户已扫码登录并生成 `cookies/chrome_connect_sph`
  - 但 OpenClaw 后续再次运行视频号上传时，仍提示重新登录
- 真实故障链路：
  - 视频号复用探测一度会误用全局默认端口 `9222`
  - `9226` 会话未成功拉起时，代码会退回旧的 profile 校验
  - profile 登录态失效后，就再次提示扫码
- 修复方式：
  - 视频号复用固定优先探测 `9226`
  - `shipinhao_setup()` 先保活并预检 `9226 + chrome_connect_sph`
  - macOS 上改用 `open -na "Google Chrome"` 拉起专用 connect Chrome
- 排障结论：
  - 只看到 `chrome_connect_sph` 目录存在，不代表 OpenClaw 本轮一定复用了它
  - 必须同时确认 `9226` 在监听，且日志没有退回 profile 流程

---

## 🧹 自动清理任务

**定时任务**: 每天凌晨 1:00 自动清理已上传的视频文件

**执行脚本**: `scripts/cleanup_uploaded_videos.py`

**清理规则**:
- 清理目录：`flash_longxia/output/`
- 保留策略：保留最近 1 天的视频文件
- 触发时间：每天凌晨 1:00 (Asia/Shanghai)
- Cron 表达式：`0 1 * * *`

**执行命令**:
```bash
cd "${OPENCLAW_UPLOAD_ROOT:-/path/to/repo}"
${OPENCLAW_PYTHON:-python3.12} scripts/cleanup_uploaded_videos.py
```

**目的**: 避免 output 目录积累大量视频文件，节省磁盘空间

**日志输出示例**:
```
[INFO] 开始清理视频文件
[INFO] 输出目录：<repo-root>/flash_longxia/output
[INFO] 保留最近 1 天的文件
[DELETED] video_1774587071.mp4 (15.23 MB)
[SUMMARY] 删除文件数：1
[SUMMARY] 释放空间：15.23 MB
```
