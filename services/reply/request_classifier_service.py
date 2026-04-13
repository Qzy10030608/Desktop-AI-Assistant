from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class RequestClassifyResult:
    request_type: str
    confidence: float
    matched_rules: List[str]
    needs_search: bool
    needs_control: bool


class RequestClassifierService:
    """
    认知层前置分类器：
    第一轮先用轻量规则，不上大模型。
    """

    SEARCH_KEYWORDS = [
        "帮我查", "查一下", "搜索", "搜一下", "网上", "网页", "新闻",
        "最新", "官网", "资料", "信息", "是什么", "为什么", "怎么回事",
    ]

    CONTROL_KEYWORDS = [
        "打开", "关闭", "点击", "运行", "启动", "帮我操作", "帮我打开",
        "浏览器", "网页", "文件夹", "设置", "下载", "安装", "搜索框",
    ]

    COMFORT_KEYWORDS = [
        "难受", "伤心", "焦虑", "崩溃", "烦", "不开心", "害怕", "累",
        "安慰", "陪陪我", "心情不好", "不舒服",
    ]

    TASK_KEYWORDS = [
        "总结", "整理", "列一下", "规划", "方案", "步骤", "清单",
        "帮我写", "帮我改", "帮我分析", "设计",
    ]

    def classify(self, text: str) -> RequestClassifyResult:
        user_text = (text or "").strip()
        lowered = user_text.lower()
        matched_rules: List[str] = []

        if not user_text:
            return RequestClassifyResult(
                request_type="chat",
                confidence=0.1,
                matched_rules=[],
                needs_search=False,
                needs_control=False,
            )

        if self._match_any(user_text, self.COMFORT_KEYWORDS):
            matched_rules.append("comfort_keywords")
            return RequestClassifyResult(
                request_type="comfort",
                confidence=0.9,
                matched_rules=matched_rules,
                needs_search=False,
                needs_control=False,
            )

        if self._match_any(user_text, self.CONTROL_KEYWORDS):
            matched_rules.append("control_keywords")
            return RequestClassifyResult(
                request_type="control",
                confidence=0.85,
                matched_rules=matched_rules,
                needs_search=False,
                needs_control=True,
            )

        if self._match_any(user_text, self.SEARCH_KEYWORDS):
            matched_rules.append("search_keywords")
            return RequestClassifyResult(
                request_type="search",
                confidence=0.85,
                matched_rules=matched_rules,
                needs_search=True,
                needs_control=False,
            )

        if self._match_any(user_text, self.TASK_KEYWORDS):
            matched_rules.append("task_keywords")
            return RequestClassifyResult(
                request_type="task",
                confidence=0.8,
                matched_rules=matched_rules,
                needs_search=False,
                needs_control=False,
            )

        if re.search(r"[？?]$", user_text) or any(k in lowered for k in ["什么", "怎么", "多少", "是否"]):
            matched_rules.append("question_pattern")
            return RequestClassifyResult(
                request_type="chat",
                confidence=0.65,
                matched_rules=matched_rules,
                needs_search=False,
                needs_control=False,
            )

        return RequestClassifyResult(
            request_type="chat",
            confidence=0.5,
            matched_rules=matched_rules,
            needs_search=False,
            needs_control=False,
        )

    def _match_any(self, text: str, keywords: List[str]) -> bool:
        return any(keyword in text for keyword in keywords)