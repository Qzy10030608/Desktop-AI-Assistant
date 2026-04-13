import json
from pathlib import Path
from typing import Dict, List, Optional

from config import (  # type: ignore
    VOICES_DIR,
    CURRENT_VOICE_FILE,
)


class VoiceProfileService:
    """
    发声模板服务
    -------------------------
    这里只负责：
    1. 表现模板本身（scene / emotion / speed ...）
    2. edge 等轻量 voice 名称
    3. 当前启用的发声模板 id

    不再负责：
    - GPT-SoVITS 语音包资源
    - ref.wav / ref.txt / gpt_sovits.json
    - gpt_model_path / sovits_model_path

    这些统一交给 TTSPackageService 管理。
    """

    def __init__(self, role_service=None):
        self.role_service = role_service
        self.voices_dir = Path(VOICES_DIR)
        self.current_voice_file = Path(CURRENT_VOICE_FILE)

        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.current_voice_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_runtime_file()

    # =========================================================
    # 基础工具
    # =========================================================
    def _ensure_runtime_file(self):
        if self.current_voice_file.exists():
            return

        self.current_voice_file.write_text(
            json.dumps({"voice_id": ""}, ensure_ascii=False, indent=2),
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

    def _iter_voice_dirs(self):
        if not self.voices_dir.exists():
            return []
        return [p for p in sorted(self.voices_dir.iterdir()) if p.is_dir()]

    def _get_voice_meta(self, voice_dir: Path) -> Dict:
        return self._read_json(voice_dir / "meta.json")

    def _find_first_available_voice_dir(self) -> Optional[Path]:
        for path in self._iter_voice_dirs():
            if (path / "meta.json").exists():
                return path
        return None

    def _find_voice_dir_by_any_key(self, value: str) -> Optional[Path]:
        key = (value or "").strip()
        if not key:
            return None

        for path in self._iter_voice_dirs():
            meta = self._get_voice_meta(path)

            dir_name = path.name
            meta_id = str(meta.get("id", "")).strip()
            meta_name = str(meta.get("name", "")).strip()

            if key in (dir_name, meta_id, meta_name):
                return path

        return None

    def _normalize_voice_id(self, name: str) -> str:
        text = (name or "").strip()
        if not text:
            return "voice_default"

        safe = []
        for ch in text:
            if ch.isalnum() or ch in ("_", "-"):
                safe.append(ch)
            elif ch in (" ", "　"):
                safe.append("_")
            else:
                safe.append("_")

        voice_id = "".join(safe).strip("_").lower()
        return voice_id or "voice_default"

    # =========================================================
    # 当前 voice 读写
    # =========================================================
    def get_current_voice_id(self) -> str:
        data = self._read_json(self.current_voice_file)
        raw_value = (
            str(data.get("voice_id", "")).strip()
            or str(data.get("id", "")).strip()
            or str(data.get("name", "")).strip()
        )

        if raw_value:
            voice_dir = self._find_voice_dir_by_any_key(raw_value)
            if voice_dir:
                meta = self._get_voice_meta(voice_dir)
                return str(meta.get("id", "")).strip() or voice_dir.name

        fallback_dir = self._find_first_available_voice_dir()
        if fallback_dir:
            meta = self._get_voice_meta(fallback_dir)
            return str(meta.get("id", "")).strip() or fallback_dir.name

        return ""

    def set_current_voice(self, voice_id: str):
        voice_dir = self._find_voice_dir_by_any_key(voice_id)
        if voice_dir:
            meta = self._get_voice_meta(voice_dir)
            final_id = str(meta.get("id", "")).strip() or voice_dir.name
        else:
            final_id = (voice_id or "").strip()

        self._write_json(self.current_voice_file, {"voice_id": final_id})

    # =========================================================
    # 列表 / 详情
    # =========================================================
    def list_voice_profiles(self) -> List[Dict]:
        items: List[Dict] = []

        for path in self._iter_voice_dirs():
            meta = self._get_voice_meta(path)
            if not meta:
                continue

            tts_config = self._read_json(path / "tts_config.json")
            backend = str(
                tts_config.get("backend")
                or meta.get("backend")
                or "edge"
            ).strip().lower() or "edge"

            items.append({
                "id": meta.get("id", path.name),
                "name": meta.get("name", path.name),
                "description": meta.get("description", ""),
                "backend": backend,
                "dir_name": path.name,
                "dir_path": str(path),
            })

        return items

    def get_voice_detail(self, voice_id: str) -> Dict:
        if not voice_id:
            return {}

        voice_dir = self._find_voice_dir_by_any_key(voice_id)
        if not voice_dir:
            return {}

        meta = self._get_voice_meta(voice_dir)
        if not meta:
            meta = {
                "id": voice_dir.name,
                "name": voice_dir.name,
                "description": "",
            }

        tts_config = self._read_json(voice_dir / "tts_config.json")
        pronunciation_dict = self._read_json(voice_dir / "pronunciation_dict.json")

        backend = str(
            tts_config.get("backend")
            or meta.get("backend")
            or "edge"
        ).strip().lower() or "edge"

        detail = {
            "id": meta.get("id", voice_dir.name),
            "name": meta.get("name", voice_dir.name),
            "description": meta.get("description", ""),
            "dir_name": voice_dir.name,
            "dir_path": str(voice_dir),

            "scene": meta.get("scene", tts_config.get("scene", "daily")),
            "emotion": meta.get("emotion", tts_config.get("emotion", "gentle")),
            "emotion_strength": meta.get("emotion_strength", tts_config.get("emotion_strength", "medium")),
            "speed": meta.get("speed", tts_config.get("speed", "normal")),
            "pause": meta.get("pause", tts_config.get("pause", "medium")),
            "intonation": meta.get("intonation", tts_config.get("intonation", "normal")),
            "emphasis": meta.get("emphasis", tts_config.get("emphasis", "natural")),

            "reference_text": meta.get("reference_text", ""),
            "backend": backend,

            "tts_config": tts_config,
            "pronunciation_dict": pronunciation_dict,
        }

        return detail

    def get_current_voice_profile(self) -> Dict:
        voice_id = self.get_current_voice_id()
        if not voice_id:
            return {}

        data = self.get_voice_detail(voice_id)
        if data:
            return data

        fallback_dir = self._find_first_available_voice_dir()
        if fallback_dir:
            meta = self._get_voice_meta(fallback_dir)
            fallback_id = str(meta.get("id", "")).strip() or fallback_dir.name
            return self.get_voice_detail(fallback_id)

        return {}

    def get_current_tts_voice_name(self) -> str:
        profile = self.get_current_voice_profile()
        if not profile:
            return "zh-CN-XiaoxiaoNeural"

        tts_config = profile.get("tts_config", {}) or {}

        voice_name = (
            tts_config.get("voice")
            or tts_config.get("voice_name")
            or tts_config.get("edge_voice")
            or profile.get("name")
        )

        return voice_name or "zh-CN-XiaoxiaoNeural"

    def get_current_tts_backend(self) -> str:
        profile = self.get_current_voice_profile()
        if not profile:
            return "edge"

        tts_config = profile.get("tts_config", {}) or {}
        backend = str(
            tts_config.get("backend")
            or profile.get("backend")
            or "edge"
        ).strip().lower()

        return backend or "edge"

    # =========================================================
    # 保存
    # =========================================================
    def save_voice_profile(self, voice_id: str, data: Dict) -> str:
        voice_id = (voice_id or "").strip()
        if voice_id:
            existing_dir = self._find_voice_dir_by_any_key(voice_id)
        else:
            existing_dir = None

        if existing_dir is not None:
            voice_dir = existing_dir
            old_meta = self._get_voice_meta(voice_dir)
            old_tts_config = self._read_json(voice_dir / "tts_config.json")
            final_id = str(old_meta.get("id", "")).strip() or voice_dir.name
        else:
            final_id = voice_id or self.get_current_voice_id()
            if not final_id:
                final_id = self._normalize_voice_id(data.get("name", ""))

            voice_dir = self.voices_dir / final_id
            voice_dir.mkdir(parents=True, exist_ok=True)
            old_meta = self._get_voice_meta(voice_dir)
            old_tts_config = self._read_json(voice_dir / "tts_config.json")

        meta = {
            "id": final_id,
            "name": data.get("name", old_meta.get("name", final_id)),
            "description": data.get("description", old_meta.get("description", "")),
            "scene": data.get("scene", old_meta.get("scene", "daily")),
            "emotion": data.get("emotion", old_meta.get("emotion", "gentle")),
            "emotion_strength": data.get("emotion_strength", old_meta.get("emotion_strength", "medium")),
            "speed": data.get("speed", old_meta.get("speed", "normal")),
            "pause": data.get("pause", old_meta.get("pause", "medium")),
            "intonation": data.get("intonation", old_meta.get("intonation", "normal")),
            "emphasis": data.get("emphasis", old_meta.get("emphasis", "natural")),
            "reference_text": data.get("reference_text", old_meta.get("reference_text", "")),
            "backend": data.get("backend", old_meta.get("backend", old_tts_config.get("backend", "edge"))),
        }

        self._write_json(voice_dir / "meta.json", meta)

        tts_config = {
            **old_tts_config,
            "backend": data.get("backend", old_tts_config.get("backend", "edge")),
            "voice": data.get("voice", old_tts_config.get("voice", "zh-CN-XiaoxiaoNeural")),
            "scene": data.get("scene", old_tts_config.get("scene", "daily")),
            "emotion": data.get("emotion", old_tts_config.get("emotion", "gentle")),
            "emotion_strength": data.get("emotion_strength", old_tts_config.get("emotion_strength", "medium")),
            "speed": data.get("speed", old_tts_config.get("speed", "normal")),
            "pause": data.get("pause", old_tts_config.get("pause", "medium")),
            "intonation": data.get("intonation", old_tts_config.get("intonation", "normal")),
            "emphasis": data.get("emphasis", old_tts_config.get("emphasis", "natural")),
        }
        self._write_json(voice_dir / "tts_config.json", tts_config)

        if not (voice_dir / "pronunciation_dict.json").exists():
            self._write_json(voice_dir / "pronunciation_dict.json", {})

        self.set_current_voice(final_id)
        return final_id

    def save_voice_profile_as_new(self, data: Dict) -> str:
        voice_id = self._normalize_voice_id(data.get("name", ""))
        base_id = voice_id
        index = 2

        while (self.voices_dir / voice_id).exists():
            voice_id = f"{base_id}_{index}"
            index += 1

        return self.save_voice_profile(voice_id, data)