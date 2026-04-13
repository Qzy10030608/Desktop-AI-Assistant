# ==========================================
# 收藏服务
# 用途：
# 1. 将 temp 中的 AI 回复语音复制到 favorites/
# 2. 自动重命名，避免文件覆盖
# ==========================================


import os
import shutil
import hashlib


class FavoriteService:
    """
    收藏服务
    作用：
    1. 判断当前语音是否已收藏
    2. 收藏到 favorites/
    3. 取消收藏并删除对应文件
    4. 提供收藏切换能力
    """

    def __init__(self, favorite_folder: str):
        self.favorite_folder = favorite_folder
        os.makedirs(self.favorite_folder, exist_ok=True)

    def _build_stable_filename(self, source_path: str) -> str:
        abs_path = os.path.abspath(source_path)
        ext = os.path.splitext(abs_path)[1] or ".mp3"
        digest = hashlib.sha1(abs_path.encode("utf-8")).hexdigest()[:16]
        return f"favorite_{digest}{ext}"

    def _build_target_path(self, source_path: str) -> str:
        filename = self._build_stable_filename(source_path)
        return os.path.join(self.favorite_folder, filename)

    def is_audio_favorited(self, source_path: str) -> bool:
        if not source_path:
            return False
        target_path = self._build_target_path(source_path)
        return os.path.exists(target_path)

    def add_audio_to_favorites(self, source_path: str) -> str:
        if not source_path or not os.path.exists(source_path):
            raise FileNotFoundError("当前没有可收藏的语音文件")

        target_path = self._build_target_path(source_path)
        shutil.copy2(source_path, target_path)
        return target_path

    def remove_audio_from_favorites(self, source_path: str) -> str:
        if not source_path:
            raise FileNotFoundError("当前没有可取消收藏的语音文件")

        target_path = self._build_target_path(source_path)
        if os.path.exists(target_path):
            os.remove(target_path)
        return target_path

    def toggle_audio_favorite(self, source_path: str) -> tuple[bool, str]:
        """
        返回:
            (is_favorite_now, target_path)
        """
        if self.is_audio_favorited(source_path):
            removed_path = self.remove_audio_from_favorites(source_path)
            return False, removed_path

        saved_path = self.add_audio_to_favorites(source_path)
        return True, saved_path