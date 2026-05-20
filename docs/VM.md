# VM 连接说明 / AI_VM_TEST VM Agent

本文说明 **Desktop AI Assistant / 小助理 Demo** 如何连接独立的 **AI_VM_TEST / VM Agent** 工程，并说明 VM 路径中的三省六部职责、权限边界、接口协议和测试命令。

- VM Agent 仓库：[Qzy10030608/AI_VM_TEST](https://github.com/Qzy10030608/AI_VM_TEST)
- 主项目文档：[DESKTOP_QIN_GOVERNANCE.md](DESKTOP_QIN_GOVERNANCE.md)
- 上传边界文档：[GIT_UPLOAD_BOUNDARY.md](GIT_UPLOAD_BOUNDARY.md)

> VM Agent 是运行在虚拟机内部的薄连接器 / 薄执行器。它不替代 Host 主项目的权限治理，不理解自然语言，也不决定是否允许执行。Host 侧的小助手仍然负责三省六部审议、权限状态、checkpoint、少府材料、御史台报告和 UI 展示。

---

## 1. 文档定位

VM 连接用于在虚拟机中测试小助手的桌面动作能力，例如：

- 浏览 VM 内文件目录；
- 打开、定位、关闭 VM 内文件或文件夹；
- 在 VM 内扫描、启动、定位、关闭软件；
- 对文件 create / rename / move / delete / restore 等动作进行测试；
- 为后续语音 / 文字桌面指令提供安全测试出口。

当前设计中有三个执行出口：

| 出口 | 是否真实执行 | 数据来源 | 用途 |
|---|---:|---|---|
| Sandbox | 否 | Host 文件 / 软件治理清单 | 审议链、权限链、回执模拟。 |
| VM | 是，仅虚拟机内 | VM Agent 返回的文件 / 软件数据 | V3 / V4 文件区、软件区动作测试。 |
| Host | 是，宿主机内 | Host 文件 / 软件治理清单 | 后置灰度能力，不应默认开放。 |

核心原则：**VM 失败不能回落 Host，Host 也不能直接用本机文件系统操作 VM 路径。**

---

## 2. 总体连接链路

```text
用户文字 / 语音 / 控制中心按钮
  ↓
Host 小助手：生成结构化 DesktopTask
  ↓
QinRuntimeService.execute_desktop_task(task)
  ↓
中书省 / 门下省 / 尚书省：拟旨、审议、调度
  ↓
工部 VM Adapter：HTTP 请求 VM Agent
  ↓
AI_VM_TEST / desktop_vm_agent.py
  ↓
VM 内部 vma/files.py 或 vma/apps.py 执行动作
  ↓
标准 receipt 回传 Host
  ↓
礼部回执 / 户部统计 / 少府材料 / 御史台记录 / UI 展示
```

### 2.1 连接关系说明

| 阶段 | 所在位置 | 职责 | 禁止事项 |
|---|---|---|---|
| 用户输入 | 主界面 / 控制中心 / 语音链路 | 接收文字、语音或按钮触发。 | 不直接拼接系统命令。 |
| 任务生成 | Host 主项目 | 转为结构化 DesktopTask / action。 | 不直接操作 VM 文件系统。 |
| 审议 | QinRuntimeService / ReviewGate | 判断模式、权限、对象、风险和执行出口。 | 不能绕过三省六部。 |
| 调度 | 工部 VM Adapter | 向 VM Agent 发送 HTTP 请求。 | VM 失败不能自动切 Host。 |
| 执行 | VM Agent | 只在虚拟机内执行结构化 action。 | 不理解自然语言，不做终审。 |
| 回执 | VM Agent → Host | 返回 ok/error、executed_in、action、data。 | 不能只返回普通文本。 |

---

## 3. 三省六部在 VM 连接中的职责

VM Agent 不是新的治理中心，它只是工部下的一个 VM 执行出口。治理仍然发生在 Host 主项目的 Qin 链中。

| 机构 | VM 路径中的职责 |
|---|---|
| 中书省 | 把 UI / 语音 / 文字请求整理成标准 action、target、arguments。 |
| 门下省 | 审议当前桌面模式、对象权限、动作风险、执行出口和是否需要确认。 |
| 尚书省 | 根据当前模式和 test_backend，把动作路由到 sandbox、vm 或 host。 |
| 工部 | 调用 VM Adapter，把已审议任务转成 VM Agent HTTP 请求。 |
| 吏部 | 管理 VM 文件对象、VM 软件对象、候选目标、对象归类。 |
| 户部 | 记录动作次数、耗时、失败率、扫描统计和执行账本。 |
| 礼部 | 生成用户可读回执、权限提示、失败说明和 UI 状态文案。 |
| 兵部 | 处理节流、急停、超时、连续失败熔断和重复点击防护。 |
| 刑部 | 对 delete / uninstall / move / update 等高危动作进行确认、拒绝或阻断。 |
| 少府 | 管理 checkpoint、隔离、restore token、manifest、备份和恢复材料。 |
| 御史台 | 记录事件、运行会话、测试矩阵、报告和审计材料。 |
| 黑冰台 | 解析运行中文件、窗口、关闭目标和软件能力索引；不审批、不执行。 |

---

## 4. VM Agent 项目结构

AI_VM_TEST 仓库建议保持如下结构：

```text
AI_VM_TEST/
├─ desktop_vm_agent.py          # HTTP 入口、GET/POST 路由、启动服务
├─ agent_config.json            # VM 内边界、端口、开关、roots 配置
├─ start_agent.bat              # 可选：快速启动脚本
├─ README.md                    # VM Agent 自身说明
└─ vma/
   ├─ __init__.py
   ├─ cfg.py                    # 配置、路径、开关、版本
   ├─ util.py                   # receipt、json_response、路径校验、命令执行
   ├─ files.py                  # 文件管理区动作
   ├─ apps.py                   # 软件管理区动作
   └─ route.py                  # ACTION_HANDLERS 与 dispatch_action
```

模块边界：

| 文件 | 职责 |
|---|---|
| `desktop_vm_agent.py` | 只保留 HTTP 接收、路由和启动，保持薄入口。 |
| `vma/cfg.py` | 读取 `agent_config.json`，暴露 host、port、roots、开关和超时。 |
| `vma/util.py` | 公共工具、路径边界、receipt、json 响应、命令执行。 |
| `vma/files.py` | roots/list/open/close/rename/move/delete/restore/create 等文件区动作。 |
| `vma/apps.py` | app.scan/locate/launch/close/uninstall/move/update 等软件区动作。 |
| `vma/route.py` | action 分发表；新增 action 时只补分发，不写业务逻辑。 |

---

## 5. 启动 VM Agent

在虚拟机中准备 AI_VM_TEST 工程后运行：

```powershell
cd C:\AI_VM_TEST
python desktop_vm_agent.py
```

启动后默认监听：

```text
http://0.0.0.0:8765
```

Host 小助手访问时应使用虚拟机 IP，例如：

```powershell
Invoke-RestMethod http://192.168.114.128:8765/health | ConvertTo-Json -Depth 10
Invoke-RestMethod http://192.168.114.128:8765/capabilities | ConvertTo-Json -Depth 10
```

建议先确认：

- VM 与 Host 在 Host-only / NAT 私有网络中可互通；
- Windows 防火墙允许 8765 端口或当前 Python 进程；
- `/health` 能返回 `executed_in="vm"`、版本、hostname、pid；
- `/capabilities` 能返回 action 列表和危险动作开关状态。

---

## 6. agent_config.json 示例

`agent_config.json` 是 VM 内的最小边界，不替代 Host 三省六部审议。测试阶段可以适度放开 VM 内路径，但正式或长期测试应收窄 roots。

```json
{
  "host": "0.0.0.0",
  "port": 8765,
  "token": "",
  "allow_legacy_apps_api": true,
  "allow_action_api": true,
  "allow_dynamic_app_scan": true,
  "enable_file_write_actions": true,
  "allow_any_vm_file_read": true,
  "allow_any_vm_file_write": true,
  "file_read_roots": ["C:\\"],
  "file_write_roots": ["C:\\"],
  "deny_roots": [
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "C:\\System Volume Information"
  ],
  "enable_app_uninstall": false,
  "enable_app_move": false,
  "enable_app_update": false,
  "test_root": "C:\\AI_VM_TEST",
  "workspace_root": "C:\\AI_VM_TEST\\workspace",
  "runtime_root": "C:\\AI_VM_TEST\\runtime",
  "quarantine_root": "C:\\AI_VM_TEST\\quarantine"
}
```

重要配置项：

| 配置项 | 说明 |
|---|---|
| `allow_action_api` | 是否允许 `POST /action`。关闭后 V4 主动作不可执行。 |
| `allow_legacy_apps_api` | 是否允许 `/apps/list`、`/files/roots`、`/files/list`。 |
| `allow_dynamic_app_scan` | 是否动态扫描注册表与快捷方式。 |
| `enable_file_write_actions` | 是否允许文件写动作，如 rename/move/delete/create/restore。 |
| `allow_any_vm_file_read/write` | 测试阶段放开 VM 内 read/write；`deny_roots` 仍优先。 |
| `file_read_roots` / `file_write_roots` | allow_any 为 false 时使用的读写白名单。 |
| `deny_roots` | 最高优先级拒绝目录，系统目录应保持拒绝。 |
| `enable_app_uninstall/move/update` | 软件高危动作开关，默认建议关闭。 |

---

## 7. HTTP 接口

| 接口 | 方法 | 用途 |
|---|---|---|
| `/health` | GET | 健康检查，返回版本、hostname、PID、feature flags。 |
| `/capabilities` | GET | 能力声明，返回 action 列表、危险开关和 roots 状态。 |
| `/apps/list` | GET | 旧兼容软件列表，用于软件治理区展示。 |
| `/files/roots` | GET | VM 文件根目录，例如 `vm_drive_c`。 |
| `/files/list` | GET | 按 `root_id + relative_path` 列出一层目录。 |
| `/action` | POST | V4 主执行接口，文件区、软件区、浏览器、会话统一入口。 |

### 7.1 标准 action payload

```json
{
  "request_id": "vm-test-001",
  "protocol_version": "v4.agent.1",
  "action": "file.open",
  "target": {
    "path": "C:\\AI_VM_TEST\\workspace\\demo.txt",
    "target_path": "C:\\AI_VM_TEST\\workspace\\demo.txt",
    "target_type": "file"
  },
  "options": {
    "timeout_sec": 10
  },
  "meta": {
    "source": "desktop_ai_assistant",
    "execution_backend": "vm",
    "path_namespace": "vm_windows"
  }
}
```

### 7.2 标准 receipt

```json
{
  "ok": true,
  "request_id": "vm-test-001",
  "protocol_version": "v4.agent.1",
  "agent": "desktop_vm_agent",
  "package_version": "0.4.2",
  "executed_in": "vm",
  "action": "file.open",
  "hostname": "VM-HOSTNAME",
  "system": "Windows-...",
  "pid": 1234,
  "timestamp_ms": 1710000000000,
  "message": "VM file open executed.",
  "status": "ok",
  "data": {},
  "error": ""
}
```

约束：

- 所有 VM 动作必须返回 `executed_in="vm"`；
- 失败时 `ok=false`，并填写 `error`；
- 打开动作应返回 `open_handle`、`pid/pids`、`tracked`、`opener`；
- 删除动作应返回 `restore_token`、`quarantine_path`、`manifest_path`；
- Host 侧应把 `request_id` 写入御史台报告，方便追踪。

---

## 8. 文件区动作

| Action | 用途 | 风险建议 | 说明 |
|---|---|---|---|
| `file.list` | 列出目录 | low | 按 root_id + relative_path 浏览一层。 |
| `file.inspect` | 读取元信息 | low | 只读，不打开文件。 |
| `file.locate` / `folder.locate` | 定位文件 / 文件夹 | low | Explorer 定位或打开目录。 |
| `file.open` / `folder.open` | 打开对象 | medium | 已打开则激活，不重复打开。 |
| `file.close` / `folder.close` | 关闭窗口 | high | 按 target_path / Explorer 路径关闭，不能强杀全局 Explorer。 |
| `file.rename` / `folder.rename` | 重命名 | high | 需要 write roots 和 restore_strategy。 |
| `file.move` / `folder.move` | 移动 | high | source/dest 均需边界检查。 |
| `file.copy` | 复制 | medium/high | 源走 read，目标走 write。 |
| `file.delete` / `folder.delete` | 隔离删除 | critical | 不真删，移动到 quarantine，生成 restore_token。 |
| `file.restore` / `folder.restore` | 恢复 | high | 基于 restore_token 或 manifest，不允许凭空推断。 |
| `file.touch` / `file.mkdir` / `file.create` | 创建 | high | 目标路径必须通过 write roots 与 deny_roots。 |

---

## 9. 软件区动作

| Action | 用途 | 开关 / 边界 | 说明 |
|---|---|---|---|
| `app.scan` | 动态扫描软件列表 | `allow_dynamic_app_scan` | 扫描注册表、快捷方式和 fallback apps。 |
| `app.locate` | 定位软件入口 | read 边界 | Explorer `/select` 或 AppX shell 入口。 |
| `app.launch` | 启动软件 | 普通启动 | local exe 或 appx shell_entry。 |
| `app.close` | 关闭软件进程 | process_name/process_names | 不应模糊关闭系统核心进程。 |
| `app.uninstall` | 启动卸载 | `enable_app_uninstall` | 高危；GUI 卸载需要用户在 VM 内确认。 |
| `app.move` / `app.relocate` | 移动 / 迁移软件 | `enable_app_move` + admin | 高危；涉及注册表、快捷方式、服务和备份。 |
| `app.update` | 执行更新 | `enable_app_update` | 高危；需要更新来源和回滚材料。 |

软件区测试应先验证 locate / launch / close；uninstall / move / update 默认保持关闭，只有 VM 快照和回滚策略确认后才打开。

---

## 10. Host 侧测试命令

主项目中可使用 Host 侧 runner 触发 VM Agent：

```powershell
# 检查文件元信息
python tools\vm_file_action_test_runner.py inspect --target-path "C:\AI_VM_TEST\workspace\测试\demo.txt" --target-type file

# 打开文件
python tools\vm_file_action_test_runner.py open --target-path "C:\AI_VM_TEST\workspace\测试\demo.txt" --target-type file

# 关闭文件
python tools\vm_file_action_test_runner.py close --target-path "C:\AI_VM_TEST\workspace\测试\demo.txt" --target-type file

# 打开文件夹
python tools\vm_file_action_test_runner.py open --target-path "C:\AI_VM_TEST\workspace\测试" --target-type directory

# 关闭文件夹
python tools\vm_file_action_test_runner.py close --target-path "C:\AI_VM_TEST\workspace\测试" --target-type directory
```

接口直接测试：

```powershell
Invoke-RestMethod http://<VM-IP>:8765/health | ConvertTo-Json -Depth 10
Invoke-RestMethod http://<VM-IP>:8765/capabilities | ConvertTo-Json -Depth 10
Invoke-RestMethod http://<VM-IP>:8765/apps/list | ConvertTo-Json -Depth 10
Invoke-RestMethod "http://<VM-IP>:8765/files/list?root_id=vm_drive_c&relative_path=AI_VM_TEST\workspace" | ConvertTo-Json -Depth 10
```

---

## 11. GitHub 上传建议

主项目可以在 README 中链接 AI_VM_TEST 仓库，但不要把 VM 运行数据混入主仓库。

建议上传：

- VM Agent 源码；
- `agent_config.example.json`；
- README / docs；
- 测试脚本；
- 空目录占位文件，例如 `.gitkeep`。

不要上传：

- `runtime/`；
- `quarantine/`；
- `backups/`；
- VM 内真实日志；
- 真实 token；
- 真实本机路径配置；
- 大型测试文件或个人文件。

---

## 12. 常见问题

### 12.1 Host 无法访问 VM Agent

检查：

1. VM Agent 是否正在运行；
2. VM IP 是否正确；
3. 端口是否为 `8765`；
4. VM 防火墙是否允许 Python 或端口访问；
5. Host 与 VM 是否处于可互通网络。

### 12.2 `/health` 正常但动作失败

检查：

1. `/capabilities` 中 `action_api` 是否为 true；
2. 写动作是否打开 `enable_file_write_actions`；
3. 目标路径是否落入 `deny_roots`；
4. `file_read_roots` / `file_write_roots` 是否覆盖目标；
5. Host 侧 Qin 审议是否拒绝了该动作。

### 12.3 VM 软件列表不完整

检查：

1. `allow_dynamic_app_scan` 是否为 true；
2. 软件是否存在注册表 Uninstall 记录；
3. 软件是否有开始菜单 / 桌面快捷方式；
4. fallback builtin apps 是否正常返回；
5. noise filter 是否过滤了系统工具。

---

## 13. 最终规则

1. VM Agent 只执行 VM 内动作，不执行 Host 动作。
2. VM Agent 不理解自然语言，只接收结构化 action。
3. Host 小助手必须先形成 DesktopTask，再进入 QinRuntimeService 审议。
4. VM 失败不能自动回落 Host。
5. `test` 权限只用于 VM，不写入 Host 权限文件。
6. 高风险动作必须有确认、材料、回执和审计。
7. Sandbox、VM、Host 三出口都不能绕过三省六部治理链。
