from __future__ import annotations

from faster_whisper import WhisperModel

from config import (
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
    ASR_LANGUAGE,
    ASR_BEAM_SIZE,
    ASR_BEST_OF,
    ASR_TEMPERATURE,
    ASR_VAD_FILTER,
    ASR_VAD_MIN_SILENCE_MS,
    ASR_CONDITION_ON_PREVIOUS_TEXT,
    ASR_INITIAL_PROMPT,
)

_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
    return _whisper_model


def _normalize_transcribed_text(text: str) -> str:
    text = (text or "").strip()

    # 清理常见空白与重复换行
    text = text.replace("\r", " ").replace("\n", " ")
    while "  " in text:
        text = text.replace("  ", " ")

    # 中文里常见的一些无意义首尾标点清理
    text = text.strip("，。！？、；： ")

    return text.strip()


def transcribe_audio(audio_path: str) -> str:
    model = get_whisper_model()

    segments, info = model.transcribe(
        audio_path,
        language=ASR_LANGUAGE,
        beam_size=ASR_BEAM_SIZE,
        best_of=ASR_BEST_OF,
        temperature=ASR_TEMPERATURE,
        vad_filter=ASR_VAD_FILTER,
        vad_parameters={
            "min_silence_duration_ms": ASR_VAD_MIN_SILENCE_MS,
        },
        condition_on_previous_text=ASR_CONDITION_ON_PREVIOUS_TEXT,
        initial_prompt=ASR_INITIAL_PROMPT,
        word_timestamps=False,
    )

    text = "".join((segment.text or "") for segment in segments).strip()
    return _normalize_transcribed_text(text)