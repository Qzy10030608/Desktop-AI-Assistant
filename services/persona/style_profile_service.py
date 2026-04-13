import json
from pathlib import Path
from typing import Dict, List, Optional

from config import (  # type: ignore
    STYLES_DIR,
    CURRENT_STYLE_FILE,
)


class StyleProfileService:
    """
    风格配置服务
    兼容：
    1. runtime/current_style.json 新命名
    2. style_id / id / name 多种 runtime 写法
    3. 目录名 / meta.id / meta.name 多种匹配方式
    """

    def __init__(self, role_service=None):
        self.role_service = role_service
        self.styles_dir = Path(STYLES_DIR)
        self.current_style_file = Path(CURRENT_STYLE_FILE)

        self.styles_dir.mkdir(parents=True, exist_ok=True)
        self.current_style_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_runtime_file()

    # =========================================================
    # 基础工具
    # =========================================================
    def _ensure_runtime_file(self):
        if self.current_style_file.exists():
            return

        self.current_style_file.write_text(
            json.dumps({"style_id": ""}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_json(self, path: Path) -> Dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_json(self, path: Path, data: Dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _write_text(self, path: Path, text: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text or "", encoding="utf-8")

    def _normalize_style_id(self, name: str) -> str:
        text = (name or "").strip()
        if not text:
            return "style_default"

        safe = []
        for ch in text:
            if ch.isalnum() or ch in ("_", "-"):
                safe.append(ch)
            elif ch in (" ", "　"):
                safe.append("_")
            else:
                safe.append("_")

        style_id = "".join(safe).strip("_").lower()
        return style_id or "style_default"

    def _iter_style_dirs(self):
        if not self.styles_dir.exists():
            return []
        return [p for p in sorted(self.styles_dir.iterdir()) if p.is_dir()]

    def _get_style_meta(self, style_dir: Path) -> Dict:
        return self._read_json(style_dir / "meta.json")

    def _find_first_available_style_dir(self) -> Optional[Path]:
        for path in self._iter_style_dirs():
            if (path / "meta.json").exists():
                return path
        return None

    def _find_style_dir_by_any_key(self, value: str) -> Optional[Path]:
        key = (value or "").strip()
        if not key:
            return None

        for path in self._iter_style_dirs():
            meta = self._get_style_meta(path)

            dir_name = path.name
            meta_id = str(meta.get("id", "")).strip()
            meta_name = str(meta.get("name", "")).strip()

            if key in (dir_name, meta_id, meta_name):
                return path

        return None

    def _get_tts_overrides(self, meta: Dict, style_rules: Dict) -> Dict:
        candidates = [
            meta.get("tts", {}),
            meta.get("tts_overrides", {}),
            meta.get("performance", {}),
            style_rules.get("tts", {}),
            style_rules.get("tts_overrides", {}),
            style_rules.get("performance", {}),
        ]

        merged: Dict = {}
        for item in candidates:
            if isinstance(item, dict):
                merged.update(item)
        return merged

    def _pick_number(self, data: Dict, *keys: str, default=0):
        for key in keys:
            if key in data:
                try:
                    return float(data.get(key, default))
                except Exception:
                    return default
        return default

    # =========================================================
    # 当前 style 读写
    # =========================================================
    def get_current_style_id(self) -> str:
        data = self._read_json(self.current_style_file)
        raw_value = (
            str(data.get("style_id", "")).strip()
            or str(data.get("id", "")).strip()
            or str(data.get("name", "")).strip()
        )

        if raw_value:
            style_dir = self._find_style_dir_by_any_key(raw_value)
            if style_dir:
                meta = self._get_style_meta(style_dir)
                return str(meta.get("id", "")).strip() or style_dir.name

        fallback_dir = self._find_first_available_style_dir()
        if fallback_dir:
            meta = self._get_style_meta(fallback_dir)
            return str(meta.get("id", "")).strip() or fallback_dir.name

        return ""

    def set_current_style(self, style_id: str):
        style_dir = self._find_style_dir_by_any_key(style_id)
        if style_dir:
            meta = self._get_style_meta(style_dir)
            final_id = str(meta.get("id", "")).strip() or style_dir.name
        else:
            final_id = (style_id or "").strip()

        self._write_json(self.current_style_file, {"style_id": final_id})

    # =========================================================
    # 列表 / 详情
    # =========================================================
    def list_styles(self) -> List[Dict]:
        items: List[Dict] = []

        for path in self._iter_style_dirs():
            meta = self._get_style_meta(path)
            if not meta:
                continue

            items.append({
                "id": meta.get("id", path.name),
                "name": meta.get("name", path.name),
                "description": meta.get("description", ""),
                "dir_name": path.name,
                "dir_path": str(path),
            })

        return items

    def get_style_detail(self, style_id: str) -> Dict:
        if not style_id:
            return {}

        style_dir = self._find_style_dir_by_any_key(style_id)
        if not style_dir:
            return {}

        meta = self._get_style_meta(style_dir)
        if not meta:
            meta = {
                "id": style_dir.name,
                "name": style_dir.name,
                "description": "",
            }

        style_rules = self._read_json(style_dir / "style_rules.json")
        examples = self._read_json(style_dir / "examples.json")
        tts_overrides = self._get_tts_overrides(meta, style_rules)

        persona = self._read_text(style_dir / "persona_base.txt")
        if not persona:
            persona = self._read_text(style_dir / "persona.txt")

        catchphrase = self._read_text(style_dir / "catchphrases.txt")
        if not catchphrase:
            catchphrase = self._read_text(style_dir / "catchphrase.txt")

        opening_style = self._read_text(style_dir / "opening_style.txt")
        if not opening_style:
            opening_style = self._read_text(style_dir / "opening.txt")

        forbidden = self._read_text(style_dir / "forbidden.txt")
        preview = self._read_text(style_dir / "preview.txt")

        detail = {
            "id": meta.get("id", style_dir.name),
            "name": meta.get("name", style_dir.name),
            "description": meta.get("description", ""),
            "dir_name": style_dir.name,
            "dir_path": str(style_dir),

            "persona": persona,
            "scene": meta.get("scene", style_rules.get("scene", "daily")),
            "reply_mode": meta.get("reply_mode", "direct"),
            "explain_tendency": meta.get("explain_tendency", style_rules.get("explain_tendency", "medium")),
            "comfort_tendency": meta.get("comfort_tendency", style_rules.get("comfort_tendency", "medium")),
            "tone_strength": meta.get("tone_strength", style_rules.get("tone_strength", "medium")),
            "catchphrase": catchphrase,
            "opening_style": opening_style,
            "forbidden": forbidden,
            "style_rules": style_rules,
            "examples": examples,
            "preview": preview,

            "rate": self._pick_number(tts_overrides, "rate", "speed", default=0),
            "volume": self._pick_number(tts_overrides, "volume", default=0),
            "pitch": self._pick_number(tts_overrides, "pitch", default=0),

            "meta": meta,
            "tts_overrides": tts_overrides,
        }

        return detail

    def get_current_style_profile(self) -> Dict:
        style_id = self.get_current_style_id()
        if not style_id:
            return {}

        data = self.get_style_detail(style_id)
        if data:
            return data

        fallback_dir = self._find_first_available_style_dir()
        if fallback_dir:
            meta = self._get_style_meta(fallback_dir)
            fallback_id = str(meta.get("id", "")).strip() or fallback_dir.name
            return self.get_style_detail(fallback_id)

        return {}

    # =========================================================
    # 保存
    # =========================================================
    def save_style_profile(self, style_id: str, data: Dict) -> str:
        style_id = (style_id or "").strip()
        if style_id:
            existing_dir = self._find_style_dir_by_any_key(style_id)
        else:
            existing_dir = None

        if existing_dir is not None:
            style_dir = existing_dir
            old_meta = self._get_style_meta(style_dir)
            old_style_rules = self._read_json(style_dir / "style_rules.json")
            final_id = str(old_meta.get("id", "")).strip() or style_dir.name
        else:
            final_id = style_id or self.get_current_style_id()
            if not final_id:
                final_id = self._normalize_style_id(data.get("name", ""))

            style_dir = self.styles_dir / final_id
            style_dir.mkdir(parents=True, exist_ok=True)
            old_meta = self._get_style_meta(style_dir)
            old_style_rules = self._read_json(style_dir / "style_rules.json")

        meta = {
            "id": final_id,
            "name": data.get("name", old_meta.get("name", final_id)),
            "description": data.get("description", old_meta.get("description", "")),
            "scene": data.get("scene", old_meta.get("scene", "daily")),
            "reply_mode": data.get("reply_mode", old_meta.get("reply_mode", "direct")),
            "explain_tendency": data.get("explain_tendency", old_meta.get("explain_tendency", "medium")),
            "comfort_tendency": data.get("comfort_tendency", old_meta.get("comfort_tendency", "medium")),
            "tone_strength": data.get("tone_strength", old_meta.get("tone_strength", "medium")),
        }

        style_rules = {
            **old_style_rules,
            "scene": data.get("scene", old_style_rules.get("scene", "daily")),
            "reply_mode": data.get("reply_mode", old_style_rules.get("reply_mode", "direct")),
            "explain_tendency": data.get("explain_tendency", old_style_rules.get("explain_tendency", "medium")),
            "comfort_tendency": data.get("comfort_tendency", old_style_rules.get("comfort_tendency", "medium")),
            "tone_strength": data.get("tone_strength", old_style_rules.get("tone_strength", "medium")),
        }

        self._write_json(style_dir / "meta.json", meta)
        self._write_json(style_dir / "style_rules.json", style_rules)

        self._write_text(style_dir / "persona_base.txt", data.get("persona", self._read_text(style_dir / "persona_base.txt")))
        self._write_text(style_dir / "catchphrases.txt", data.get("catchphrase", self._read_text(style_dir / "catchphrases.txt")))
        self._write_text(style_dir / "opening_style.txt", data.get("opening_style", self._read_text(style_dir / "opening_style.txt")))
        self._write_text(style_dir / "forbidden.txt", data.get("forbidden", self._read_text(style_dir / "forbidden.txt")))

        if "preview" in data:
            self._write_text(style_dir / "preview.txt", data.get("preview", ""))

        if "examples" in data and isinstance(data.get("examples"), dict):
            self._write_json(style_dir / "examples.json", data.get("examples", {}))
        elif not (style_dir / "examples.json").exists():
            self._write_json(style_dir / "examples.json", {})

        if not (style_dir / "preview.txt").exists():
            self._write_text(style_dir / "preview.txt", "")

        self.set_current_style(final_id)
        return final_id

    def save_style_profile_as_new(self, data: Dict) -> str:
        style_id = self._normalize_style_id(data.get("name", ""))
        base_id = style_id
        index = 2

        while (self.styles_dir / style_id).exists():
            style_id = f"{base_id}_{index}"
            index += 1

        return self.save_style_profile(style_id, data)