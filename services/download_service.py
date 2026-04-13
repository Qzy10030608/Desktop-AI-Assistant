# services/download_service.py
# ==========================================
# 下载导出服务
# 用途：
# 1. 默认导出到项目 downloads/
# 2. 支持用户自定义导出目录
# 3. 支持用户自定义文件名
# ==========================================

import os
import shutil
from datetime import datetime


class DownloadService:
    def __init__(self, default_download_folder: str):
        self.default_download_folder = default_download_folder
        os.makedirs(self.default_download_folder, exist_ok=True)

    def build_default_filename(self, source_path: str, prefix: str = "ai_reply") -> str:
        """
        生成默认文件名
        例如：ai_reply_20260317_153022.mp3
        """
        ext = os.path.splitext(source_path)[1] or ".mp3"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}{ext}"

    def export_audio(
        self,
        source_path: str,
        target_folder: str | None = None,
        target_name: str | None = None,
    ) -> str:
        """
        导出语音文件

        :param source_path: 原始语音文件路径
        :param target_folder: 用户指定导出目录，未指定则使用默认目录
        :param target_name: 用户指定文件名，未指定则自动生成
        :return: 导出后的完整路径
        """
        if not source_path or not os.path.exists(source_path):
            raise FileNotFoundError("当前没有可下载的语音文件")

        folder = target_folder or self.default_download_folder
        os.makedirs(folder, exist_ok=True)

        ext = os.path.splitext(source_path)[1] or ".mp3"

        if not target_name:
            filename = self.build_default_filename(source_path)
        else:
            filename = target_name.strip()
            if not filename:
                filename = self.build_default_filename(source_path)

            # 如果用户没写扩展名，就自动补上
            if not os.path.splitext(filename)[1]:
                filename += ext

        target_path = os.path.join(folder, filename)
        shutil.copy2(source_path, target_path)
        return target_path