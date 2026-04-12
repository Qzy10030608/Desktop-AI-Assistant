from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

import requests

from bootstrap.machine_profile_service import MachineProfileService


class StartupCheckService:
    """
    启动检查服务
    -------------------------
    负责：
    1. 检查 machine_profile.json 是否完整
    2. 探测 Ollama 是否可连接
    3. 探测 GPT-SoVITS 路径与关键文件是否有效
    4. 只检查有限候选路径，不做全盘扫描
    """

    def __init__(self, machine_profile_service: MachineProfileService):
        self.machine_profile_service = machine_profile_service
        self.project_root = machine_profile_service.project_root

    def _timestamp(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def _unique_strings(self, values: List[str]) -> List[str]:
        seen = set()
        result: List[str] = []
        for item in values:
            value = str(item or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _check_ollama(self, host: str) -> Dict[str, Any]:
        host = str(host or "").strip() or "http://localhost:11434"
        url = host.rstrip("/") + "/api/tags"

        try:
            resp = requests.get(url, timeout=(2, 6))
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            models = data.get("models", []) if isinstance(data, dict) else []
            return {
                "ok": True,
                "host": host,
                "model_count": len(models) if isinstance(models, list) else 0,
                "error": "",
            }
        except Exception as e:
            return {
                "ok": False,
                "host": host,
                "model_count": 0,
                "error": str(e),
            }

    def _build_gpt_root_candidates(self, configured_root: str) -> List[str]:
        project_root = self.project_root
        parent = project_root.parent

        recent_roots = self.machine_profile_service.get_recent_valid_gpt_roots()

        candidates = [
            configured_root,
            *recent_roots,
            str(project_root / "GPT-SoVITS"),
            str(parent / "GPT-SoVITS"),
            str(parent / "gpt_train" / "GPT-SoVITS-v3lora-20250228"),
            str(parent / "gpt_train" / "GPT-SoVITS"),
            "G:/gpt_train/GPT-SoVITS-v3lora-20250228",
            "G:/gpt_train/GPT-SoVITS",
            "G:/TV/Cupcut/gpt_train/GPT-SoVITS-v3lora-20250228",
            "G:/TV/Cupcut/gpt_train/GPT-SoVITS",
        ]
        return self._unique_strings(candidates)

    def _resolve_python_candidates(self, root: Path, configured_python: str) -> List[str]:
        candidates = [
            configured_python,
            str(root / "runtime" / "python.exe"),
            str(root / "runtime" / "python" / "python.exe"),
            str(root / ".venv" / "Scripts" / "python.exe"),
            str(root / "venv" / "Scripts" / "python.exe"),
        ]
        return self._unique_strings(candidates)

    def _inspect_gpt_root(self, root_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
        root_dir = str(root_dir or "").strip()
        if not root_dir:
            return {
                "ok": False,
                "root_dir": "",
                "resolved_root_dir": "",
                "python_exe": "",
                "api_script_path": "",
                "tts_config_path": "",
                "error": "未提供 GPT-SoVITS 根目录",
            }

        root = Path(root_dir).expanduser()
        if not root.exists() or not root.is_dir():
            return {
                "ok": False,
                "root_dir": root_dir,
                "resolved_root_dir": "",
                "python_exe": "",
                "api_script_path": "",
                "tts_config_path": "",
                "error": "根目录不存在",
            }

        api_script_rel = str(config.get("api_script", "api_v2.py")).strip() or "api_v2.py"
        tts_config_rel = str(
            config.get("tts_config", "GPT_SoVITS/configs/tts_infer.yaml")
        ).strip() or "GPT_SoVITS/configs/tts_infer.yaml"
        configured_python = str(config.get("python_exe", "")).strip()

        api_script_path = (root / api_script_rel).resolve()
        tts_config_path = (root / tts_config_rel).resolve()

        python_candidates = self._resolve_python_candidates(root, configured_python)
        resolved_python = ""
        for item in python_candidates:
            if item and Path(item).exists():
                resolved_python = item
                break

        missing = []
        if not api_script_path.exists():
            missing.append("api_script")
        if not tts_config_path.exists():
            missing.append("tts_config")

        ok = not missing
        error = ""
        if missing:
            error = "缺少关键文件：" + "、".join(missing)

        return {
            "ok": ok,
            "root_dir": root_dir,
            "resolved_root_dir": str(root.resolve()),
            "python_exe": resolved_python,
            "api_script_path": str(api_script_path),
            "tts_config_path": str(tts_config_path),
            "error": error,
        }

    def _check_gpt_sovits(self, config: Dict[str, Any]) -> Dict[str, Any]:
        configured_root = str(config.get("root_dir", "")).strip()
        candidates = self._build_gpt_root_candidates(configured_root)

        inspected_results: List[Dict[str, Any]] = []
        first_ok: Dict[str, Any] | None = None

        for candidate in candidates:
            info = self._inspect_gpt_root(candidate, config)
            inspected_results.append(info)
            if info.get("ok"):
                first_ok = info
                break

        if first_ok:
            return {
                "ok": True,
                "configured_root": configured_root,
                "resolved_root_dir": first_ok.get("resolved_root_dir", ""),
                "python_exe": first_ok.get("python_exe", ""),
                "api_script_path": first_ok.get("api_script_path", ""),
                "tts_config_path": first_ok.get("tts_config_path", ""),
                "checked_candidates": candidates,
                "error": "",
            }

        return {
            "ok": False,
            "configured_root": configured_root,
            "resolved_root_dir": "",
            "python_exe": "",
            "api_script_path": "",
            "tts_config_path": "",
            "checked_candidates": candidates,
            "error": inspected_results[0].get("error", "未找到可用 GPT-SoVITS 路径") if inspected_results else "未找到可用 GPT-SoVITS 路径",
        }

    def run(self, auto_patch: bool = True) -> Dict[str, Any]:
        checked_at = self._timestamp()

        ollama_cfg = self.machine_profile_service.get_ollama_config()
        gpt_cfg = self.machine_profile_service.get_gpt_sovits_config()

        ollama_report = self._check_ollama(ollama_cfg.get("host", "http://localhost:11434"))
        gpt_report = self._check_gpt_sovits(gpt_cfg)

        auto_patched_profile = False

        if auto_patch and gpt_report.get("ok"):
            resolved_root = str(gpt_report.get("resolved_root_dir", "")).strip()
            resolved_python = str(gpt_report.get("python_exe", "")).strip()
            if resolved_root:
                patch_data = {"root_dir": resolved_root}
                if resolved_python:
                    patch_data["python_exe"] = resolved_python
                self.machine_profile_service.update_section("gpt_sovits", patch_data)
                self.machine_profile_service.append_recent_valid_gpt_root(resolved_root)
                auto_patched_profile = True

        self.machine_profile_service.set_ollama_health(
            ok=bool(ollama_report.get("ok", False)),
            error=str(ollama_report.get("error", "")).strip(),
        )
        self.machine_profile_service.set_gpt_sovits_health(
            ok=bool(gpt_report.get("ok", False)),
            error=str(gpt_report.get("error", "")).strip(),
        )

        startup_status = "ok" if ollama_report.get("ok") else "warning"
        self.machine_profile_service.set_startup_status(startup_status, checked_at)

        return {
            "checked_at": checked_at,
            "auto_patched_profile": auto_patched_profile,
            "ollama": ollama_report,
            "gpt_sovits": gpt_report,
        }