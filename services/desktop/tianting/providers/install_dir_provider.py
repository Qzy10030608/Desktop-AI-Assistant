from __future__ import annotations

from pathlib import Path


class InstallDirProvider:
    def guess(self, target_path: str, *, fallback: str = "") -> str:
        text = str(target_path or "").strip()
        if text:
            try:
                path = Path(text).expanduser().resolve(strict=False)
                if path.suffix.lower() == ".exe":
                    return str(path.parent)
                if path.is_dir():
                    return str(path)
            except Exception:
                return text
        return str(fallback or "").strip()
