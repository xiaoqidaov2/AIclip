from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseFailureMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _failure(
        self,
        operation: str,
        message: str,
        *,
        code: str,
        path: Optional[str] = None,
    ) -> Dict[str, Any]:

        return ToolResult(
            ok=False,
            status="error",
            code=code,
            message=message,
            operation=operation,
            validation=ValidationSnapshot(passed=False, errors=[message]),
            render_state=RenderState(ready=False, blockers=[code]),
            artifacts=[ArtifactRef(type="project", path=path)] if path else [],
            state={"path": path} if path else {},
            summary=message,
            error=message,
        ).to_dict()
