import json
import os

from bootstrap.hundun.load import get_engine_config
from bootstrap.hundun.seed import load_defaults

# =========================
# 基础路径配置（项目根目录）
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =========================
# 1. 基础组件库（兼容旧结构）
# =========================
LIBRARY_DIR = os.path.join(BASE_DIR, "library")
STYLES_DIR = os.path.join(LIBRARY_DIR, "styles")
VOICES_DIR = os.path.join(LIBRARY_DIR, "voices")
PRESETS_DIR = os.path.join(LIBRARY_DIR, "presets")

# =========================
# 2. 正式角色目录
# =========================
CHARACTERS_DIR = os.path.join(BASE_DIR, "characters")

# =========================
# 3. 数据目录
# =========================
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULTS_DIR = os.path.join(DATA_DIR, "defaults")
WORKSPACE_DIR = os.path.join(DATA_DIR, "workspace")
RUNTIME_DIR = os.path.join(DATA_DIR, "runtime")
HISTORIES_DIR = os.path.join(DATA_DIR, "histories")
USER_PREFS_DIR = os.path.join(DATA_DIR, "user_prefs")
LOGS_DIR = os.path.join(DATA_DIR, "logs")

# =========================
# 4. 模型目录
# =========================
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODELS_LLM_DIR = os.path.join(MODELS_DIR, "llm")
MODELS_ASR_DIR = os.path.join(MODELS_DIR, "asr")
MODELS_TTS_DIR = os.path.join(MODELS_DIR, "tts")
MODEL_REGISTRY_DIR = os.path.join(MODELS_DIR, "registry")

# =========================
# 5. 静态资源目录
# =========================
STATIC_DIR = os.path.join(BASE_DIR, "static")

# =========================
# 6. 临时目录
# =========================
TEMP_DIR = os.path.join(BASE_DIR, "temp")
RECORD_FOLDER = os.path.join(TEMP_DIR, "records")
REPLY_FOLDER = os.path.join(TEMP_DIR, "replies")
CACHE_FOLDER = os.path.join(TEMP_DIR, "cache")
SESSION_TEMP_DIR = os.path.join(TEMP_DIR, "sessions")

# 兼容旧命名
TEMP_FOLDER = TEMP_DIR

# =========================
# 7. 用户导出目录
# =========================
FAVORITES_FOLDER = os.path.join(BASE_DIR, "favorites")
DOWNLOADS_FOLDER = os.path.join(BASE_DIR, "downloads")

# =========================
# 8. defaults / local / runtime 文件
# =========================

# defaults（系统自带模板）
DEFAULT_DESKTOP_MODE_FILE = os.path.join(DEFAULTS_DIR, "desktop_mode.json")
DEFAULT_PERMS_FILE = os.path.join(DEFAULTS_DIR, "perms.json")
DEFAULT_APP_MAP_FILE = os.path.join(DEFAULTS_DIR, "app_map.json")
DEFAULT_ROOT_SEED_FILE = os.path.join(DEFAULTS_DIR, "root_seed.json")
DEFAULT_ENGINE_MAP_FILE = os.path.join(DEFAULTS_DIR, "engine_map.json")
DEFAULT_SEARCH_SEED_FILE = os.path.join(DEFAULTS_DIR, "search_seed.json")
DEFAULT_REPLY_POLICY_FILE = os.path.join(DEFAULTS_DIR, "reply_policy.json")
DEFAULT_INIT_SEED_FILE = os.path.join(DEFAULTS_DIR, "init_seed.json")

# local（本机绑定）
MACHINE_LOCAL_FILE = os.path.join(USER_PREFS_DIR, "machine.local.json")
ENGINES_LOCAL_FILE = os.path.join(USER_PREFS_DIR, "engines.local.json")
ROOTS_LOCAL_FILE = os.path.join(USER_PREFS_DIR, "roots.local.json")
APPS_LOCAL_FILE = os.path.join(USER_PREFS_DIR, "apps.local.json")
APPS_CANDIDATES_LOCAL_FILE = os.path.join(USER_PREFS_DIR, "apps.candidates.local.json")
DESKTOP_MODE_LOCAL_FILE = os.path.join(USER_PREFS_DIR, "desktop_mode.local.json")
SEARCH_LOCAL_FILE = os.path.join(USER_PREFS_DIR, "search.local.json")
INSTALL_LOCAL_FILE = os.path.join(USER_PREFS_DIR, "install.local.json")
AUDIO_DEVICE_LOCAL_FILE = os.path.join(USER_PREFS_DIR, "audio_device.local.json")

# runtime（运行状态）
ENGINE_RUNTIME_FILE = os.path.join(RUNTIME_DIR, "engine_runtime.json")
DESKTOP_RUNTIME_FILE = os.path.join(RUNTIME_DIR, "desktop_runtime.json")
DESKTOP_SESSION_STATE_FILE = os.path.join(RUNTIME_DIR, "desktop_session_state.json")
DESKTOP_LAST_ACTIONS_FILE = os.path.join(RUNTIME_DIR, "desktop_last_actions.json")

# 兼容旧命名（这轮先保留，后面再慢慢删）
MODEL_REPLY_POLICY_RULES_FILE = DEFAULT_REPLY_POLICY_FILE
TOOL_PERMISSIONS_FILE = DEFAULT_PERMS_FILE
APP_MAPPINGS_FILE = DEFAULT_APP_MAP_FILE
SEARCH_PATHS_FILE = SEARCH_LOCAL_FILE
INSTALL_MANIFEST_FILE = INSTALL_LOCAL_FILE
MACHINE_PROFILE_FILE = MACHINE_LOCAL_FILE
# 9. runtime 文件
# =========================
CURRENT_CHARACTER_FILE = os.path.join(RUNTIME_DIR, "current_character.json")
CURRENT_ROLE_FILE = os.path.join(RUNTIME_DIR, "current_role.json")   # 兼容旧命名
CURRENT_MODEL_FILE = os.path.join(RUNTIME_DIR, "current_model.json")
CURRENT_OUTPUT_MODE_FILE = os.path.join(RUNTIME_DIR, "current_output_mode.json")
CURRENT_SESSION_FILE = os.path.join(RUNTIME_DIR, "current_session.json")
TEMP_RUNTIME_STATE_FILE = os.path.join(RUNTIME_DIR, "temp_runtime_state.json")
CURRENT_STYLE_FILE = os.path.join(RUNTIME_DIR, "current_style.json")
CURRENT_VOICE_FILE = os.path.join(RUNTIME_DIR, "current_voice.json")
CURRENT_TTS_PACKAGE_FILE = os.path.join(RUNTIME_DIR, "current_tts_package.json")

# =========================
# 10. workspace 文件
# =========================
WORKSPACE_DRAFT_IDENTITY_FILE = os.path.join(WORKSPACE_DIR, "draft_identity.json")
WORKSPACE_STYLE_SELECTION_FILE = os.path.join(WORKSPACE_DIR, "current_style_selection.json")
WORKSPACE_VOICE_SELECTION_FILE = os.path.join(WORKSPACE_DIR, "current_voice_selection.json")
WORKSPACE_PERSONA_DRAFT_FILE = os.path.join(WORKSPACE_DIR, "current_persona_draft.txt")
WORKSPACE_PREVIEW_TEXT_FILE = os.path.join(WORKSPACE_DIR, "preview_text.txt")
WORKSPACE_PREVIEW_AUDIO_FILE = os.path.join(WORKSPACE_DIR, "preview_audio.wav")
WORKSPACE_RAW_REPLY_FILE = os.path.join(WORKSPACE_DIR, "raw_reply.txt")
WORKSPACE_VISIBLE_REPLY_FILE = os.path.join(WORKSPACE_DIR, "visible_reply.txt")
WORKSPACE_TTS_REPLY_FILE = os.path.join(WORKSPACE_DIR, "tts_reply.txt")

# =========================
# 11. 桌面程序基础配置
# =========================
APP_TITLE = "本地桌面语音 AI 原型"
APP_ICON_FILE = os.path.join(BASE_DIR, "ui", "assets", "咖啡.ico")
USER_NAME = "用户"
ASSISTANT_NAME = "语音AI助手"

# =========================
# 12. LLM 基础配置
# =========================
DEFAULT_OLLAMA_MODEL_NAME = "qwen3:4b"
OLLAMA_MODEL = DEFAULT_OLLAMA_MODEL_NAME
SYSTEM_PROMPT = (
    "你是一个自然、温和、适合中文桌面对话的AI助手。"
    "请使用简洁、自然、偏口语的中文回答。"
    "回答不要过长，适合语音播放。"
)

MAX_HISTORY_MESSAGES = 6
OLLAMA_CONNECT_TIMEOUT = 10
OLLAMA_READ_TIMEOUT = 300
OLLAMA_NUM_CTX = 2048
OLLAMA_NUM_PREDICT = -1
OLLAMA_TEMPERATURE = 0.6
OLLAMA_TOP_P = 0.9
OLLAMA_KEEP_ALIVE = "10m"
OLLAMA_HOST = "http://localhost:11434"
GPT_SOVITS_ROOT = ""
GPT_SOVITS_PYTHON_EXE = ""
GPT_SOVITS_HOST = "127.0.0.1"
GPT_SOVITS_PORT = 9880
GPT_SOVITS_API_SCRIPT = "api_v2.py"
GPT_SOVITS_TTS_CONFIG = "GPT_SoVITS/configs/tts_infer.yaml"

# =========================
# 13. Whisper / ASR 配置
# =========================
WHISPER_MODEL_SIZE = "small"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float16"
ASR_LANGUAGE = "zh"

# ASR 稳定性参数
ASR_BEAM_SIZE = 5
ASR_BEST_OF = 5
ASR_TEMPERATURE = 0.0
ASR_VAD_FILTER = True
ASR_VAD_MIN_SILENCE_MS = 350
ASR_CONDITION_ON_PREVIOUS_TEXT = False
ASR_INITIAL_PROMPT = (
    "以下内容是中文普通话口语转写，常见内容包括日常问答、数字计算、"
    "桌面软件操作、语音助手对话。请直接准确转写，不要补写，不要总结。"
)

# =========================
# 14. 录音配置
# =========================
SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_DTYPE = "float32"
MIN_RECORD_SECONDS = 2
MAX_RECORD_SECONDS = 60
RECORD_EXTENSION = ".wav"

# 录音落盘与预处理
RECORD_SAVE_SUBTYPE = "PCM_16"
RECORD_NORMALIZE_AUDIO = True
RECORD_NORMALIZE_PEAK = 0.95
RECORD_MIN_PEAK_FOR_NORMALIZE = 0.01

# =========================
# 15. TTS 配置
# =========================
TTS_VOICE = "zh-CN-XiaoxiaoNeural"
TTS_OUTPUT_EXTENSION = ".mp3"
AUTO_PLAY_AUDIO = True
DEFAULT_SPEECH_RATE = 1.0
DEFAULT_OUTPUT_MODE = "text_voice"

# =========================
# 16. 本地引擎配置缓存读取（兼容入口）
# =========================
def reload_machine_profile_cache() -> dict:
    global _MACHINE_PROFILE_CACHE
    global _OLLAMA_CFG
    global _GPT_SOVITS_CFG
    global OLLAMA_HOST
    global GPT_SOVITS_ROOT
    global GPT_SOVITS_PYTHON_EXE
    global GPT_SOVITS_HOST
    global GPT_SOVITS_PORT
    global GPT_SOVITS_API_SCRIPT
    global GPT_SOVITS_TTS_CONFIG

    _OLLAMA_CFG = get_engine_config("ollama", BASE_DIR)
    _GPT_SOVITS_CFG = get_engine_config("gpt_sovits", BASE_DIR)

    _MACHINE_PROFILE_CACHE = {
        "ollama": _OLLAMA_CFG,
        "gpt_sovits": _GPT_SOVITS_CFG,
    }

    OLLAMA_HOST = str(_OLLAMA_CFG.get("host", "http://localhost:11434")).strip() or "http://localhost:11434"

    GPT_SOVITS_ROOT = str(_GPT_SOVITS_CFG.get("root_dir", "")).strip()
    GPT_SOVITS_PYTHON_EXE = str(_GPT_SOVITS_CFG.get("python_exe", "")).strip()
    GPT_SOVITS_HOST = str(_GPT_SOVITS_CFG.get("host", "127.0.0.1")).strip() or "127.0.0.1"
    GPT_SOVITS_PORT = int(_GPT_SOVITS_CFG.get("port", 9880) or 9880)
    GPT_SOVITS_API_SCRIPT = str(_GPT_SOVITS_CFG.get("api_script", "api_v2.py")).strip() or "api_v2.py"
    GPT_SOVITS_TTS_CONFIG = str(
        _GPT_SOVITS_CFG.get("tts_config", "GPT_SoVITS/configs/tts_infer.yaml")
    ).strip() or "GPT_SoVITS/configs/tts_infer.yaml"

    return _MACHINE_PROFILE_CACHE


_MACHINE_PROFILE_CACHE = {}
_OLLAMA_CFG = {}
_GPT_SOVITS_CFG = {}

# =========================
# 17. 目录初始化
# =========================
PROJECT_DIRS = [
    LIBRARY_DIR,
    STYLES_DIR,
    VOICES_DIR,
    PRESETS_DIR,
    CHARACTERS_DIR,
    DATA_DIR,
    WORKSPACE_DIR,
    RUNTIME_DIR,
    HISTORIES_DIR,
    USER_PREFS_DIR,
    LOGS_DIR,
    MODELS_DIR,
    MODELS_LLM_DIR,
    MODELS_ASR_DIR,
    MODELS_TTS_DIR,
    MODEL_REGISTRY_DIR,
    TEMP_DIR,
    RECORD_FOLDER,
    REPLY_FOLDER,
    CACHE_FOLDER,
    SESSION_TEMP_DIR,
    FAVORITES_FOLDER,
    DOWNLOADS_FOLDER,
    STATIC_DIR,
    DEFAULTS_DIR,
]

def _default_model_reply_policy_rules() -> dict:
    return {
        "version": "v1",
        "family_aliases": {
            "qwen": ["qwen", "qwq"],
            "deepseek": ["deepseek"],
            "llama": ["llama"],
            "gpt": ["gpt"],
            "gemini": ["gemini"],
            "claude": ["claude"],
            "mistral": ["mistral"],
        },
        "size_tiers": [
            {"name": "small", "max_b": 4.5},
            {"name": "medium", "max_b": 16.0},
            {"name": "large", "min_b": 16.0001}
        ],
        "provider_default_tiers": {
            "ollama": "medium",
            "local": "medium",
            "api": "large"
        },
        "tier_template_mapping": {
            "small": "small_local_strict",
            "medium": "medium_local_balanced",
            "large": "large_local_light",
            "api": "api_high_trust"
        },
        "family_policy_overrides": {
            "qwen": {
                "small": {
                    "template": "small_local_strict",
                    "policy_patch": {
                        "notes": "Qwen 小模型：启用强提取，抑制过度铺垫与尾句干扰。"
                    }
                },
                "medium": {
                    "template": "medium_local_balanced",
                    "policy_patch": {
                        "notes": "Qwen 中模型：保留简短解释，但避免过度裁剪。"
                    }
                },
                "large": {
                    "template": "large_local_light",
                    "policy_patch": {
                        "notes": "Qwen 大模型：尽量轻处理，保留原始结构。"
                    }
                }
            },
            "deepseek": {
                "small": {
                    "template": "small_local_strict",
                    "policy_patch": {
                        "notes": "DeepSeek 小模型：使用强策略，但保留一定解释空间。"
                    }
                }
            }
        },
        "explicit_model_rules": [
            {
                "match_type": "contains",
                "value": "qwen3:4b",
                "family": "qwen",
                "size_tier": "small",
                "template": "small_local_strict"
            },
            {
                "match_type": "contains",
                "value": "qwen3:8b",
                "family": "qwen",
                "size_tier": "medium",
                "template": "medium_local_balanced"
            }
        ]
    }

def _ensure_json_file(path: str, default_data: dict) -> None:
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)


def _ensure_text_file(path: str, default_text: str = "") -> None:
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(default_text)


def ensure_project_dirs() -> None:
    for folder in PROJECT_DIRS:
        os.makedirs(folder, exist_ok=True)

    defaults = load_defaults(BASE_DIR)
    _ensure_json_file(
        DEFAULT_ROOT_SEED_FILE,
        defaults.get("root_seed", {"roots": []}),
    )

    _ensure_json_file(CURRENT_CHARACTER_FILE, {"role_id": ""})
    _ensure_json_file(CURRENT_ROLE_FILE, {"role_id": ""})   # 兼容旧命名
    _ensure_json_file(CURRENT_MODEL_FILE, {"model_id": ""})
    _ensure_json_file(CURRENT_OUTPUT_MODE_FILE, {"mode": DEFAULT_OUTPUT_MODE})
    _ensure_json_file(CURRENT_SESSION_FILE, {"session_id": ""})
    _ensure_json_file(TEMP_RUNTIME_STATE_FILE, {})
    _ensure_json_file(CURRENT_STYLE_FILE, {"style_id": ""})
    _ensure_json_file(CURRENT_VOICE_FILE, {"voice_id": ""})
    _ensure_json_file(CURRENT_TTS_PACKAGE_FILE, {"backend": "", "package_id": ""})

    _ensure_json_file(WORKSPACE_DRAFT_IDENTITY_FILE, {})
    _ensure_json_file(WORKSPACE_STYLE_SELECTION_FILE, {"id": "", "name": ""})
    _ensure_json_file(WORKSPACE_VOICE_SELECTION_FILE, {"id": "", "name": ""})

    _ensure_text_file(WORKSPACE_PERSONA_DRAFT_FILE, "")
    _ensure_text_file(WORKSPACE_PREVIEW_TEXT_FILE, "")
    _ensure_text_file(WORKSPACE_RAW_REPLY_FILE, "")
    _ensure_text_file(WORKSPACE_VISIBLE_REPLY_FILE, "")
    _ensure_text_file(WORKSPACE_TTS_REPLY_FILE, "")
