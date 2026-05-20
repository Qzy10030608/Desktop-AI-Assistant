from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def _norm(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def get_project_root(project_root: str | Path | None = None) -> Path:
    if project_root:
        return Path(project_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def collect_machine_paths(project_root: str | Path | None = None) -> Dict[str, str]:
    root = get_project_root(project_root)
    home = Path.home()

    documents = Path(os.environ.get("USERPROFILE", str(home))) / "Documents"
    downloads = Path(os.environ.get("USERPROFILE", str(home))) / "Downloads"
    desktop = Path(os.environ.get("USERPROFILE", str(home))) / "Desktop"

    appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
    localappdata = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
    programfiles = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    programfiles_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))

    return {
        "OS": "windows" if os.name == "nt" else os.name,
        "PROJECT_ROOT": _norm(root),
        "USER_HOME": _norm(home),
        "DOCUMENTS": _norm(documents),
        "DOWNLOADS": _norm(downloads),
        "DESKTOP": _norm(desktop),
        "APPDATA": _norm(appdata),
        "LOCALAPPDATA": _norm(localappdata),
        "PROGRAMFILES": _norm(programfiles),
        "PROGRAMFILES_X86": _norm(programfiles_x86),
    }