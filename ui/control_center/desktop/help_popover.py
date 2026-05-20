from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class HelpPopover(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("desktopHelpPopover")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.title_label = QLabel("")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("color: #E8F0FF; font-weight: 700;")
        layout.addWidget(self.title_label)

        self.body_label = QLabel("")
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body_label.setStyleSheet("color: #CFE0FA; line-height: 1.35;")
        layout.addWidget(self.body_label)

        self.setFixedWidth(420)
        self.setStyleSheet(
            "QFrame#desktopHelpPopover {"
            "background-color: rgba(12, 20, 32, 0.98);"
            "border: 1px solid rgba(56, 189, 248, 0.72);"
            "border-radius: 8px;"
            "}"
        )

    def set_content(self, title: str, body: str) -> None:
        self.title_label.setText(str(title or "说明"))
        self.body_label.setText(str(body or ""))
        self.adjustSize()

    def show_near(self, widget: QWidget) -> None:
        if widget is None:
            return
        self.adjustSize()
        pos = widget.mapToGlobal(QPoint(0, widget.height() + 8))
        screen = widget.screen()
        if screen is not None:
            available = screen.availableGeometry()
            if pos.x() + self.width() > available.right():
                pos.setX(max(available.left(), available.right() - self.width()))
            if pos.y() + self.height() > available.bottom():
                pos = widget.mapToGlobal(QPoint(0, -self.height() - 8))
                if pos.y() < available.top():
                    pos.setY(max(available.top(), available.bottom() - self.height()))
        self.move(pos)
        self.show()
        self.raise_()

    def hide_popup(self) -> None:
        self.hide()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.hide_popup()
            return
        super().keyPressEvent(event)


class HoverHelpButton(QPushButton):
    def __init__(self, text: str = "说明", parent: QWidget | None = None, *, hover_delay_ms: int = 1000) -> None:
        super().__init__(text, parent)
        self.setToolTip("说明：悬停查看规则")
        self.setFixedHeight(22)
        self.setMinimumWidth(44)
        self.setMaximumWidth(56)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton {"
            "background: rgba(15, 23, 42, 0.18);"
            "border: 1px solid rgba(148, 163, 184, 0.48);"
            "border-radius: 6px;"
            "color: #CFE0FA;"
            "font-size: 11px;"
            "padding: 1px 6px;"
            "}"
            "QPushButton:hover {"
            "background: rgba(56, 189, 248, 0.12);"
            "border-color: rgba(56, 189, 248, 0.68);"
            "}"
        )
        self._help_title = "说明"
        self._help_body = ""
        self._popover = HelpPopover(self.window())
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(max(200, int(hover_delay_ms)))
        self._hover_timer.timeout.connect(self._show_now)
        self.clicked.connect(self._show_now)
        self.installEventFilter(self)

    def set_help_content(self, title: str, body: str) -> None:
        self._help_title = str(title or "说明")
        self._help_body = str(body or "")
        self._popover.set_content(self._help_title, self._help_body)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hover_timer.stop()
        self._popover.hide_popup()
        super().leaveEvent(event)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if watched is self and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self._popover.hide_popup()
                return True
        return super().eventFilter(watched, event)

    def _show_now(self) -> None:
        self._hover_timer.stop()
        self._popover.set_content(self._help_title, self._help_body)
        self._popover.show_near(self)
