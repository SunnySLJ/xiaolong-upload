# 四平台登录流程说明

## 一、AUTH_MODE（环境变量）

| 模式 | 说明 | Cookie 文件 |
|------|------|-------------|
| `profile` | 使用固定 Chrome 用户目录，登录态持久化（**推荐**） | 不需要 |
| `cookie` | 每次新开 Chrome，通过 cookie 文件保存/加载 | 需要 |
| `connect` | 连接已打开的 Chrome（需先运行 `--remote-debugging-port=9222`） | 不需要 |

## 二、统一登录流程

```
                    ┌─────────────────────────────────────┐
                    │           platform_setup()           │
                    └─────────────────┬───────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │ try_connect_*   │    │   cookie_auth   │    │  cookie_gen     │
    │ (抖音/视频号)   │    │ 校验已有登录态   │    │ 引导扫码登录    │
    └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
             │                      │                      │
             │ 成功                 │ 已登录               │ 登录成功
             ▼                      ▼                      ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │            返回 (True, browser, tab) 或 (True, (browser, tab))   │
    │                    tab 已在发布页，供 upload 复用                 │
    └─────────────────────────────────────────────────────────────────┘
```

## 三、各平台对比

| 项目 | 抖音 | 小红书 | 快手 | 视频号 |
|------|------|--------|------|--------|
| try_connect | ✅ | ❌ | ❌ | ✅ |
| cookie_auth 返回 | (bool, browser) | (bool, browser, tab) | (bool, browser, tab) | (bool, browser, tab) |
| cookie_gen 返回 | (browser, tab) | (browser, tab, was_reused) | (browser, tab) | (browser, tab) |
| setup 返回 (browser, tab) | ✅ | ✅ | ✅ | ✅ |
| 登录检测方式 | 轮询 15s | 轮询 15s | 轮询 15s | 轮询 15s |
| profile 前缀 | dy | xhs | ks | sph |

## 四、关键点

### 1. 复用已在发布页的 tab

**问题**：cookie_gen 登录成功后，若 upload 再调用 `browser.get(url)` 开新 tab，可能丢失会话（profile 模式下新建 tab 有时不继承）。

**解决**：cookie_gen 返回 `(browser, tab)`，tab 已在发布页，upload 直接复用，不再 `browser.get()`。

### 2. Chrome 复用与 StopIteration

nodriver 连接已有 Chrome 时，`browser.get()` 可能抛出 `StopIteration`。  
**解决**：`try_reuse=True` 失败时自动 `try_reuse=False` 开新浏览器。

### 3. 复用浏览器时不 stop()

当 `was_reused=True` 时，不要调用 `browser.stop()`，避免关闭用户已打开的 Chrome。

## 五、发布页 URL

| 平台 | 发布页 URL |
|------|------------|
| 抖音 | https://creator.douyin.com/creator-micro/content/upload |
| 小红书 | https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video |
| 快手 | https://cp.kuaishou.com/article/publish/video |
| 视频号 | https://channels.weixin.qq.com/platform/post/create |
