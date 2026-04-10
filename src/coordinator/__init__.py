"""coordinator 包 — 任务编排核心。

模块结构：
- task.py          任务类型、状态机、Task 接口
- registry.py      任务注册表 + 特性开关
- notification.py  通知队列 (<task-notification> XML)
- worker.py        Worker 管理
- context.py       上下文管理（Continue vs Spawn Fresh）
- coordinator.py   协调器模式（四阶段工作流）
- verification.py  验证代理（强制执行验证）
"""

from .task import (
    TaskType,
    TaskStatus,
    TaskError,
    TaskInstance,
    Task,
    LocalBashTask,
    LocalAgentTask,
    RemoteAgentTask,
    InProcessTeammateTask,
    LocalWorkflowTask,
    MonitorMCPTask,
    DreamTask,
)
from .registry import TaskRegistry, FeatureFlags
from .notification import TaskNotification, NotificationQueue
from .worker import WorkerManager
from .context import ContextManager, ContextDecision, WorkerContext
from .coordinator import CoordinatorMode, WorkflowPhase, ConcurrencyMode, WorkItem
from .verification import (
    VerificationAgent,
    VerificationReport,
    VerificationCheck,
    CheckResult,
    AdversarialVerifier,
    detect_rationalization,
)
from .stop import stop_task, TaskStopTool, StopTaskError

__all__ = [
    # task
    "TaskType",
    "TaskStatus",
    "TaskError",
    "TaskInstance",
    "Task",
    "LocalBashTask",
    "LocalAgentTask",
    "RemoteAgentTask",
    "InProcessTeammateTask",
    "LocalWorkflowTask",
    "MonitorMCPTask",
    "DreamTask",
    # registry
    "TaskRegistry",
    "FeatureFlags",
    # notification
    "TaskNotification",
    "NotificationQueue",
    # worker
    "WorkerManager",
    # context
    "ContextManager",
    "ContextDecision",
    "WorkerContext",
    # coordinator
    "CoordinatorMode",
    "WorkflowPhase",
    "ConcurrencyMode",
    "WorkItem",
    # verification
    "VerificationAgent",
    "VerificationReport",
    "VerificationCheck",
    "CheckResult",
    "AdversarialVerifier",
    "detect_rationalization",
    # stop
    "stop_task",
    "TaskStopTool",
    "StopTaskError",
]
