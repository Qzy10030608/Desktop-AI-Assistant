from __future__ import annotations


class MessagePresenter:
    """Central wording for dangerous desktop action receipts."""

    ACTION_LABELS = {
        "app.uninstall": "软件卸载",
        "app.move": "软件迁移",
        "app.relocate": "软件迁移",
        "app.update": "软件更新",
        "file.copy": "文件复制",
        "file.move": "文件移动",
        "file.rename": "文件重命名",
        "file.close": "文件关闭",
        "folder.close": "文件夹关闭",
        "app.close": "软件关闭",
        "file.delete": "文件删除",
    }

    def action_label(self, action: str) -> str:
        normalized_action = str(action or "").strip().lower()
        return self.ACTION_LABELS.get(normalized_action, normalized_action or "-")

    def receipt_outcome(self, *, backend: str, action: str, ok: bool) -> str:
        label = self.action_label(action)
        normalized_backend = str(backend or "").strip().lower()
        if normalized_backend == "sandbox":
            return f"{label}预演，未真实执行（沙盒测试）。"
        if normalized_backend == "vm":
            return f"{label}{'已执行' if ok else '执行失败'}（虚拟机测试）。"
        if normalized_backend == "host":
            return f"{label}未执行（Host 当前阶段禁用）。"
        return f"{label}{'成功' if ok else '失败'}。"

    def confirm_required(self, *, action: str, risk_level: str) -> str:
        normalized_action = str(action or "").strip() or "-"
        normalized_risk = str(risk_level or "").strip() or "unknown"
        return (
            f"Dangerous action requires confirmation before VM execution: "
            f"{normalized_action} ({normalized_risk})."
        )

    def checkpoint_created(self, *, checkpoint_id: str) -> str:
        return f"Action checkpoint created before VM execution: {checkpoint_id}."

    def emergency_stopped(self) -> str:
        return "Desktop execution is blocked by emergency stop."

    def throttled(self) -> str:
        return "Desktop execution is temporarily throttled."

    def circuit_open(self) -> str:
        return "Desktop execution is blocked by an open circuit."
