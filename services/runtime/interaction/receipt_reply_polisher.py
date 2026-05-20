"""Safe reply polishing for factual interaction receipts.

This module may ask an LLM to rewrite display text, but never treats LLM output
as a fact source. If anything is uncertain, it falls back to safe local text or
the original receipt text.
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from config import OLLAMA_HOST, OLLAMA_MODEL


ALLOWED_ACTIONS = {
    "app.launch",
    "app.close",
    "folder.open",
    "file.open",
    "system_info.read_datetime",
}
BLOCKED_STATUS_MARKERS = (
    "failed",
    "blocked",
    "denied",
    "need",
    "pending",
    "multiple",
    "confirmation",
)
UNSUPPORTED_CLAIMS = (
    "我已经确认",
    "我看到",
    "我检测到",
    "权限",
    "进程",
    "后台",
    "路径",
)
LAUNCH_DONE_FORBIDDEN = (
    "已打开",
    "已完成打开",
    "已经成功打开",
)


class ReceiptReplyPolisher:
    def __init__(
        self,
        *,
        model_config: dict[str, Any] | None = None,
        timeout_seconds: float = 2.5,
        enabled: bool = True,
    ) -> None:
        self.model_config = dict(model_config or {})
        self.timeout_seconds = float(timeout_seconds)
        self.enabled = bool(enabled)

    def polish(self, interaction_result: dict[str, Any]) -> dict[str, Any]:
        result = interaction_result if isinstance(interaction_result, dict) else {}
        original_text = self._display_text(result)
        if not self._should_polish(result, original_text):
            return self._skipped("not_eligible", original_text)

        template = self._local_template(result, original_text)
        if template.get("ok"):
            return template

        if not self.enabled:
            return self._skipped("disabled", original_text)

        try:
            llm_result = self._polish_with_llm(result, original_text)
            if llm_result.get("ok"):
                return llm_result
            if template.get("display_text"):
                return template
            return llm_result
        except Exception as exc:
            if template.get("display_text"):
                template["reason"] = f"llm_failed_template_fallback:{exc.__class__.__name__}"
                return template
            return {
                "ok": False,
                "used_llm": True,
                "status": "failed",
                "display_text": original_text,
                "tts_text": original_text,
                "reason": str(exc),
                "raw_response_head": "",
            }

    def _should_polish(self, result: dict[str, Any], original_text: str) -> bool:
        if not bool(result.get("handled", False)):
            return False
        if not bool(result.get("ok", False)):
            return False
        if not original_text:
            return False
        action = str(result.get("action", "") or "").strip()
        route = str(result.get("route", "") or "").strip()
        status = str(result.get("status", "") or "").strip().lower()
        if action not in ALLOWED_ACTIONS:
            return False
        if route not in {"desktop_command", "system_skill"}:
            return False
        if any(marker in status for marker in BLOCKED_STATUS_MARKERS):
            return False
        ui_prompt = result.get("ui_prompt", {}) if isinstance(result.get("ui_prompt"), dict) else {}
        if bool(ui_prompt.get("transient", False)):
            return False
        if action in {"app.launch", "app.close", "folder.open", "file.open"}:
            target = str(result.get("target", "") or "").strip()
            if not target:
                return False
        if action == "system_info.read_datetime" and len(original_text) <= 30:
            return False
        return True

    def _local_template(self, result: dict[str, Any], original_text: str) -> dict[str, Any]:
        action = str(result.get("action", "") or "").strip()
        status = str(result.get("status", "") or "").strip().lower()
        target = str(result.get("target", "") or "").strip()
        executed = bool(result.get("executed", False))

        text = ""
        if action == "app.launch" and ("启动请求" in original_text or "launch" in status):
            text = f"好的，已发送{self._object_particle(target)}启动请求。"
        elif action == "app.close":
            text = f"好的，{self._subject(target)}已经关闭。" if executed else f"已发送关闭{self._object_particle(target)}请求。"
        elif action in {"folder.open", "file.open"} and executed:
            text = f"好的，已打开{self._object_text(target)}。"

        if not text:
            return self._skipped("no_safe_template", original_text)
        return {
            "ok": True,
            "used_llm": False,
            "status": "polished",
            "display_text": text,
            "tts_text": text,
            "reason": "local_safe_template",
            "raw_response_head": "",
        }

    def _polish_with_llm(self, result: dict[str, Any], original_text: str) -> dict[str, Any]:
        model = self.model_config
        provider = str(model.get("provider", "ollama") or "ollama").strip().lower()
        if provider != "ollama":
            return self._failed("unsupported_provider", original_text, "")

        model_name = str(model.get("model_name", OLLAMA_MODEL) or OLLAMA_MODEL).strip()
        host = str(model.get("host", OLLAMA_HOST) or OLLAMA_HOST).strip()
        prompt = self._build_prompt(result, original_text)
        raw_response = self._ollama_generate(prompt=prompt, host=host, model_name=model_name)
        parsed = self._parse_json(raw_response)
        display_text = str(parsed.get("display_text", "") or "").strip()
        tts_text = str(parsed.get("tts_text", display_text) or "").strip()
        if not tts_text:
            tts_text = display_text
        if not self._valid_polished_text(result, original_text, display_text, tts_text):
            return self._failed("validation_failed", original_text, raw_response)
        return {
            "ok": True,
            "used_llm": True,
            "status": "polished",
            "display_text": display_text,
            "tts_text": tts_text,
            "reason": "llm_polished",
            "raw_response_head": raw_response[:240],
        }

    def _build_prompt(self, result: dict[str, Any], original_text: str) -> str:
        facts = {
            "route": str(result.get("route", "") or ""),
            "action": str(result.get("action", "") or ""),
            "status": str(result.get("status", "") or ""),
            "ok": bool(result.get("ok", False)),
            "executed": bool(result.get("executed", False)),
            "target": str(result.get("target", "") or ""),
            "original_text": original_text,
        }
        return (
            "你是桌面助手的“回执润色器”。\n"
            "你只能把已有回执改写成更自然、更简短的中文。\n"
            "你不能改变事实，不能新增事实，不能改变执行状态。\n"
            "如果原文表示“已发送启动请求”，不能改成“已经打开”。\n"
            "如果原文表示“已关闭”，可以改成“好的，目标已经关闭。”\n"
            "如果不确定，原样返回。\n\n"
            "只输出 JSON：\n"
            "{\"display_text\":\"...\",\"tts_text\":\"...\"}\n\n"
            "事实字段：\n"
            f"route: {facts['route']}\n"
            f"action: {facts['action']}\n"
            f"status: {facts['status']}\n"
            f"ok: {facts['ok']}\n"
            f"executed: {facts['executed']}\n"
            f"target: {facts['target']}\n"
            f"original_text: {facts['original_text']}"
        )

    def _ollama_generate(self, *, prompt: str, host: str, model_name: str) -> str:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "top_p": 0.5,
                "num_predict": 80,
            },
        }
        request = urllib.request.Request(
            host.rstrip("/") + "/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(body)
        return str(parsed.get("response", "") or "")

    def _parse_json(self, text: str) -> dict[str, Any]:
        raw = str(text or "").strip()
        if not raw:
            raise ValueError("empty_llm_response")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end <= start:
                raise
            value = json.loads(raw[start : end + 1])
        if not isinstance(value, dict):
            raise ValueError("llm_response_not_object")
        return value

    def _valid_polished_text(
        self,
        result: dict[str, Any],
        original_text: str,
        display_text: str,
        tts_text: str,
    ) -> bool:
        if not isinstance(display_text, str) or not isinstance(tts_text, str):
            return False
        if not display_text.strip() or len(display_text.strip()) > 60 or len(tts_text.strip()) > 60:
            return False
        combined = display_text + tts_text
        if any(word in combined for word in UNSUPPORTED_CLAIMS):
            return False
        if self._looks_like_path_or_process_claim(combined):
            return False
        action = str(result.get("action", "") or "")
        status = str(result.get("status", "") or "").lower()
        if action == "app.launch" and (
            "启动请求" in original_text or status in {"app_launch_done", "app_launch_sent"} or "launch" in status
        ):
            if any(word in combined for word in LAUNCH_DONE_FORBIDDEN):
                return False
        return True

    def _looks_like_path_or_process_claim(self, text: str) -> bool:
        return bool(re.search(r"[A-Za-z]:\\|\\\\|\.exe\b|pid\s*[:=]?\s*\d+", text, re.IGNORECASE))

    def _object_particle(self, target: str) -> str:
        clean = str(target or "").strip()
        if not clean:
            return ""
        return f" {clean} 的" if self._is_asciiish(clean) else f"{clean}的"

    def _object_text(self, target: str) -> str:
        clean = str(target or "").strip()
        if not clean:
            return ""
        return f" {clean}" if self._is_asciiish(clean) else clean

    def _subject(self, target: str) -> str:
        clean = str(target or "").strip()
        if not clean:
            return ""
        return f"{clean} " if self._is_asciiish(clean) else clean

    def _is_asciiish(self, text: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9 ._\\-]+", str(text or "").strip()))

    def _display_text(self, result: dict[str, Any]) -> str:
        return (
            str(result.get("display_text", "") or "").strip()
            or str(result.get("safe_user_message", "") or "").strip()
        )

    def _skipped(self, reason: str, original_text: str) -> dict[str, Any]:
        return {
            "ok": False,
            "used_llm": False,
            "status": "skipped",
            "display_text": original_text,
            "tts_text": original_text,
            "reason": reason,
            "raw_response_head": "",
        }

    def _failed(self, reason: str, original_text: str, raw_response: str) -> dict[str, Any]:
        return {
            "ok": False,
            "used_llm": False,
            "status": "failed",
            "display_text": original_text,
            "tts_text": original_text,
            "reason": reason,
            "raw_response_head": str(raw_response or "")[:240],
        }
