# 语言理解与回复编排层设计边界

## 定位

LanguageInteractionCenter 是运行时编排门面，不是新执行系统。

它用于在 ChatRuntimeService 和现有业务模块之间建立稳定的标准层，后续逐步承接语言理解、pending、系统能力、桌面命令、纠察司、秦链、回执与回复之间的连接顺序。

## 它负责

- 标准化用户输入上下文
- 标准化路由理解包
- 标准化最终交互结果
- 未来逐步连接 pending、system skill、desktop command、Jiuchasi、Qin、ResultBridge
- 帮助 ChatRuntimeService 瘦身

## 它不负责

- 不直接执行桌面动作
- 不直接回答事实类信息
- 不直接生成当前时间、日期、天气
- 不绕过 QinRuntimeService
- 不替代 JiuchasiService
- 不替代 PendingTaskService
- 不替代 ResultBridgeService
- 不直接写 UI
- 不直接调用 LLM

## 依赖边界

- app.py：UI 输入与窗口生命周期
- ChatRuntimeService：请求生命周期、ChatWorker、流式 UI、TTS
- LanguageInteractionCenter：运行时编排门面
- DesktopCommandDetector：快速桌面意图识别
- BasicSystemSkillRouter：快速系统能力识别
- JiuchasiService：复杂桌面理解和证据判断
- PendingTaskService：pending 状态存储
- QinRuntimeService：三省六部执行入口
- ResultBridgeService：事实回执到安全回复
- CommandMemoryService：记忆读写，不代表权限

## 当前实际连接顺序

当前代码中的主链路以 ChatRuntimeService 为请求生命周期入口，LanguageInteractionCenter 作为编排门面参与路由、pending、系统能力、纠察司和回执处理。实际顺序如下：

用户输入
→ app.py
→ ChatRuntimeService.start_chat_request
→ RequestClassifierService.classify
→ LanguageInteractionCenter.route_desktop_command
→ DesktopCommandDetector 快速桌面识别
→ LanguageInteractionCenter.route_pending_followup
→ pending followup 纠正 / 文字确认判断
→ 如果仍为 chat_reply，再进入 LanguageInteractionCenter.route_basic_system_skill
→ BasicSystemSkillRouter / SystemSkillSemanticRouter 系统能力识别
→ 如果是 desktop_command，进入 JiuchasiService 证据判断与候选确认
→ 如果需要用户确认，进入 PendingTaskService
→ 如果可以执行，进入 QinRuntimeService
→ Qin / Host / VM / adapter 返回事实回执
→ ResultBridgeService / ReceiptMaterial / InteractionResult
→ ReceiptReplyPolisher 只润色 display_text / tts_text
→ ChatRuntimeService._finish_direct_safe_reply
→ UI / TTS

说明：

- 当前实际代码中，DesktopCommandDetector 的调用早于 BasicSystemSkillRouter；系统能力只有在桌面识别仍为 chat_reply 时才继续判断。
- pending followup 会在桌面识别之后进行二次修正，避免“确认 / 选择第一个 / 取消”等短句落入普通聊天。
- SystemSkillSemanticRouter 只作为 BasicSystemSkillRouter 未命中后的受限语义兜底，不能输出事实答案。
- Jiuchasi、PendingTaskService、QinRuntimeService 仍各自保持原职责，LanguageInteractionCenter 只负责连接与标准化，不直接执行。

## ReceiptMaterial 回执材料边界

ReceiptMaterial 是事实回执标准包。

它不负责判断事实，不负责生成新回复，也不调用语言渲染服务。它只承接 Qin、Jiuchasi、Pending、SystemSkill 等已有结果，把这些结果整理成稳定字段，方便后续 ResultBridge 或回复渲染层生成 InteractionResult。

ReceiptMaterial 不改变 ok、executed、status、message_key、safe_user_message 等字段含义。它只做字段标准化，不做业务判断。

## MemoryUpdatePlan 记忆更新计划边界

MemoryUpdatePlan 只是计划，不是写入动作。

只有用户确认且执行结果可信后，未来才允许根据 MemoryUpdatePlan 写入 CommandMemoryService。本阶段不写入任何记忆文件，不写 software_terms.local.json、file_terms.local.json 或 user_habits.local.json。

## 第一阶段状态

当前只新增标准层，不接入主流程，不改变任何行为。
