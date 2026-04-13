# services/session_service.py
# ==========================================
# 会话管理服务
# 用途：
# 1. 管理当前 session_id
# 2. 刷新页面 / 切换角色时生成新会话
# 3. 判断后台线程结果是否仍属于当前会话
# ==========================================

from dataclasses import dataclass


@dataclass
class SessionState:
    """
    保存当前会话状态
    """
    current_id: int = 0


class SessionService:
    """
    会话服务
    当前先使用整数递增方式，和你现有 app.py 的逻辑一致，
    这样最容易接入，不会影响已有线程判断。
    """

    def __init__(self):
        self._state = SessionState(current_id=0)

    @property
    def current_id(self) -> int:
        """
        获取当前会话 ID
        """
        return self._state.current_id

    def new_session(self) -> int:
        """
        创建一个新会话
        常用于：
        - 刷新页面
        - 切换角色
        - 手动重置上下文
        """
        self._state.current_id += 1
        return self._state.current_id

    def is_current(self, request_id: int) -> bool:
        """
        判断某个后台请求是否仍然属于当前会话
        旧线程返回结果时，可用它过滤掉过期结果
        """
        return request_id == self._state.current_id

    def reset(self) -> None:
        """
        重置为初始状态
        一般调试时可用
        """
        self._state.current_id = 0