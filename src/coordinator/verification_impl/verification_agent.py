from __future__ import annotations

import os
import tempfile
from typing import Any, Dict

from .verification_models import CheckResult, VerificationCheck, VerificationReport, detect_rationalization


class VerificationError(Exception):
    pass


class VerificationAgent:
    PROTECTED_DIRS = {"src", "lib", "app", "tests", "config"}

    def __init__(self, project_root: str, allowed_tmp_dir: str = "/tmp"):
        self.project_root = os.path.abspath(project_root)
        self.tmp_dir = allowed_tmp_dir
        self._report = VerificationReport()

    async def verify(self, context: Dict[str, Any]) -> VerificationReport:
        self._report = VerificationReport()
        if "reasoning" in context:
            action = detect_rationalization(context["reasoning"])
            if action:
                self._report.add_check(VerificationCheck(name="rationalization_detection", description="检测到合理化借口", result=CheckResult.FAIL, error_message=f"检测到借口，应采取行动: {action}"))
                return self._report
        for check_spec in context.get("checks", []):
            self._report.add_check(await self._run_check(check_spec))
        return self._report

    async def _run_check(self, spec: Dict[str, Any]) -> VerificationCheck:
        import asyncio
        check = VerificationCheck(name=spec.get("name", "unnamed_check"), description=spec.get("description", ""))
        command = spec.get("command", "")
        if not command:
            check.result = CheckResult.SKIP
            check.error_message = "未提供执行命令"
            return check
        try:
            proc = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=self.project_root)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=spec.get("timeout", 30))
            check.command_run = command
            check.output_observed = stdout.decode(errors="replace") or stderr.decode(errors="replace") or "(no output)"
            expected_output = spec.get("expected_output")
            expected_exit_code = spec.get("expected_exit_code", 0)
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
        except Exception as exc:
            check.command_run = command
            check.result = CheckResult.FAIL
            check.error_message = str(exc)
        return check

    def validate_file_write(self, path: str) -> bool:
        abs_path = os.path.abspath(path)
        if abs_path.startswith(self.tmp_dir):
            return True
        return not any(abs_path.startswith(os.path.join(self.project_root, protected)) for protected in self.PROTECTED_DIRS)

    def create_temp_script(self, content: str, suffix: str = ".sh") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix, dir=self.tmp_dir)
        with os.fdopen(fd, "w") as handle:
            handle.write(content)
        os.chmod(path, 0o755)
        return path
