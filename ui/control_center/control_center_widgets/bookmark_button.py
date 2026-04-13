from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from ui.control_center.config import UI_SIZE  # type: ignore


class BookmarkButton(QPushButton):
    """
    左侧书签式导航按钮
    这里只做一个轻封装，主要目的是统一高度与可选中状态
    """

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(UI_SIZE["btn_height_bookmark"])