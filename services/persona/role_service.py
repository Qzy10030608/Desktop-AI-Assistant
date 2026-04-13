import json
from pathlib import Path
from typing import Dict, List, Optional

from config import BASE_DIR, CURRENT_CHARACTER_FILE # type: ignore


class RoleService:
    def __init__(self):
        self.base_dir = Path(BASE_DIR)
        self.characters_dir = self.base_dir / "characters"
        self.runtime_dir = self.base_dir / "data" / "runtime"

        self.current_role_file = Path(CURRENT_CHARACTER_FILE)
        self.legacy_current_role_file = self.runtime_dir / "current_role.json"

        self.characters_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_runtime_file()

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

    def _get_default_role_id(self) -> str:
        role_dirs = self.list_role_dirs()
        return role_dirs[0]["id"] if role_dirs else "character_001"

    def _ensure_runtime_file(self):
        if self.current_role_file.exists():
            return

        if self.legacy_current_role_file.exists():
            old_data = self._read_json(self.legacy_current_role_file)
            role_id = (
                str(old_data.get("role_id", "")).strip()
                or str(old_data.get("character_id", "")).strip()
                or str(old_data.get("id", "")).strip()
            )
            self._write_json(
                self.current_role_file,
                {"role_id": role_id or self._get_default_role_id()},
            )
            return

        self._write_json(
            self.current_role_file,
            {"role_id": self._get_default_role_id()},
        )

    def list_role_dirs(self) -> List[Dict]:
        roles = []
        if not self.characters_dir.exists():
            return roles

        for role_dir in sorted(self.characters_dir.iterdir()):
            if not role_dir.is_dir():
                continue

            meta_path = role_dir / "meta.json"
            meta = self._read_json(meta_path)
            if not meta:
                continue

            role_id = meta.get("id", role_dir.name)
            role_name = meta.get("name", role_dir.name)
            enabled = meta.get("enabled", True)

            roles.append({
                "id": role_id,
                "name": role_name,
                "enabled": enabled,
                "dir_name": role_dir.name,
                "dir_path": str(role_dir),
                "meta": meta,
            })
        return roles

    def get_role_dir_by_id(self, role_id: str) -> Optional[Path]:
        for item in self.list_role_dirs():
            if item["id"] == role_id:
                return Path(item["dir_path"])
        return None

    def get_current_role_id(self) -> str:
        data = self._read_json(self.current_role_file)
        role_id = (
            str(data.get("role_id", "")).strip()
            or str(data.get("character_id", "")).strip()
            or str(data.get("id", "")).strip()
        )
        if role_id:
            return role_id

        return self._get_default_role_id()

    def set_current_role(self, role_id: str):
        self._write_json(self.current_role_file, {"role_id": role_id})

    def get_current_role_meta(self) -> Dict:
        role_id = self.get_current_role_id()
        role_dir = self.get_role_dir_by_id(role_id)
        if not role_dir:
            return {}

        meta = self._read_json(role_dir / "meta.json")
        if "id" not in meta:
            meta["id"] = role_id
        if "dir_path" not in meta:
            meta["dir_path"] = str(role_dir)
        return meta

    def get_current_role_dir(self) -> Optional[Path]:
        return self.get_role_dir_by_id(self.get_current_role_id())

    def read_role_text_file(self, relative_path: str, default: str = "") -> str:
        role_dir = self.get_current_role_dir()
        if not role_dir:
            return default

        path = role_dir / relative_path
        if not path.exists():
            return default

        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return default

    def read_role_json_file(self, relative_path: str, default: Optional[Dict] = None) -> Dict:
        if default is None:
            default = {}

        role_dir = self.get_current_role_dir()
        if not role_dir:
            return default

        path = role_dir / relative_path
        if not path.exists():
            return default

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default