# AI语音设计｜当前固定版结构图（详细版）

2026-04 Demo Fixed Version

本文件用于说明当前固定版压缩包的 **真实工程结构**、**目录职责**、**运行连接关系**、**控制中心分层** 以及 **可搬运设计思路**。适合用于 GitHub 仓库详细说明、开发交接和下一阶段“连接电脑”设计前的统一基线。

## 1. 文档定位

当前项目已经不只是一个单页聊天程序，而是一个开始走向“可搬运桌面原型”的工程包。为了避免后续在新电脑、新聊天、新阶段中重复解释，本文件将当前固定版整理为一份可直接延续的基线说明。

## 2. 当前压缩包的真实工程结构

```text
voice_ai_test/
├─ app.py
├─ config.py
├─ requirements.txt
├─ bootstrap/
│  ├─ machine_profile_service.py
│  └─ startup_check_service.py
├─ characters/
│  └─ character_001/
├─ data/
│  ├─ runtime/
│  ├─ workspace/
│  ├─ histories/
│  ├─ logs/
│  └─ user_prefs/
├─ downloads/
├─ favorites/
├─ library/
│  ├─ presets/
│  ├─ styles/
│  ├─ temp/
│  └─ voices/
├─ models/
│  ├─ asr/
│  ├─ llm/
│  ├─ registry/
│  └─ tts/
│     └─ gpt_sovits/
├─ services/
│  ├─ persona/
│  ├─ reply/
│  │  └─ reply_engine/
│  ├─ runtime/
│  └─ tts/
│     └─ backends/
├─ static/
├─ temp/
│  ├─ cache/
│  ├─ records/
│  ├─ replies/
│  └─ sessions/
├─ ui/
│  ├─ chat_panel.py
│  ├─ main_window.py
│  ├─ main_window_config.py
│  ├─ reply_pipeline_window.py
│  ├─ assets/
│  ├─ components/
│  ├─ control_center/
│  │  ├─ actions.py
│  │  ├─ config.py
│  │  ├─ forms.py
│  │  ├─ loader.py
│  │  ├─ logic.py
│  │  ├─ state.py
│  │  ├─ window.py
│  │  ├─ control_center_pages/
│  │  │  ├─ page_connection.py
│  │  │  ├─ page_model.py
│  │  │  ├─ page_style.py
│  │  │  └─ page_info.py
│  │  └─ control_center_widgets/
│  ├─ theme/
│  └─ workers/
└─ docs/
   └─ architecture/
```

## 3. 顶层目录职责

### app.py

主程序入口。负责：

- 创建主窗口
- 启动 bootstrap
- 装配服务实例
- 绑定 UI 与运行时链路
- 调起控制中心与回复文本窗口

### config.py

项目基础配置中心。负责：

- 项目根目录与各子目录常量
- runtime / workspace / user_prefs 文件路径
- 默认 LLM / ASR / TTS 参数
- 机器配置缓存读取
- 目录初始化

### bootstrap/

负责“这台电脑是否能跑起来”的启动准备层。

- `machine_profile_service.py`：维护每台电脑自己的外部路径与连接配置
- `startup_check_service.py`：检查 Ollama 与 GPT-SoVITS 是否可用，只检查有限候选路径，不做全盘扫描

### data/

#### data/runtime/
保存当前已应用状态，例如：

- 当前模型
- 当前角色
- 当前风格
- 当前输出模式
- 当前语音配置
- 当前 TTS 包

这部分数据用于“程序现在真的在用什么”。

#### data/workspace/
保存临时草稿和中间结果，例如：

- 草稿身份
- 当前风格选择
- 当前语音选择
- preview 文本
- raw / visible / tts 三段回复文本

这部分数据用于“正在编辑或刚刚处理中”。

#### data/user_prefs/
保存和机器相关、用户相关的配置，例如：

- `machine_profile.json`
- `search_paths.json`
- `tool_permissions.json`
- `install_manifest.json`

这一层是后续“连接电脑 / 文件搜索 / 应用启动”设计的重要落点。

### characters/

保存正式角色资产、角色风格和 voice profile 等结构化内容，是角色系统的正式资产层。

### library/

保存当前原型阶段仍在使用的预设、风格模板、测试语音、组合方案等库资源。它与 `characters/` 并存，说明项目正处于“旧资源库 + 新角色结构”并行过渡阶段。

### models/

保存本地模型相关目录：

- `models/llm/`
- `models/asr/`
- `models/registry/`
- `models/tts/`

当前压缩包中已经包含 `models/tts/gpt_sovits/` 示例资源目录。

### temp/

临时运行目录：

- `records/`：录音文件
- `replies/`：回复音频
- `cache/`：临时缓存
- `sessions/`：临时会话文件

### downloads/ / favorites/

保存用户主动导出或收藏的音频结果。

### ui/

界面层目录，负责：

- 主聊天页
- 设置与状态弹窗
- 音频消息卡与录音消息卡
- 控制中心
- 回复文本查看窗口
- 主题与样式资源
- worker 线程封装

## 4. services 分层职责

### services/persona/

角色与风格层：

- `prompt_builder_service.py`
- `role_service.py`
- `style_profile_service.py`
- `temporary_style_service.py`
- `voice_profile_service.py`

负责把角色、风格、临时语气、声音配置组合成可用于聊天和 TTS 的当前状态。

### services/reply/

回复链路层：

- LLM 后端控制
- 请求分类
- presence / stream 状态
- 模型回复策略
- `reply_engine/` 内部提取、修复、评估、策略选择、封装

这一层是后续“桌面指令 / 工具调用 / 文件操作回复包装”的关键扩展位置。

### services/runtime/

主运行协作层：

- `app_bootstrap_service.py`
- `app_lifecycle_runtime_service.py`
- `audio_runtime_service.py`
- `chat_runtime_service.py`
- `media_library_runtime_service.py`
- `ui_bridge_service.py`

负责把 UI、LLM、TTS、音频播放、收藏下载、应用生命周期真正串起来。

### services/tts/

TTS 层：

- `tts_service.py`
- `tts_package_service.py`
- `tts_backend_controller_service.py`
- `backends/gpt_sovits_adapter.py`
- `backends/gpt_sovits_manager.py`

当前已形成 Edge / GPT-SoVITS 双后端结构，并且 GPT-SoVITS 的延迟问题已经通过 adapter 复用与串行化做过一轮优化。

## 5. 控制中心分层结构

控制中心当前不是一个单文件，而是明确分层：

### 容器层

- `window.py`

负责窗口本体、页面引用、信号转发、整体状态组织。

### 加载层

- `loader.py`

负责从 runtime / workspace / services 中读取当前状态并回填到 UI。

### 联动层

- `logic.py`

负责页面内联动行为，例如控件联动、可见性切换、规则判断。

### 表单层

- `forms.py`

负责把各页面上的控件值收集成可保存的数据字典。

### 状态层

- `state.py`

负责脏状态、窗口标题提示、切页前确认等逻辑。

### 动作层

- `actions.py`

负责真正的“应用 / 保存 / 删除 / 纯 TTS 测试 / 加载 / 播放”执行。

### 页面层

- `page_connection.py`：连接配置
- `page_model.py`：运行配置
- `page_style.py`：风格设计
- `page_info.py`：组合 / 测试 / 摘要

## 6. 关键运行连接关系

### 启动阶段

1. `app.py` 创建 `DesktopAIController`
2. `AppBootstrapService` 启动
3. 读取 `machine_profile.json`
4. 运行 `startup_check_service.py`
5. 检查 Ollama 与 GPT-SoVITS 可用性
6. 创建主窗口与控制中心

### 主聊天阶段

1. 主页面接收文字或录音
2. 录音交给 ASR
3. 文字进入 `ChatRuntimeService`
4. `PromptBuilderService` 组装系统提示
5. LLM 生成回复
6. `ReplyPipelineService` 产出 `raw / visible / tts` 三段文本
7. `TTSService` 合成音频
8. 主页面展示消息并接入播放 / 收藏 / 下载

### 回复文本查看阶段

`reply_pipeline_window.py` 只读展示 `data/workspace/` 中的三段回复文件，用于检查模型原始回复、可见回复和 TTS 文本之间的差异。

### 控制中心应用阶段

控制中心页面的操作最终由 `actions.py` 触发，写入 runtime 或 workspace，再经 `loader.py` 刷新 UI。与主窗口之间通过状态信号同步当前角色、模型、语音后端与包选择。

## 7. 当前固定版的可搬运设计思路

这部分是当前压缩包最重要的工程方向之一。

### 已经具备的可搬运基础

- 项目以相对路径组织主目录
- 每台电脑差异信息集中到 `machine_profile.json`
- 启动检查不做全盘扫描，只做有限候选路径检查
- runtime、workspace、user_prefs 已经分离
- TTS、角色、风格、组合、回复文本分别落在不同目录

### 当前仍需注意的问题

- `requirements.txt` 中仍混入了一条本机 pip 命令记录，不适合直接发布
- `.history/` 体积很大，适合开发阶段保留，不适合最终演示压缩包
- 语音资产、模型权重、示例角色是否全部公开，需要后续筛选
- `library/` 与 `characters/` 同时存在，后续要决定长期归并策略

### 对外发布建议

若要做 GitHub Demo 或跨电脑搬运版本，建议：

1. README 放在根目录
2. 结构文档放在 `docs/architecture/`
3. 机器路径只改 `machine_profile.json`，不改源码
4. 模型大文件与敏感语音资产单独说明，不直接上传全部训练资产
5. 将“正式发布包”和“开发历史包”分离

## 8. 为什么这份文档对下一阶段重要

下一阶段要进入“连接电脑 / 桌面控制”设计，这要求项目从“会聊天、会说话”进一步扩展为“能访问本地资源并安全执行动作”的桌面代理原型。

而当前压缩包里已经存在一些很关键的基础：

- `machine_profile.json`：机器级配置
- `search_paths.json`：搜索根路径预留
- `tool_permissions.json`：工具权限预留
- `desktop` 配置块：桌面软件与默认项目目录预留

这说明当前项目已经具备继续向下扩展桌面能力的结构基础，不需要推翻重写。

## 9. 下一阶段建议的衔接方式

进入连接电脑设计时，建议保持以下原则：

- 不推翻当前主页面布局
- 不推翻当前控制中心多页面结构
- 电脑连接能力优先落在 `services/runtime/` 与新增 `services/desktop/` 层
- 权限、白名单、确认逻辑优先落在 `data/user_prefs/` 配置层
- 主页面只显示结果与状态，不承担复杂系统逻辑

这样可以在保留当前固定版成果的前提下，平滑进入下一阶段。
