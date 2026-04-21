from __future__ import annotations

from .app_impl import (
    CLIAppAgentMixin,
    CLIAppCommandsMixin,
    CLIAppCoordinatorMixin,
    CLIAppRuntimeMixin,
    CLIAppStateMixin,
)


class CLIApp(
    CLIAppCommandsMixin,
    CLIAppCoordinatorMixin,
    CLIAppStateMixin,
    CLIAppAgentMixin,
    CLIAppRuntimeMixin,
):
    pass
