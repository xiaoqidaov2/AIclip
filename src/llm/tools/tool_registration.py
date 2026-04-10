from typing import Any, Callable, Dict, Optional


class ToolRegistration:
    """Tool registry for registering and looking up tools."""

    def __init__(self):
        self.tools: Dict[str, Callable[..., Any]] = {}
        self.tool_docs: Dict[str, str] = {}

    def register_tool(self, name: str, func: Callable[..., Any]) -> None:
        """Register a tool."""
        self.tools[name] = func

    def register_tool_doc(self, name: str, doc: str) -> None:
        """Register tool documentation."""
        self.tool_docs[name] = doc

    def get_tool(self, name: str) -> Optional[Callable[..., Any]]:
        """Get a tool."""
        return self.tools.get(name)

    def get_tool_doc(self, name: str) -> Optional[str]:
        """Get tool documentation."""
        return self.tool_docs.get(name)

    def list_tools(self) -> list[str]:
        """List registered tools."""
        return list(self.tools.keys())

    def list_tool_docs(self) -> Dict[str, str]:
        """List registered tool docs."""
        return dict(self.tool_docs)
