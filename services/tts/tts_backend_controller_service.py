from pathlib import Path
from typing import Any, Dict, List, Optional

from bootstrap.machine_profile_service import MachineProfileService # type: ignore
from services.tts.backends.gpt_sovits_manager import GPTSoVITSManager  # type: ignore

class TTSBackendControllerService:
    """
    TTS 后端控制服务（完整版初版）

    职责：
    1. 统一管理不同 TTS backend 的启动 / 停止 / 探活
    2. 提供统一的 backend 状态查询
    3. 提供“预加载”入口，供 UI 做加载条显示
    4. 屏蔽不同后端之间的运行差异

    当前支持：
    - edge
    - gpt_sovits

    后续可扩展：
    - cosyvoice
    - fishspeech
    - qwen_tts
    - 其他本地 / API 型语音后端
    """

    def __init__(self):
        self._gpt_manager: Optional[GPTSoVITSManager] = None
        self._preload_state: Dict[str, Dict[str, Any]] = {}
        self.machine_profile_service = MachineProfileService()

    # =========================================================
    # 基础工具
    # =========================================================
    def _normalize_backend(self, backend: str | None) -> str:
        text = (backend or "").strip().lower()
        return text or "edge"

    def _build_gpt_manager(self) -> GPTSoVITSManager:
        gpt_cfg = self.machine_profile_service.get_gpt_sovits_config()

        root_dir_raw = str(gpt_cfg.get("root_dir", "")).strip()
        if not root_dir_raw:
            raise FileNotFoundError(
                "machine_profile.json 中未配置 gpt_sovits.root_dir，请先填写 GPT-SoVITS 根目录。"
            )

        root_dir = Path(root_dir_raw).expanduser().resolve()
        if not root_dir.exists():
            raise FileNotFoundError(f"GPT-SoVITS 根目录不存在：{root_dir}")

        python_exe = None
        python_exe_raw = str(gpt_cfg.get("python_exe", "")).strip()
        if python_exe_raw:
            python_exe = str(Path(python_exe_raw).expanduser().resolve())

        host = str(gpt_cfg.get("host", "127.0.0.1")).strip() or "127.0.0.1"
        port = int(gpt_cfg.get("port", 9880) or 9880)

        api_script_value = str(gpt_cfg.get("api_script", "api_v2.py")).strip() or "api_v2.py"
        api_script_path = Path(api_script_value)
        if not api_script_path.is_absolute():
            api_script_path = root_dir / api_script_path
        api_script_path = api_script_path.resolve()

        if not api_script_path.exists():
            raise FileNotFoundError(f"找不到 GPT-SoVITS 启动脚本：{api_script_path}")

        tts_config_path = None
        tts_config_value = str(
            gpt_cfg.get("tts_config", "GPT_SoVITS/configs/tts_infer.yaml")
        ).strip()

        if tts_config_value:
            config_path = Path(tts_config_value)
            if not config_path.is_absolute():
                config_path = root_dir / config_path
            config_path = config_path.resolve()
            if config_path.exists():
                tts_config_path = str(config_path)

        return GPTSoVITSManager(
            root_dir=str(root_dir),
            host=host,
            port=port,
            python_exe=python_exe,
            api_script=str(api_script_path),
            tts_config_path=tts_config_path,
        )
    def _get_gpt_manager(self) -> GPTSoVITSManager:
        if self._gpt_manager is None:
            self._gpt_manager = self._build_gpt_manager()
        return self._gpt_manager

    def _set_preload_state(
        self,
        backend: str,
        *,
        is_loading: bool,
        progress: int,
        status: str,
        package_id: str = "",
        detail: str = "",
    ):
        backend = self._normalize_backend(backend)
        self._preload_state[backend] = {
            "backend": backend,
            "is_loading": is_loading,
            "progress": max(0, min(progress, 100)),
            "status": status,
            "package_id": package_id,
            "detail": detail,
        }

    def _get_default_preload_state(self, backend: str) -> Dict[str, Any]:
        backend = self._normalize_backend(backend)
        return {
            "backend": backend,
            "is_loading": False,
            "progress": 0,
            "status": "未预加载",
            "package_id": "",
            "detail": "",
        }

    # =========================================================
    # backend 列表 / 描述
    # =========================================================
    def list_backend_specs(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "edge",
                "name": "Edge-TTS",
                "requires_server": False,
                "supports_preload": False,
                "supports_stop": False,
                "supports_packages": True,
                "description": "系统在线语音，无需本地服务进程。",
            },
            {
                "id": "gpt_sovits",
                "name": "GPT-SoVITS",
                "requires_server": True,
                "supports_preload": True,
                "supports_stop": True,
                "supports_packages": True,
                "description": "本地克隆语音后端，需要先启动 API 服务。",
            },
        ]

    def get_backend_spec(self, backend: str | None) -> Dict[str, Any]:
        backend = self._normalize_backend(backend)
        for item in self.list_backend_specs():
            if item.get("id") == backend:
                return item
        return {
            "id": backend,
            "name": backend,
            "requires_server": False,
            "supports_preload": False,
            "supports_stop": False,
            "supports_packages": False,
            "description": "未知后端",
        }

    def backend_requires_server(self, backend: str | None) -> bool:
        spec = self.get_backend_spec(backend)
        return bool(spec.get("requires_server", False))

    # =========================================================
    # 状态查询
    # =========================================================
    def get_backend_status(self, backend: str | None) -> Dict[str, Any]:
        backend = self._normalize_backend(backend)
        spec = self.get_backend_spec(backend)

        if backend == "edge":
            return {
                "backend": backend,
                "name": spec.get("name", "Edge-TTS"),
                "requires_server": False,
                "running": True,
                "healthy": True,
                "can_start": False,
                "can_stop": False,
                "message": "Edge-TTS 无需单独启动。",
            }

        if backend == "gpt_sovits":
            try:
                manager = self._get_gpt_manager()
                running = manager.is_running()
                healthy = manager.health_check() if running else False
                return {
                    "backend": backend,
                    "name": spec.get("name", "GPT-SoVITS"),
                    "requires_server": True,
                    "running": running,
                    "healthy": healthy,
                    "can_start": True,
                    "can_stop": True,
                    "message": "GPT-SoVITS 已就绪。" if healthy else "GPT-SoVITS 未启动或未就绪。",
                    "base_url": manager.base_url,
                    "root_dir": str(manager.root_dir),
                }
            except Exception as e:
                return {
                    "backend": backend,
                    "name": spec.get("name", "GPT-SoVITS"),
                    "requires_server": True,
                    "running": False,
                    "healthy": False,
                    "can_start": True,
                    "can_stop": False,
                    "message": f"GPT-SoVITS 未配置：{e}",
                    "base_url": "",
                    "root_dir": "",
                }

        return {
            "backend": backend,
            "name": spec.get("name", backend),
            "requires_server": bool(spec.get("requires_server", False)),
            "running": False,
            "healthy": False,
            "can_start": False,
            "can_stop": False,
            "message": f"暂未实现该后端控制：{backend}",
        }

    # =========================================================
    # 启动 / 停止 / 确保可用
    # =========================================================
    def start_backend(self, backend: str | None) -> Dict[str, Any]:
        backend = self._normalize_backend(backend)

        if backend == "edge":
            return self.get_backend_status("edge")

        if backend == "gpt_sovits":
            manager = self._get_gpt_manager()
            manager.start_server()

            ok = manager.wait_until_ready(timeout=20.0)
            if not ok:
                raise RuntimeError(manager.last_error or "GPT-SoVITS 启动失败或超时。")

            return self.get_backend_status("gpt_sovits")

        raise ValueError(f"不支持启动的 TTS backend: {backend}")

    def stop_backend(self, backend: str | None) -> Dict[str, Any]:
        backend = self._normalize_backend(backend)

        if backend == "edge":
            return self.get_backend_status("edge")

        if backend == "gpt_sovits":
            manager = self._get_gpt_manager()
            manager.stop_server()
            return {
                "backend": "gpt_sovits",
                "name": "GPT-SoVITS",
                "requires_server": True,
                "running": False,
                "healthy": False,
                "can_start": True,
                "can_stop": True,
                "message": "已发送 GPT-SoVITS 停止请求。",
            }

        raise ValueError(f"不支持停止的 TTS backend: {backend}")

    def ensure_backend_ready(self, backend: str | None) -> Dict[str, Any]:
        backend = self._normalize_backend(backend)

        if not self.backend_requires_server(backend):
            return self.get_backend_status(backend)

        status = self.get_backend_status(backend)
        if status.get("healthy"):
            return status

        if backend == "gpt_sovits":
            return self.start_backend("gpt_sovits")

        return self.start_backend(backend)

    # =========================================================
    # 预加载
    # =========================================================
    def preload_backend(
        self,
        backend: str | None,
        package: Optional[Dict[str, Any]] = None,
        runtime_cfg: Optional[Dict[str, Any]] = None,
        progress_cb=None,
    ) -> Dict[str, Any]:
        """
        预加载后端或语音包
        当前初版逻辑：
        - edge: 无需预加载，直接返回
        - gpt_sovits:
            1. 确保服务启动
            2. 优先使用 runtime_cfg 中的模型/参考音频信息
            3. 若 runtime_cfg 为空，再回退读取包目录
            4. 加载权重并尝试 warmup
        """
        backend = self._normalize_backend(backend)
        package = package or {}

        if backend == "edge":
            self._set_preload_state(
                backend,
                is_loading=False,
                progress=100,
                status="Edge-TTS 无需预加载",
                package_id=str(package.get("id", "")),
            )
            return self.get_preload_status(backend)

        if backend != "gpt_sovits":
            self._set_preload_state(
                backend,
                is_loading=False,
                progress=0,
                status=f"暂未实现该后端预加载：{backend}",
                package_id=str(package.get("id", "")),
            )
            return self.get_preload_status(backend)

        package_id = str(package.get("id", "")).strip()
        package_name = str(package.get("name", "")).strip()
        package_path = str(package.get("path", "")).strip()

        self._set_preload_state(
            backend,
            is_loading=True,
            progress=5,
            status="正在检查 GPT-SoVITS 服务",
            package_id=package_id,
        )
        if progress_cb:
            progress_cb("正在检查 GPT-SoVITS 服务…", 5)

        manager = self._get_gpt_manager()
        self.ensure_backend_ready("gpt_sovits")

        self._set_preload_state(
            backend,
            is_loading=True,
            progress=30,
            status="GPT-SoVITS 服务已启动",
            package_id=package_id,
        )
        if progress_cb:
            progress_cb("GPT-SoVITS 服务已启动…", 30)

        # 1) 先优先使用 runtime_cfg
        cfg = dict(runtime_cfg or {})

        # 2) 如果 runtime_cfg 为空，再回退旧逻辑
        if not cfg:
            package_dir = Path(package_path) if package_path else None
            if package_dir and package_dir.exists():
                gpt_json = package_dir / "gpt_sovits.json"
                ref_wav = package_dir / "ref.wav"
                ref_txt = package_dir / "ref.txt"

                raw_cfg: Dict[str, Any] = {}
                if gpt_json.exists():
                    try:
                        import json
                        raw_cfg = json.loads(gpt_json.read_text(encoding="utf-8"))
                    except Exception:
                        raw_cfg = {}

                cfg = {
                    "gpt_model_path": str(raw_cfg.get("gpt_model_path", "")).strip(),
                    "sovits_model_path": str(raw_cfg.get("sovits_model_path", "")).strip(),
                    "prompt_text": str(raw_cfg.get("prompt_text", "")).strip(),
                    "prompt_lang": str(raw_cfg.get("prompt_lang", "zh")).strip() or "zh",
                    "text_lang": str(raw_cfg.get("text_lang", "zh")).strip() or "zh",
                    "ref_audio_path": str(ref_wav.resolve()) if ref_wav.exists() else "",
                    "package_name": package_name,
                    "package_id": package_id,
                }

                if not cfg["prompt_text"] and ref_txt.exists():
                    try:
                        cfg["prompt_text"] = ref_txt.read_text(encoding="utf-8").strip()
                    except Exception:
                        cfg["prompt_text"] = ""

        # 3) 不管 cfg 来自 runtime_cfg 还是 fallback，都统一在这里取值
        gpt_model_path = str(cfg.get("gpt_model_path", "")).strip()
        sovits_model_path = str(cfg.get("sovits_model_path", "")).strip()
        prompt_text = str(cfg.get("prompt_text", "")).strip()
        prompt_lang = str(cfg.get("prompt_lang", "zh")).strip() or "zh"
        text_lang = str(cfg.get("text_lang", "zh")).strip() or "zh"
        ref_audio_path = str(cfg.get("ref_audio_path", "")).strip()
        package_name = str(cfg.get("package_name", "")).strip() or package_name
        package_id = str(cfg.get("package_id", "")).strip() or package_id

        if not gpt_model_path or not sovits_model_path:
            raise RuntimeError("预加载失败：缺少 gpt_model_path 或 sovits_model_path。")

        self._set_preload_state(
            backend,
            is_loading=True,
            progress=55,
            status="正在加载 GPT / SoVITS 权重",
            package_id=package_id,
        )
        manager.set_gpt_weights(gpt_model_path)
        manager.set_sovits_weights(sovits_model_path)

        if progress_cb:
            progress_cb("正在加载 GPT / SoVITS 权重…", 55)

        if ref_audio_path and prompt_text:
            self._set_preload_state(
                backend,
                is_loading=True,
                progress=80,
                status="正在进行语音预热",
                package_id=package_id,
            )
            try:
                manager.warmup(
                    ref_audio_path=ref_audio_path,
                    prompt_text=prompt_text,
                    prompt_lang=prompt_lang,
                    text_lang=text_lang,
                )
            except Exception:
                pass

        self._set_preload_state(
            backend,
            is_loading=False,
            progress=100,
            status="预加载完成",
            package_id=package_id,
            detail=package_name or package_id,
        )
        if progress_cb:
            progress_cb("预加载完成", 100)

        return self.get_preload_status(backend)

    def get_preload_status(self, backend: str | None) -> Dict[str, Any]:
        backend = self._normalize_backend(backend)
        return self._preload_state.get(backend, self._get_default_preload_state(backend))

    def clear_preload_status(self, backend: str | None):
        backend = self._normalize_backend(backend)
        if backend in self._preload_state:
            del self._preload_state[backend]
    def prepare_current_runtime(
        self,
        voice_profile_service,
        tts_package_service,
        progress_cb=None,
    ) -> Dict[str, Any]:
        backend = (voice_profile_service.get_current_tts_backend() or "edge").strip().lower()

        if backend != "gpt_sovits":
            status = self.get_backend_status(backend)
            return {
                "backend": backend,
                "healthy": bool(status.get("healthy", True)),
                "service_ready": True,
                "package_ready": True,
                "package_id": "",
                "detail": "",
                "message": status.get("message", "当前语音后端无需预加载"),
            }

        package = (
            tts_package_service.ensure_valid_current_package(backend)
            or tts_package_service.get_current_package(backend)
            or {}
        )
        if not package:
            raise RuntimeError("当前未找到可用的 GPT-SoVITS 语音包。")

        runtime_cfg = tts_package_service.build_runtime_config(backend, package)

        result = self.preload_backend(
            backend,
            package,
            runtime_cfg=runtime_cfg,
            progress_cb=progress_cb,
        )

        return {
            "backend": backend,
            "healthy": True,
            "service_ready": True,
            "package_ready": True,
            "package_id": str(result.get("package_id", "")).strip() or str(runtime_cfg.get("package_id", "")).strip(),
            "detail": str(result.get("detail", "")).strip() or str(runtime_cfg.get("package_name", "")).strip(),
            "message": str(result.get("status", "预加载完成")).strip() or "预加载完成",
        }
    # =========================================================
    # 高级接口
    # =========================================================
    def get_gpt_manager(self) -> GPTSoVITSManager:
        return self._get_gpt_manager()