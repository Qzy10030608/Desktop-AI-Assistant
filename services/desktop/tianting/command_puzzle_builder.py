from __future__ import annotations
import re

import json
from pathlib import Path
from typing import Any

from services.desktop.tianting.command_schema import make_command_puzzle, normalize_action_hint
from services.desktop.language.language_service import DesktopLanguageService
from services.desktop.tianting.target_text_normalizer import normalize_target_text

OPEN_WORDS = ("打开", "开启", "启动", "运行")
CLOSE_WORDS = ("关闭", "关掉", "退出", "停止", "把", "关了")
FILE_WORDS = ("文件", "文档", "报告", "说明", "材料", "txt", "doc", "docx", "pdf", "md", "json")
APP_WORDS = ("软件", "程序", "应用", "浏览器", "steam", "vscode", "obs", "edge", "chrome")
CONNECTION_WORDS = ("连接电脑", "桌面连接", "开启连接", "关闭连接")
RECENT_WORDS = ("刚才", "最近", "这个", "那个", "昨天")
FOLDER_WORDS = ("文件夹", "目录", "文件目录", "文件夹目录", "路径", "根目录", "根路径", "根文件夹")
TRAILING_PARTICLES = ("吗", "呢", "呀", "啊", "吧", "嘛", "么", "？", "?", "。", ".", "！", "!")
REQUEST_FILLERS = ("请", "帮我", "给我", "麻烦", "可以", "能不能", "能否", "请帮我", "帮我把")

class CommandPuzzleBuilder:
    def __init__(self, contract_dir: str | Path | None = None) -> None:
        self.contract_dir = Path(contract_dir or Path(__file__).resolve().parent / "command_contract_library")
        self.action_contracts = self._read_json("action_contracts.json", {})
        self.synonym_map = self._read_json("synonym_map.json", {})
        self.slot_templates = self._read_json("slot_templates.json", {})
        self.role_policy_rules = self._read_json("role_policy_rules.json", {})
        self.language_service = DesktopLanguageService()
    def build(
        self,
        *,
        raw_user_text: str,
        llm_hint: Any = None,
        actor_role: str = "normal_user",
        input_channel: str = "text",
        context_pack: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text = str(raw_user_text or "").strip()
        action, matched = self._select_action(text, llm_hint)
        slots = self._extract_slots(text, action)
        missing_slots = self._missing_slots(action, slots)
        needs = self._needs(action, slots, missing_slots)
        confidence = self._confidence(action, slots, matched)

        return make_command_puzzle(
            raw_user_text=text,
            actor_role=actor_role,
            input_channel=input_channel,
            selected_action_hint=action,
            matched_actions=matched,
            slots=slots,
            missing_slots=missing_slots,
            needs=needs,
            confidence=confidence,
            source={
                "origin": "tianting.command_puzzle_builder",
                "llm_trust": "untrusted",
                "llm_hint_present": llm_hint is not None,
                "context_pack_version": str((context_pack or {}).get("schema_version", "") or ""),
            },
        )

    def _select_action(self, text: str, llm_hint: Any) -> tuple[str, list[dict[str, Any]]]:
        candidates: list[dict[str, Any]] = []
        lowered = text.lower()
        compact = text.replace(" ", "").replace("　", "")

        if any(word in text for word in CONNECTION_WORDS):
            if any(word in text for word in ("关闭连接", "关闭桌面连接", "断开", "关掉连接")):
                candidates.append({
                    "action_id": "desktop.connection.disable",
                    "score": 0.95,
                    "reason": "connection_disable_words",
                })
            elif any(word in text for word in ("开启连接", "开启桌面连接", "连接电脑", "打开桌面连接")):
                candidates.append({
                    "action_id": "desktop.connection.enable",
                    "score": 0.95,
                    "reason": "connection_enable_words",
                })

        has_open = any(word in text for word in OPEN_WORDS)
        has_close = any(word in text for word in CLOSE_WORDS)

        folder_words = self._folder_words(text)
        has_folder = any(word and word.replace(" ", "") in compact for word in folder_words)

        # “文件夹”必须先于“文件”判断，否则会被误判为 file.open
        has_file = any(word in text for word in FILE_WORDS) and not has_folder
        has_app = any(word.lower() in lowered for word in APP_WORDS)

        drive_root = self._drive_root_path(text)

        if has_open and drive_root:
            candidates.append({
                "action_id": "folder.open",
                "score": 0.98,
                "reason": "drive_root_open",
            })

        if has_open and has_folder:
            candidates.append({
                "action_id": "folder.open",
                "score": 0.90,
                "reason": "open_folder_words",
            })

        if has_close and has_folder:
            candidates.append({
                "action_id": "folder.close",
                "score": 0.84,
                "reason": "close_folder_words",
            })

        if has_open and has_file:
            candidates.append({
                "action_id": "file.open",
                "score": 0.78,
                "reason": "open_file_words",
            })

        if has_close and has_file:
            candidates.append({
                "action_id": "file.close",
                "score": 0.78,
                "reason": "close_file_words",
            })

        if has_open and has_app:
            candidates.append({
                "action_id": "app.launch",
                "score": 0.78,
                "reason": "launch_app_words",
            })

        if has_close and has_app:
            candidates.append({
                "action_id": "app.close",
                "score": 0.78,
                "reason": "close_app_words",
            })

        if has_close and not has_app and not has_file and not has_folder and any(word in text for word in RECENT_WORDS):
            candidates.append({
                "action_id": "file.close",
                "score": 0.45,
                "reason": "ambiguous_recent_close",
            })

        hint_action = self._hint_action(llm_hint)
        if hint_action:
            # 盘符根目录不允许被不可信 hint 拉成软件/文件
            if not (drive_root and hint_action in {"app.launch", "file.open", "desktop.resolve"}):
                candidates.append({
                    "action_id": hint_action,
                    "score": 0.62 if hint_action == "desktop.resolve" else 0.35,
                    "reason": "untrusted_llm_hint",
                })

        # 关键：有打开/关闭意图，但目标类型不确定时，保留 desktop.resolve。
        # 这一步交给 Jiuchasi 通过 evidence / memory / LLM 判断，而不是在这里猜 app.launch。
        if has_open and not drive_root and not has_folder and not has_file and not has_app:
            candidates.append({
                "action_id": "desktop.resolve",
                "score": 0.64,
                "reason": "implicit_open_target",
            })

        if has_close and not has_folder and not has_file and not has_app:
            candidates.append({
                "action_id": "desktop.resolve",
                "score": 0.64,
                "reason": "implicit_close_target",
            })

        candidates = self._merge_candidates(candidates)
        if not candidates:
            return "", []

        candidates.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)

        if len(candidates) > 1:
            top = float(candidates[0].get("score", 0.0))
            second = float(candidates[1].get("score", 0.0))
            if top - second < 0.15:
                return "", candidates

        return normalize_action_hint(candidates[0].get("action_id", "")), candidates

    def _extract_slots(self, text: str, action: str) -> dict[str, Any]:
        slots: dict[str, Any] = {
            "target.kind": "",
            "target.name_hint": "",
            "target.path_hint": "",
            "target.app_hint": "",
            "target.time_hint": "",
            "target.format_hint": "",
            "target.identity": "",
            "query.choice_index": None,
        }

        if action.startswith("folder."):
            slots["target.kind"] = "folder"
            slots["target.path_hint"] = self._drive_root_path(text)
            slots["target.name_hint"] = self._clean_target_hint(text, action)

        elif action.startswith("file."):
            slots["target.kind"] = "file"
            slots["target.name_hint"] = self._clean_target_hint(text, action)

        elif action.startswith("app."):
            slots["target.kind"] = "app"
            slots["target.app_hint"] = self._app_hint(text, action)
            slots["target.name_hint"] = slots["target.app_hint"] or self._clean_target_hint(text, action)

        elif action == "desktop.resolve":
            slots["target.kind"] = "unknown"
            slots["target.name_hint"] = self._clean_target_hint(text, action)

        elif action.startswith("desktop.connection."):
            slots["target.kind"] = "desktop_connection"

        for word in RECENT_WORDS:
            if word in text:
                slots["target.time_hint"] = word
                slots["target.identity"] = "contextual_reference"
                break

        for suffix in (".txt", ".md", ".json", ".docx", ".doc", ".pdf", ".xlsx", ".xls", ".pptx", ".ppt"):
            if suffix in text.lower():
                slots["target.format_hint"] = suffix
                break

        return slots

    def _missing_slots(self, action: str, slots: dict[str, Any]) -> list[str]:
        if not action:
            return ["selected_action_hint"]
        if action.startswith("desktop.connection."):
            return []
        if action.startswith("file.") and not (slots.get("target.name_hint") or slots.get("target.path_hint") or slots.get("target.identity")):
            return ["target.name_hint"]
        if action.startswith("app.") and not (slots.get("target.app_hint") or slots.get("target.name_hint") or slots.get("target.identity")):
            return ["target.app_hint"]
        if action.startswith("folder.") and not (slots.get("target.path_hint") or slots.get("target.name_hint") or slots.get("target.identity")):
            return ["target.path_hint"]
        return []

    def _needs(self, action: str, slots: dict[str, Any], missing_slots: list[str]) -> dict[str, Any]:
        needs = {
            "qin_review": True,
            "candidate_search": False,
            "target_material": False,
            "user_choice_if_ambiguous": True,
            "user_clarification": bool(missing_slots),
        }

        if action in {"file.open", "app.launch", "desktop.resolve"}:
            needs["candidate_search"] = True

        if action == "folder.open":
            # 盘符根目录可以直接验证；具体文件夹名需要候选搜索
            needs["candidate_search"] = not bool(slots.get("target.path_hint"))

        if action in {"file.close", "folder.close", "app.close"}:
            needs["target_material"] = True

        if action == "":
            needs["user_clarification"] = True

        return needs

    def _confidence(self, action: str, slots: dict[str, Any], matched: list[dict[str, Any]]) -> float:
        if not action:
            return 0.0
        score = float(matched[0].get("score", 0.0)) if matched else 0.2
        if slots.get("target.name_hint") or slots.get("target.app_hint") or action.startswith("desktop.connection."):
            score += 0.1
        return max(0.0, min(1.0, score))

    def _hint_action(self, llm_hint: Any) -> str:
        if isinstance(llm_hint, dict):
            for key in ("selected_action_hint", "action", "intent"):
                raw_action = str(llm_hint.get(key, "") or "").strip()
                action = normalize_action_hint(raw_action)
                if action:
                    return action
        return ""

    def _merge_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for item in candidates:
            action = normalize_action_hint(item.get("action_id", ""))
            if not action:
                continue
            current = merged.get(action)
            if current is None or float(item.get("score", 0.0)) > float(current.get("score", 0.0)):
                next_item = dict(item)
                next_item["action_id"] = action
                merged[action] = next_item
        return list(merged.values())

    def _clean_target_hint(self, text: str, action_hint: str = "") -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""

        # 先用通用语言规则清洗，避免“文件夹”被拆成“夹”
        generic = self._generic_clean_target_hint(raw, action_hint)

        try:
            result = normalize_target_text(raw, action_hint=action_hint)
            normalized = str(result.get("normalized_target", "") or "").strip()
        except Exception:
            normalized = ""

        if action_hint.startswith("folder.") or action_hint == "desktop.resolve":
            return generic or normalized

        # 如果 normalizer 产生了明显残留，例如“个人AI设计 夹”，优先使用 generic
        if generic and self._looks_like_dirty_normalized_target(normalized, raw):
            return generic

        return normalized or generic


    def _generic_clean_target_hint(self, text: str, action_hint: str = "") -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""

        profile = self.language_service.profile_for_text(raw)

        open_words = self.language_service.list(profile, "command.open_verbs") or list(OPEN_WORDS)
        close_words = self.language_service.list(profile, "command.close_verbs") or list(CLOSE_WORDS)

        action_words = [
            str(word or "").strip()
            for word in [*open_words, *close_words]
            if str(word or "").strip() and str(word).strip() != "把"
        ]

        candidate = raw

        # 只取最后一个动作词之后的内容：
        # “你真棒，那么可以帮我打开英雄联盟吗” -> “英雄联盟吗”
        best_pos = -1
        best_word = ""
        for word in sorted(action_words, key=len, reverse=True):
            pos = candidate.rfind(word)
            if pos >= 0 and pos + len(word) > best_pos:
                best_pos = pos + len(word)
                best_word = word

        if best_pos >= 0:
            candidate = candidate[best_pos:]

        candidate = candidate.strip(" ，,。.!！?？：:；;　")

        # 去掉请求语气词，只做语言清洗，不做目标映射
        for word in sorted(self._request_filler_words(raw), key=len, reverse=True):
            if candidate.startswith(word):
                candidate = candidate[len(word):].strip(" ，,。.!！?？：:；;　")

        # 去掉尾部疑问/语气符号
        candidate = self._strip_trailing_particles(candidate)

        # 文件夹动作去掉“文件夹/目录”等后缀，避免留下“夹”
        if action_hint.startswith("folder.") or action_hint == "desktop.resolve":
            for word in sorted(self._folder_words(raw), key=len, reverse=True):
                if word and candidate.endswith(word):
                    candidate = candidate[: -len(word)].strip(" ，,。.!！?？：:；;　")
                    break

        return candidate.strip()


    def _folder_words(self, text: str) -> list[str]:
        profile = self.language_service.profile_for_text(str(text or ""))
        words: list[str] = []
        words.extend(self.language_service.list(profile, "command.filesystem.folder_words"))
        words.extend(self.language_service.list(profile, "command.filesystem.root_words"))

        if not words:
            words.extend(FOLDER_WORDS)

        result: list[str] = []
        seen: set[str] = set()
        for word in words:
            value = str(word or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result


    def _request_filler_words(self, text: str) -> list[str]:
        profile = self.language_service.profile_for_text(str(text or ""))
        words = self.language_service.list(profile, "command.target_clean.request_fillers")
        if not words:
            words = list(REQUEST_FILLERS)
        return [str(word or "").strip() for word in words if str(word or "").strip()]


    def _strip_trailing_particles(self, text: str) -> str:
        value = str(text or "").strip()
        while value:
            removed = False
            for token in TRAILING_PARTICLES:
                if token and value.endswith(token):
                    value = value[: -len(token)].strip()
                    removed = True
                    break
            if not removed:
                break
        return value.strip(" ，,。.!！?？：:；;　")


    def _looks_like_dirty_normalized_target(self, normalized: str, raw: str) -> bool:
        value = str(normalized or "").strip()
        if not value:
            return False

        # “文件夹”被错误拆词后常见残留
        if "文件夹" in raw and value.endswith("夹"):
            return True

        # 如果还残留明显动作词，说明清洗不完整
        compact = value.replace(" ", "").replace("　", "")
        for word in [*OPEN_WORDS, *CLOSE_WORDS]:
            if word and word in compact:
                return True

        return False

    def _app_hint(self, text: str, action_hint: str = "app.launch") -> str:
        # 这里不再硬猜具体软件，具体匹配交给吏部候选、记忆和后续纠察司 evidence。
        return self._clean_target_hint(text, action_hint)

    def _drive_root_path(self, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""

        profile = self.language_service.profile_for_text(raw)
        drive_suffixes = self.language_service.list(profile, "command.filesystem.drive_suffixes") or ["盘"]
        root_words = self.language_service.list(profile, "command.filesystem.root_words") or ["根目录"]
        folder_words = self.language_service.list(profile, "command.filesystem.folder_words") or ["文件夹", "目录"]

        compact = raw.replace(" ", "").replace("　", "")

        # 允许 “G盘” / “G盘根目录” / “G盘目录”
        for suffix in drive_suffixes:
            match = re.search(r"(?i)([a-z])" + re.escape(str(suffix)), compact)
            if not match:
                continue

            # 只要出现盘符，就先认为是磁盘根；root/folder 词用于提高语义明确度。
            # 后续纠察司可用 file_roots evidence 再验证这个盘是否真实存在。
            letter = match.group(1).upper()
            return f"{letter}:\\"

        return ""
    
    def _read_json(self, name: str, fallback: Any) -> Any:
        path = self.contract_dir / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data
        except Exception:
            return fallback


def build_command_puzzle(
    *,
    raw_user_text: str,
    llm_hint: Any = None,
    actor_role: str = "normal_user",
    input_channel: str = "text",
    context_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return CommandPuzzleBuilder().build(
        raw_user_text=raw_user_text,
        llm_hint=llm_hint,
        actor_role=actor_role,
        input_channel=input_channel,
        context_pack=context_pack,
    )
