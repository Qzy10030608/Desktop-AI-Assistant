# Desktop AI Assistant / 小助理 Demo

小助理 Demo 是一个面向 Windows 桌面的本地语音 AI 助手工程。它不是单纯的聊天壳，而是用于验证“语音 / 文本交互 + 本地 LLM / TTS + 桌面连接中间层 + 权限治理链”的完整 Demo。

当前版本的重点是：让 AI 在明确权限边界内完成聊天、语音输出、文件 / 软件查看、Sandbox 回执、VM 测试和受控动作规划。所有可能触达文件系统、软件进程、VM 或 Host 的动作，都必须进入结构化任务链路，不允许 LLM、UI 或临时脚本直接越权执行。

> 当前阶段建议作为开发 / 测试 Demo 使用。Host 真实执行能力应保持灰度或关闭；VM / Sandbox 是主要测试出口。

---

## 目录

- [当前能力](#当前能力)
- [运行环境](#运行环境)
- [安装步骤](#安装步骤)
- [启动方式](#启动方式)
- [Ollama / LLM 配置](#ollama--llm-配置)
- [TTS 与 GPT-SoVITS 配置](#tts-与-gpt-sovits-配置)
- [ASR / 语音输入配置](#asr--语音输入配置)
- [桌面连接与安全边界](#桌面连接与安全边界)
- [工程目录结构](#工程目录结构)
- [需要本机生成或配置的内容](#需要本机生成或配置的内容)
- [GitHub 上传边界](#github-上传边界)
- [相关文档](#相关文档)
- [开发状态](#开发状态)

---

## 当前能力

- PySide6 桌面端主界面与控制中心。
- 文字输入、语音录制、ASR 识别、AI 回复、TTS 输出。
- Ollama / 本地 LLM / 外部 provider 的路由配置预留。
- Edge-TTS 与 GPT-SoVITS 后端适配。
- 中 / 英 / 日快速 UI 语言切换。
- 角色、风格、声音、模型、输出模式配置。
- 桌面连接中间层：软件发现、文件视图、权限模式、Sandbox / VM 测试出口。
- 秦治理链：动作规划、权限审核、执行出口、材料留存、审计报告。
- 控制中心桌面治理页面：文件治理区、软件治理区、权限显示、测试出口切换。

---

## 运行环境

### 基础环境

| 项目 | 建议版本 / 状态 | 说明 |
|---|---|---|
| 操作系统 | Windows 10 / Windows 11 | 当前 Demo 主要面向 Windows 桌面。 |
| Python | 推荐 3.10.x | 历史开发和依赖测试以 Python 3.10 为主要基线。 |
| pip | 建议升级到最新版 | 避免 PySide6、faster-whisper 等依赖安装失败。 |
| Git | 可选但推荐 | 用于从 GitHub 拉取项目和版本管理。 |
| 虚拟环境 | 推荐 venv | 避免污染系统 Python 环境。 |

### 核心 Python 依赖

建议优先使用仓库中的 `requirements.txt` 安装。常见依赖类别如下：

| 类别 | 可能依赖 | 用途 |
|---|---|---|
| UI | `PySide6` | 主窗口、控制中心、桌面治理页面。 |
| 网络请求 | `requests`, `httpx` | 连接 Ollama、GPT-SoVITS API、VM Agent。 |
| ASR | `faster-whisper`, `sounddevice`, `numpy` | 麦克风输入和语音识别。 |
| TTS | `edge-tts` | Edge-TTS 轻量语音输出。 |
| 音频处理 | `soundfile`, `pydub` 或项目实际依赖 | 录音、播放、临时音频文件处理。 |
| 数据处理 | `pydantic` / `dataclasses` / 标准库 JSON | 配置、schema、运行态数据。 |
| 本地服务 | `uvicorn` / `fastapi`（如 VM Agent 使用） | VM Agent 或本地测试服务。 |

> 如果实际 `requirements.txt` 与上表不同，应以仓库文件为准。上表用于说明依赖类别和安装环境准备，不代表每个依赖都必须手动安装。

### 可选外部能力

| 能力 | 是否必须 | 说明 |
|---|---:|---|
| Ollama | 可选但推荐 | 用于本地 LLM 回复。未配置时可使用外部 provider 或关闭本地模型能力。 |
| GPT-SoVITS | 可选 | 用于本地高质量音色合成；需要用户自行准备外部工程、权重和参考音频。 |
| VM Agent | 可选 | 用于虚拟机内真实执行测试。Host 不应因 VM 失败自动接管执行。 |
| Sandbox | 推荐保留 | 用于审议链、权限链和回执模拟，不真实修改 Host / VM。 |

---

## 安装步骤

### 1. 获取项目

```powershell
git clone <your-repository-url>
cd <your-repository-folder>
```

如果是直接下载 zip，请解压到不含特殊权限限制的目录，例如：

```text
D:\Projects\desktop-ai-assistant
```

不建议直接放在系统目录、Program Files、桌面同步盘或路径过深的目录中。

### 2. 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 禁止执行脚本，可临时允许当前用户执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

然后重新激活虚拟环境。

### 3. 升级安装工具

```powershell
python -m pip install --upgrade pip setuptools wheel
```

### 4. 安装依赖

```powershell
pip install -r requirements.txt
```

如果安装 ASR、音频或 PySide6 依赖失败，建议先确认：

- 当前终端已经进入 `.venv`。
- Python 版本与项目建议版本一致。
- pip 已升级。
- Windows 已安装必要运行库。
- 网络可以访问 PyPI 或已配置镜像源。

### 5. 检查默认目录

首次启动前，仓库中应至少保留以下可上传的默认目录：

```text
data/defaults/
library/styles/default/
library/voices/
models/registry/
docs/
```

以下目录通常由首次运行生成，不建议手动上传真实内容：

```text
data/user_prefs/
data/runtime/
data/workspace/
data/logs/
temp/
```

---

## 启动方式

在项目根目录运行：

```powershell
python app.py
```

启动后可以进行以下检查：

1. 主窗口是否正常显示。
2. 控制中心是否能打开。
3. UI 语言切换是否正常。
4. 文本输入是否能返回回复。
5. 麦克风设备是否能被识别。
6. TTS 是否可以播放测试语音。
7. 桌面连接页面是否默认处于安全模式或测试模式。

---

## Ollama / LLM 配置

如果使用 Ollama，本机需要先安装并启动 Ollama 服务。常见本地地址为：

```text
http://localhost:11434
```

推荐先使用小模型验证链路，例如 3B / 4B / 7B 级别模型。控制中心中应保存模型 provider、模型名称和服务地址。

LLM 在本项目中的职责边界：

- 可以理解用户意图。
- 可以生成候选计划或解释执行结果。
- 不可以直接调用系统命令。
- 不可以绕过桌面治理链直接操作文件、软件、VM 或 Host。

---

## TTS 与 GPT-SoVITS 配置

### Edge-TTS

Edge-TTS 是轻量语音输出方案，适合作为默认或备用 TTS 出口。安装依赖后通常不需要额外准备模型权重。

### GPT-SoVITS

GPT-SoVITS 当前作为外部 TTS 服务接入。本仓库不包含 GPT-SoVITS 工程、模型权重、参考音频和本机路径配置。

推荐连接链路：GPT-SoVITS 官方仓库：[RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)
本仓库只负责连接已经启动的 GPT-SoVITS API，不包含 GPT-SoVITS 源码、模型权重、参考音频或训练素材。

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

默认服务地址通常为：

```text
http://127.0.0.1:9880
```

示例本机配置结构：

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

这些路径属于本机配置，应写入 `data/user_prefs/*.local.json` 或项目已有本地配置文件，不应上传 GitHub。

### GPT-SoVITS 语音包结构

每个语音包建议使用独立目录：

```text
models/
└─ tts/
   └─ gpt_sovits/
      └─ example_voice/
         ├─ gpt.ckpt
         ├─ sovits.pth
         ├─ ref.wav
         └─ ref.txt
```

文件说明：

| 文件 | 说明 |
|---|---|
| `gpt.ckpt` | GPT 模型权重。 |
| `sovits.pth` | SoVITS 模型权重。 |
| `ref.wav` | 参考音频。 |
| `ref.txt` | 参考音频对应文本。 |

注意：

- `models/tts/` 应被 `.gitignore` 排除。
- `.ckpt`、`.pth`、`.wav` 等大文件和个人素材不应上传。
- V3 训练模型、多参考音频和不同命名规则需要在后续适配中单独处理。

---

## ASR / 语音输入配置

语音输入通常包含三层：

```text
麦克风设备
  ↓
录音 Worker
  ↓
ASR 服务
  ↓
文本输入链路
```

建议首次运行时先做麦克风设备测试，只确认音量输入和设备枚举，不要直接触发桌面动作。

如果 ASR 无法运行，优先检查：

- Windows 麦克风权限。
- 当前 Python 环境是否安装音频依赖。
- 默认输入设备是否正确。
- faster-whisper 模型是否已准备。
- CPU / GPU 运行模式是否与本机环境匹配。

---

## 桌面连接与安全边界

桌面连接部分采用中间层设计，不让 LLM 或 UI 直接操作系统。

简化链路：

```text
用户输入 / UI 按钮
  ↓
ChatRuntimeService / Control Center
  ↓
桌面意图识别与目标解析
  ↓
Tianting：连接、发现、候选目标准备
  ↓
QinRuntimeService：结构化任务入口
  ↓
门下审议 + 兵部/刑部/少府守卫
  ↓
尚书路由
  ↓
工部 Sandbox / VM / Host Adapter
  ↓
礼部回执 + 户部统计 + 御史台记录
```

核心原则：

- LLM 不直接执行系统命令。
- UI 不是最终权限来源。
- 文件和软件操作必须经过权限、对象、风险和执行出口检查。
- Sandbox 只做回执模拟，不真实执行。
- VM 只在虚拟机内执行，不写 Host 权限配置。
- Host 真实执行应保持后置灰度，不能因 VM 或 Sandbox 失败自动回落。
- 删除、卸载、移动、更新、覆盖等高风险动作必须经过确认、审计和恢复材料设计。

详细说明见：[docs/DESKTOP_QIN_GOVERNANCE.md](docs/DESKTOP_QIN_GOVERNANCE.md)。

---

## 工程目录结构

当前 README 目录树采用 GitHub 展示版本，重点说明模块职责和上传边界。具体文件数量会随开发阶段变化。

```text
.
├─ app.py                         # 桌面应用入口；创建主窗口、绑定运行服务
├─ config.py                      # 全局路径、默认模式、资源位置和运行文件位置
├─ requirements.txt               # Python 依赖列表
├─ bootstrap/                     # 启动初始化、机器画像、默认配置补齐
│  ├─ machine_profile*            # 本机环境画像/检测逻辑
│  └─ defaults*                   # 默认配置绑定与首次运行补齐
├─ services/
│  ├─ runtime/                    # 聊天、音频、生命周期、UI 桥接运行服务
│  │  ├─ interaction/             # 语言交互中心、系统技能、桌面命令识别入口
│  │  └─ audio/                   # 录音、播放、音频设备相关运行服务
│  ├─ reply/                      # 回复链路、LLM 服务、策略选择、回复修复
│  ├─ tts/                        # TTS 控制器、Edge-TTS、GPT-SoVITS 适配
│  ├─ persona/                    # 角色、风格、声音配置服务
│  ├─ desktop/                    # 桌面连接中间层与秦治理链
│  │  ├─ tiandi/                  # 天地：桌面模式、运行态、出口状态
│  │  ├─ tianting/                # 天庭：连接桥、VM 连接、对象发现
│  │  ├─ qin/                     # 秦：三省六部治理主链
│  │  │  ├─ zhongshu/             # 中书省：任务编译、拟旨、DesktopTask 形成
│  │  │  ├─ menxia/               # 门下省：ReviewGate、权限/风险/出口审议
│  │  │  ├─ shangshu/             # 尚书省：路由、分发、结果 schema
│  │  │  ├─ gongbu/               # 工部：Sandbox / VM / Host adapter 执行层
│  │  │  ├─ libu/                 # 吏部：对象名册、候选、软件/文件对象治理
│  │  │  ├─ hubu/                 # 户部：权限账本、统计、一次性授权记录
│  │  │  ├─ liyi/                 # 礼部：权限提示、用户回执、展示文案
│  │  │  ├─ bingbu/               # 兵部：节流、急停、会话保护、失败熔断
│  │  │  ├─ xingbu/               # 刑部：高风险确认、破坏性动作阻断
│  │  │  ├─ shaofu/               # 少府：快照、隔离、恢复材料、restore token
│  │  │  ├─ yushitai/             # 御史台：审计事件、运行报告、测试矩阵
│  │  │  ├─ heibingtai/           # 黑冰台：文件/窗口/关闭目标解析
│  │  │  └─ zongzheng/            # 宗正：动作目录、风险模型、制度词汇
│  │  └─ xingjun/                 # 星君：测试计划、dry-run、VM 测试辅助线
│  ├─ developer/                  # 开发者模式、调试开关、深层配置显示
│  └─ maintenance/                # 清理、完整度检查、维护脚本
├─ ui/
│  ├─ main_window.py              # 主窗口
│  ├─ control_center/             # 控制中心与桌面连接页面
│  │  └─ desktop/                 # 文件治理区、软件治理区、扫描 worker、权限 UI
│  ├─ components/                 # 消息卡片、工具栏、弹窗、pending 组件
│  ├─ workers/                    # ASR / TTS / Chat 后台任务
│  ├─ theme/                      # 主题配置、颜色、字体、尺寸
│  └─ assets/                     # UI 图标、背景、必要图片资源
├─ data/
│  └─ defaults/                   # 可上传默认种子配置；用于首次运行补齐
├─ library/
│  ├─ styles/default/             # 默认风格示例
│  └─ voices/                     # 可上传的通用声音配置示例，不放私人 ref 音频
├─ models/
│  └─ registry/                   # 默认模型注册配置；不放模型权重
└─ docs/
   ├─ GIT_UPLOAD_BOUNDARY.md      # GitHub 上传边界说明
   └─ DESKTOP_QIN_GOVERNANCE.md   # 秦治理链、三省六部、权限协议说明
```

---

## 需要本机生成或配置的内容

以下内容属于本机运行态或个人配置，不应上传到 GitHub：

| 路径 | 用途 | 上传策略 |
|---|---|---|
| `data/user_prefs/` | 本机权限、语言、工具许可、VM 配置、模型路径 | 不上传真实内容，可上传 `.example.json`。 |
| `data/runtime/` | 当前会话、桌面缓存、扫描结果、审计报告 | 不上传。 |
| `data/workspace/` | 当前角色、风格、声音草稿 | 不上传真实工作态。 |
| `data/logs/` | 运行日志 | 不上传。 |
| `models/tts/` | GPT-SoVITS 权重和参考素材 | 不上传。 |
| `agent_config.json` | 本机或 VM Agent 真实边界配置 | 不上传真实配置，只上传模板。 |
| `temp/` | 临时音频、临时结果 | 不上传。 |

---

## GitHub 上传边界

上传前必须检查：

- 不使用 `git add .` 盲目提交。
- 不上传模型权重、参考音频、本机路径、运行日志、权限账本。
- 不上传 Word 临时锁文件，例如 `~$*.docx`。
- 默认配置只上传模板或种子，不上传真实本机配置。
- 设计说明文档上传前应检查是否包含本机绝对路径、个人隐私路径、真实权限记录。

详细规则见：[docs/GIT_UPLOAD_BOUNDARY.md](docs/GIT_UPLOAD_BOUNDARY.md)。

---

## 相关文档

| 文档 | 说明 |
|---|---|
| [docs/DESKTOP_QIN_GOVERNANCE.md](docs/DESKTOP_QIN_GOVERNANCE.md) | 桌面连接、秦治理链、三省六部、权限状态、协议 schema。 |
| [docs/GIT_UPLOAD_BOUNDARY.md](docs/GIT_UPLOAD_BOUNDARY.md) | GitHub 上传边界、本机运行数据排除规则。 |
| `docs/VM_AGENT*.md`（如后续添加） | VM Agent 安装、启动、接口和测试命令。 |

---

## 开发状态

当前版本处于 Demo 工程整理和桌面连接测试阶段。

当前建议优先验证：

1. 主界面基础聊天链路。
2. Edge-TTS / GPT-SoVITS 切换链路。
3. ASR 录音和转写链路。
4. 控制中心设置保存与恢复。
5. Sandbox 审议回执。
6. VM Agent 连接、VM 软件列表、VM 定位 / 启动 / 关闭。
7. Host 真实执行保持关闭或灰度，不作为默认能力开放。

最终目标是把小助理从“能聊天的桌面 UI”推进为“可审计、可回退、可分层授权的本地桌面 AI 助手”。
