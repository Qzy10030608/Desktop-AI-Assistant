from __future__ import annotations

from typing import Any, Dict


def replace_tokens(text: str, token_map: Dict[str, str]) -> str:
    result = str(text or "")
    for key, value in token_map.items():
        result = result.replace(f"${{{key}}}", str(value))
    return result


def bind_tokens(data: Any, token_map: Dict[str, str]) -> Any:
    if isinstance(data, dict):
        bound: Dict[str, Any] = {}

        if "path_token" in data:
            bound["path"] = replace_tokens(str(data.get("path_token", "")), token_map)

        for key, value in data.items():
            if key == "path_token":
                continue
            bound[key] = bind_tokens(value, token_map)
        return bound

    if isinstance(data, list):
        return [bind_tokens(item, token_map) for item in data]

    if isinstance(data, str):
        return replace_tokens(data, token_map)

    return data