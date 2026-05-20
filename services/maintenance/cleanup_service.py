from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


class CleanupService:
    """Safe backend for the control-center project cleanup card."""

    CATEGORY_TITLES = {
        "downloads": "下载文件",
        "favorites": "收藏文件",
        "operation_logs": "操作日志",
        "history_operations": "历史操作记录",
        "temporary_files": "临时文件",
    }

    SKIP_SUFFIXES = {
        ".py",
        ".pyw",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".css",
        ".html",
        ".qss",
        ".ui",
        ".bat",
        ".cmd",
        ".ps1",
        ".sh",
        ".toml",
        ".yaml",
        ".yml",
        ".ini",
        ".env",
        ".gguf",
        ".safetensors",
        ".pt",
        ".pth",
        ".onnx",
        ".bin",
        ".ckpt",
        ".model",
    }

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2]).resolve(strict=False)
        self.desktop_runtime_dir = self.project_root / "data" / "runtime" / "desktop"
        self.yushitai_dir = self.desktop_runtime_dir / "yushitai"
        self.shaofu_dir = self.desktop_runtime_dir / "shaofu"

    def get_categories(self) -> list[dict[str, Any]]:
        return [self._category_summary(key, scan_files=False) for key in self.CATEGORY_TITLES]

    def scan(self) -> dict[str, Any]:
        categories = [self._category_summary(key, scan_files=True) for key in self.CATEGORY_TITLES]
        return {"ok": True, "categories": categories}

    def delete_selected(self, category_keys: list[str]) -> dict[str, Any]:
        keys = [str(key or "").strip() for key in category_keys]
        deleted_count = 0
        deleted_size = 0
        skipped: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []

        for key in keys:
            if key not in self.CATEGORY_TITLES:
                continue
            if key == "downloads":
                result = self._delete_directory_contents(self._downloads_paths())
            elif key == "favorites":
                result = self._delete_directory_contents(self._favorites_paths())
            elif key == "operation_logs":
                # 操作日志 = 御史台旧 run 清理
                # 只删除 _old_yushitai_run_candidates() 允许的 closed/interrupted 旧 run。
                result = self._delete_old_yushitai_runs()
            elif key == "history_operations":
                # 历史操作记录 = 少府
                # 少府删除必须等下一轮通过 StorageIndex / RestoreRegistry 规则统一设计。
                result = {
                    "deleted_count": 0,
                    "deleted_size_bytes": 0,
                    "failed": [],
                    "skipped": [{"key": key, "reason": "shaofu_cleanup_deferred"}],
                }
            elif key == "temporary_files":
                result = self._delete_temporary_files()
            else:
                result = {"deleted_count": 0, "deleted_size_bytes": 0, "failed": [], "skipped": []}
            deleted_count += int(result.get("deleted_count", 0) or 0)
            deleted_size += int(result.get("deleted_size_bytes", 0) or 0)
            failed.extend(result.get("failed", []) if isinstance(result.get("failed"), list) else [])
            skipped.extend(result.get("skipped", []) if isinstance(result.get("skipped"), list) else [])

        return {
            "ok": not failed,
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "deleted_size_text": self._format_size(deleted_size),
            "failed_count": len(failed),
            "failed": failed[:50],
            "skipped_count": len(skipped),
            "skipped": skipped[:50],
            "scan": self.scan(),
        }

    def open_category_folder(self, category_key: str) -> dict[str, Any]:
        key = str(category_key or "").strip()
        open_path = {
            "downloads": self.project_root / "downloads",
            "favorites": self.project_root / "favorites",
            "operation_logs": self.yushitai_dir / "runs",
            "history_operations": self.shaofu_dir,
            "temporary_files": self.project_root / "temp",
        }.get(key)
        if open_path is None:
            return {"ok": False, "path": "", "message": "未知分类"}
        if open_path.exists() and open_path.is_dir() and self._is_inside_project(open_path):
            return {"ok": True, "path": str(open_path), "message": ""}
        return {"ok": False, "path": "", "message": "该分类暂无可打开目录"}

    def _category_summary(self, key: str, *, scan_files: bool) -> dict[str, Any]:
        if key == "downloads":
            return self._path_category_summary(
                key,
                self._downloads_paths(),
                risk="safe",
                can_delete=True,
                note="清理项目下载导出目录内容，不删除目录本身。",
                scan_files=scan_files,
            )
        if key == "favorites":
            return self._path_category_summary(
                key,
                self._favorites_paths(),
                risk="warning",
                can_delete=True,
                note="清理收藏导出内容，不删除目录本身。",
                scan_files=scan_files,
            )
        if key == "operation_logs":
            return self._operation_logs_summary(scan_files=scan_files)
        if key == "history_operations":
            return self._history_operations_summary(scan_files=scan_files)
        if key == "temporary_files":
            return self._temporary_files_summary(scan_files=scan_files)
        return self._empty_category(key, risk="protected", can_delete=False, note="未知分类")

    def _path_category_summary(
        self,
        key: str,
        paths: list[Path],
        *,
        risk: str,
        can_delete: bool,
        note: str,
        scan_files: bool,
    ) -> dict[str, Any]:
        existing = [path for path in self._effective_roots(paths) if path.exists()]
        size, file_count, dir_count = self._measure_paths(existing) if scan_files else (0, 0, 0)
        return self._category_payload(
            key=key,
            paths=paths,
            existing_paths=existing,
            size_bytes=size,
            file_count=file_count,
            dir_count=dir_count,
            risk=risk,
            can_delete=can_delete,
            protected_count=0,
            note=note,
        )

    def _operation_logs_summary(self, *, scan_files: bool) -> dict[str, Any]:
        # 操作日志 = 御史台 runtime runs
        # 长期 audit/checkpoint ledger 暂时不混入本轮项目清扫。
        paths = [
            self.yushitai_dir / "runs",
        ]
        existing = [path for path in paths if path.exists() and self._is_inside_project(path)]

        size, file_count, dir_count = self._measure_paths(existing) if scan_files else (0, 0, 0)
        candidates = self._old_yushitai_run_candidates()
        protected_count = max(0, len(self._all_yushitai_run_dirs()) - len(candidates))

        note = (
            "操作日志连接御史台运行记录；只保护当前正在使用的 running / active run，"
            "其余已关闭、中断或失败的旧 run 均允许清理。"
        )

        return self._category_payload(
            key="operation_logs",
            paths=paths,
            existing_paths=existing,
            size_bytes=size,
            file_count=file_count,
            dir_count=dir_count,
            risk="warning",
            can_delete=bool(candidates),
            protected_count=protected_count,
            note=note,
            extra={"cleanup_candidate_count": len(candidates)},
        )
    
    def _history_operations_summary(self, *, scan_files: bool) -> dict[str, Any]:
        # 历史操作记录 = 少府
        # 本轮只完成线路切换和扫描，不做少府真实删除。
        paths = [self.shaofu_dir]
        existing = [path for path in paths if path.exists() and self._is_inside_project(path)]

        size, file_count, dir_count = self._measure_paths(existing) if scan_files else (0, 0, 0)
        candidates = self._shaofu_cleanup_candidates() if scan_files else []

        note = (
            "历史操作记录连接少府；本轮只扫描少府材料，不直接删除。"
            "少府真实清理将在下一轮按已恢复、已过期、不可逆变更记录等规则统一设计。"
        )

        return self._category_payload(
            key="history_operations",
            paths=paths,
            existing_paths=existing,
            size_bytes=size,
            file_count=file_count,
            dir_count=dir_count,
            risk="warning",
            can_delete=False,
            protected_count=max(0, file_count + dir_count),
            note=note,
            extra={"cleanup_candidate_count": len(candidates)},
        )

    def _shaofu_cleanup_candidates(self) -> list[dict[str, Any]]:
        """
        少府清理候选只用于扫描展示。
        本轮不执行删除，避免绕过少府自身规则。
        """
        try:
            from services.desktop.qin.shaofu.storage_index import StorageIndex

            index = StorageIndex(self.project_root)
            candidates = index.cleanup_candidates()
            return candidates if isinstance(candidates, list) else []
        except Exception:
            return []

    def _temporary_files_summary(self, *, scan_files: bool) -> dict[str, Any]:
        paths = self._temporary_paths()
        existing = [path for path in paths if path.exists() and self._is_inside_project(path)]
        size, file_count, dir_count = self._measure_paths(existing) if scan_files else (0, 0, 0)
        return self._category_payload(
            key="temporary_files",
            paths=paths,
            existing_paths=existing,
            size_bytes=size,
            file_count=file_count,
            dir_count=dir_count,
            risk="safe",
            can_delete=True,
            protected_count=0,
            note="清理普通 temp 与黑冰台测试缓存；不清理正式 yushitai/shaofu。",
        )

    def _empty_category(self, key: str, *, risk: str, can_delete: bool, note: str) -> dict[str, Any]:
        return self._category_payload(
            key=key,
            paths=[],
            existing_paths=[],
            size_bytes=0,
            file_count=0,
            dir_count=0,
            risk=risk,
            can_delete=can_delete,
            protected_count=0,
            note=note,
        )

    def _category_payload(
        self,
        *,
        key: str,
        paths: list[Path],
        existing_paths: list[Path],
        size_bytes: int,
        file_count: int,
        dir_count: int,
        risk: str,
        can_delete: bool,
        protected_count: int,
        note: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "key": key,
            "title": self.CATEGORY_TITLES.get(key, key),
            "count": file_count + dir_count,
            "file_count": file_count,
            "dir_count": dir_count,
            "item_count": file_count + dir_count,
            "size_bytes": size_bytes,
            "total_size_bytes": size_bytes,
            "size_label": self._format_size(size_bytes),
            "total_size_text": self._format_size(size_bytes),
            "paths": [str(path) for path in paths],
            "existing_paths": [str(path) for path in existing_paths],
            "open_path": str(existing_paths[0]) if existing_paths else "",
            "exists": bool(existing_paths),
            "risk": risk,
            "can_delete": bool(can_delete),
            "protected_count": int(protected_count or 0),
            "note": note,
        }
        if extra:
            payload.update(extra)
        return payload

    def _downloads_paths(self) -> list[Path]:
        return [
            self.project_root / "downloads",
            self.project_root / "data" / "downloads",
            self.project_root / "data" / "exports" / "downloads",
        ]

    def _favorites_paths(self) -> list[Path]:
        return [
            self.project_root / "favorites",
            self.project_root / "data" / "favorites",
            self.project_root / "data" / "collections",
        ]

    def _temporary_paths(self) -> list[Path]:
        paths = [
            self.project_root / "temp" / "records",
            self.project_root / "temp" / "replies",
            self.project_root / "temp" / "cache",
            self.project_root / "temp" / "sessions",
            self.project_root / "temp" / "py_compile_check",
            self.project_root / "data" / "runtime" / "temp",
            self.project_root / "data" / "runtime" / "cache",
            self.project_root / "data" / "runtime" / "tmp",
        ]
        paths.extend(self.desktop_runtime_dir.glob("heibingtai_close_test*"))
        paths.extend([
            self.desktop_runtime_dir / "heibingtai_window_probe",
            self.desktop_runtime_dir / "heibingtai_resolver_test",
        ])
        paths.extend(self.desktop_runtime_dir.glob("heibingtai_test*"))
        return [path.resolve(strict=False) for path in paths]

    def _delete_directory_contents(self, paths: list[Path]) -> dict[str, Any]:
        deleted_count = 0
        deleted_size = 0
        failed: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        for root in self._effective_roots(paths):
            if not root.exists() or not root.is_dir() or not self._is_inside_project(root):
                continue
            result = self._clear_directory_contents(root)
            deleted_count += int(result.get("deleted_count", 0) or 0)
            deleted_size += int(result.get("deleted_size_bytes", 0) or 0)
            failed.extend(result.get("failed", []))
            skipped.extend(result.get("skipped", []))
        return {
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "failed": failed,
            "skipped": skipped,
        }

    def _delete_temporary_files(self) -> dict[str, Any]:
        deleted_count = 0
        deleted_size = 0
        failed: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        for path in self._temporary_paths():
            if not path.exists() or not self._is_inside_project(path):
                continue
            if path.is_dir() and path.name.startswith("heibingtai"):
                result = self._delete_tree(path)
            elif path.is_dir():
                result = self._clear_directory_contents(path)
            else:
                result = self._delete_file(path)
            deleted_count += int(result.get("deleted_count", 0) or 0)
            deleted_size += int(result.get("deleted_size_bytes", 0) or 0)
            failed.extend(result.get("failed", []))
            skipped.extend(result.get("skipped", []))
        return {
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "failed": failed,
            "skipped": skipped,
        }

    def _delete_old_yushitai_runs(self) -> dict[str, Any]:
        deleted_count = 0
        deleted_size = 0
        failed: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        for run_dir in self._old_yushitai_run_candidates():
            result = self._delete_tree(run_dir)
            deleted_count += int(result.get("deleted_count", 0) or 0)
            deleted_size += int(result.get("deleted_size_bytes", 0) or 0)
            failed.extend(result.get("failed", []))
            skipped.extend(result.get("skipped", []))
        return {
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "failed": failed,
            "skipped": skipped,
        }

    def _old_yushitai_run_candidates(self) -> list[Path]:
        runs = self._run_records()
        protected_ids = self._protected_run_ids(runs)

        result: list[Path] = []
        for item in runs:
            run_id = str(item.get("run_id", "") or "").strip()
            status = str(item.get("status", "") or "").strip().lower()
            path = item.get("path")

            if run_id in protected_ids:
                continue

            if status not in {"closed", "interrupted", "failed"}:
                continue

            if isinstance(path, Path) and path.exists() and path.is_dir() and self._is_inside_project(path):
                result.append(path)

        return result

    def _protected_run_ids(self, runs: list[dict[str, Any]]) -> set[str]:
        protected: set[str] = set()
        index = self._read_json(self.yushitai_dir / "index.json", {})
        for key in ("active_run_id", "active_host_run_id", "host_active_run_id", "active_vm_run_id", "vm_active_run_id"):
            value = str(index.get(key, "") or "").strip()
            if value:
                protected.add(value)
        for item in runs:
            if item["status"] == "running":
                protected.add(item["run_id"])
        return protected

    def _all_yushitai_run_dirs(self) -> list[Path]:
        result: list[Path] = []
        runs_dir = self.yushitai_dir / "runs"
        for backend in ("host", "vm"):
            backend_dir = runs_dir / backend
            if not backend_dir.exists():
                continue
            result.extend([path for path in backend_dir.iterdir() if path.is_dir()])
        return result

    def _run_records(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for path in self._all_yushitai_run_dirs():
            meta = self._read_json(path / "run_meta.json", {})
            run_id = str(meta.get("run_id", path.name) or path.name)
            status = str(meta.get("status", "") or "").strip().lower()
            timestamp = self._parse_time(
                str(meta.get("ended_at", "") or meta.get("closed_at", "") or meta.get("started_at", "") or "")
            )
            result.append({
                "run_id": run_id,
                "status": status,
                "path": path,
                "timestamp": timestamp,
            })
        return result

    def _measure_paths(self, roots: Iterable[Path]) -> tuple[int, int, int]:
        total_size = 0
        file_count = 0
        dir_count = 0
        for root in self._effective_roots(list(roots)):
            if root.is_file():
                try:
                    total_size += root.stat().st_size
                    file_count += 1
                except Exception:
                    pass
                continue
            for file_path in self._iter_files(root):
                try:
                    total_size += file_path.stat().st_size
                    file_count += 1
                except Exception:
                    pass
            dir_count += self._count_dirs(root)
        return total_size, file_count, dir_count

    def _clear_directory_contents(self, root: Path) -> dict[str, Any]:
        deleted_count = 0
        deleted_size = 0
        failed: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        for file_path in self._iter_files(root):
            if not self._can_delete_file(file_path):
                skipped.append({"path": str(file_path), "reason": "protected_suffix_or_outside_project"})
                continue
            result = self._delete_file(file_path)
            deleted_count += int(result.get("deleted_count", 0) or 0)
            deleted_size += int(result.get("deleted_size_bytes", 0) or 0)
            failed.extend(result.get("failed", []))
        deleted_count += self._remove_empty_children(root, failed)
        return {
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "failed": failed,
            "skipped": skipped,
        }

    def _delete_tree(self, path: Path) -> dict[str, Any]:
        if not path.exists() or not self._is_inside_project(path):
            return {"deleted_count": 0, "deleted_size_bytes": 0, "failed": [], "skipped": []}
        size, file_count, dir_count = self._measure_paths([path])
        try:
            shutil.rmtree(path)
            return {
                "deleted_count": file_count + dir_count + 1,
                "deleted_size_bytes": size,
                "failed": [],
                "skipped": [],
            }
        except Exception as exc:
            return {
                "deleted_count": 0,
                "deleted_size_bytes": 0,
                "failed": [{"path": str(path), "error": str(exc)}],
                "skipped": [],
            }

    def _delete_file(self, path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file() or not self._can_delete_file(path):
            return {"deleted_count": 0, "deleted_size_bytes": 0, "failed": [], "skipped": []}
        try:
            size = path.stat().st_size
            path.unlink()
            return {"deleted_count": 1, "deleted_size_bytes": size, "failed": [], "skipped": []}
        except Exception as exc:
            return {
                "deleted_count": 0,
                "deleted_size_bytes": 0,
                "failed": [{"path": str(path), "error": str(exc)}],
                "skipped": [],
            }

    def _effective_roots(self, paths: list[Path]) -> list[Path]:
        roots: list[Path] = []
        for path in sorted({path.resolve(strict=False) for path in paths}, key=lambda item: len(item.parts)):
            if not path.exists() or not self._is_inside_project(path):
                continue
            if any(self._is_relative_to(path, root) for root in roots):
                continue
            roots.append(path)
        return roots

    def _iter_files(self, root: Path) -> Iterable[Path]:
        try:
            if root.is_file():
                yield root
                return
            yield from (path for path in root.rglob("*") if path.is_file())
        except Exception:
            return

    def _count_dirs(self, root: Path) -> int:
        try:
            return sum(1 for path in root.rglob("*") if path.is_dir()) if root.is_dir() else 0
        except Exception:
            return 0

    def _remove_empty_children(self, root: Path, failed: list[dict[str, str]]) -> int:
        deleted = 0
        try:
            children = [path for path in root.rglob("*") if path.is_dir()]
        except Exception:
            return deleted
        for path in sorted(children, key=lambda item: len(item.parts), reverse=True):
            if path == root or not self._is_inside_project(path):
                continue
            try:
                path.rmdir()
                deleted += 1
            except OSError:
                pass
            except Exception as exc:
                failed.append({"path": str(path), "error": str(exc)})
        return deleted

    def _can_delete_file(self, path: Path) -> bool:
        if not self._is_inside_project(path):
            return False
        if path.suffix.lower() in self.SKIP_SUFFIXES:
            return False
        return True

    def _is_inside_project(self, path: Path) -> bool:
        try:
            path.resolve(strict=False).relative_to(self.project_root)
            return True
        except Exception:
            return False

    def _is_relative_to(self, path: Path, root: Path) -> bool:
        try:
            path.resolve(strict=False).relative_to(root.resolve(strict=False))
            return True
        except Exception:
            return False

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(default)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(default)
        return data if isinstance(data, dict) else dict(default)

    def _parse_time(self, value: str) -> datetime:
        text = str(value or "").strip()
        if not text:
            return datetime.fromtimestamp(0, timezone.utc).astimezone()
        try:
            normalized = text.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone()
        except Exception:
            return datetime.fromtimestamp(0, timezone.utc).astimezone()

    def _format_size(self, size: int) -> str:
        value = float(max(0, int(size)))
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{value:.1f} GB"
