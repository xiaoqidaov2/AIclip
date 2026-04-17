---
name: 集成 CapCut 视频工具到 LLM 工具系统
overview: 将 capcut_video_tool.py 移动到 src/llm/tools/ 并集成到现有工具注册系统
todos:
  - id: move-tool-file
    content: 移动 capcut_video_tool.py 到 src/llm/tools/capcut_tool.py 并修复导入路径
    status: completed
  - id: create-doc-file
    content: 创建 resources/docs/capcut_video_creation.txt 工具文档
    status: completed
  - id: register-tool
    content: 在 tool_setup.py 中注册 CapCut 工具并更新 __init__.py 导出
    status: completed
    dependencies:
      - move-tool-file
      - create-doc-file
---

## 用户需求

将 `utils/capcut-agents/capcut_video_tool.py` 移动到 `src/llm/tools/` 目录中，并将其注册到 LLM 工具系统中供 LLM 调用。

## 核心功能

- 移动工具文件到目标目录
- 调整导入路径以适应新位置
- 在 ToolSetup 中注册新工具
- 创建工具文档供 LLM 理解和使用

## 功能说明

该工具用于通过 CapCut Mate 快速创建视频，支持自动解析 ASR 文件获取文案和时间戳，添加特效和贴纸等。

## 技术栈

- Python 工具模块
- LangChain 工具装饰器 (`@tool`)
- 现有工具注册机制 (ToolSetup, ToolSpec)

## 实施方案

### 核心改动

1. **移动文件**: 将 `capcut_video_tool.py` 移动到 `src/llm/tools/capcut_tool.py`
2. **更新导入路径**: 由于原文件依赖 `utils/capcut-agents/` 下的模块，需要将相对导入改为从项目根目录的绝对导入
3. **工具注册**: 

- 在 `ToolSetup._resources` 中添加工具资源
- 在 `_specs` 中添加 `ToolSpec` 配置

4. **创建文档**: 在 `resources/docs/` 创建工具使用文档
5. **更新导出**: 在 `__init__.py` 中添加导出

### 导入路径调整

原文件中的导入：

```python
from core.video_processor import create_video
from tools.asr_utils import parse_asr_output
```

需要修改为从项目根目录的绝对导入：

```python
from utils.capcut_agents.core.video_processor import create_video
from utils.capcut_agents.tools.asr_utils import parse_asr_output
```

### 注意事项

- `utils/capcut-agents` 目录名包含连字符，Python 无法直接导入。但现有代码通过 `sys.path` 操作解决了这个问题，移动后需要保持这一机制或确保 `utils/` 在 Python 路径中
- 该工具使用 LangChain 的 `@tool` 装饰器，与现有的类式工具（MoviePyTool、SubtitleTool）模式不同，需要适配注册机制

## 目录结构

```
c:/Users/64061/AIclip/
├── src/llm/tools/
│   ├── capcut_tool.py          # [NEW] 移动后的 CapCut 视频工具
│   ├── tool_setup.py           # [MODIFY] 添加工具注册
│   └── __init__.py             # [MODIFY] 添加导出
├── resources/docs/
│   └── capcut_video_creation.txt  # [NEW] 工具文档
└── utils/capcut-agents/        # [UNCHANGED] 保持不动
```