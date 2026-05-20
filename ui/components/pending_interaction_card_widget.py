from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.main_window_config import MAIN_WINDOW_SIZE, build_pending_interaction_card_qss  # type: ignore


KNOWN_PENDING_ACTIONS = {
    "confirm",
    "cancel",
    "deep_search",
    "refresh_software",
    "manual_select",
    "select_candidate",
}


class PendingInteractionCardWidget(QWidget):
    action_requested = Signal(dict)

    def __init__(self, ui_prompt: dict[str, Any], parent=None):
        super().__init__(parent)
        self.ui_prompt = ui_prompt if isinstance(ui_prompt, dict) else {}
        self.pending_task_id = str(self.ui_prompt.get("pending_task_id", "") or "")
        self.prompt_type = str(self.ui_prompt.get("prompt_type", "") or "confirmation_card")
        self._buttons: list[QPushButton] = []
        self._candidate_frames: list[QFrame] = []

        self.setObjectName("pendingInteractionCardRoot")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("pendingInteractionCard")
        root.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(
            MAIN_WINDOW_SIZE["chat_pending_padding_h"],
            MAIN_WINDOW_SIZE["chat_pending_padding_v"],
            MAIN_WINDOW_SIZE["chat_pending_padding_h"],
            MAIN_WINDOW_SIZE["chat_pending_padding_v"],
        )
        layout.setSpacing(MAIN_WINDOW_SIZE["chat_pending_spacing"])

        self.title_label = QLabel(self._title_text())
        self.title_label.setObjectName("pendingTitle")
        layout.addWidget(self.title_label)

        self.text_label = QLabel(str(self.ui_prompt.get("display_text", "") or ""))
        self.text_label.setObjectName("pendingText")
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.text_label)

        self.candidate_box = QVBoxLayout()
        self.candidate_box.setContentsMargins(0, 0, 0, 0)
        self.candidate_box.setSpacing(MAIN_WINDOW_SIZE["chat_message_spacing"])
        layout.addLayout(self.candidate_box)
        self._build_candidates()

        self.action_row = QHBoxLayout()
        self.action_row.setContentsMargins(0, 2, 0, 0)
        self.action_row.setSpacing(MAIN_WINDOW_SIZE["chat_action_spacing"])
        self.action_row.addStretch()
        layout.addLayout(self.action_row)
        self._build_actions()

        self.status_label = QLabel("")
        self.status_label.setObjectName("pendingStatus")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        self._apply_style()

    def mark_resolved(self, text: str = "") -> None:
        self._disable_buttons()
        self.status_label.setText(str(text or "Resolved."))
        self.status_label.show()
        self.card.setProperty("state", "resolved")
        self.card.style().unpolish(self.card)
        self.card.style().polish(self.card)

    def mark_cancelled(self, text: str = "") -> None:
        self._disable_buttons()
        self.status_label.setText(str(text or "Cancelled."))
        self.status_label.show()
        self.card.setProperty("state", "cancelled")
        self.card.style().unpolish(self.card)
        self.card.style().polish(self.card)

    def collapse(self) -> None:
        for frame in self._candidate_frames:
            frame.hide()
        for button in self._buttons:
            button.hide()
        self.status_label.show()

    def _build_actions(self) -> None:
        actions = self.ui_prompt.get("actions", [])
        if not isinstance(actions, list):
            actions = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_name = str(action.get("action", "") or "").strip()
            if not action_name:
                continue
            label = self._action_label(action)
            button = QPushButton(label)
            button.setObjectName("pendingActionButton")
            button.clicked.connect(lambda _checked=False, item=action: self._emit_action(item))
            self._buttons.append(button)
            self.action_row.addWidget(button)

    def _build_candidates(self) -> None:
        candidates = self.ui_prompt.get("candidates", [])
        if not isinstance(candidates, list):
            return
        for index, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, dict):
                continue
            frame = QFrame()
            frame.setObjectName("pendingCandidateRow")
            frame_layout = QHBoxLayout(frame)
            frame_layout.setContentsMargins(
                MAIN_WINDOW_SIZE["chat_pending_candidate_padding_h"],
                MAIN_WINDOW_SIZE["chat_pending_candidate_padding_v"],
                MAIN_WINDOW_SIZE["chat_pending_candidate_padding_h"],
                MAIN_WINDOW_SIZE["chat_pending_candidate_padding_v"],
            )
            frame_layout.setSpacing(MAIN_WINDOW_SIZE["chat_pending_spacing"])

            display_index = self._int(candidate.get("display_index"), index)
            label = str(candidate.get("label", "") or "-")
            subtitle = str(candidate.get("subtitle", "") or "")

            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(MAIN_WINDOW_SIZE["spacing_small"] if "spacing_small" in MAIN_WINDOW_SIZE else 4)

            label_widget = QLabel(f"{display_index}. {label}")
            label_widget.setObjectName("pendingCandidateLabel")
            label_widget.setWordWrap(True)
            text_box.addWidget(label_widget)

            if subtitle:
                subtitle_widget = QLabel(subtitle)
                subtitle_widget.setObjectName("pendingCandidateSubtitle")
                subtitle_widget.setWordWrap(True)
                text_box.addWidget(subtitle_widget)

            frame_layout.addLayout(text_box, 1)

            select_button = QPushButton(str(candidate.get("action_label", "") or "Select"))
            select_button.setObjectName("pendingCandidateButton")
            select_button.clicked.connect(
                lambda _checked=False, item=candidate: self._emit_candidate(item)
            )
            self._buttons.append(select_button)
            frame_layout.addWidget(select_button, 0)

            self._candidate_frames.append(frame)
            self.candidate_box.addWidget(frame)

    def _emit_action(self, action: dict[str, Any]) -> None:
        action_name = str(action.get("action", "") or "").strip()
        if not action_name:
            return
        self._disable_buttons()
        event = {
            "source": "pending_interaction_card",
            "pending_task_id": self.pending_task_id,
            "action": action_name,
        }
        payload = action.get("payload", {})
        if isinstance(payload, dict):
            event.update(payload)
        event["source"] = "pending_interaction_card"
        event["action"] = action_name
        event["pending_task_id"] = str(event.get("pending_task_id", "") or self.pending_task_id)
        self.action_requested.emit(event)

    def _emit_candidate(self, candidate: dict[str, Any]) -> None:
        self._disable_buttons()
        display_index = self._int(candidate.get("display_index"), 0)
        self.action_requested.emit(
            {
                "source": "pending_interaction_card",
                "pending_task_id": self.pending_task_id,
                "action": "select_candidate",
                "candidate_id": str(candidate.get("candidate_id", "") or ""),
                "display_index": display_index,
            }
        )

    def _disable_buttons(self) -> None:
        for button in self._buttons:
            button.setEnabled(False)

    def _title_text(self) -> str:
        if self.prompt_type == "deep_search_card":
            return "Deep search"
        if self.prompt_type == "candidate_card":
            return "Candidate selection"
        if self.prompt_type == "confirmation_card":
            return "Target confirmation"
        return "Pending confirmation"

    def _action_label(self, action: dict[str, Any]) -> str:
        label = str(action.get("label", "") or "").strip()
        if label:
            return label
        label_key = str(action.get("label_key", "") or "").strip()
        if label_key:
            return label_key
        return str(action.get("action", "") or "action").strip()

    @staticmethod
    def _int(value: Any, fallback: int) -> int:
        try:
            return int(value)
        except Exception:
            return fallback

    def _apply_style(self) -> None:
        self.setStyleSheet(build_pending_interaction_card_qss())
