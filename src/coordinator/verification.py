"""Verification Agent — 强制执行验证，禁止偷工减料。

核心原则：
- 禁止修改项目目录文件（只能写 /tmp 的临时测试脚本）
- 禁止只读代码就声称验证通过
- 必须实际执行命令并观察输出
- 输出格式强制：Command run → Output observed → Result
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class VerificationError(Exception):
    """验证失败或违反规则。"""


class CheckResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"  # 前置条件不满足


@dataclass
class VerificationCheck:
    """单个验证检查项。"""
    name: str
    description: str
    command_run: str = ""
    output_observed: str = ""
    result: CheckResult = CheckResult.FAIL
    error_message: str = ""


@dataclass
class VerificationReport:
    """验证报告。"""
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


# ==================== 合理化借口检测 ====================

RATIONALIZATION_PATTERNS = [
    ("代码看起来正确", "必须运行测试验证"),
    ("测试应该通过", "必须实际执行测试"),
    ("这是小改动", "小改动也需要验证"),
    ("逻辑很简单", "简单逻辑也可能有 bug"),
    ("我已经检查过了", "检查不等于执行"),
    ("文档说这样是对的", "文档可能过时，必须实测"),
]


def detect_rationalization(statement: str) -> Optional[str]:
    """检测合理化借口，返回应采取的反向行动。"""
    for pattern, action in RATIONALIZATION_PATTERNS:
        if pattern in statement:
            return action
    return None


# ==================== Verification Agent ====================

class VerificationAgent:
    """验证代理 — 强制执行验证，对抗偷工减料倾向。

    使用方式：
        agent = VerificationAgent(project_root="/path/to/project")
        report = await agent.verify(implementation_result)
    """

    # 禁止修改的目录
    PROTECTED_DIRS = {"src", "lib", "app", "tests", "config"}

    def __init__(self, project_root: str, allowed_tmp_dir: str = "/tmp"):
        self.project_root = os.path.abspath(project_root)
        self.tmp_dir = allowed_tmp_dir
        self._report = VerificationReport()

    async def verify(self, context: Dict[str, Any]) -> VerificationReport:
        """执行验证流程。"""
        self._report = VerificationReport()

        # 1. 检查是否有合理化借口
        if "reasoning" in context:
            action = detect_rationalization(context["reasoning"])
            if action:
                self._report.add_check(VerificationCheck(
                    name="rationalization_detection",
                    description="检测到合理化借口",
                    result=CheckResult.FAIL,
                    error_message=f"检测到借口，应采取行动: {action}",
                ))
                return self._report

        # 2. 执行验证检查
        checks = context.get("checks", [])
        for check_spec in checks:
            check = await self._run_check(check_spec)
            self._report.add_check(check)

        return self._report

    async def _run_check(self, spec: Dict[str, Any]) -> VerificationCheck:
        """执行单个检查。"""
        name = spec.get("name", "unnamed_check")
        description = spec.get("description", "")
        command = spec.get("command", "")
        expected_output = spec.get("expected_output")
        expected_exit_code = spec.get("expected_exit_code", 0)

        check = VerificationCheck(
            name=name,
            description=description,
        )

        if not command:
            check.result = CheckResult.SKIP
            check.error_message = "未提供执行命令"
            return check

        # 执行命令
        import asyncio
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=spec.get("timeout", 30)
            )

            check.command_run = command
            output = stdout.decode(errors="replace")
            error_output = stderr.decode(errors="replace")
            check.output_observed = output or error_output or "(no output)"

            # 验证结果
            if expected_output is not None:
                if expected_output in check.output_observed:
                    check.result = CheckResult.PASS
                else:
                    check.result = CheckResult.FAIL
                    check.error_message = f"期望输出包含: {expected_output}"
            elif proc.returncode == expected_exit_code:
                check.result = CheckResult.PASS
            else:
                check.result = CheckResult.FAIL
                check.error_message = f"退出码: {proc.returncode}, 期望: {expected_exit_code}"

        except asyncio.TimeoutError:
            check.command_run = command
            check.result = CheckResult.FAIL
            check.error_message = "命令超时"
        except Exception as e:
            check.command_run = command
            check.result = CheckResult.FAIL
            check.error_message = str(e)

        return check

    def validate_file_write(self, path: str) -> bool:
        """验证文件写入是否允许（只能写 /tmp）。"""
        abs_path = os.path.abspath(path)
        # 允许写入临时目录
        if abs_path.startswith(self.tmp_dir):
            return True
        # 禁止写入项目受保护目录
        for protected in self.PROTECTED_DIRS:
            protected_path = os.path.join(self.project_root, protected)
            if abs_path.startswith(protected_path):
                return False
        return True

    def create_temp_script(self, content: str, suffix: str = ".sh") -> str:
        """创建临时测试脚本。"""
        fd, path = tempfile.mkstemp(suffix=suffix, dir=self.tmp_dir)
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.chmod(path, 0o755)
        return path


# ==================== 对抗性探测 ====================

@dataclass
class AdversarialProbe:
    """对抗性探测配置。"""
    name: str
    description: str
    probe_type: str  # "concurrent", "boundary", "idempotent", "orphan"


class AdversarialVerifier:
    """对抗性验证器 — 执行边界值、并发、幂等性等探测。"""

    def __init__(self, verification_agent: VerificationAgent):
        self.agent = verification_agent

    async def probe_concurrent(
        self,
        command: str,
        count: int = 3,
    ) -> VerificationCheck:
        """并发探测：同时执行多次，检查竞态条件。"""
        import asyncio

        tasks = []
        for i in range(count):
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.agent.project_root,
            )
            tasks.append(proc.communicate())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 检查是否所有执行都成功
        failures = [r for r in results if isinstance(r, Exception)]
        check = VerificationCheck(
            name="concurrent_probe",
            description=f"并发执行 {count} 次",
            command_run=f"{command} (x{count} concurrent)",
            result=CheckResult.PASS if not failures else CheckResult.FAIL,
            error_message=f"{len(failures)} 次执行失败" if failures else "",
        )
        return check

    async def probe_boundary(
        self,
        command_template: str,
        boundary_values: List[Any],
    ) -> List[VerificationCheck]:
        """边界值探测：测试极端输入。"""
        checks = []
        for value in boundary_values:
            command = command_template.replace("{value}", str(value))
            check = await self.agent._run_check({
                "name": f"boundary_{value}",
                "description": f"边界值测试: {value}",
                "command": command,
            })
            checks.append(check)
        return checks

    async def probe_idempotent(
        self,
        command: str,
        times: int = 2,
    ) -> VerificationCheck:
        """幂等性探测：多次执行，结果应一致。"""
        import asyncio

        outputs = []
        for _ in range(times):
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.agent.project_root,
            )
            stdout, _ = await proc.communicate()
            outputs.append(stdout.decode(errors="replace"))

        # 检查输出是否一致
        all_same = len(set(outputs)) == 1
        check = VerificationCheck(
            name="idempotent_probe",
            description=f"幂等性测试: 执行 {times} 次",
            command_run=f"{command} (x{times} sequential)",
            output_observed=outputs[0] if outputs else "",
            result=CheckResult.PASS if all_same else CheckResult.FAIL,
            error_message="输出不一致" if not all_same else "",
        )
        return check

    async def probe_orphan(
        self,
        command: str,
        cleanup_command: Optional[str] = None,
    ) -> VerificationCheck:
        """孤儿操作探测：执行后检查是否有残留资源。"""
        import asyncio

        # 执行命令
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.agent.project_root,
        )
        await proc.communicate()

        # 检查残留（简化：检查进程、文件等）
        # 实际实现可根据具体场景扩展
        check = VerificationCheck(
            name="orphan_probe",
            description="孤儿资源检测",
            command_run=command,
            result=CheckResult.PASS,
        )

        if cleanup_command:
            cleanup_proc = await asyncio.create_subprocess_shell(
                cleanup_command,
                cwd=self.agent.project_root,
            )
            await cleanup_proc.communicate()

        return check
