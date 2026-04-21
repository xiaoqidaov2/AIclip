from __future__ import annotations

from .app_impl import (
    CLIAppAgentMixin,
    CLIAppCommandsMixin,
    CLIAppRuntimeMixin,
    CLIAppStateMixin,
)


class CLIApp(
    CLIAppCommandsMixin,
    CLIAppStateMixin,
    CLIAppAgentMixin,
    CLIAppRuntimeMixin,
):
    pass
