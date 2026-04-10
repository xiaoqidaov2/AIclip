class ToolRegistration:
    """工具注册类，用于注册和管理工具"""

    def __init__(self):
        self.tools = {}

    def register_tool(self, name: str, func):
        """注册工具"""
        self.tools[name] = func

    def get_tool(self, name: str):
        """获取工具"""
        return self.tools.get(name)

    def list_tools(self):
        """列出所有注册的工具"""
        return list(self.tools.keys())