# personal-ai
# 个人AI助手原型

本项目是一个用于本地运行与界面验证的 **桌面 AI 助手原型**。  
当前重点不是完整产品发布，而是围绕 **本地 LLM、语音输入、文本回复、TTS 语音输出、控制中心配置** 以及后续 **连接电脑 / 桌面控制能力** 进行结构设计与功能测试。

---

## 项目定位

这是一个面向 Windows 桌面的本地 AI 原型工程，当前阶段主要用于：

- 验证主页面与聊天交互流程
- 验证控制中心的分层设计是否合理
- 验证本地 LLM 与 TTS 后端接入方式
- 验证 Edge / GPT-SoVITS 双语音后端的切换与运行
- 为下一阶段“连接电脑”模块预留结构

目前它仍属于 **原型测试阶段**，不是最终的一键安装版，也不是完整商业化产品。

---

## 当前已完成内容

- 主页面聊天界面基本稳定
- 控制中心已拆分为多页面结构
- 回复文本查看窗口已独立
- 已接入 Edge 与 GPT-SoVITS 双 TTS 后端
- GPT-SoVITS 首次使用延迟问题已做结构级优化
- 项目开始整理为“可搬运压缩包 + GitHub 展示”结构

---

## 当前核心能力

- 文字输入
- 录音输入
- ASR 语音识别转文字
- 本地 LLM 文本回复
- TTS 语音回复
- 回复音频播放 / 下载 / 收藏
- 控制中心管理模型、风格、语音包、输出模式
- 回复文本窗口查看 raw / visible / tts 三段文本

---

## 当前主要结构

```text
voice_ai_test/
├─ app.py
├─ config.py
├─ bootstrap/
├─ ui/
│  ├─ main_window.py
│  ├─ main_window_config.py
│  ├─ reply_pipeline_window.py
│  ├─ components/
│  └─ control_center/
├─ services/
│  ├─ runtime/
│  ├─ reply/
│  ├─ tts/
│  └─ ...
├─ data/
│  ├─ runtime/
│  ├─ workspace/
│  ├─ histories/
│  ├─ logs/
│  └─ user_prefs/
├─ models/
├─ temp/
├─ downloads/
├─ favorites/
├─ static/
└─ characters/

运行环境建议

- Windows 10 / 11
- Python 3.10.x
- PySide6
- Ollama
- faster-whisper
- edge-tts
- GPT-SoVITS（可选）

## 启动方式

### 1. 安装依赖

建议优先手动安装或清理 `requirements.txt` 后再安装，因为当前文件内仍保留过一次本机 pip 命令记录。

在启动本项目之前，建议先准备以下环境：

- Python 3.10.x
- Ollama
- Git（可选，用于拉取或更新项目）
- 可用的本地语音后端
- 基础音频依赖与 Python 包

建议基础依赖至少包括：

- `PySide6`
- `flask`
- `flask-cors`
- `ollama`
- `faster-whisper`
- `edge-tts`
- `requests`
- 以及录音 / 音频播放相关依赖


### 2. 准备本地引擎

- 启动 Ollama
https://ollama.com/
- 如需使用 GPT-SoVITS，请确保其根目录、Python、API 脚本、配置文件有效（之后会添加其他的tts文件设计现在暂时使用的）
https://github.com/RVC-Boss/GPT-SoVITS

### 3. 检查机器配置
重点配置文件：

- `data/user_prefs/machine_profile.json`

其中会保存：

- Ollama 地址
- GPT-SoVITS 根目录
- GPT-SoVITS Python 路径
- 端口与 API 脚本
- 最近成功路径

### 4. 启动程序

```bash
python app.py
```

## 连接 GPT-SoVITS

首次使用外部 GPT-SoVITS 前，请先在：

`data/user_prefs/machine_profile.json`

中配置 `gpt_sovits` 信息。

### 配置示例

```json
{
  "gpt_sovits": {
    "enabled": true,
    "root_dir": "GPT-SoVITS 根目录",
    "python_exe": "GPT-SoVITS 环境中的的python.exe",
    "host": "127.0.0.1",
    "port": 9880,
    "api_script": "api_v2.py",
    "tts_config": "GPT_SoVITS/configs/tts_infer.yaml",
    "last_health_ok": true,
    "last_error": "",
    "recent_valid_root_dirs": [
      "最近有效的 GPT-SoVITS 根目录记录"
    ]
  }
}
```

### 字段说明

- `enabled`：是否启用 GPT-SoVITS
- `root_dir`：GPT-SoVITS 根目录
- `python_exe`：GPT-SoVITS 环境中的 Python 可执行文件
- `host`：本地服务地址
- `port`：本地服务端口
- `api_script`：启动脚本，通常为 `api_v2.py`
- `tts_config`：TTS 推理配置文件路径
- `last_health_ok`：上一次健康检查状态
- `last_error`：上一次错误信息
- `recent_valid_root_dirs`：最近有效的 GPT-SoVITS 根目录记录

### 启动示例

进入 GPT-SoVITS 目录后运行：

```bash
runtime/python.exe api_v2.py -a 127.0.0.1 -p 9880
```

### 注意
- `root_dir` 和 `python_exe` 必须改成你自己电脑上的实际路径
- 如果使用的是其他 Python 环境，也可以替换为对应的 `python.exe`
- 启动成功后，接口通常为：`http://127.0.0.1:9880`
- 设计问题现在只能使用V2训练的模型进行语音包的替换之后会修改可以连接使用V3训练出来的语音包
- 语音文件放入"models\tts\gpt_sovits\{文件夹名}"
## GPT-SoVITS 语音包结构

每个 GPT-SoVITS 语音包建议单独放在一个独立文件夹中，例如：

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

### 必需文件

一个可用的语音包目录中，应包含以下 4 个文件：

- `gpt.ckpt`  
  GPT 模型权重文件

- `sovits.pth`  
  SoVITS 模型权重文件

- `ref.wav`  
  参考音频文件，用于提供音色参考

- `ref.txt`  
  参考音频对应的文本内容，必须与 `ref.wav` 的实际语音内容一致

### 说明

- `gpt.ckpt` 和 `sovits.pth` 是模型推理必须使用的核心权重文件
- `ref.wav` 和 `ref.txt` 用于推理时提供参考音色和参考文本
- `ref.txt` 中的文本应与 `ref.wav` 中说出的内容尽量完全一致，否则可能影响合成效果
- 推荐将每个角色/音色单独放在一个文件夹中，文件夹名可作为语音包名称使用

### 命名要求

当前项目默认使用以下固定文件名：

```text
gpt.ckpt
sovits.pth
ref.wav
ref.txt
```

请不要随意改名，否则程序可能无法自动识别（之后会修改这个问题）。

### 常见问题

#### 1. 缺少 `gpt.ckpt` 或 `sovits.pth`
模型无法正常加载。

#### 2. 缺少 `ref.wav` 或 `ref.txt`
程序无法完成参考音色推理，可能导致合成失败。

#### 3. `ref.txt` 与 `ref.wav` 内容不一致
语音生成质量可能下降，音色和发音稳定性可能异常。
## 文档

- [AI语音设计｜当前固定版结构图（简版 Word）](docs/AI语音设计_当前固定版结构图.docx)
- [AI语音设计｜当前固定版结构图（详细版 Markdown）](docs/AI语音设计_当前固定版结构图_详细版.md)
