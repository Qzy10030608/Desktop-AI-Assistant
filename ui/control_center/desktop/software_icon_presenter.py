from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFileIconProvider, QLabel


class SoftwareIconPresenter:
    def __init__(self, page_loader) -> None:
        self.page_loader = page_loader
        self.icon_provider = QFileIconProvider()

    def _fallback_label(self, row: dict, tooltip: str, font_size_key: str) -> QLabel:
        label = QLabel(str(row.get("icon_text", "APP")))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setToolTip(tooltip)
        self.page_loader._apply_widget_font(label, font_size_key)
        icon_kind = str(row.get("icon_kind", "missing") or "").strip().lower()
        palette = {
            "steam_platform": ("#E6F4FF", "rgba(24, 63, 112, 0.88)", "rgba(110, 180, 255, 0.38)"),
            "epic_platform": ("#F5F5F5", "rgba(24, 24, 27, 0.92)", "rgba(180, 180, 180, 0.32)"),
            "battlenet_platform": ("#E0F2FE", "rgba(13, 59, 102, 0.90)", "rgba(56, 189, 248, 0.30)"),
            "ea_platform": ("#FFF7ED", "rgba(124, 45, 18, 0.88)", "rgba(251, 146, 60, 0.28)"),
        }
        text_color, background_color, border_color = palette.get(
            icon_kind,
            ("#B8C7E0", "rgba(17, 26, 40, 0.72)", "rgba(110, 138, 180, 0.20)"),
        )
        label.setStyleSheet(
            "QLabel {"
            f"color: {text_color};"
            f"background-color: {background_color};"
            f"border: 1px solid {border_color};"
            "border-radius: 6px;"
            "padding: 4px 6px;"
            "font-weight: 700;"
            "}"
        )
        return label

    def _pixmap_from_local_object(self, source_path: str):
        if not source_path:
            return None
        path = Path(source_path)
        if not path.exists():
            return None

        file_info = QFileInfo(str(path))
        icon = self.icon_provider.icon(file_info)
        if icon.isNull():
            return None

        icon_size = self.page_loader._size_int("software_icon_size")
        pixmap = icon.pixmap(icon_size, icon_size)
        return None if pixmap.isNull() else pixmap

    def _pixmap_from_generic_icon(self, source_path: str):
        if not source_path:
            return None
        icon = QIcon(source_path)
        if icon.isNull():
            return None
        icon_size = self.page_loader._size_int("software_icon_size")
        pixmap = icon.pixmap(icon_size, icon_size)
        return None if pixmap.isNull() else pixmap

    def build_icon_widget(self, row: dict, tooltip: str, font_size_key: str):
        label = self._fallback_label(row, tooltip, font_size_key)

        icon_source_path = str(row.get("icon_source_path", "") or "").strip()
        icon_kind = str(row.get("icon_kind", "") or "").strip().lower()

        lower = icon_source_path.lower()
        is_protocol_path = lower.startswith(
            (
                "steam://",
                "epic://",
                "battlenet://",
                "origin://",
                "ea://",
                "http://",
                "https://",
            )
        )

        pixmap = None

        # 关键修改：
        # 只要 icon_source_path 是本地文件，就允许渲染。
        # 不再因为 launch_target_kind == protocol 就阻止 Steam 游戏图标。
        if icon_source_path and not is_protocol_path:
            path = Path(icon_source_path)
            suffix = path.suffix.lower()

            # .ico / .png / .jpg 这类图标文件，优先按真实图标文件读取
            if suffix in {".ico", ".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
                pixmap = self._pixmap_from_generic_icon(icon_source_path)

            # exe / lnk / 文件夹 / 普通文件，走 Windows 文件图标
            if pixmap is None:
                pixmap = self._pixmap_from_local_object(icon_source_path)

            # 最后再兜底 QIcon
            if pixmap is None:
                pixmap = self._pixmap_from_generic_icon(icon_source_path)

        if pixmap is not None:
            label.setPixmap(pixmap)
            label.setText("")
            label.setStyleSheet("border: none; background: transparent;")

        return label
