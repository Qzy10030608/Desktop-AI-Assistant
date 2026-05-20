# Desktop AI Assistant / 小助理 Demo

本仓库是一个本地桌面语音 AI 助手 demo。当前目标不是做通用聊天壳，而是验证一套可审计、可回退、可分层授权的桌面 AI 连接方案：用户可以通过文字或语音与 AI 交互，AI 在权限边界内完成回复、语音输出、桌面连接、文件/软件查看和受控动作规划。

当前版本处于安装包整理前阶段，仓库只保留源码、默认配置、工程说明和必要 UI 资源；本机运行数据、权限偏好、模型权重、语音参考素材不会上传到 GitHub。

## 当前能力

- PySide6 桌面端主界面与控制中心。
- 文字输入、语音录制、ASR 识别、AI 回复、TTS 输出。
- Ollama / 本地 LLM 路由配置。
- Edge-TTS 与 GPT-SoVITS 后端适配。
- 中 / 英 / 日快速 UI 语言切换。
- 角色、风格、声音、模型、输出模式配置。
- 桌面连接中间层：软件发现、文件视图、权限模式、VM / Sandbox 测试出口。
- 秦治理链：动作规划、权限审核、执行出口、材料留存、审计报告。

## 运行环境建议

建议先在本地开发环境运行，不建议直接在生产机器上开启高权限桌面动作。

- OS：Windows 10 / Windows 11
- Python：3.10 或 3.11
- UI：PySide6
- LLM：Ollama，本地模型建议从小模型开始验证
- ASR：faster-whisper
- TTS：Edge-TTS；GPT-SoVITS 需要用户自行准备模型权重
- 音频设备：需要可用麦克风和播放设备
- 可选测试出口：VM Agent 或本地 Sandbox 规则

## 安装

创建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
pip install -r requirements.txt
```

如果使用 Ollama，需要先启动本地 Ollama 服务，并在控制中心中配置模型。

如果使用 GPT-SoVITS，需要自行准备外部 GPT-SoVITS 工程、模型权重和参考音频。本仓库不会包含 `.ckpt`、`.pth`、`.wav` 等本机模型和音频素材。

GPT-SoVITS 外部工程：

- [RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)

## 启动

```powershell
python app.py
```

启动后主界面提供文字输入、录音、发送文字、系统状态和设置入口。右上角设置中可以切换界面语言，当前支持中文、English、日本語。

## GPT-SoVITS 连接方式

当前 demo 将 GPT-SoVITS 作为外部 TTS 服务接入。推荐连接路径如下：

```text
小助理 Demo
  ↓
TTSBackendController
  ↓
GPT-SoVITS Adapter
  ↓
本机 GPT-SoVITS API
  ↓
语音包目录 models/tts/gpt_sovits/{voice_package}
```

GPT-SoVITS API 通常单独启动，例如：

```powershell
runtime/python.exe api_v2.py -a 127.0.0.1 -p 9880
```

启动成功后，默认服务地址通常为：

```text
http://127.0.0.1:9880
```

连接配置应保存在本机配置中，不上传 GitHub。当前仓库只保留代码和说明，不保留真实 GPT-SoVITS 根目录、Python 路径、模型路径或参考音频。

示例配置结构：

```json
{
  "gpt_sovits": {
    "enabled": true,
    "root_dir": "GPT-SoVITS 根目录",
    "python_exe": "GPT-SoVITS 环境中的 python.exe",
    "host": "127.0.0.1",
    "port": 9880,
    "api_script": "api_v2.py",
    "tts_config": "GPT_SoVITS/configs/tts_infer.yaml"
  }
}
```

字段说明：

- `enabled`：是否启用 GPT-SoVITS 后端。
- `root_dir`：本机 GPT-SoVITS 工程根目录。
- `python_exe`：GPT-SoVITS 环境中的 Python 可执行文件。
- `host` / `port`：本机 GPT-SoVITS API 地址和端口。
- `api_script`：GPT-SoVITS API 启动脚本，常见为 `api_v2.py`。
- `tts_config`：GPT-SoVITS 推理配置文件路径。

## GPT-SoVITS 语音包结构

每个 GPT-SoVITS 语音包建议单独放在一个独立目录中：

```text
models/
└─ tts/
   └─ gpt_sovits/
      └─ taowu/
         ├─ gpt.ckpt
         ├─ sovits.pth
         ├─ ref.wav
         └─ ref.txt
```

当前 demo 默认识别以下固定文件名：

- `gpt.ckpt`：GPT 模型权重文件。
- `sovits.pth`：SoVITS 模型权重文件。
- `ref.wav`：参考音频文件，用于提供音色参考。
- `ref.txt`：参考音频对应文本，内容应尽量与 `ref.wav` 中的语音一致。

注意事项：

- `gpt.ckpt`、`sovits.pth`、`ref.wav`、`ref.txt` 缺一不可。
- `ref.txt` 与 `ref.wav` 内容不一致会影响合成质量。
- 推荐每个角色或音色单独一个文件夹，文件夹名可作为语音包名称。
- 当前 demo 暂按 GPT-SoVITS V2 常见结构和固定文件名识别；V3 训练模型、更多命名规则和多参考音频结构需要后续适配。
- `models/tts/` 已被 `.gitignore` 排除，不会上传到 GitHub。

## 当前目录结构

```text
.
├─ app.py                         # 桌面应用入口
├─ config.py                      # 全局路径、默认模式和运行文件位置
├─ bootstrap/                     # 启动初始化、机器画像和默认配置绑定
├─ services/
│  ├─ runtime/                    # 聊天、音频、生命周期、UI 桥接运行服务
│  ├─ reply/                      # 回复链路、LLM 服务、策略选择和修复
│  ├─ tts/                        # TTS 控制器与后端适配
│  ├─ persona/                    # 角色、风格、声音配置服务
│  ├─ desktop/                    # 桌面连接中间层与秦治理链
│  ├─ developer/                  # 开发者模式相关服务
│  └─ maintenance/                # 清理和维护服务
├─ ui/
│  ├─ main_window.py              # 主窗口
│  ├─ control_center/             # 控制中心与桌面连接页面
│  ├─ components/                 # 消息卡片、工具栏、弹窗组件
│  ├─ workers/                    # ASR / TTS / Chat 后台任务
│  ├─ theme/                      # 主题配置
│  └─ assets/                     # UI 图标和必要图片资源
├─ data/
│  └─ defaults/                   # 可上传的默认种子配置
├─ library/
│  ├─ styles/default/             # 默认风格示例
│  └─ voices/                     # 可上传的通用声音配置示例
├─ models/
│  └─ registry/                   # 默认模型注册配置
└─ docs/
   └─ GIT_UPLOAD_BOUNDARY.md      # GitHub 上传边界说明
```

## 文档

当前 GitHub 版本默认上传工程说明和上传边界文档：

- [README.md](README.md)：项目定位、安装启动、运行环境、桌面连接中间层、GPT-SoVITS 连接方式。
- [docs/GIT_UPLOAD_BOUNDARY.md](docs/GIT_UPLOAD_BOUNDARY.md)：GitHub 上传边界，说明哪些本机文件不能进入仓库。

设计说明类 Word 文档需要单独确认后再上传。上传前应检查是否包含本机路径、权限配置、运行记录、模型路径或临时锁文件。

## 桌面连接中间层设计

桌面连接部分采用中间层设计，不让 LLM 直接操作系统。LLM 只负责理解用户意图和生成候选计划；真正的文件、软件、权限和执行动作由本地服务链路接管。

主要链路：

```text
用户输入
  ↓
主界面 / 语音识别
  ↓
ChatRuntimeService
  ↓
桌面意图识别与目标解析
  ↓
Tianting / 九察司：意图判断、证据收集、候选目标、澄清问题
  ↓
Qin Runtime：动作任务标准化
  ↓
礼仪 / 门下 / 吏部 / 工部 / 少府 / 御史台
  ↓
Host / VM / Sandbox 执行出口
  ↓
结果回传、审计记录、必要时生成报告
```

中间层的核心原则：

- LLM 不直接执行系统命令。
- 文件和软件操作必须经过权限规则、候选目标和执行出口检查。
- 桌面模式分级控制：禁用、受限、信任、测试。
- Host 动作与 VM / Sandbox 测试动作区分记录。
- 关键动作需要可追踪材料，包括目标、来源、执行结果、回退信息和审计报告。

## 秦治理链简述

桌面动作被拆分为治理链中的多个职责层：

- 天庭 / 九察司：理解用户意图，判断是否属于桌面动作，收集证据并生成候选。
- 礼仪：维护权限规则、动作边界和安全等级。
- 门下：执行前审核，决定允许、拒绝、澄清或要求确认。
- 吏部：维护软件名册、候选目标、可信记录和可见性。
- 工部：连接具体执行出口，包括 Host、VM、Sandbox 适配器。
- 少府：管理执行材料、隔离、回退信息和结果归档。
- 御史台：记录事件、运行报告、测试矩阵和审计摘要。

这套结构的目的不是增加形式复杂度，而是把桌面动作从“直接执行”改成“可解释、可审核、可回退”的工程链路。

## 需要本地生成或配置的内容

这些内容不会上传到 GitHub，首次运行或正式安装时需要在本机生成：

- `data/user_prefs/`：本机权限、搜索根目录、语言选择、工具许可、VM 配置。
- `data/runtime/`：当前会话、运行状态、桌面缓存、审计报告。
- `data/workspace/`：当前角色、声音、风格草稿。
- `data/logs/`：运行日志。
- `models/tts/`：GPT-SoVITS 权重和参考素材。
- `agent_config.json`：本机文件读写边界，正式发布时应使用模板而不上传真实配置。

## GitHub 上传边界

上传前必须参考：

- [docs/GIT_UPLOAD_BOUNDARY.md](docs/GIT_UPLOAD_BOUNDARY.md)

禁止上传：

- 本机运行数据：`data/runtime/`
- 用户偏好和权限：`data/user_prefs/`
- 工作态草稿：`data/workspace/`
- 日志：`data/logs/`
- GPT-SoVITS 权重：`models/tts/`
- 本机语音参考：`library/voices/**/ref.*`
- 本机权限配置：`agent_config.json`
- Word 临时锁文件：`~$*.docx`

推荐使用白名单方式提交，不使用 `git add .`。

## 开发状态

当前版本是小助理 demo 的工程整理版，重点验证主界面、控制中心、语音链路、模型配置、桌面连接中间层和权限治理链。安装包、完整多语言资源体系、正式模板配置和发布说明会在后续阶段继续收口。
