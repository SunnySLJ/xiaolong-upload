# longxia-deploy

龙虾上传项目一键部署技能 - 专为 openclaw 设计

## 使用方法

### 方式一：使用部署脚本（推荐）

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\deploy.ps1"
```

### 方式二：手动执行

```powershell
cd "C:\Users\爽爽\Desktop\shuang\xiaolong-upload"
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 方式三：验证安装

```powershell
longxia-upload --help
```

## 部署脚本参数

| 参数 | 说明 |
|------|------|
| `-Quick` | 快速模式，跳过部分检查 |
| `-Verbose` | 详细输出模式 |
| `-ProjectPath` | 自定义项目路径 |

示例：
```powershell
.\deploy.ps1 -Quick
.\deploy.ps1 -Verbose
```

## 部署流程

1. 检查 Python 版本（需要 >= 3.10）
2. 检查项目目录完整性
3. 安装依赖（优先使用清华镜像源）
4. 验证安装是否成功

## 部署成功后

使用以下命令上传视频：

```powershell
# 抖音
longxia-upload -p douyin "video.mp4" "标题" "文案" "标签 1,标签 2"

# 快手
longxia-upload -p kuaishou "video.mp4" "标题" "文案"

# 视频号
longxia-upload -p shipinhao "video.mp4" "" "" "标签 1,标签 2"

# 小红书
longxia-upload -p xiaohongshu "video.mp4" "标题"
```

## 故障排除

### pip 安装失败
使用国内镜像源：
```powershell
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Python 版本过低
需要安装 Python 3.10 或更高版本

### longxia-upload 命令不存在
使用 `python upload.py` 代替
