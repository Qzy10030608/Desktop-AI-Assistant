import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from bootstrap.machine_profile_service import MachineProfileService  # type: ignore
from config import BASE_DIR  # type: ignore


class TTSPackageService:
    """
    语音包选择服务
    ========================

    作用：
    1. 按 TTS 后端列出可用语音包
    2. 记录当前启用的语音包
    3. 统一输出 runtime_config

    目录约定：
        models/tts/
        ├─ gpt_sovits/
        │  ├─ taowu/
        │  ├─ xxx/
        │  └─ ...
        ├─ edge/
        │  └─ edge_voices.json
        ├─ cosyvoice/
        └─ ...

    runtime 记录：
        data/runtime/current_tts_package.json
    """

    def __init__(self):
        self.base_dir = Path(BASE_DIR)
        self.tts_root_dir = self.base_dir / "models" / "tts"
        self.runtime_dir = self.base_dir / "data" / "runtime"
        self.current_package_file = self.runtime_dir / "current_tts_package.json"

        self.tts_root_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.machine_profile_service = MachineProfileService()
        self._ensure_runtime_file()

    # =========================================================
    # 基础工具
    # =========================================================
    def _ensure_runtime_file(self):
        if self.current_package_file.exists():
            return

        self.current_package_file.write_text(
            json.dumps(
                {
                    "backend": "gpt_sovits",
                    "package_id": "",
                },
                ensure_ascii=False,
                indent=2,
            ),
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

    def _normalize_backend(self, backend: str) -> str:
        text = (backend or "").strip().lower()
        return text or "gpt_sovits"

    def _get_backend_dir(self, backend: str) -> Path:
        return self.tts_root_dir / self._normalize_backend(backend)

    # =========================================================
    # 当前语音包
    # =========================================================
    def get_current_selection(self) -> Dict:
        data = self._read_json(self.current_package_file)
        return {
            "backend": self._normalize_backend(data.get("backend", "gpt_sovits")),
            "package_id": str(data.get("package_id", "")).strip(),
        }

    def set_current_package(self, backend: str, package_id: str):
        backend = self._normalize_backend(backend)
        raw_id = (package_id or "").strip()

        final_id = raw_id
        if raw_id:
            detail = self._find_package_by_any_key(backend, raw_id)
            if detail:
                final_id = self._canonical_package_id(backend, detail)

        self._write_json(
            self.current_package_file,
            {
                "backend": backend,
                "package_id": final_id,
            },
        )

    def get_current_backend(self) -> str:
        return self.get_current_selection().get("backend", "gpt_sovits")

    def get_current_package_id(self, backend: str | None = None) -> str:
        data = self.get_current_selection()
        target_backend = self._normalize_backend(backend or data.get("backend", "gpt_sovits"))

        if data.get("backend") == target_backend and data.get("package_id"):
            detail = self._find_package_by_any_key(target_backend, data["package_id"])
            if detail:
                return self._canonical_package_id(target_backend, detail)

        fallback = self._find_first_available_package_id(target_backend)
        return fallback

    # =========================================================
    # 列表 / 详情
    # =========================================================
    def _find_first_available_package_id(self, backend: str) -> str:
        packages = self.list_packages(backend)
        if not packages:
            return ""

        first = packages[0]
        if self._normalize_backend(backend) == "edge":
            return str(first.get("id", "")).strip()

        return str(first.get("dir_name", "") or first.get("id", "")).strip()

    def list_packages(self, backend: str) -> List[Dict]:
        backend = self._normalize_backend(backend)

        if backend == "edge":
            return self._list_edge_packages()

        return self._list_dir_packages(backend)

    def _list_dir_packages(self, backend: str) -> List[Dict]:
        items: List[Dict] = []
        backend_dir = self._get_backend_dir(backend)

        if not backend_dir.exists():
            return items

        for path in sorted(backend_dir.iterdir()):
            if not path.is_dir():
                continue

            meta = self._read_json(path / "meta.json")
            item = {
                "id": meta.get("id", path.name),
                "name": meta.get("name", path.name),
                "description": meta.get("description", ""),
                "backend": backend,
                "path": str(path.resolve()),
                "dir_name": path.name,
            }
            items.append(item)

        return items

    def _list_edge_packages(self) -> List[Dict]:
        backend = "edge"
        backend_dir = self._get_backend_dir(backend)
        json_file = backend_dir / "edge_voices.json"

        if json_file.exists():
            data = self._read_json(json_file)

            if isinstance(data, list):
                result = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    result.append(
                        {
                            "id": item.get("id", item.get("voice", "")),
                            "name": item.get("name", item.get("voice", "")),
                            "description": item.get("description", ""),
                            "backend": backend,
                            "voice": item.get("voice", item.get("id", "")),
                        }
                    )
                return result

            if isinstance(data, dict):
                voices = data.get("voices", [])
                if isinstance(voices, list):
                    result = []
                    for item in voices:
                        if not isinstance(item, dict):
                            continue
                        result.append(
                            {
                                "id": item.get("id", item.get("voice", "")),
                                "name": item.get("name", item.get("voice", "")),
                                "description": item.get("description", ""),
                                "backend": backend,
                                "voice": item.get("voice", item.get("id", "")),
                            }
                        )
                    return result

        return [
            {
                "id": "zh-CN-XiaoxiaoNeural",
                "name": "晓晓（Edge）",
                "description": "默认中文女声",
                "backend": "edge",
                "voice": "zh-CN-XiaoxiaoNeural",
            },
            {
                "id": "zh-CN-YunxiNeural",
                "name": "云希（Edge）",
                "description": "默认中文男声",
                "backend": "edge",
                "voice": "zh-CN-YunxiNeural",
            },
        ]

    def _canonical_package_id(self, backend: str, item: Dict) -> str:
        backend = self._normalize_backend(backend)
        if backend == "edge":
            return str(item.get("id", "")).strip()
        return str(item.get("dir_name", "") or item.get("id", "")).strip()

    def _find_package_by_any_key(self, backend: str, package_key: str) -> Dict:
        backend = self._normalize_backend(backend)
        key = (package_key or "").strip()
        if not key:
            return {}

        for item in self.list_packages(backend):
            item_id = str(item.get("id", "")).strip()
            item_name = str(item.get("name", "")).strip()
            dir_name = str(item.get("dir_name", "")).strip()
            path_name = Path(str(item.get("path", "")).strip()).name if item.get("path") else ""

            if key in (item_id, item_name, dir_name, path_name):
                return item

        return {}

    def get_package_detail(self, backend: str, package_id: str) -> Dict:
        backend = self._normalize_backend(backend)
        package_id = (package_id or "").strip()

        if not package_id:
            return {}

        return self._find_package_by_any_key(backend, package_id)

    def get_current_package(self, backend: str | None = None) -> Dict:
        target_backend = self._normalize_backend(backend or self.get_current_backend())
        package_id = self.get_current_package_id(target_backend)

        if not package_id:
            return {}

        return self.get_package_detail(target_backend, package_id)

    def ensure_valid_current_package(self, backend: str) -> Dict:
        backend = self._normalize_backend(backend)
        current_id = self.get_current_package_id(backend)
        detail = self.get_package_detail(backend, current_id)

        if detail:
            self.set_current_package(backend, self._canonical_package_id(backend, detail))
            return detail

        first_id = self._find_first_available_package_id(backend)
        if first_id:
            self.set_current_package(backend, first_id)
            return self.get_package_detail(backend, first_id)

        self.set_current_package(backend, "")
        return {}

    # =========================================================
    # runtime config（统一接口，不统一资源文件名）
    # =========================================================
    def _resolve_relative_path(self, base_dir: Path, raw_path: str) -> str:
        text = (raw_path or "").strip()
        if not text:
            return ""

        path = Path(text)
        if not path.is_absolute():
            path = base_dir / path

        return str(path.resolve())

    def _resolve_first_existing_file(self, base_dir: Path, candidates: List[str]) -> str:
        for name in candidates:
            path = base_dir / name
            if path.exists() and path.is_file():
                return str(path.resolve())
        return ""

    def _read_text_file(self, path_str: str) -> str:
        if not path_str:
            return ""
        try:
            return Path(path_str).read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _read_json_file_by_str(self, path_str: str) -> Dict:
        if not path_str:
            return {}
        path = Path(path_str)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _get_gpt_sovits_api_url(self) -> str:
        cfg = self.machine_profile_service.get_gpt_sovits_config()
        host = str(cfg.get("host", "127.0.0.1")).strip() or "127.0.0.1"
        port = int(cfg.get("port", 9880) or 9880)
        return f"http://{host}:{port}/tts"

    def build_runtime_config(self, backend: str, package: Optional[Dict] = None) -> Dict[str, Any]:
        backend = self._normalize_backend(backend)
        package = package or self.get_current_package(backend) or {}

        if backend == "edge":
            return self._build_edge_runtime_config(package)

        if backend == "gpt_sovits":
            return self._build_gpt_sovits_runtime_config(package)

        return self._build_generic_runtime_config(backend, package)

    def _build_generic_runtime_config(self, backend: str, package: Dict) -> Dict[str, Any]:
        return {
            "backend": backend,
            "package_id": package.get("id", ""),
            "package_name": package.get("name", ""),
            "package_path": package.get("path", ""),
            "voice": package.get("voice", ""),
            "requires_package": False,
            "requires_reference": False,
            "ref_audio_path": "",
            "prompt_text_path": "",
            "prompt_text": "",
            "model_config_path": "",
            "api_url": "",
            "text_lang": "",
            "prompt_lang": "",
            "gpt_model_path": "",
            "sovits_model_path": "",
        }

    def _build_edge_runtime_config(self, package: Dict) -> Dict[str, Any]:
        voice_name = (
            package.get("voice")
            or package.get("id")
            or "zh-CN-XiaoxiaoNeural"
        )

        return {
            "backend": "edge",
            "package_id": package.get("id", voice_name),
            "package_name": package.get("name", voice_name),
            "package_path": "",
            "voice": voice_name,
            "requires_package": False,
            "requires_reference": False,
            "ref_audio_path": "",
            "prompt_text_path": "",
            "prompt_text": "",
            "model_config_path": "",
            "api_url": "",
            "text_lang": "",
            "prompt_lang": "",
            "gpt_model_path": "",
            "sovits_model_path": "",
        }

    def _build_gpt_sovits_runtime_config(self, package: Dict) -> Dict[str, Any]:
        package_path = str(package.get("path", "")).strip()
        if not package_path:
            raise RuntimeError("当前未选择 GPT-SoVITS 语音包。")

        package_dir = Path(package_path)
        if not package_dir.exists():
            raise FileNotFoundError(f"GPT-SoVITS 语音包目录不存在：{package_dir}")

        config_path = self._resolve_first_existing_file(
            package_dir,
            ["gpt_sovits.json", "gpt_sovits.JSON"],
        )
        cfg = self._read_json_file_by_str(config_path)

        ref_audio_path = self._resolve_relative_path(
            package_dir,
            str(cfg.get("ref_audio_path", "")).strip(),
        )
        if not ref_audio_path:
            ref_audio_path = self._resolve_first_existing_file(
                package_dir,
                ["ref.wav", "ref.WAV", "reference.wav", "reference.WAV"],
            )

        prompt_text_path = self._resolve_relative_path(
            package_dir,
            str(
                cfg.get("prompt_text_path", "")
                or cfg.get("ref_txt", "")
                or cfg.get("prompt_text_file", "")
            ).strip(),
        )
        if not prompt_text_path:
            prompt_text_path = self._resolve_first_existing_file(
                package_dir,
                ["ref.txt", "reference.txt", "prompt.txt", "ref_text.txt"],
            )

        prompt_text = str(cfg.get("prompt_text", "")).strip()
        if not prompt_text and prompt_text_path:
            prompt_text = self._read_text_file(prompt_text_path)

        gpt_model_path = self._resolve_relative_path(
            package_dir,
            str(cfg.get("gpt_model_path", "")).strip(),
        )
        if not gpt_model_path:
            gpt_model_path = self._resolve_first_existing_file(
                package_dir,
                ["gpt.ckpt", "gpt.pth", "gpt_weights.ckpt"],
            )

        sovits_model_path = self._resolve_relative_path(
            package_dir,
            str(cfg.get("sovits_model_path", "")).strip(),
        )
        if not sovits_model_path:
            sovits_model_path = self._resolve_first_existing_file(
                package_dir,
                ["sovits.pth", "SoVITS.pth", "sovits_weights.pth"],
            )
        print("[PKG][package_dir]", package_dir)
        print("[PKG][config_path]", config_path)
        print("[PKG][gpt_model_path]", gpt_model_path)
        print("[PKG][sovits_model_path]", sovits_model_path)
        print("[PKG][ref_audio_path]", ref_audio_path)
        print("[PKG][prompt_text_path]", prompt_text_path)

        return {
            "backend": "gpt_sovits",
            "package_id": str(package.get("dir_name", "") or package.get("id", package_dir.name)),
            "package_name": package.get("name", package_dir.name),
            "package_path": str(package_dir.resolve()),
            "voice": None,
            "requires_package": True,
            "requires_reference": True,
            "ref_audio_path": ref_audio_path,
            "prompt_text_path": prompt_text_path,
            "prompt_text": prompt_text,
            "model_config_path": config_path,
            "api_url": self._get_gpt_sovits_api_url(),
            "text_lang": str(cfg.get("text_lang", "zh")).strip() or "zh",
            "prompt_lang": str(cfg.get("prompt_lang", "zh")).strip() or "zh",
            "gpt_model_path": gpt_model_path,
            "sovits_model_path": sovits_model_path,
        }