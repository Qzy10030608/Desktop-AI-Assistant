from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from bootstrap.machine_profile_service import MachineProfileService
from bootstrap.startup_check_service import StartupCheckService

from config import ensure_project_dirs, RECORD_FOLDER, REPLY_FOLDER, CACHE_FOLDER  # type: ignore
from services.reply.llm_backend_controller_service import LLMBackendControllerService  # type: ignore
from services.session_service import SessionService  # type: ignore
from services.temp_cleanup_service import TempCleanupService  # type: ignore


@dataclass
class AppBootstrapBundle:
    machine_profile_service: MachineProfileService
    startup_check_service: StartupCheckService
    startup_report: Dict[str, Any]
    llm_backend_controller: LLMBackendControllerService
    temp_cleanup_service: TempCleanupService
    session_service: SessionService


class AppBootstrapService:
    """
    app 启动底座
    -------------------------
    作用：
    1. 初始化目录
    2. 初始化 machine profile / startup check
    3. 初始化 llm backend controller
    4. 初始化 temp/session 服务
    """

    def bootstrap(self) -> AppBootstrapBundle:
        ensure_project_dirs()

        machine_profile_service = MachineProfileService()
        startup_check_service = StartupCheckService(
            machine_profile_service=machine_profile_service
        )
        startup_report = startup_check_service.run(auto_patch=True)

        llm_backend_controller = LLMBackendControllerService()

        temp_cleanup_service = TempCleanupService(
            temp_dirs=[RECORD_FOLDER, REPLY_FOLDER, CACHE_FOLDER]
        )
        temp_cleanup_service.ensure_temp_dirs()

        session_service = SessionService()

        return AppBootstrapBundle(
            machine_profile_service=machine_profile_service,
            startup_check_service=startup_check_service,
            startup_report=startup_report,
            llm_backend_controller=llm_backend_controller,
            temp_cleanup_service=temp_cleanup_service,
            session_service=session_service,
        )