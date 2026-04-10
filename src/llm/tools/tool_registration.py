class ToolRegistration:
    """工具注册类，用于注册和管理工具"""

    def __init__(self):
        self.tools = {}
        self.tool_docs = {}

    def register_tool(self, name: str, func):
        """注册工具"""
        self.tools[name] = func

    def register_tool_doc(self, name: str, doc: str):
        """注册工具说明文档。"""
        self.tool_docs[name] = doc

    def get_tool(self, name: str):
        """获取工具"""
        return self.tools.get(name)

    def get_tool_doc(self, name: str):
        """获取工具说明文档。"""
        return self.tool_docs.get(name)

    def list_tools(self):
        """列出所有注册的工具"""
        return list(self.tools.keys())

    def list_tool_docs(self):
        """列出所有已注册工具说明。"""
        return dict(self.tool_docs)