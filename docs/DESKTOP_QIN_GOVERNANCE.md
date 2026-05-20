# 桌面连接秦治理链说明

本文用于放在 GitHub `docs/` 目录中，作为 README 的扩展说明。README 负责安装、启动和总览；本文负责说明桌面连接、秦治理链、三省六部、协议结构和权限设计。

---

## 1. 文档定位

桌面连接模块不是让 LLM 或 UI 直接操作系统，而是把文件、软件、虚拟机和宿主机动作统一纳入结构化治理链。

核心原则：

- 所有真实触达 Host、VM 或文件系统的动作，都必须形成结构化 `DesktopTask`。
- LLM 只负责理解意图、生成候选计划或解释结果，不拥有直接执行权限。
- UI 只负责展示和触发，不是最终权限来源。
- Sandbox、VM、Host 三个出口必须隔离，失败不能自动回落到更高风险出口。
- 高风险动作必须具备确认、审计、checkpoint、隔离或恢复材料。

---

## 2. 总体连接结构

```text
用户输入 / 语音输入 / UI 按钮
  ↓
主界面 / 控制中心
  ↓
ChatRuntimeService / LanguageInteractionCenter
  ↓
Tianting：连接、发现、候选目标、VM bridge
  ↓
QinRuntimeService：统一治理入口
  ↓
中书省：任务编译
  ↓
门下省：审议权限、模式、风险、出口
  ↓
兵部 / 刑部 / 少府：节流、确认、材料保护
  ↓
尚书省：路由分发
  ↓
工部：Sandbox / VM / Host adapter
  ↓
礼部：用户回执
  ↓
户部：统计账本
  ↓
御史台：审计事件与运行报告
```

---

## 3. services/desktop 目录关系

```text
services/desktop/
├─ tiandi/                 # 天地：桌面模式、运行态、出口状态
├─ tianting/               # 天庭：连接桥、VM bridge、目标发现
├─ qin/                    # 秦：三省六部治理主链
│  ├─ zhongshu/            # 中书省：任务编译
│  ├─ menxia/              # 门下省：ReviewGate 审议
│  ├─ shangshu/            # 尚书省：路由与分发
│  ├─ gongbu/              # 工部：执行适配器
│  ├─ libu/                # 吏部：对象名册与候选治理
│  ├─ hubu/                # 户部：权限账本与统计
│  ├─ liyi/                # 礼部：回执、提示、展示文案
│  ├─ bingbu/              # 兵部：节流、急停、会话保护
│  ├─ xingbu/              # 刑部：高风险确认与阻断
│  ├─ shaofu/              # 少府：材料、快照、隔离、恢复
│  ├─ yushitai/            # 御史台：审计、报告、测试矩阵
│  ├─ heibingtai/          # 黑冰台：目标解析、关闭协调
│  └─ zongzheng/           # 宗正：动作目录、风险模型、制度词汇
└─ xingjun/                # 星君：测试计划、dry-run、测试矩阵辅助
```

---

## 4. 三省六部结构表

| 机构 | 工程定位 | 主要职责 | 是否执行动作 |
|---|---|---|---|
| 中书省 | `qin/zhongshu/` | 将 UI / LLM / 测试入口整理为结构化 `DesktopTask`。 | 否 |
| 门下省 | `qin/menxia/` | 审议桌面模式、对象权限、动作风险、执行出口。核心为 `ReviewGate`。 | 否 |
| 尚书省 | `qin/shangshu/` | 根据审议结果进行路由、分发和结果结构化。 | 间接调度 |
| 吏部 | `qin/libu/` | 管理文件对象、软件对象、候选目标、可见性、对象归类。 | 否 |
| 户部 | `qin/hubu/` | 记录权限账本、一次性授权、动作次数、耗时、失败率和扫描统计。 | 否 |
| 礼部 | `qin/liyi/` | 生成权限提示、按钮文案、拒绝理由、用户可读回执和报告摘要。 | 否 |
| 兵部 | `qin/bingbu/` | 处理节流、急停、连续失败熔断、超时和防重复点击。 | 否 |
| 刑部 | `qin/xingbu/` | 对删除、卸载、移动、更新、恢复等危险动作进行确认和阻断。 | 否 |
| 工部 | `qin/gongbu/` | 调用 Sandbox / VM / Host adapter 执行已审议任务。 | 是 |

---

## 5. 扩展机构职责

| 机构 | 工程定位 | 职责 |
|---|---|---|
| 天地 | `services/desktop/tiandi/` | 管理桌面模式、运行态、Host / Sandbox / VM 出口状态。 |
| 天庭 | `services/desktop/tianting/` | 连接桥接、对象发现、VM 连接 worker、命令候选准备；不审批、不最终执行。 |
| 星君 | `services/desktop/xingjun/` | 测试计划、测试矩阵、dry-run 辅助；不直接执行系统动作。 |
| 宗正 | `qin/zongzheng/` | 定义动作目录、风险模型、权限词汇、审议词汇和 schema。 |
| 少府 | `qin/shaofu/` | 管理快照、隔离、恢复材料、restore token、恢复索引。 |
| 御史台 | `qin/yushitai/` | 记录运行会话、事件、审计快照、报告和测试矩阵。 |
| 黑冰台 | `qin/heibingtai/` | 解析文件、窗口、运行中文档、关闭目标和软件能力索引。 |

---

## 6. 桌面模式与执行出口

### 6.1 桌面模式

| 模式 | 含义 | 规则 |
|---|---|---|
| `disabled` | 桌面连接关闭 | 拒绝全部桌面动作。 |
| `restricted` | 受限模式 | 只允许只读、查看、基础浏览或系统信息读取。 |
| `trusted` | 信任模式 | 可显示完整治理区和可调整状态；Host 实控仍应灰度后置。 |
| `test` | 测试模式 | 默认 Sandbox；用户明确选择后进入 VM 测试。 |

### 6.2 执行出口

| 出口 | 显示对象 | 真实执行位置 | 是否写 Host 权限配置 | 当前用途 |
|---|---|---|---|---|
| `sandbox` | Host 文件 / Host 软件治理数据 | 不真实执行 | 可写测试配置或回执状态 | 审议、权限、回执模拟。 |
| `vm` | VM Agent 返回的文件 / 软件数据 | 虚拟机内执行 | 不写 Host 权限配置 | V2.5 / V3 真实测试主出口。 |
| `host` | Host 文件 / Host 软件治理数据 | 宿主机执行 | 写 Host 权限与审计 | V4 后灰度开放，当前不默认开放。 |

---

## 7. 权限状态设计

| 权限状态 | UI 文案 | 适用范围 | 含义 |
|---|---|---|---|
| `unset` | 未设置 / 否 | Host 文件 / Host 软件 | 默认不执行，只提示用户配置权限。 |
| `deny` | 禁止 / 否 | Host 文件 / Host 软件 | 明确禁止，直接拒绝并记录原因。 |
| `once` | 受限 / 仅一次 | Host 沙盒回执、未来 Host 灰度 | 允许一次，执行后消费。 |
| `allow` | 是 / 允许 | Host 白名单对象 | 允许经过审议的动作，但仍受模式、出口和风险约束。 |
| `test` | 测试 | VM 文件 / VM 软件 | 只用于 VM，不写入 Host 权限配置。 |

注意：`permission_state="test"` 不应进入 Host / Sandbox 的正式权限判断。VM 模式应由 VM 相关服务分流，不得混入 Host 权限账本。

---

## 8. 权限与动作矩阵

### 8.1 软件动作

| 动作 | 风险 | Sandbox | VM | Host 当前阶段 | 未来 Host V4 |
|---|---|---|---|---|---|
| `app.locate` | 低 | 回执模拟 | 允许测试 | 禁止或灰度关闭 | 条件允许 |
| `app.launch` | 中 | 回执模拟 | 允许测试 | 禁止或灰度关闭 | 条件允许 |
| `app.close` | 中高 | 回执模拟 | 允许测试 | 禁止或灰度关闭 | 条件允许 |
| `app.uninstall` | 高危 | 拒绝或危险回执 | 暂禁 / 后续预演 | 禁止 | 强确认后评估 |
| `app.move` | 高危 | 拒绝或危险回执 | 暂禁 / 后续预演 | 禁止 | 强确认后评估 |
| `app.update` | 高危 | 拒绝或危险回执 | 暂禁 / 后续预演 | 禁止 | 强确认后评估 |

### 8.2 文件动作

| 动作 | Sandbox | VM workspace | Host 当前阶段 | 备注 |
|---|---|---|---|---|
| `file.list` | 回执模拟 | 允许 | 只读或缓存 | VM 限定 workspace。 |
| `file.meta` | 回执模拟 | 允许 | 只读或缓存 | 返回 exists / size / modified_at 等。 |
| `file.open` / `file.locate` | 回执模拟 | 允许 | 灰度后置 | 打开语义与关闭语义分离。 |
| `file.create` | 回执模拟 | V3 测试 | 禁止或灰度后置 | 限 workspace。 |
| `file.rename` | 回执模拟 | V3 测试 | 禁止或灰度后置 | 需记录旧名和新名。 |
| `file.move` | 危险回执 | V3 测试 | 禁止或灰度后置 | 需确认目标路径和恢复策略。 |
| `file.delete` | 危险回执 | 高危测试 | 禁止直接硬删 | 优先 quarantine，不直接永久删除。 |
| `file.restore` | 恢复回执 | 基于材料恢复 | 基于少府材料恢复 | 依赖 restore token / material。 |

---

## 9. 结构化协议说明

### 9.1 DesktopTask

所有桌面动作应进入统一任务结构。

```json
{
  "task_id": "uuid-or-string",
  "source": "chat | voice | ui | test_runner",
  "intent": "file.open | file.rename | app.launch | app.close | vm.connect | system_info.read_datetime",
  "target": {
    "kind": "file | folder | app | vm | system",
    "id": "stable-object-id",
    "path": "optional-local-path",
    "display_name": "user-facing-name"
  },
  "mode": "disabled | restricted | trusted | test",
  "execution_backend": "sandbox | vm | host",
  "risk_level": "low | medium | high | destructive",
  "requires_confirmation": false,
  "restore_strategy": "none | checkpoint | quarantine | snapshot",
  "metadata": {
    "request_text": "用户原始请求",
    "created_by": "llm | ui | system",
    "candidate_confidence": 0.92
  }
}
```

### 9.2 ReviewDecision

门下省审议后输出决策。

```json
{
  "decision": "allow | deny | need_confirm | route_to_test",
  "reason_code": "permission_denied | high_risk | allowed_by_once | vm_only | backend_disabled",
  "required_confirmation": false,
  "execution_backend": "sandbox | vm | host",
  "guards": ["throttle", "checkpoint", "deny_roots"],
  "message": "给 UI 或礼部使用的短原因"
}
```

### 9.3 Receipt

执行后输出统一回执。

```json
{
  "ok": true,
  "executed": true,
  "executed_in": "sandbox | vm | host",
  "status": "success | denied | need_confirm | failed | action_not_enabled",
  "display_text": "给用户看的短回执",
  "tts_text": "用于语音播放的回执",
  "audit": {
    "run_id": "...",
    "event_id": "..."
  },
  "restore_material": {
    "kind": "checkpoint | quarantine | none",
    "id": "..."
  }
}
```

### 9.4 VM Action Payload

VM Agent 只接收结构化 action，不接收自然语言。

```json
{
  "action": "app.launch",
  "target": {
    "app_id": "vm_notepad"
  },
  "request_id": "uuid",
  "dry_run": false
}
```

文件动作示例：

```json
{
  "action": "file.rename",
  "target": {
    "root_id": "vm_workspace",
    "relative_path": "demo/a.txt"
  },
  "args": {
    "new_name": "a-renamed.txt"
  },
  "request_id": "uuid",
  "dry_run": false
}
```

---

## 10. VM Agent 安全规则

VM Agent 是虚拟机真实测试的执行边界，不应承担 Host 侧审议职责。

| 规则 | 要求 |
|---|---|
| 只接受结构化请求 | 不接受自然语言。 |
| 软件动作只接受 `app_id` | 不允许 Host 直接传任意 exe 路径让 VM 执行。 |
| 文件动作只接受 `root_id + relative_path` | 不接受任意绝对路径。 |
| 内部白名单映射 | `path`、`shell_entry`、`process_name` 由 VM Agent 内部配置决定。 |
| close 白名单 | 只关闭白名单中的进程名。 |
| 禁止 shell 直通 | 不开放任意命令行执行。 |
| 网络边界 | 建议 Host-only / NAT 私有网络，不开放公网。 |
| Token 预留 | 后续应校验 Authorization。 |
| 失败不回落 | VM 失败不能自动切换 Host 执行。 |

---

## 11. 文件治理区规则

| 区域 | 数据来源 | 执行规则 |
|---|---|---|
| Host 文件区 | Host 文件缓存 / Host 适配器 | trusted 下灰度执行，必须经过权限、审议、guard、少府材料和御史台记录。 |
| VM 文件区 | VM Agent `/files/roots` 与 `/files/list` | 在虚拟机中执行；Host 不直接操作 VM 路径。 |
| Sandbox 文件区 | Host 文件治理数据 | 只做模拟回执，不修改 Host 或 VM 文件。 |

文件治理区 UI 规则：

- 点击磁盘或目录时，只浏览允许范围。
- 无缓存且允许扫描时，默认只扫描一层，不做全盘递归。
- 系统目录、deny_roots、未授权磁盘应 blocked 或隐藏。
- 文件表不建议放“关闭”按钮；关闭文件 / 文件夹应走聊天命令和黑冰台链路。
- `rename` / `move` / `delete` / `restore` 必须生成材料，并进入审议链。

---

## 12. 软件治理区规则

| 区域 | 数据来源 | 执行规则 |
|---|---|---|
| Host 软件区 | Host 软件治理数据 / software view cache | trusted 下按权限、能力、审议和 guard 执行。 |
| Sandbox 软件区 | Host 软件治理数据 | 只改变执行出口，不改变显示数据来源；只返回审议与模拟回执。 |
| VM 软件区 | VM Agent `/apps/list` | 不读取 Host software cache；VM 动作通过 VM Adapter。 |

软件治理区 UI 规则：

- 普通用户可查看软件名称、状态、路径摘要。
- 开发者模式显示权限列和高风险动作列。
- `locate` / `launch` / `close` 可在 VM 中测试。
- `uninstall` / `move` / `update` 属于高风险动作，当前阶段应禁用或仅做危险回执。
- Host 真实启动 / 关闭不应在当前阶段默认开放。

---

## 13. 黑冰台目标解析规则

黑冰台负责把“关闭这个文件”“关闭刚才的报告”“关闭 Steam”这类模糊表达解析成可审议目标。它不审批、不执行、不修改权限。

```text
用户关闭意图
  ↓
黑冰台解析目标：注册记录 / 运行中文档 / 窗口标题 / 文档适配器
  ↓
生成关闭计划：文件关闭 / 文件夹关闭 / 应用关闭 / 需要用户选择
  ↓
门下省审议
  ↓
工部执行已批准任务
  ↓
礼部回执 + 御史台记录
```

常见模块：

| 模块 | 职责 |
|---|---|
| `registered_resolver` | 已注册目标解析。 |
| `unregistered_resolver` | 未注册目标解析。 |
| `running_document_resolver` | 运行中文档解析。 |
| `file_target_resolver` | 文件目标解析。 |
| `file_close_planner` | 文件关闭计划。 |
| `folder_close_planner` | 文件夹关闭计划。 |
| `software_capability_index` | 软件能力索引。 |
| `file_open_policy_service` | 文件打开策略。 |
| `close_coordinator` | 关闭协调。 |

---

## 14. 最终原则

Sandbox 负责审议与回执模拟；VM 负责虚拟机真实测试；Host 是 trusted 模式下的灰度真实执行出口。三者都不能绕过秦治理链。
