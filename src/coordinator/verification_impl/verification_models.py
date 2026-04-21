from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class CheckResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class VerificationCheck:
    name: str
    description: str
    command_run: str = ""
    output_observed: str = ""
    result: CheckResult = CheckResult.FAIL
    error_message: str = ""


@dataclass
class VerificationReport:
    checks: List[VerificationCheck] = field(default_factory=list)
    all_passed: bool = False
    summary: str = ""

    def add_check(self, check: VerificationCheck) -> None:
        self.checks.append(check)
        self._update_summary()

    def _update_summary(self) -> None:
        passed = sum(1 for c in self.checks if c.result == CheckResult.PASS)
        total = len(self.checks)
        self.all_passed = passed == total and total > 0
        self.summary = f"{passed}/{total} checks passed"


RATIONALIZATION_PATTERNS = [
    ("代码看起来正确", "必须运行测试验证"),
    ("测试应该通过", "必须实际执行测试"),
    ("这是小改动", "小改动也需要验证"),
    ("逻辑很简单", "简单逻辑也可能有 bug"),
    ("我已经检查过了", "检查不等于执行"),
    ("文档说这样是对的", "文档可能过时，必须实测"),
]


def detect_rationalization(statement: str) -> Optional[str]:
    for pattern, action in RATIONALIZATION_PATTERNS:
        if pattern in statement:
            return action
    return None
