# services/temp_cleanup_service.py
# ==========================================
# temp 临时文件清理服务
# 用途：
# 1. 确保 temp/records temp/replies temp/cache 存在
# 2. 程序退出时统一清理 temp
# 3. 后续可扩展按 session 清理
# ==========================================

import os
import shutil
from typing import Iterable


class TempCleanupService:
    """
    临时文件清理服务
    """

    def __init__(self, temp_dirs: Iterable[str]):
        """
        :param temp_dirs: 需要管理的临时目录列表
                         例如 [RECORD_FOLDER, REPLY_FOLDER, CACHE_FOLDER]
        """
        self.temp_dirs = list(temp_dirs)

    def ensure_temp_dirs(self) -> None:
        """
        确保所有临时目录存在
        """
        for folder in self.temp_dirs:
            os.makedirs(folder, exist_ok=True)

    def clear_all_temp(self) -> None:
        """
        清空所有临时目录中的文件和子目录
        注意：
        - 只清目录内容，不删除目录本身
        - 适合在程序退出时调用
        """
        for folder in self.temp_dirs:
            self._clear_folder(folder)

    def clear_temp_folder(self, folder: str) -> None:
        """
        单独清理某一个临时目录
        """
        self._clear_folder(folder)

    def _clear_folder(self, folder: str) -> None:
        """
        真正执行清理的内部方法
        """
        if not os.path.exists(folder):
            return

        for name in os.listdir(folder):
            path = os.path.join(folder, name)

            try:
                if os.path.isfile(path) or os.path.islink(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
            except Exception as e:
                # 当前阶段先打印日志，后面可以接入 data/logs/
                print(f"[TempCleanupService] 清理失败: {path} -> {e}")