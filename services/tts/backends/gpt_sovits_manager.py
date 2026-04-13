from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

import requests


class GPTSoVITSManager:
    def __init__(
        self,
        root_dir: str,
        host: str = "127.0.0.1",
        port: int = 9880,
        python_exe: Optional[str] = None,
        api_script: str = "api_v2.py",
        tts_config_path: Optional[str] = None,
    ):
        self.root_dir = Path(root_dir)
        self.host = host
        self.port = port
        self.python_exe = python_exe or "python"
        self.api_script = api_script
        self.tts_config_path = tts_config_path
        self.process: Optional[subprocess.Popen] = None
        self.last_error: str = ""

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def is_running(self) -> bool:
        try:
            resp = requests.get(
                f"{self.base_url}/control",
                params={"command": "noop"},
                timeout=1,
            )
            return resp.status_code in (200, 400, 500)
        except Exception:
            return False

    def _validate_paths(self):
        if not self.root_dir.exists():
            raise FileNotFoundError(f"GPT-SoVITS 根目录不存在：{self.root_dir}")

        if not self.root_dir.is_dir():
            raise NotADirectoryError(f"GPT-SoVITS 根路径不是文件夹：{self.root_dir}")

        script_path = self.root_dir / self.api_script
        if not script_path.exists():
            raise FileNotFoundError(f"找不到启动脚本：{script_path}")

        if self.tts_config_path:
            cfg_path = Path(self.tts_config_path)
            if not cfg_path.exists():
                raise FileNotFoundError(f"找不到 TTS 配置文件：{cfg_path}")

        py_path = Path(self.python_exe)
        if py_path.name.lower() != "python" and not py_path.exists():
            raise FileNotFoundError(f"找不到 GPT-SoVITS Python：{py_path}")

    def start_server(self) -> None:
        if self.is_running():
            self.last_error = ""
            return

        self._validate_paths()

        script_path = self.root_dir / self.api_script
        cmd = [self.python_exe, str(script_path), "-a", self.host, "-p", str(self.port)]

        if self.api_script == "api_v2.py" and self.tts_config_path:
            cmd += ["-c", self.tts_config_path]

        log_dir = self.root_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_file = open(log_dir / "gpt_sovits_stdout.log", "ab")
        stderr_file = open(log_dir / "gpt_sovits_stderr.log", "ab")

        self.process = subprocess.Popen(
            cmd,
            cwd=str(self.root_dir),
            stdout=stdout_file,
            stderr=stderr_file,
        )
        self.last_error = ""

    def wait_until_ready(self, timeout: float = 20.0) -> bool:
        start = time.time()

        while time.time() - start < timeout:
            if self.health_check():
                self.last_error = ""
                return True

            if self.process is not None:
                code = self.process.poll()
                if code is not None:
                    self.last_error = f"GPT-SoVITS 进程已退出，退出码：{code}"
                    return False

            time.sleep(0.5)

        self.last_error = "等待 GPT-SoVITS 就绪超时"
        return False

    def health_check(self) -> bool:
        try:
            resp = requests.get(
                f"{self.base_url}/control",
                params={"command": "noop"},
                timeout=2,
            )
            return resp.status_code in (200, 400, 500)
        except Exception:
            return False

    def ensure_started(self) -> None:
        if not self.is_running():
            self.start_server()
        ok = self.wait_until_ready()
        if not ok:
            raise RuntimeError(self.last_error or "GPT-SoVITS 服务启动失败或超时。")

    def stop_server(self) -> None:
        try:
            requests.get(
                f"{self.base_url}/control",
                params={"command": "exit"},
                timeout=2,
            )
        except Exception:
            pass

    def set_gpt_weights(self, weights_path: str) -> None:
        resp = requests.get(
            f"{self.base_url}/set_gpt_weights",
            params={"weights_path": weights_path},
            timeout=30,
        )
        resp.raise_for_status()

    def set_sovits_weights(self, weights_path: str) -> None:
        resp = requests.get(
            f"{self.base_url}/set_sovits_weights",
            params={"weights_path": weights_path},
            timeout=30,
        )
        resp.raise_for_status()

    def set_refer_audio(self, refer_audio_path: str) -> None:
        resp = requests.get(
            f"{self.base_url}/set_refer_audio",
            params={"refer_audio_path": refer_audio_path},
            timeout=30,
        )
        resp.raise_for_status()

    def warmup(
        self,
        ref_audio_path: str,
        prompt_text: str,
        prompt_lang: str = "zh",
        text_lang: str = "zh",
    ) -> None:
        payload = {
            "text": "你好",
            "text_lang": text_lang,
            "ref_audio_path": ref_audio_path,
            "prompt_lang": prompt_lang,
            "prompt_text": prompt_text or "你好",
            "media_type": "wav",
            "streaming_mode": False,
        }
        requests.post(f"{self.base_url}/tts", json=payload, timeout=120)