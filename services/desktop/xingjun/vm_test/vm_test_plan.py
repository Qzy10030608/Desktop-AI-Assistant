from __future__ import annotations

from services.desktop.xingjun.vm_test.vm_test_stage import (
    V3_STAGE_APP_BASIC,
    V3_STAGE_APP_DANGEROUS,
    V3_STAGE_BROWSER_SEARCH,
    V3_STAGE_CONNECTION,
    V3_STAGE_ISOLATION,
)

V3_TEST_PLAN = [
    {"stage": V3_STAGE_CONNECTION, "title": "V3-00 VM 连接监管"},
    {"stage": V3_STAGE_APP_BASIC, "title": "V3-01 软件定位/启动/关闭"},
    {"stage": V3_STAGE_BROWSER_SEARCH, "title": "V3-02 浏览器搜索"},
    {"stage": V3_STAGE_APP_DANGEROUS, "title": "V3-03 VM 软件高危真实测试"},
    {"stage": V3_STAGE_ISOLATION, "title": "V3-04 Host/VM 隔离回归"},
]

