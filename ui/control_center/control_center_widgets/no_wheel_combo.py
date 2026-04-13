from PySide6.QtWidgets import QComboBox


class NoWheelComboBox(QComboBox):
    """
    禁止鼠标滚轮直接修改下拉框选项
    滚轮只用于页面滚动
    """

    def wheelEvent(self, event):
        event.ignore()