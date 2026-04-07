# 四平台发布接口需求

本文档定义登录完成后的发布接口与执行约束，作为“auth 负责登录、upload 负责发布”的补充说明。

## 1. 总原则

1. `auth` 只负责登录检查、拉起登录页、获取二维码、等待登录完成。
2. 登录完成后，不自动发布。
3. 若用户要求“登录后仍需要确认再发布”，则必须停在“已登录、可发布”状态，等待用户明确下达发布指令。
4. 真正进入发布阶段时，只调用统一发布接口，不再在调用方重复拼接平台内部逻辑。

## 2. 统一发布接口

项目对外暴露一个统一发布入口：

- CLI 入口：`upload.py`
- Python 函数入口：`upload.upload(...)`

### CLI 形式

```bash
python upload.py --platform <platform> <video_path> [title] [description] [tags]
```

支持平台：

- `douyin`
- `xiaohongshu`
- `kuaishou`
- `shipinhao`

示例：

```bash
python upload.py --platform douyin /path/video.mp4 "标题" "文案" "标签1,标签2"
python upload.py --platform xiaohongshu /path/video.mp4 "标题" "文案" "标签1,标签2"
python upload.py --platform kuaishou /path/video.mp4 "标题" "文案" "标签1,标签2"
python upload.py --platform shipinhao /path/video.mp4 "标题" "文案" "标签1,标签2"
```

### Python 形式

```python
from upload import upload

ok = upload(
    platform="douyin",
    video_path="/path/video.mp4",
    title="标题",
    description="文案",
    tags=["标签1", "标签2"],
    account_name="default",
    handle_login=False,
)
```

## 3. 平台发布映射

统一入口内部映射如下：

- 抖音：`platforms.douyin_upload.api.upload_to_douyin`
- 小红书：`platforms.xhs_upload.upload.upload`
- 快手：`platforms.ks_upload.upload.upload`
- 视频号：`platforms.shipinhao_upload.api.upload_to_shipinhao`

调用方不直接调用这些平台内部模块，统一走 `upload.py`。

## 4. 推荐调用顺序

### 场景 A：只做登录，不立即发布

1. 调用 `scripts/platform_login.py --platform <platform>`
2. 等待登录成功
3. 回传“该平台已登录，可发布”
4. 等待用户明确说“继续发布/现在发布”

### 场景 B：用户确认后发布

1. 先做登录检查：

```bash
python scripts/platform_login.py --platform shipinhao --check-only
```

说明：当前项目的公共“登录检查/补登录”入口暂时只支持视频号；其它平台不要再引用 `scripts/platform_login.py --check-only` 作为标准流程。

2. 若已登录，可直接调用：

```bash
python upload.py --platform <platform> <video_path> <title> <description> <tags>
```

3. 若未登录：
   - 先进入 `auth` 流程完成登录
   - 登录完成后等待用户确认
   - 再调用统一发布接口

## 4.1 四平台确认发布模板

以下模板用于“已经登录完成，现等待用户确认发布”的场景。

### 抖音

确认发布：

```bash
python upload.py --platform douyin "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"
```

Python 调用：

```python
from upload import upload

upload(
    platform="douyin",
    video_path="<视频路径>",
    title="<标题>",
    description="<文案>",
    tags=["标签1", "标签2"],
    handle_login=False,
)
```

### 小红书

确认发布：

```bash
python upload.py --platform xiaohongshu "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"
```

Python 调用：

```python
from upload import upload

upload(
    platform="xiaohongshu",
    video_path="<视频路径>",
    title="<标题>",
    description="<文案>",
    tags=["标签1", "标签2"],
    handle_login=False,
)
```

### 快手

确认发布：

```bash
python upload.py --platform kuaishou "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"
```

Python 调用：

```python
from upload import upload

upload(
    platform="kuaishou",
    video_path="<视频路径>",
    title="<标题>",
    description="<文案>",
    tags=["标签1", "标签2"],
    handle_login=False,
)
```

### 视频号

登录检查：

```bash
python scripts/platform_login.py --platform shipinhao --check-only
```

确认发布：

```bash
python upload.py --platform shipinhao "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"
```

Python 调用：

```python
from upload import upload

upload(
    platform="shipinhao",
    video_path="<视频路径>",
    title="<标题>",
    description="<文案>",
    tags=["标签1", "标签2"],
    handle_login=False,
)
```

## 4.2 标准回传模板

若当前只完成登录，未开始发布，标准回传为：

```text
<平台> 已登录，可发布，等待确认。
登录目录：cookies/chrome_connect_<platform>
下一步发布命令：python upload.py --platform <platform> "<视频路径>" "<标题>" "<文案>" "<标签1,标签2,...>"
```

若用户明确确认发布，再执行对应平台模板。

## 5. 强制行为约束

1. 未经用户确认，不因“登录已完成”自动触发发布。
2. 登录成功后的标准回传应为：
   - 哪个平台已登录
   - 登录信息写入了哪个 `cookies/chrome_connect_*`
   - 当前可以继续发布，但尚未开始发布
3. 发布成功与否必须由发布日志判定，不能由“已登录”推断。
4. 批量任务场景中，若用户要求“先登录后人工确认再发布”，则各平台登录完成后都应停住，不自动继续。
5. 若需要把登录二维码发到微信：
   - 二维码文件由登录脚本生成
   - 发送动作由 OpenClaw 执行
   - 脚本只负责产出文件和判断页面是否已登录
