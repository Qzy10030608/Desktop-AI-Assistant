# GitHub 上传边界说明

本文档用于约束“小助理 demo”上传到 GitHub 时的文件范围，避免把本机运行数据、权限配置、模型权重、语音素材和临时文件上传到远程仓库。

## 允许上传

- `app.py`、`config.py`、`bootstrap/`、`services/`、`ui/`、`tools/` 等项目源码。
- `requirements.txt`、`.gitignore`、`README.md`、安装说明、设计说明等工程文件。
- `data/defaults/` 中的默认种子配置。
- `models/registry/model_registry.json` 这类不包含密钥和本机绝对路径的默认模型注册模板。
- `library/styles/default/`、通用示例角色/风格/语音配置，前提是不包含个人路径、密钥、真实音频素材。
- UI 图标、按钮图片、主题文件等必要静态资源。

## 禁止上传

- `data/runtime/`：当前会话、运行状态、扫描缓存、御史台报告、文件视图缓存。
- `data/user_prefs/`：本机权限、路径、工具许可、安装清单、语言选择、VM 连接配置。
- `data/workspace/`：当前草稿身份、当前风格、当前声音选择等本机工作态。
- `data/logs/`、`downloads/`、`favorites/`、`temp/`：日志、下载、收藏、临时输出。
- `models/tts/`：GPT-SoVITS 权重、参考音频、推理模型文件。
- `library/voices/**/ref.*`：语音参考音频和参考文本。
- `library/voices/**/gpt_sovits.json`：通常包含本机模型路径。
- `agent_config.json`：本机权限边界和根目录配置。
- Office 临时锁文件，例如 `~$*.docx`。

## 提交前检查

提交前先查看将要上传的文件：

```powershell
git status --short
git diff --cached --name-only
```

如果列表中出现 `data/runtime/`、`data/user_prefs/`、`models/tts/`、`ref.wav`、`ref.WAV`、`agent_config.json`、`~$*.docx`，应先从 Git 索引移除。

## 推荐上传方式

不要使用 `git add .`。推荐使用白名单方式：

```powershell
git add .gitignore README.md requirements.txt app.py config.py
git add bootstrap services ui tools data/defaults models/registry
git add docs/GIT_UPLOAD_BOUNDARY.md
```

如需上传设计文档，应只上传正式版文档，不上传 Word 临时锁文件。
