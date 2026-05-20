from __future__ import annotations

import subprocess
import urllib.parse
import webbrowser
from datetime import datetime
from typing import Any


class SystemSkillExecutorService:
    def execute(self, route: dict[str, Any]) -> dict[str, Any]:
        skill = str(route.get("skill", "") or "").strip()
        args = route.get("arguments", {})
        if not isinstance(args, dict):
            args = {}

        if skill == "datetime.read":
            return self._datetime_read(args)

        if skill == "weather.open_display":
            return self._weather_open_display(args)

        if skill == "weather.query":
            return {
                "ok": False,
                "skill": skill,
                "message_key": "desktop.system.weather.query_not_configured",
                "message_params": {},
                "result": "我已经理解你在问天气，但当前还没有接入天气数据读取；可以先帮你打开天气页面查看。",
            }

        return {
            "ok": False,
            "skill": skill,
            "message_key": "desktop.system.skill_not_supported",
            "message_params": {"skill": skill},
            "result": f"当前还不支持这个系统能力：{skill}",
        }

    def _datetime_read(self, args: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now()

        need_time = bool(args.get("need_time", False))
        need_date = bool(args.get("need_date", False))
        need_weekday = bool(args.get("need_weekday", False))

        if not any((need_time, need_date, need_weekday)):
            need_time = True

        weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        parts: list[str] = []

        if need_date:
            parts.append(now.strftime("%Y年%m月%d日"))

        if need_weekday:
            parts.append(weekday_names[now.weekday()])

        if need_time:
            parts.append(now.strftime("%H点%M分"))

        result = "现在是" + "，".join(parts) + "。"

        return {
            "ok": True,
            "skill": "datetime.read",
            "message_key": "desktop.system.datetime.done",
            "message_params": {"result": result},
            "result": result,
        }

    def _weather_open_display(self, args: dict[str, Any]) -> dict[str, Any]:
        location = str(
            args.get("location", "")
            or args.get("default_location", "")
            or ""
        ).strip()

        if location == "current":
            location = ""

        query = f"{location} weather".strip() if location else "weather"
        url = "https://www.bing.com/search?q=" + urllib.parse.quote(query)

        opened = False
        error = ""

        # 第一优先：系统默认浏览器。通常 Windows 上如果默认是 Edge，就会用 Edge 打开。
        try:
            opened = bool(webbrowser.open(url))
        except Exception as exc:
            error = str(exc)

        # 备用：直接尝试 Edge。
        if not opened:
            try:
                subprocess.Popen(["cmd", "/c", "start", "msedge", url], shell=False)
                opened = True
            except Exception as exc:
                error = str(exc)

        if opened:
            if location:
                result = f"已打开“{location}”的天气页面。"
                message_key = "desktop.system.weather.opened_with_location"
                message_params = {"location": location}
            else:
                result = "已打开天气页面。"
                message_key = "desktop.system.weather.opened"
                message_params = {}

            return {
                "ok": True,
                "skill": "weather.open_display",
                "message_key": message_key,
                "message_params": message_params,
                "result": result,
                "url": url,
            }

        return {
            "ok": False,
            "skill": "weather.open_display",
            "message_key": "desktop.system.weather.open_failed",
            "message_params": {"error": error},
            "result": f"天气页面打开失败：{error}",
            "url": url,
        }