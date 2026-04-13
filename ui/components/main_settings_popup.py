from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame
)

from ui.main_window_config import MAIN_WINDOW_SIZE, build_main_settings_popup_qss  


class MainSettingsPopup(QWidget):
    """
    设置弹窗
    - Qt.Popup：点击外部自动关闭
    - 放控制中心 / 输出模式 / 打开文件夹 / 重启项目
    """

    control_center_requested = Signal()
    output_mode_selected = Signal(str)
    folder_menu_requested = Signal(QPoint)
    restart_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("mainSettingsPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._mode_buttons = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("popupTitle")
        root.addWidget(title)

        line = QFrame()
        line.setObjectName("popupLine")
        line.setFixedHeight(1)
        root.addWidget(line)

        action_label = QLabel("快捷入口")
        action_label.setObjectName("sectionLabel")
        root.addWidget(action_label)

        self.control_center_btn = QPushButton("打开控制中心")
        self.control_center_btn.setObjectName("popupActionButton")
        self.control_center_btn.clicked.connect(self._on_control_center_clicked)
        root.addWidget(self.control_center_btn)

        self.folder_btn = QPushButton("打开文件夹")
        self.folder_btn.setObjectName("popupActionButton")
        self.folder_btn.clicked.connect(self._on_folder_clicked)
        root.addWidget(self.folder_btn)

        self.restart_btn = QPushButton("重启项目")
        self.restart_btn.setObjectName("popupActionButton")
        self.restart_btn.clicked.connect(self._on_restart_clicked)
        root.addWidget(self.restart_btn)

        mode_label = QLabel("输出模式")
        mode_label.setObjectName("sectionLabel")
        root.addWidget(mode_label)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)

        self._mode_buttons["text_only"] = self._build_mode_btn("仅文字", "text_only")
        self._mode_buttons["text_voice"] = self._build_mode_btn("文字+语音", "text_voice")
        self._mode_buttons["voice_only"] = self._build_mode_btn("仅语音", "voice_only")

        mode_row.addWidget(self._mode_buttons["text_only"])
        mode_row.addWidget(self._mode_buttons["text_voice"])
        mode_row.addWidget(self._mode_buttons["voice_only"])
        root.addLayout(mode_row)

        self.setStyleSheet(build_main_settings_popup_qss())
    def _build_mode_btn(self, text: str, mode: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("modeChipButton")
        btn.setProperty("active", False)
        btn.clicked.connect(lambda: self.output_mode_selected.emit(mode))
        return btn

    def set_current_mode(self, mode: str):
        for key, btn in self._mode_buttons.items():
            btn.setProperty("active", key == mode)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def _on_control_center_clicked(self):
        self.control_center_requested.emit()
        self.hide()

    def _on_folder_clicked(self):
        self.folder_menu_requested.emit(
            self.folder_btn.mapToGlobal(self.folder_btn.rect().bottomLeft())
        )

    def _on_restart_clicked(self):
        self.restart_requested.emit()
        self.hide()

    def show_at(self, global_pos):
        self.adjustSize()
        self.move(global_pos)
        self.show()
        self.raise_()