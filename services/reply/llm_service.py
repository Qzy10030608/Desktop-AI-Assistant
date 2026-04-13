from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import requests

from config import OLLAMA_HOST, OLLAMA_MODEL, SYSTEM_PROMPT  # type: ignore

_session: Optional[requests.Session] = None

ChunkCallback = Callable[[str, str], None]
StopPredicate = Callable[[str], bool]


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"Content-Type": "application/json"})
    return _session


def _normalize_timeout(timeout: Union[int, Tuple[int, int]]) -> Tuple[int, int]:
    if isinstance(timeout, tuple):
        return timeout
    return (10, timeout)


def _build_messages(
    text: str,
    history: Optional[List[dict]] = None,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    history = history or []
    user_text = (text or "").strip()
    if not user_text:
        raise ValueError("用户输入不能为空。")

    final_system_prompt = (system_prompt or SYSTEM_PROMPT).strip()

    messages: List[Dict[str, str]] = []
    if final_system_prompt:
        messages.append({"role": "system", "content": final_system_prompt})

    for item in history:
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_text})
    return messages


def _merge_request_options(
    model_options: Optional[Dict[str, Any]],
    request_options: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if isinstance(model_options, dict):
        result.update(model_options)
    if isinstance(request_options, dict):
        result.update(request_options)
    return result


def _normalize_provider(provider: str | None) -> str:
    value = str(provider or "ollama").strip().lower()
    if value not in ("ollama", "local", "api"):
        return "ollama"
    return value


def _resolve_model_config(
    model_config: Optional[Dict[str, Any]] = None,
    *,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    host: Optional[str] = None,
) -> Dict[str, Any]:
    model_config = dict(model_config or {})
    final_provider = _normalize_provider(provider or model_config.get("provider"))

    return {
        "provider": final_provider,
        "model_name": str(model_name or model_config.get("model_name") or OLLAMA_MODEL).strip() or OLLAMA_MODEL,
        "host": str(host or model_config.get("host") or OLLAMA_HOST).strip() or OLLAMA_HOST,
        "keep_alive": str(model_config.get("keep_alive", "10m")).strip() or "10m",
        "think": bool(model_config.get("think", False)),
        "request_options": dict(model_config.get("request_options", {}) or {}),
        "api_base": str(model_config.get("api_base", "")).strip(),
        "api_key": str(model_config.get("api_key", "")).strip(),
        "executable_path": str(model_config.get("executable_path", "")).strip(),
        "model_path": str(model_config.get("model_path", "")).strip(),
    }


def _chat_with_ollama_stream(
    text: str,
    history: Optional[List[dict]] = None,
    model_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
    host: str = OLLAMA_HOST,
    timeout: Union[int, Tuple[int, int]] = (10, 300),
    request_options: Optional[Dict[str, Any]] = None,
    on_chunk: Optional[ChunkCallback] = None,
    should_stop: Optional[StopPredicate] = None,
    keep_alive: str = "10m",
    think: bool = False,
) -> str:
    model_name = (model_name or OLLAMA_MODEL).strip()
    messages = _build_messages(
        text=text,
        history=history,
        system_prompt=system_prompt,
    )

    url = host.rstrip("/") + "/api/chat"
    payload: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "stream": True,
        "keep_alive": keep_alive,
        "think": think,
    }

    if request_options:
        payload["options"] = request_options

    session = _get_session()
    content_parts: List[str] = []
    thinking_parts: List[str] = []
    raw_chunks_for_debug: List[str] = []

    with session.post(
        url,
        json=payload,
        timeout=_normalize_timeout(timeout),
        stream=True,
    ) as resp:
        resp.raise_for_status()

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue

            raw_chunks_for_debug.append(raw_line)

            try:
                data = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            if data.get("error"):
                raise RuntimeError(str(data["error"]))

            message = data.get("message", {}) or {}

            piece = str(message.get("content", ""))
            if piece:
                content_parts.append(piece)
                current_text = "".join(content_parts)

                if on_chunk is not None:
                    on_chunk(piece, current_text)

                if should_stop is not None:
                    try:
                        if should_stop(current_text):
                            break
                    except Exception:
                        pass

            thinking_piece = str(message.get("thinking", ""))
            if thinking_piece:
                thinking_parts.append(thinking_piece)

            if data.get("done", False):
                break

    content = "".join(content_parts).strip()
    thinking_text = "".join(thinking_parts).strip()

    if content:
        return content

    if thinking_text:
        return thinking_text

    debug_preview = "\n".join(raw_chunks_for_debug[:5])
    raise RuntimeError(
        "Ollama 返回为空。前几个原始 chunk 如下：\n"
        f"{debug_preview}"
    )


def chat_stream(
    text: str,
    history: Optional[List[dict]] = None,
    model_config: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
    host: Optional[str] = None,
    provider: Optional[str] = None,
    timeout: Union[int, Tuple[int, int]] = (10, 300),
    request_options: Optional[Dict[str, Any]] = None,
    on_chunk: Optional[ChunkCallback] = None,
    should_stop: Optional[StopPredicate] = None,
) -> str:
    resolved = _resolve_model_config(
        model_config=model_config,
        provider=provider,
        model_name=model_name,
        host=host,
    )
    final_provider = resolved["provider"]
    final_options = _merge_request_options(
        resolved.get("request_options"),
        request_options,
    )

    if final_provider == "ollama":
        return _chat_with_ollama_stream(
            text=text,
            history=history,
            model_name=resolved["model_name"],
            system_prompt=system_prompt,
            host=resolved["host"],
            timeout=timeout,
            request_options=final_options,
            on_chunk=on_chunk,
            should_stop=should_stop,
            keep_alive=resolved["keep_alive"],
            think=bool(resolved.get("think", False)),
        )

    if final_provider == "local":
        raise RuntimeError(
            "当前已切到 provider=local，但 llm_service.py 里还没有接入本地执行器。"
        )

    if final_provider == "api":
        raise RuntimeError(
            "当前已切到 provider=api，但 llm_service.py 里还没有接入 API 执行器。"
        )

    raise RuntimeError(f"不支持的 LLM provider：{final_provider}")


def chat(
    text: str,
    history: Optional[List[dict]] = None,
    model_config: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
    host: Optional[str] = None,
    provider: Optional[str] = None,
    timeout: Union[int, Tuple[int, int]] = (10, 300),
    request_options: Optional[Dict[str, Any]] = None,
) -> str:
    return chat_stream(
        text=text,
        history=history,
        model_config=model_config,
        model_name=model_name,
        system_prompt=system_prompt,
        host=host,
        provider=provider,
        timeout=timeout,
        request_options=request_options,
        on_chunk=None,
        should_stop=None,
    )


# -------------------------
# 兼容旧调用名
# -------------------------
def chat_with_ollama_stream(
    text: str,
    history: Optional[List[dict]] = None,
    model_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
    host: str = OLLAMA_HOST,
    timeout: Union[int, Tuple[int, int]] = (10, 300),
    request_options: Optional[Dict[str, Any]] = None,
    on_chunk: Optional[ChunkCallback] = None,
    should_stop: Optional[StopPredicate] = None,
) -> str:
    return chat_stream(
        text=text,
        history=history,
        model_config={"provider": "ollama", "host": host, "model_name": model_name or OLLAMA_MODEL},
        model_name=model_name,
        system_prompt=system_prompt,
        host=host,
        provider="ollama",
        timeout=timeout,
        request_options=request_options,
        on_chunk=on_chunk,
        should_stop=should_stop,
    )


def chat_with_ollama(
    text: str,
    history: Optional[List[dict]] = None,
    model_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
    host: str = OLLAMA_HOST,
    timeout: Union[int, Tuple[int, int]] = (10, 300),
    request_options: Optional[Dict[str, Any]] = None,
) -> str:
    return chat(
        text=text,
        history=history,
        model_config={"provider": "ollama", "host": host, "model_name": model_name or OLLAMA_MODEL},
        model_name=model_name,
        system_prompt=system_prompt,
        host=host,
        provider="ollama",
        timeout=timeout,
        request_options=request_options,
    )