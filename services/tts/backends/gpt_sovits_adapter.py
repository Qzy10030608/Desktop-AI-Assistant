from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .gpt_sovits_manager import GPTSoVITSManager  # type: ignore


class GPTSoVITSAdapter:
    def __init__(self, manager: GPTSoVITSManager):
        self.manager = manager
        self._last_model_key: Optional[str] = None

    def _read_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _resolve_relative_path(self, base_dir: Path, raw_path: str) -> str:
        text = (raw_path or "").strip()
        if not text:
            return ""

        path = Path(text)
        if not path.is_absolute():
            path = base_dir / path

        return str(path.resolve())

    def _resolve_runtime_config(self, voice_profile: Dict[str, Any]) -> Dict[str, Any]:
        voice_profile = voice_profile or {}

        model_config_path = (
            voice_profile.get("gpt_sovits_json")
            or voice_profile.get("model_config_path")
            or ""
        )
        model_config_path = str(model_config_path).strip()

        config_path = Path(model_config_path) if model_config_path else None
        config_data: Dict[str, Any] = {}

        if config_path and config_path.exists():
            config_data = self._read_json(config_path)
            base_dir = config_path.parent
        else:
            voice_dir = str(voice_profile.get("voice_dir", "")).strip()
            if voice_dir:
                base_dir = Path(voice_dir)
            else:
                ref_audio_hint = str(
                    voice_profile.get("ref_audio_path")
                    or voice_profile.get("ref_wav")
                    or ""
                ).strip()
                base_dir = Path(ref_audio_hint).parent if ref_audio_hint else Path.cwd()

        ref_audio_path = (
            str(voice_profile.get("ref_audio_path", "")).strip()
            or str(voice_profile.get("ref_wav", "")).strip()
            or self._resolve_relative_path(base_dir, str(config_data.get("ref_audio_path", "")).strip())
        )

        prompt_text_path = (
            str(voice_profile.get("prompt_text_path", "")).strip()
            or str(voice_profile.get("ref_txt", "")).strip()
            or self._resolve_relative_path(
                base_dir,
                str(
                    config_data.get("prompt_text_path", "")
                    or config_data.get("ref_txt", "")
                    or config_data.get("prompt_text_file", "")
                ).strip(),
            )
        )

        prompt_text = (
            str(voice_profile.get("prompt_text", "")).strip()
            or str(config_data.get("prompt_text", "")).strip()
        )
        if not prompt_text and prompt_text_path:
            prompt_text = self._read_text(Path(prompt_text_path))

        text_lang = (
            str(voice_profile.get("text_lang", "")).strip()
            or str(config_data.get("text_lang", "")).strip()
            or "zh"
        )
        prompt_lang = (
            str(voice_profile.get("prompt_lang", "")).strip()
            or str(config_data.get("prompt_lang", "")).strip()
            or "zh"
        )

        gpt_model_path = (
            str(voice_profile.get("gpt_model_path", "")).strip()
            or self._resolve_relative_path(base_dir, str(config_data.get("gpt_model_path", "")).strip())
        )
        sovits_model_path = (
            str(voice_profile.get("sovits_model_path", "")).strip()
            or self._resolve_relative_path(base_dir, str(config_data.get("sovits_model_path", "")).strip())
        )

        api_url = (
            str(voice_profile.get("api_url", "")).strip()
            or f"{self.manager.base_url}/tts"
        )

        return {
            "ref_audio_path": ref_audio_path,
            "prompt_text_path": prompt_text_path,
            "prompt_text": prompt_text,
            "prompt_lang": prompt_lang,
            "text_lang": text_lang,
            "gpt_model_path": gpt_model_path,
            "sovits_model_path": sovits_model_path,
            "api_url": api_url,
            "top_k": voice_profile.get("top_k", config_data.get("top_k", 5)),
            "top_p": voice_profile.get("top_p", config_data.get("top_p", 1.0)),
            "temperature": voice_profile.get("temperature", config_data.get("temperature", 1.0)),
            "speed_factor": voice_profile.get("speed_factor", config_data.get("speed_factor", 1.0)),
            "text_split_method": voice_profile.get("text_split_method", config_data.get("text_split_method", "cut5")),
            "batch_size": voice_profile.get("batch_size", config_data.get("batch_size", 1)),
            "batch_threshold": voice_profile.get("batch_threshold", config_data.get("batch_threshold", 0.75)),
            "split_bucket": voice_profile.get("split_bucket", config_data.get("split_bucket", True)),
            "fragment_interval": voice_profile.get("fragment_interval", config_data.get("fragment_interval", 0.3)),
            "seed": voice_profile.get("seed", config_data.get("seed", -1)),
            "parallel_infer": voice_profile.get("parallel_infer", config_data.get("parallel_infer", True)),
            "repetition_penalty": voice_profile.get("repetition_penalty", config_data.get("repetition_penalty", 1.35)),
            "media_type": voice_profile.get("media_type", config_data.get("media_type", "wav")),
            "streaming_mode": voice_profile.get("streaming_mode", config_data.get("streaming_mode", False)),
        }

    def _ensure_model_loaded(self, cfg: Dict[str, Any]) -> None:
        gpt_model_path = str(cfg.get("gpt_model_path", "")).strip()
        sovits_model_path = str(cfg.get("sovits_model_path", "")).strip()
        model_key = f"{gpt_model_path}|{sovits_model_path}"

        if not gpt_model_path or not sovits_model_path:
            raise ValueError("GPT-SoVITS 缺少 gpt_model_path 或 sovits_model_path。")

        if model_key == self._last_model_key:
            return

        self.manager.set_gpt_weights(gpt_model_path)
        self.manager.set_sovits_weights(sovits_model_path)
        self._last_model_key = model_key

    def synthesize(self, text: str, output_file: str, voice_profile: Dict[str, Any]) -> str:
        if not text or not text.strip():
            raise ValueError("GPT-SoVITS 文本不能为空。")

        cfg = self._resolve_runtime_config(voice_profile)

        ref_audio_path = str(cfg.get("ref_audio_path", "")).strip()
        if not ref_audio_path:
            raise ValueError("当前配置缺少 ref_audio_path/ref_wav。")

        prompt_text = str(cfg.get("prompt_text", "")).strip()
        if not prompt_text:
            raise ValueError("当前配置缺少 prompt_text 或 prompt_text_path/ref_txt。")

        self.manager.ensure_started()
        self._ensure_model_loaded(cfg)

        payload = {
            "text": text,
            "text_lang": cfg["text_lang"],
            "ref_audio_path": ref_audio_path,
            "prompt_lang": cfg["prompt_lang"],
            "prompt_text": prompt_text,
            "top_k": cfg["top_k"],
            "top_p": cfg["top_p"],
            "temperature": cfg["temperature"],
            "text_split_method": cfg["text_split_method"],
            "batch_size": cfg["batch_size"],
            "batch_threshold": cfg["batch_threshold"],
            "split_bucket": cfg["split_bucket"],
            "speed_factor": cfg["speed_factor"],
            "fragment_interval": cfg["fragment_interval"],
            "seed": cfg["seed"],
            "media_type": cfg["media_type"],
            "streaming_mode": cfg["streaming_mode"],
            "parallel_infer": cfg["parallel_infer"],
            "repetition_penalty": cfg["repetition_penalty"],
        }

        resp = requests.post(
            cfg["api_url"],
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(resp.content)
        return str(output_path)