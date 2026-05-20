from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.desktop.language.language_service import DesktopLanguageService
from services.desktop.tianting.command_memory_service import CommandMemoryService


class SoftwareAliasDialog(QDialog):
    """Manage user-confirmed software terms without touching execution policy."""

    def __init__(
        self,
        target_label: str,
        target_app_id: str = "",
        canonical_app_id: str = "",
        permission_state: str = "",
        icon_path: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.target_label = str(target_label or "").strip()
        self.target_app_id = str(target_app_id or "").strip()
        self.canonical_app_id = str(canonical_app_id or "").strip()
        self.permission_state = str(permission_state or "").strip()
        self.icon_path = str(icon_path or "").strip()
        self.memory_service = CommandMemoryService()
        self.language_service = DesktopLanguageService()
        self.language_profile = self.language_service.load_profile("zh-CN")

        self.setWindowTitle(self._text("desktop.software.alias.dialog.title"))
        self.setMinimumWidth(560)
        self.setMinimumHeight(420)
        self.setStyleSheet(self._style_sheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        root.addLayout(self._build_header())
        root.addWidget(self._build_info_panel())

        terms_title = QLabel(self._text("desktop.software.alias.current_terms"))
        terms_title.setObjectName("sectionTitle")
        root.addWidget(terms_title)

        self.terms_list = QListWidget()
        self.terms_list.setObjectName("aliasList")
        self.terms_list.itemSelectionChanged.connect(self._refresh_delete_state)
        root.addWidget(self.terms_list, 1)

        input_row = QHBoxLayout()
        self.term_input = QLineEdit()
        self.term_input.setPlaceholderText(self._text("desktop.software.alias.add_placeholder"))
        self.term_input.returnPressed.connect(self._add_alias)
        input_row.addWidget(self.term_input, 1)

        self.add_button = QPushButton(self._text("desktop.software.alias.add"))
        self.add_button.clicked.connect(self._add_alias)
        input_row.addWidget(self.add_button)
        root.addLayout(input_row)

        button_row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        button_row.addWidget(self.status_label, 1)

        self.delete_button = QPushButton(self._text("desktop.software.alias.delete_selected"))
        self.delete_button.clicked.connect(self._delete_selected_alias)
        button_row.addWidget(self.delete_button)

        self.close_button = QPushButton(self._text("desktop.software.alias.close"))
        self.close_button.clicked.connect(self.accept)
        button_row.addWidget(self.close_button)
        root.addLayout(button_row)

        self._reload_terms()

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        icon_label.setObjectName("iconBox")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = self._load_icon_pixmap()
        if pixmap is not None:
            icon_label.setPixmap(
                pixmap.scaled(
                    38,
                    38,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        row.addWidget(icon_label)

        title_col = QVBoxLayout()
        title = QLabel(self.target_label or "-")
        title.setObjectName("dialogTitle")
        title.setWordWrap(True)
        title_col.addWidget(title)

        subtitle = QLabel(self._text("desktop.software.alias.dialog.title"))
        subtitle.setObjectName("dialogSubtitle")
        title_col.addWidget(subtitle)
        row.addLayout(title_col, 1)
        return row

    def _build_info_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("infoPanel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        rows = [
            (self._text("desktop.software.alias.official_name"), self.target_label or "-"),
            (self._text("desktop.software.alias.app_id"), self.target_app_id or "-"),
            (self._text("desktop.software.alias.canonical_app_id"), self.canonical_app_id or "-"),
            (self._text("desktop.software.alias.permission_state"), self.permission_state or "-"),
        ]
        for index, (label, value) in enumerate(rows):
            key_label = QLabel(label)
            key_label.setObjectName("infoKey")
            value_label = QLabel(value)
            value_label.setObjectName("infoValue")
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_label.setWordWrap(True)
            layout.addWidget(key_label, index, 0)
            layout.addWidget(value_label, index, 1)
        return panel

    def _reload_terms(self) -> None:
        self.terms_list.clear()
        result = self.memory_service.list_terms_for_target(
            memory_domain="software_terms",
            target_label=self.target_label,
            target_app_id=self.target_app_id,
        )
        terms = result.get("terms", []) if isinstance(result, dict) else []
        if not isinstance(terms, list):
            terms = []

        for row in terms:
            if not isinstance(row, dict):
                continue
            term = str(row.get("term", "") or "").strip()
            source = str(row.get("source", "") or "").strip() or "local"
            enabled = bool(row.get("enabled", True))
            aliases = row.get("aliases", [])
            alias_text = ", ".join(str(item) for item in aliases if str(item or "").strip()) if isinstance(aliases, list) else ""
            label = f"{term}  [{source}]"
            if alias_text:
                label = f"{label}  {alias_text}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, {"term": term, "source": source, "enabled": enabled})
            if source != "local":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setToolTip(self._text("desktop.software.alias.seed_read_only"))
            self.terms_list.addItem(item)

        self._refresh_delete_state()

    def _refresh_delete_state(self) -> None:
        row = self._selected_alias_row()
        self.delete_button.setEnabled(bool(row and row.get("source") == "local"))

    def _add_alias(self) -> None:
        term = self.term_input.text().strip()
        if not term:
            self._show_info(self._text("desktop.software.alias.empty_input"))
            return
        if _normalize_alias_text(term) == _normalize_alias_text(self.target_label):
            self._show_info(self._text("desktop.software.alias.same_as_title"))
            return

        lookup = self.memory_service.lookup_term(memory_domain="software_terms", term=term)
        if bool(lookup.get("found")):
            existing_label = str(lookup.get("target_label", "") or lookup.get("target_label_hint", "") or "")
            if _normalize_alias_text(existing_label) == _normalize_alias_text(self.target_label):
                self._show_info(self._text("desktop.software.alias.exists_same_target", term=term))
                return
            answer = QMessageBox.question(
                self,
                self._text("desktop.software.alias.confirm_rebind.title"),
                self._text(
                    "desktop.software.alias.confirm_rebind.body",
                    term=term,
                    existing_target=existing_label,
                    target=self.target_label,
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            result = self.memory_service.promote_confirmed_term(
                memory_domain="software_terms",
                term=term,
                target_label=self.target_label,
                target_app_id=self.target_app_id,
                canonical_app_id=self.canonical_app_id,
                overwrite=True,
            )
        else:
            result = self.memory_service.promote_confirmed_term(
                memory_domain="software_terms",
                term=term,
                target_label=self.target_label,
                target_app_id=self.target_app_id,
                canonical_app_id=self.canonical_app_id,
            )

        if bool(result.get("ok")) and bool(result.get("promoted")):
            self.term_input.clear()
            self._reload_terms()
            self._show_info(self._text("desktop.software.alias.added", term=term))
            return

        reason = str(result.get("reason", "") or "")
        if reason == "already_exists_same_target":
            self._show_info(self._text("desktop.software.alias.exists_same_target", term=term))
        elif reason == "term_bound_to_other_target":
            self._show_info(
                self._text(
                    "desktop.software.alias.exists_other_target",
                    term=term,
                    existing_target=str(result.get("existing_target_label", "") or ""),
                )
            )
        elif reason == "same_as_target_label":
            self._show_info(self._text("desktop.software.alias.same_as_title"))
        else:
            self._show_info(self._text("desktop.software.alias.operation_failed", reason=reason))

    def _delete_selected_alias(self) -> None:
        row = self._selected_alias_row()
        if not row:
            return
        if row.get("source") != "local":
            self._show_info(self._text("desktop.software.alias.seed_read_only"))
            return

        term = str(row.get("term", "") or "").strip()
        if not term:
            return
        answer = QMessageBox.question(
            self,
            self._text("desktop.software.alias.delete_confirm.title"),
            self._text("desktop.software.alias.delete_confirm.body", term=term),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        result = self.memory_service.remove_confirmed_term(
            memory_domain="software_terms",
            term=term,
            target_label=self.target_label,
        )
        if bool(result.get("ok")) and bool(result.get("removed")):
            self._reload_terms()
            self._show_info(self._text("desktop.software.alias.deleted", term=term))
            return
        self._show_info(self._text("desktop.software.alias.operation_failed", reason=str(result.get("reason", "") or "")))

    def _selected_alias_row(self) -> dict[str, Any]:
        item = self.terms_list.currentItem()
        if item is None:
            return {}
        data = item.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, dict) else {}

    def _load_icon_pixmap(self) -> QPixmap | None:
        if not self.icon_path:
            return None
        try:
            path = Path(self.icon_path)
            if not path.exists():
                return None
            pixmap = QPixmap(str(path))
            return pixmap if not pixmap.isNull() else None
        except Exception:
            return None

    def _show_info(self, text: str) -> None:
        self.status_label.setText(text)

    def _text(self, key: str, **params: Any) -> str:
        clean_key = str(key or "").strip()
        ui_catalog = self.language_profile.get("ui", {}) if isinstance(self.language_profile.get("ui"), dict) else {}
        reply_catalog = self.language_profile.get("reply", {}) if isinstance(self.language_profile.get("reply"), dict) else {}
        template = str(ui_catalog.get(clean_key, reply_catalog.get(clean_key, clean_key)) or clean_key)
        safe_params = {name: str(value if value is not None else "") for name, value in params.items()}
        try:
            return template.format(**safe_params)
        except Exception:
            return template

    def _style_sheet(self) -> str:
        return """
        QDialog {
            background: #111827;
            color: #e5e7eb;
        }
        QLabel {
            color: #e5e7eb;
        }
        QLabel#dialogTitle {
            font-size: 18px;
            font-weight: 700;
            color: #f9fafb;
        }
        QLabel#dialogSubtitle,
        QLabel#sectionTitle,
        QLabel#infoKey {
            color: #9ca3af;
        }
        QLabel#statusLabel {
            color: #6ee7b7;
        }
        QLabel#iconBox,
        QFrame#infoPanel {
            border: 1px solid #1f9f8b;
            border-radius: 8px;
            background: rgba(15, 118, 110, 0.16);
        }
        QListWidget,
        QLineEdit {
            background: #0b1220;
            border: 1px solid #254458;
            border-radius: 6px;
            color: #f9fafb;
            padding: 7px;
            selection-background-color: #0f766e;
        }
        QPushButton {
            background: #0f766e;
            border: 1px solid #2dd4bf;
            border-radius: 6px;
            color: #ecfeff;
            padding: 7px 12px;
            font-weight: 600;
        }
        QPushButton:hover {
            background: #0d9488;
        }
        QPushButton:disabled {
            background: #374151;
            border-color: #4b5563;
            color: #9ca3af;
        }
        """


def _normalize_alias_text(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return "".join(char for char in text if char.isalnum() or "\u4e00" <= char <= "\u9fff")
