import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QRadioButton, QButtonGroup
)


class DownloadDialog(QDialog):
    """
    下载设置对话框
    功能：
    1. 默认使用项目 downloads 目录
    2. 可切换为自定义目录
    3. 可修改文件名
    4. 黑色主题显示
    """

    def __init__(self, default_folder: str, default_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("下载语音")
        self.resize(560, 250)

        self.default_folder = default_folder

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(14, 14, 14, 14)

        # 文件名
        root.addWidget(QLabel("文件名："))
        self.name_edit = QLineEdit(default_filename)
        root.addWidget(self.name_edit)

        # 路径模式
        self.use_default_radio = QRadioButton("使用默认下载位置")
        self.use_custom_radio = QRadioButton("使用当前选择路径")
        self.use_default_radio.setChecked(True)

        self.path_group = QButtonGroup(self)
        self.path_group.addButton(self.use_default_radio)
        self.path_group.addButton(self.use_custom_radio)

        root.addWidget(self.use_default_radio)
        root.addWidget(self.use_custom_radio)

        # 路径输入
        root.addWidget(QLabel("下载路径："))
        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        self.path_edit = QLineEdit(default_folder)
        self.path_edit.setEnabled(False)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setEnabled(False)

        path_row.addWidget(self.path_edit)
        path_row.addWidget(self.browse_btn)
        root.addLayout(path_row)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.ok_btn = QPushButton("确认下载")
        self.cancel_btn = QPushButton("取消")

        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

        self.use_default_radio.toggled.connect(self._on_mode_changed)
        self.browse_btn.clicked.connect(self._choose_folder)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("""
        QDialog {
            background-color: #111111;
            color: white;
        }
        QLabel {
            color: white;
            font-size: 14px;
        }
        QLineEdit {
            background-color: #1E1E1E;
            color: white;
            border: 1px solid #444444;
            border-radius: 8px;
            padding: 8px;
            min-height: 20px;
        }
        QLineEdit:disabled {
            background-color: #151515;
            color: #888888;
            border: 1px solid #2A2A2A;
        }
        QPushButton {
            background-color: #2563EB;
            color: white;
            border: none;
            border-radius: 10px;
            padding: 8px 14px;
            min-height: 34px;
        }
        QPushButton:hover {
            background-color: #3B82F6;
        }
        QPushButton:pressed {
            background-color: #1D4ED8;
        }
        QPushButton:disabled {
            background-color: #374151;
            color: #A0AEC0;
        }

        /* 单选按钮文字 */
        QRadioButton {
            color: white;
            font-size: 14px;
            spacing: 8px;
        }

        /* 默认白圈 */
        QRadioButton::indicator {
            width: 16px;
            height: 16px;
            border-radius: 8px;
            border: 2px solid white;
            background: transparent;
        }

        /* 选中后红色 */
        QRadioButton::indicator:checked {
            background-color: #DC2626;
            border: 2px solid #FFFFFF;
        }
        """)

    def _on_mode_changed(self):
        use_default = self.use_default_radio.isChecked()
        self.path_edit.setEnabled(not use_default)
        self.browse_btn.setEnabled(not use_default)
        if use_default:
            self.path_edit.setText(self.default_folder)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            self.path_edit.text().strip() or self.default_folder
        )
        if folder:
            self.path_edit.setText(folder)

    def get_download_result(self):
        folder = self.default_folder if self.use_default_radio.isChecked() else self.path_edit.text().strip()
        filename = self.name_edit.text().strip()

        if not folder:
            folder = self.default_folder

        if not filename:
            filename = "ai_reply.mp3"

        return {
            "folder": folder,
            "filename": filename,
        }