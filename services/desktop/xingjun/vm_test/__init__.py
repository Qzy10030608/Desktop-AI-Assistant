from __future__ import annotations

from services.desktop.xingjun.vm_test.vm_test_plan import V3_TEST_PLAN
from services.desktop.xingjun.vm_test.vm_test_session import default_test_mode_label
from services.desktop.xingjun.vm_test.vm_test_stage import (
    V3_STAGE_APP_BASIC,
    V3_STAGE_APP_DANGEROUS,
    V3_STAGE_BROWSER_SEARCH,
    V3_STAGE_CONNECTION,
    V3_STAGE_ISOLATION,
)

__all__ = [
    "V3_TEST_PLAN",
    "default_test_mode_label",
    "V3_STAGE_CONNECTION",
    "V3_STAGE_APP_BASIC",
    "V3_STAGE_BROWSER_SEARCH",
    "V3_STAGE_APP_DANGEROUS",
    "V3_STAGE_ISOLATION",
]

