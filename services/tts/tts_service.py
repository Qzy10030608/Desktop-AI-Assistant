from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import edge_tts

from services.tts.tts_backend_controller_service import TTSBackendControllerService  # type: ignore
from services.tts.backends.gpt_sovits_adapter import GPTSoVITSAdapter  # type: ignore


_tts_backend_controller: Optional[TTSBackendControllerService] = None
_gpt_sovits_adapter: Optional[GPTSoVITSAdapter] = None

# 共享一个 GPT-SoVITS 服务时，权重切换 / 合成请求最好串行
# 否则并发请求可能互相覆盖模型状态
_gpt_sovits_lock = threading.RLock()
_adapter_init_lock = threading.RLock()


@dataclass
class TTSRequest:
    text: str
    output_file: str

    backend: str = "edge"
    voice: Optional[str] = None
    voice_profile: Dict[str, Any] = field(default_factory=dict)
    performance_profile: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


def _ensure_parent_dir(output_file: str) -> None:
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)


def _get_tts_backend_controller() -> TTSBackendControllerService:
    global _tts_backend_controller
    if _tts_backend_controller is None:
        _tts_backend_controller = TTSBackendControllerService()
    return _tts_backend_controller


def _get_gpt_sovits_adapter() -> GPTSoVITSAdapter:
    """
    复用同一个 GPT-SoVITSAdapter，保留 _last_model_key，
    避免每次请求都丢失“当前已加载模型”的缓存状态。
    """
    global _gpt_sovits_adapter

    if _gpt_sovits_adapter is not None:
        return _gpt_sovits_adapter

    with _adapter_init_lock:
        if _gpt_sovits_adapter is None:
            controller = _get_tts_backend_controller()
            manager = controller.get_gpt_manager()
            _gpt_sovits_adapter = GPTSoVITSAdapter(manager)

    return _gpt_sovits_adapter


def reset_gpt_sovits_adapter_cache() -> None:
    """
    可选工具：
    当你显式重启 GPT-SoVITS 服务、切根目录、切 host/port 时，
    可以调用这个方法丢弃旧 adapter。
    """
    global _gpt_sovits_adapter
    with _adapter_init_lock:
        _gpt_sovits_adapter = None


def _normalize_edge_rate(value: Any) -> str:
    if value is None:
        return "+0%"

    if isinstance(value, str):
        value = value.strip()
        if value.endswith("%"):
            return value
        try:
            num = int(float(value))
            return f"{num:+d}%"
        except Exception:
            return "+0%"

    try:
        num = int(float(value))
        return f"{num:+d}%"
    except Exception:
        return "+0%"


def _normalize_edge_volume(value: Any) -> str:
    if value is None:
        return "+0%"

    if isinstance(value, str):
        value = value.strip()
        if value.endswith("%"):
            return value
        try:
            num = int(float(value))
            return f"{num:+d}%"
        except Exception:
            return "+0%"

    try:
        num = int(float(value))
        return f"{num:+d}%"
    except Exception:
        return "+0%"


def _normalize_edge_pitch(value: Any) -> str:
    if value is None:
        return "+0Hz"

    if isinstance(value, str):
        value = value.strip()
        if value.lower().endswith("hz"):
            return value
        try:
            num = int(float(value))
            return f"{num:+d}Hz"
        except Exception:
            return "+0Hz"

    try:
        num = int(float(value))
        return f"{num:+d}Hz"
    except Exception:
        return "+0Hz"


def _extract_edge_params(request: TTSRequest):
    perf = request.performance_profile or {}
    voice_profile = request.voice_profile or {}
    tts_config = voice_profile.get("tts_config", {}) or {}

    edge_voice = (
        request.voice
        or tts_config.get("voice")
        or tts_config.get("voice_name")
        or tts_config.get("edge_voice")
        or voice_profile.get("edge_voice")
        or voice_profile.get("voice_name")
        or "zh-CN-XiaoxiaoNeural"
    )

    rate = _normalize_edge_rate(perf.get("rate", voice_profile.get("rate")))
    volume = _normalize_edge_volume(perf.get("volume", voice_profile.get("volume")))
    pitch = _normalize_edge_pitch(perf.get("pitch", voice_profile.get("pitch")))

    return edge_voice, rate, volume, pitch


async def _generate_edge_tts(request: TTSRequest) -> None:
    if not request.text or not request.text.strip():
        raise ValueError("TTS 文本不能为空。")

    _ensure_parent_dir(request.output_file)

    voice, rate, volume, pitch = _extract_edge_params(request)

    communicate = edge_tts.Communicate(
        text=request.text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
    )
    await communicate.save(request.output_file)


def _merge_gpt_profile(request: TTSRequest) -> Dict[str, Any]:
    """
    将 voice_profile / extra / performance_profile 合并成最终运行配置。
    保持你当前项目已有逻辑不变，只是抽成单独函数。
    """
    merged_profile = dict(request.voice_profile or {})

    for key, value in (request.extra or {}).items():
        if key not in merged_profile or merged_profile.get(key) in ("", None):
            merged_profile[key] = value

    for key, value in (request.performance_profile or {}).items():
        if key not in merged_profile or merged_profile.get(key) in ("", None):
            merged_profile[key] = value

    return merged_profile


async def _generate_gpt_sovits_tts(request: TTSRequest) -> None:
    if not request.text or not request.text.strip():
        raise ValueError("TTS 文本不能为空。")

    _ensure_parent_dir(request.output_file)
    loop = asyncio.get_running_loop()

    merged_profile = _merge_gpt_profile(request)

    def _run():
        adapter = _get_gpt_sovits_adapter()

        # 共享一个 GPT-SoVITS 服务时串行执行，避免：
        # - 权重切换互相覆盖
        # - _last_model_key 在并发下失去意义
        with _gpt_sovits_lock:
            adapter.synthesize(
                text=request.text,
                output_file=request.output_file,
                voice_profile=merged_profile,
            )

    await loop.run_in_executor(None, _run)


async def generate_tts_async(request: TTSRequest) -> str:
    backend = (request.backend or "edge").strip().lower()

    if backend == "edge":
        await _generate_edge_tts(request)
    elif backend == "gpt_sovits":
        await _generate_gpt_sovits_tts(request)
    else:
        raise ValueError(f"不支持的 TTS backend: {backend}")

    return request.output_file


def generate_tts(request: TTSRequest) -> str:
    return asyncio.run(generate_tts_async(request))


def text_to_speech(text, output_file, voice):
    request = TTSRequest(
        text=text,
        output_file=output_file,
        backend="edge",
        voice=voice,
    )
    return generate_tts(request)