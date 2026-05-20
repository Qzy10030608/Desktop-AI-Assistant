from __future__ import annotations
import re
import json
import time
from pathlib import Path
from typing import Any

from services.desktop.language.language_service import DesktopLanguageService
from services.desktop.tianting.command_memory_service import CommandMemoryService

ROUTE_SCHEMA_VERSION = "desktop_route_decision_v1"

PENDING_WORDS = {
    "第一个", "第二个", "第三个", "第1个", "第2个", "第3个",
    "1", "2", "3", "取消", "算了", "不用了", "客户端", "游戏那个",
    "游戏", "启动器", "后台", "docx那个", "pdf那个", "最近修改的",
}
OPEN_WORDS = ("打开", "开启", "启动", "运行", "找到并打开")
CLOSE_WORDS = ("关闭", "关掉", "退出", "停止", "关了")
APP_WORDS = ("软件", "程序", "应用", "浏览器", "steam", "vscode", "vs code", "code", "obs", "edge", "chrome", "记事本")
FILE_WORDS = ("文件", "文档", "报告", "说明", "材料", "结构图", "docx", "doc", "pdf", "md", "json", "txt")
CONNECTION_ENABLE_WORDS = ("开启桌面连接", "打开桌面连接", "连接电脑", "开启连接")
CONNECTION_DISABLE_WORDS = ("关闭桌面连接", "断开桌面连接", "关闭连接", "断开连接")
UNCLEAR_PATTERNS = ("帮我弄一下", "处理一下那个", "你看着办", "搞一下", "弄一下", "处理一下")
WEB_WORDS = ("查一下", "搜一下", "搜索", "打开网页", "网页", "网上查", "查查")
DEVELOPER_WORDS = ("显示 puzzle", "显示dry-run", "显示 dry-run", "显示 task", "显示task", "task 草案", "查看 pending", "切换 sandbox", "切换 vm", "vm 测试")
CHAT_HINT_WORDS = ("为什么", "怎么", "解释", "你觉得", "设计怎么样", "方案合理", "帮我写", "写一份", "分析一下", "说明一下")
MATH_CHAT_WORDS = ("等于多少", "几加几", "怎么算", "多少呀", "多少啊")


class DesktopCommandDetector:
    _json_cache: dict[str, tuple[float, Any]] = {}

    def __init__(self, contract_dir: str | Path | None = None, memory_service: CommandMemoryService | None = None) -> None:
        self.contract_dir = Path(contract_dir or Path(__file__).resolve().parent / "command_contract_library")
        self.memory_service = memory_service or CommandMemoryService()
        self.language_service = DesktopLanguageService()
        self.action_contracts = self._read_json("action_contracts.json", {})
        self.synonym_map = self._read_json("synonym_map.json", {})

    def detect(
        self,
        raw_user_text: str,
        *,
        input_channel: str = "text",
        actor_role: str = "normal_user",
        classifier_result: Any = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        detector_started = time.perf_counter()
        text = str(raw_user_text or "").strip()
        channel = "voice" if str(input_channel or "").strip().lower() == "voice" else "text"
        role = "developer" if str(actor_role or "").strip().lower() == "developer" else "normal_user"
        lowered = text.lower()
        compact = "".join(text.split()).lower()
        profile = self.language_service.profile_for_text(text)

        if not text:
            return self._finish_decision(detector_started, self._decision(text, channel, role, "chat_reply", 0.1))

        if self._looks_like_pending_followup(compact, profile):
            pending_id = self._latest_pending_id()
        else:
            pending_id = ""
        if pending_id:
            return self._finish_decision(detector_started, self._decision(
                text,
                channel,
                role,
                "pending_followup",
                0.94,
                matched_rules=["pending_followup_words", "pending_task_exists"],
                pending_task_id=pending_id,
                safe_user_message="正在处理你的选择。",
            ))

        if self._looks_like_fast_chat(compact, profile):
            return self._finish_decision(
                detector_started,
                self._decision(text, channel, role, "chat_reply", 0.9, matched_rules=["fast_chat_question"]),
            )

        if self._looks_like_developer_command(lowered, compact, profile):
            if role != "developer":
                return self._finish_decision(detector_started, self._decision(
                    text,
                    channel,
                    role,
                    "need_clarification",
                    0.8,
                    matched_rules=["developer_command_blocked"],
                    safe_user_message="这个调试指令只对开发者开放。",
                ))
            return self._finish_decision(detector_started, self._decision(
                text,
                channel,
                role,
                "developer_command",
                0.9,
                matched_rules=["developer_command"],
                safe_user_message="开发者指令已识别。本轮只返回 dry-run 或调试摘要，不执行真实动作。",
            ))

        if self._looks_like_web_command(compact, profile):
            return self._finish_decision(detector_started, self._decision(
                text,
                channel,
                role,
                "web_command_reserved",
                0.85,
                matched_rules=["web_reserved_words"],
                safe_user_message="网页搜索功能已预留，当前版本还未启用。",
            ))

        if self._looks_unclear(compact, profile):
            return self._finish_decision(detector_started, self._decision(
                text,
                channel,
                role,
                "need_clarification",
                0.78,
                matched_rules=["unclear_operation_words"],
                safe_user_message="你是想打开、关闭、查找，还是整理这个对象？",
            ))

        if self._looks_like_chat(compact, profile) and not self._has_strong_desktop_action(compact, profile):
            return self._finish_decision(
                detector_started,
                self._decision(text, channel, role, "chat_reply", 0.72, matched_rules=["chat_hint_words"]),
            )

        action_hint, rules, score = self._desktop_action_hint(
            text,
            lowered,
            compact,
            classifier_result,
            profile=profile,
        )
        if action_hint:
            memory_hint = self.memory_service.lookup_target_hint(
                text,
                action_hint=action_hint,
                input_channel=channel,
                actor_role=role,
            )
            if channel == "voice" and score < 0.7:
                return self._finish_decision(detector_started, self._decision(
                    text,
                    channel,
                    role,
                    "need_clarification",
                    0.62,
                    matched_rules=[*rules, "voice_low_confidence"],
                    action_hint=action_hint,
                    target_hint=memory_hint.get("target_hint", {}) if isinstance(memory_hint, dict) else {},
                    safe_user_message="我听到的是桌面操作吗？请再明确一下要打开还是关闭哪个对象。",
                ))
            return self._finish_decision(detector_started, self._decision(
                text,
                channel,
                role,
                "desktop_command",
                score,
                matched_rules=rules,
                action_hint=action_hint,
                target_hint=memory_hint if isinstance(memory_hint, dict) else {},
                safe_user_message="桌面操作已识别，将先进行安全 dry-run。",
            ))

        return self._finish_decision(
            detector_started,
            self._decision(text, channel, role, "chat_reply", 0.55, matched_rules=["default_chat"]),
        )

    def _desktop_action_hint(
        self,
        text: str,
        lowered: str,
        compact: str,
        classifier_result: Any,
        *,
        profile: dict[str, Any] | None = None,
    ) -> tuple[str, list[str], float]:
        used_profile = profile if isinstance(profile, dict) else self.language_service.profile_for_text(text)

        open_words = self.language_service.list(used_profile, "command.open_verbs") or list(OPEN_WORDS)
        close_words = self.language_service.list(used_profile, "command.close_verbs") or list(CLOSE_WORDS)
        app_words = self.language_service.list(used_profile, "command.generic_app_words") or list(APP_WORDS)
        file_words = self.language_service.list(used_profile, "command.generic_file_words") or list(FILE_WORDS)

        connection_enable_words = self.language_service.list(used_profile, "command.connection_words.enable") or list(CONNECTION_ENABLE_WORDS)
        connection_disable_words = self.language_service.list(used_profile, "command.connection_words.disable") or list(CONNECTION_DISABLE_WORDS)

        normalized_compact = compact
        normalized_lowered = lowered.replace(" ", "")

        if any(str(word).lower().replace(" ", "") in normalized_compact for word in connection_disable_words):
            return "desktop.connection.disable", ["connection_disable_words", "language_profile"], 0.95

        if any(str(word).lower().replace(" ", "") in normalized_compact for word in connection_enable_words):
            return "desktop.connection.enable", ["connection_enable_words", "language_profile"], 0.95

        has_open = any(str(word).lower().replace(" ", "") in normalized_compact for word in open_words)
        has_close = any(str(word).lower().replace(" ", "") in normalized_compact for word in close_words)

        # app/file 只是辅助，不再要求全部写死具体软件名
        has_app = any(str(word).lower().replace(" ", "") in normalized_lowered for word in app_words)
        has_file = any(str(word).lower().replace(" ", "") in normalized_lowered for word in file_words)

        drive_root = self._extract_drive_root_from_text(text)
        looks_like_folder = self._looks_like_folder_target(normalized_compact, used_profile)

        if has_open and drive_root:
            return "folder.open", ["open_words", "drive_root_words", "language_profile"], 0.92

        if has_open and looks_like_folder and not has_app:
            return "folder.open", ["open_words", "folder_words", "language_profile"], 0.82
        # 兼容已知老逻辑里的软件名
        if not has_app:
            has_app = any(word.lower().replace(" ", "") in normalized_lowered for word in APP_WORDS)

        if not has_file:
            has_file = any(word.lower().replace(" ", "") in normalized_lowered for word in FILE_WORDS)

        if has_open and has_file:
            return "file.open", ["open_words", "file_words", "language_profile"], 0.84

        if has_close and has_file:
            return "file.close", ["close_words", "file_words", "language_profile"], 0.84

        if has_open and has_app:
            return "app.launch", ["open_words", "app_words", "language_profile"], 0.84

        if has_close and has_app:
            return "app.close", ["close_words", "app_words", "language_profile"], 0.84

        # 不确定目标类型时，不再默认猜 app.launch / app.close。
        # 这里交给 Jiuchasi 通过 evidence + memory + LLM 判断。
        if has_open and not self._looks_like_chat(compact, used_profile):
            return "desktop.resolve", ["open_words", "implicit_target", "language_profile"], 0.64

        if has_close and not self._looks_like_chat(compact, used_profile):
            return "desktop.resolve", ["close_words", "implicit_target", "language_profile"], 0.64

        needs_control = bool(getattr(classifier_result, "needs_control", False))
        if needs_control and (has_open or has_close):
            return "desktop.unknown", ["classifier_control_hint"], 0.50

        return "", [], 0.0

    def _looks_like_pending_followup(self, compact: str, profile: dict[str, Any] | None = None) -> bool:
        exact_words: list[str] = []
        choice_words: list[str] = []
        if isinstance(profile, dict):
            exact_words.extend(self.language_service.list(profile, "pending.confirm_words"))
            exact_words.extend(self.language_service.list(profile, "pending.cancel_words"))
            choice_words.extend(self.language_service.list(profile, "pending.choice_words"))
        if not exact_words and not choice_words:
            choice_words.extend(PENDING_WORDS)
        if compact in {
            str(item).lower().replace(" ", "")
            for item in [*exact_words, *choice_words]
            if str(item or "").strip()
        }:
            return True
        return any(
            str(word).lower().replace(" ", "") in compact
            for word in choice_words
            if len(str(word).strip()) >= 2
        )

    def _looks_like_developer_command(self, lowered: str, compact: str, profile: dict[str, Any] | None = None) -> bool:
        words = self.language_service.list(profile or {}, "command.developer_words") if isinstance(profile, dict) else []
        if not words:
            words = list(DEVELOPER_WORDS)
        return any(str(word).lower().replace(" ", "") in compact or str(word).lower() in lowered for word in words)

    def _looks_like_web_command(self, compact: str, profile: dict[str, Any] | None = None) -> bool:
        words = self.language_service.list(profile or {}, "command.web_words") if isinstance(profile, dict) else []
        if not words:
            words = list(WEB_WORDS)
        return any(str(word).lower().replace(" ", "") in compact for word in words)

    def _looks_unclear(self, compact: str, profile: dict[str, Any] | None = None) -> bool:
        words = self.language_service.list(profile or {}, "command.unclear_patterns") if isinstance(profile, dict) else []
        if not words:
            words = list(UNCLEAR_PATTERNS)
        return any(str(word).lower().replace(" ", "") in compact for word in words)

    def _looks_like_chat(self, compact: str, profile: dict[str, Any] | None = None) -> bool:
        words: list[str] = []
        if isinstance(profile, dict):
            words.extend(self.language_service.list(profile, "command.chat_hint_words"))
            words.extend(self.language_service.list(profile, "command.math_chat_words"))
        if not words:
            words.extend(CHAT_HINT_WORDS)
            words.extend(MATH_CHAT_WORDS)
        return any(str(word).lower().replace(" ", "") in compact for word in words)

    def _looks_like_fast_chat(self, compact: str, profile: dict[str, Any] | None = None) -> bool:
        words = self.language_service.list(profile or {}, "command.math_chat_words") if isinstance(profile, dict) else []
        if not words:
            words = list(MATH_CHAT_WORDS)
        if any(str(word).lower().replace(" ", "") in compact for word in words):
            return True
        if "加" in compact and "等于" in compact:
            return True
        if compact.endswith(("吗", "呢", "呀", "啊", "？", "?")) and not self._has_strong_desktop_action(compact, profile):
            return True
        return False

    def _has_strong_desktop_action(self, compact: str, profile: dict[str, Any] | None = None) -> bool:
        used_profile = profile if isinstance(profile, dict) else {}
        words: list[str] = []

        if used_profile:
            words.extend(self.language_service.list(used_profile, "command.open_verbs"))
            words.extend(self.language_service.list(used_profile, "command.close_verbs"))
            words.extend(self.language_service.list(used_profile, "command.connection_words.enable"))
            words.extend(self.language_service.list(used_profile, "command.connection_words.disable"))

        if not words:
            words.extend([*OPEN_WORDS, *CLOSE_WORDS, *CONNECTION_ENABLE_WORDS, *CONNECTION_DISABLE_WORDS])

        return any(str(word).lower().replace(" ", "") in compact for word in words)
    def _extract_drive_root_from_text(self, text: str) -> str:
        raw = str(text or "").strip()
        compact = raw.replace(" ", "").replace("　", "")
        if not compact:
            return ""

        match = re.search(r"(?i)([a-z])[:：]?盘", compact)
        if match:
            return f"{match.group(1).upper()}:\\"

        match = re.search(r"(?i)\b([a-z])[:：][\\/]", compact)
        if match:
            return f"{match.group(1).upper()}:\\"

        match = re.search(r"(?i)打开([a-z])根目录", compact)
        if match:
            return f"{match.group(1).upper()}:\\"

        return ""

    def _looks_like_folder_target(self, compact: str, profile: dict[str, Any] | None = None) -> bool:
        used_profile = profile if isinstance(profile, dict) else {}
        folder_words: list[str] = []

        if used_profile:
            folder_words.extend(self.language_service.list(used_profile, "command.filesystem.root_words"))
            folder_words.extend(self.language_service.list(used_profile, "command.filesystem.folder_words"))

        if not folder_words:
            folder_words.extend(["根目录", "根路径", "根文件夹", "文件夹", "目录", "路径"])

        return any(
            str(word).lower().replace(" ", "") in compact
            for word in folder_words
            if str(word or "").strip()
        )
    
    def _latest_pending_id(self) -> str:
        try:
            from services.desktop.tianting.pending_task_service import get_latest_pending_task

            task = get_latest_pending_task()
            return str((task or {}).get("pending_task_id", "") or "")
        except Exception:
            return ""

    def _decision(
        self,
        raw_user_text: str,
        input_channel: str,
        actor_role: str,
        route: str,
        confidence: float,
        *,
        matched_rules: list[str] | None = None,
        action_hint: str = "",
        target_hint: dict[str, Any] | None = None,
        pending_task_id: str = "",
        safe_user_message: str = "",
    ) -> dict[str, Any]:
        return {
            "schema_version": ROUTE_SCHEMA_VERSION,
            "raw_user_text": str(raw_user_text or ""),
            "input_channel": input_channel,
            "actor_role": actor_role,
            "route": route,
            "confidence": max(0.0, min(1.0, float(confidence or 0.0))),
            "matched_rules": matched_rules or [],
            "action_hint": action_hint,
            "target_hint": target_hint or {},
            "pending_task_id": pending_task_id,
            "safe_user_message": safe_user_message,
            "allow_direct_execution": False,
            "requires_qin_review": True,
            "debug_summary": {
                "contract_loaded": bool(self.action_contracts),
                "synonym_loaded": bool(self.synonym_map),
            },
        }

    def _finish_decision(self, detector_started: float, decision: dict[str, Any]) -> dict[str, Any]:
        elapsed_ms = (time.perf_counter() - detector_started) * 1000.0
        route = str(decision.get("route", "") or "")
        action_hint = str(decision.get("action_hint", "") or "")
        debug_summary = decision.get("debug_summary")
        if isinstance(debug_summary, dict):
            debug_summary["detector_ms"] = round(elapsed_ms, 3)
        print(f"[DesktopRoute] route={route} action_hint={action_hint} detector_ms={elapsed_ms:.2f}")
        if elapsed_ms > 100.0:
            print(f"[DesktopRouteSlow] detector_ms={elapsed_ms:.2f} route={route}")
        return decision

    def _read_json(self, name: str, fallback: Any) -> Any:
        try:
            path = self.contract_dir / name
            mtime = path.stat().st_mtime
            cache_key = str(path)
            cached = self._json_cache.get(cache_key)
            if cached and cached[0] == mtime:
                return cached[1]
            data = json.loads(path.read_text(encoding="utf-8"))
            self._json_cache[cache_key] = (mtime, data)
            return data
        except Exception:
            return fallback


def detect_desktop_route(raw_user_text: str, **kwargs: Any) -> dict[str, Any]:
    return DesktopCommandDetector().detect(raw_user_text, **kwargs)
