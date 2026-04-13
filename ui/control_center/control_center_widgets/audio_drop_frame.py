from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QFileDialog,
)


class AudioDropFrame(QFrame):
    """
    整块可拖拽音频文件的区域：
    - 可拖入 wav/mp3/flac
    - 可点击“选择文件”按钮
    - 中间显示当前状态
    """
    file_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("audioDropFrame")
        self._file_path = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        self.header_label = QLabel("请上传并填写参考信息")
        self.header_label.setObjectName("audioDropHeader")
        layout.addWidget(self.header_label)

        self.tip_badge = QLabel("♪ 请上传3~10秒内参考音频，超过会报错！")
        self.tip_badge.setObjectName("audioDropTip")
        layout.addWidget(self.tip_badge, alignment=Qt.AlignmentFlag.AlignLeft)

        self.drop_area = QFrame()
        self.drop_area.setObjectName("audioDropInner")

        inner_layout = QVBoxLayout(self.drop_area)
        inner_layout.setContentsMargins(20, 20, 20, 20)
        inner_layout.setSpacing(10)

        self.icon_label = QLabel("⇪")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setObjectName("audioDropIcon")

        self.main_label = QLabel("拖放音讯至此处")
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_label.setObjectName("audioDropMain")

        self.sub_label = QLabel("- 或 -\n點擊上傳")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setObjectName("audioDropSub")

        self.path_label = QLabel("当前文件：未选择")
        self.path_label.setWordWrap(True)
        self.path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.path_label.setObjectName("audioDropPath")

        self.select_btn = QPushButton("选择文件")
        self.select_btn.clicked.connect(self.choose_file)

        inner_layout.addStretch()
        inner_layout.addWidget(self.icon_label)
        inner_layout.addWidget(self.main_label)
        inner_layout.addWidget(self.sub_label)
        inner_layout.addWidget(self.path_label)
        inner_layout.addWidget(self.select_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        inner_layout.addStretch()

        layout.addWidget(self.drop_area)

    def apply_button_size(self, width: int, height: int):
        self.select_btn.setFixedWidth(width)
        self.select_btn.setFixedHeight(height)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.choose_file()
        super().mousePressEvent(event)

    def choose_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择参考音频",
            "",
            "Audio Files (*.wav *.mp3 *.flac)"
        )
        if file_path:
            self.set_file(file_path)

    def set_file(self, file_path: str):
        self._file_path = file_path
        self.path_label.setText(f"当前文件：{Path(file_path).name}")
        self.file_changed.emit(file_path)

    def get_file(self) -> str:
        return self._file_path

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile().lower()
                if path.endswith((".wav", ".mp3", ".flac")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.set_file(file_path)
            event.acceptProposedAction()