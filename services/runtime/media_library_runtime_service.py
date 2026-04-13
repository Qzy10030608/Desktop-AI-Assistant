from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QDialog

from config import DOWNLOADS_FOLDER, FAVORITES_FOLDER, RECORD_FOLDER, REPLY_FOLDER, CACHE_FOLDER  # type: ignore
from ui.download_dialog import DownloadDialog  # type: ignore


class MediaLibraryRuntimeService:
    """
    媒体资源运行时服务
    -------------------------
    负责：
    - 下载 AI 回复语音
    - 收藏 AI 回复语音
    - 播放 AI 回复语音
    - 打开项目相关文件夹
    """

    def __init__(self, controller: Any):
        self.c = controller

    def handle_download_audio_for_path(self, audio_path: str):
        if not audio_path or not os.path.exists(audio_path):
            self.c.window.set_status("当前语音文件不存在，无法下载")
            QMessageBox.warning(self.c.window, "提示", "当前语音文件不存在，无法下载。")
            return

        default_name = self.c.download_service.build_default_filename(audio_path)

        dialog = DownloadDialog(
            default_folder=DOWNLOADS_FOLDER,
            default_filename=default_name,
            parent=self.c.window,
        )

        result_code = dialog.exec()
        if result_code != QDialog.DialogCode.Accepted:
            self.c.window.set_status("已取消下载")
            return

        try:
            result = dialog.get_download_result()
            folder = result.get("folder", "").strip()
            filename = result.get("filename", "").strip()

            if not folder:
                folder = DOWNLOADS_FOLDER

            if not filename:
                filename = default_name

            saved_path = self.c.download_service.export_audio(
                source_path=audio_path,
                target_folder=folder,
                target_name=filename,
            )

            self.c.window.set_status(f"语音已导出：{os.path.basename(saved_path)}")
        except Exception as e:
            self.c.window.set_status(f"下载失败：{str(e)}")
            QMessageBox.warning(self.c.window, "提示", f"下载失败：\n{str(e)}")

    def handle_play_ai_audio_for_path(self, audio_path: str):
        if not audio_path or not os.path.exists(audio_path):
            self.c.window.set_status("当前语音文件不存在")
            return

        self.c.ai_player.stop()
        self.c.ai_player.setSource(QUrl.fromLocalFile(audio_path))
        self.c.ai_player.setPlaybackRate(self.c.current_speech_rate)
        self.c.ai_player.play()
        self.c.window.set_status("正在播放 AI 语音")

    def handle_favorite_audio_for_path(self, audio_path: str):
        if not audio_path or not os.path.exists(audio_path):
            self.c.window.set_status("当前语音文件不存在，无法收藏")
            QMessageBox.warning(self.c.window, "提示", "当前语音文件不存在，无法收藏。")
            return

        try:
            is_favorite_now, target_path = self.c.favorite_service.toggle_audio_favorite(audio_path)

            if is_favorite_now:
                self.c.window.set_status(f"语音已收藏：{os.path.basename(target_path)}")
            else:
                self.c.window.set_status("已取消收藏并删除对应文件")

        except Exception as e:
            self.c.window.set_status(f"收藏操作失败：{str(e)}")
            QMessageBox.warning(self.c.window, "提示", f"收藏操作失败：\n{str(e)}")

    def handle_open_folder(self, folder_type: str):
        folder_map = {
            "downloads": DOWNLOADS_FOLDER,
            "favorites": FAVORITES_FOLDER,
            "records": RECORD_FOLDER,
            "replies": REPLY_FOLDER,
            "temp": CACHE_FOLDER,
        }

        folder = folder_map.get(folder_type)
        if not folder:
            self.c.window.set_status("未知文件夹类型")
            return

        try:
            os.makedirs(folder, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
            self.c.window.set_status(f"已打开文件夹：{os.path.basename(folder)}")
        except Exception as e:
            self.c.window.set_status(f"打开文件夹失败：{str(e)}")
            QMessageBox.warning(self.c.window, "提示", f"打开文件夹失败：\n{str(e)}")