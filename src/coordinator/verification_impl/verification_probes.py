from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from .verification_agent import VerificationAgent
from .verification_models import CheckResult, VerificationCheck


@dataclass
class AdversarialProbe:
    name: str
    description: str
    probe_type: str


class AdversarialVerifier:
    def __init__(self, verification_agent: VerificationAgent):
        self.agent = verification_agent

    async def probe_concurrent(self, command: str, count: int = 3) -> VerificationCheck:
        import asyncio
        procs = []
        for _ in range(count):
            proc = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=self.agent.project_root)
            procs.append(proc.communicate())
        results = await asyncio.gather(*procs, return_exceptions=True)
        failures = [item for item in results if isinstance(item, Exception)]
        return VerificationCheck(name="concurrent_probe", description=f"并发执行 {count} 次", command_run=f"{command} (x{count} concurrent)", result=CheckResult.PASS if not failures else CheckResult.FAIL, error_message=f"{len(failures)} 次执行失败" if failures else "")

    async def probe_boundary(self, command_template: str, boundary_values: List[Any]) -> List[VerificationCheck]:
        checks = []
        for value in boundary_values:
            checks.append(await self.agent._run_check({"name": f"boundary_{value}", "description": f"边界值测试: {value}", "command": command_template.replace("{value}", str(value))}))
        return checks

    async def probe_idempotent(self, command: str, times: int = 2) -> VerificationCheck:
        import asyncio
        outputs = []
        for _ in range(times):
            proc = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=self.agent.project_root)
            stdout, _ = await proc.communicate()
            outputs.append(stdout.decode(errors="replace"))
        all_same = len(set(outputs)) == 1
        return VerificationCheck(name="idempotent_probe", description=f"幂等性测试: 执行 {times} 次", command_run=f"{command} (x{times} sequential)", output_observed=outputs[0] if outputs else "", result=CheckResult.PASS if all_same else CheckResult.FAIL, error_message="输出不一致" if not all_same else "")

    async def probe_orphan(self, command: str, cleanup_command: Optional[str] = None) -> VerificationCheck:
        import asyncio
        proc = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=self.agent.project_root)
        await proc.communicate()
        if cleanup_command:
            cleanup_proc = await asyncio.create_subprocess_shell(cleanup_command, cwd=self.agent.project_root)
            await cleanup_proc.communicate()
        return VerificationCheck(name="orphan_probe", description="孤儿资源检测", command_run=command, result=CheckResult.PASS)
