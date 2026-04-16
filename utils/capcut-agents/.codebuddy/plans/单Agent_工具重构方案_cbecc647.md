---
name: 单Agent+工具重构方案
overview: 将多Agent协作架构简化为单Agent+三个Add工具的模式，主Agent接收完整上下文和当前片段，自主决定调用哪些工具
todos:
  - id: create-add-tools
    content: 创建 tools/add_tools.py，实现四个Add工具（add_effect, add_sticker, add_transition, skip_segment）
    status: completed
  - id: create-unified-agent
    content: 创建 agents/unified_agent.py，实现UnifiedAgent类，包含系统提示词和工具调用逻辑
    status: completed
    dependencies:
      - create-add-tools
  - id: refactor-main-graph
    content: 重构 agents/main_graph.py，删除子Agent节点，添加主Agent循环节点
    status: completed
    dependencies:
      - create-unified-agent
  - id: delete-old-files
    content: 删除旧的子Agent文件和agent_tools文件
    status: completed
    dependencies:
      - refactor-main-graph
  - id: update-imports
    content: 更新相关文件的import语句，验证重构后的工作流
    status: completed
    dependencies:
      - delete-old-files
---

## 产品概述

将现有的多Agent协作架构重构为单Agent + 工具调用模式，简化工作流程，提高决策灵活性和智能化程度。

## 核心功能

- 创建统一的MainAgent，接收完整上下文（视频主题、整体基调）和单个片段信息
- 实现三个Add工具：add_effect、add_sticker、add_transition，只将效果信息添加到State列表中，不调用实际接口
- 主Agent根据上下文自主决策调用哪些工具（可同时调用多个或全部跳过）
- 简化工作流：create_draft → add_videos → [主Agent逐片段循环] → apply_all → save_draft → export_video
- 删除原有的transition_agent、effect_agent、sticker_agent三个子Agent

## 技术栈

- 语言：Python 3.10+
- 框架：LangChain + LangGraph
- LLM：ChatOpenAI（通过config配置）
- 工具定义：@tool装饰器 + Pydantic BaseModel

## 实现方案

### 架构对比

**旧架构：**

```
create_draft → add_videos → transition_agent → effect_agent → sticker_agent → apply_visual_elements → save_draft → export_video
```

**新架构：**

```
create_draft → add_videos → [MainAgent逐片段循环] → apply_visual_elements → save_draft → export_video
```

### 核心设计

#### 1. MainAgent 输入设计

```python
{
    "video_script": "完整视频文案",
    "script_summary": "视频摘要（减少token）",
    "current_segment": {"text": "...", "start": 0.0, "end": 3.5},
    "segment_index": 1,
    "total_segments": 10
}
```

#### 2. 四个Add工具设计

- `add_effect(effect_name, start_time, duration, reason)` - 添加特效到effects列表
- `add_sticker(sticker_type, start_time, duration, trigger_text, reason)` - 添加贴纸到stickers列表
- `add_transition(effect_name, start_time, duration, reason)` - 添加转场到transitions列表
- `skip_segment(reason)` - 跳过当前片段（不做任何添加）

#### 3. State结构保持兼容

```python
class VideoWorkflowState(TypedDict):
    # 输入
    draft_name: str
    video_files: list[dict]
    video_script: str
    timestamps: list[dict]
    
    # 中间状态
    draft_id: str | None
    script_summary: str | None
    current_segment_index: int
    
    # 收集的结果
    transitions: list[dict]  # 开幕效果
    effects: list[dict]
    stickers: list[dict]
    
    # 输出
    final_video_path: str | None
    error: str | None
```

### 实现要点

#### 性能优化

- 预先总结video_script生成script_summary，避免每次调用都传入完整文案
- MainAgent单次LLM调用可同时决策多个元素（特效+贴纸），减少API调用次数
- 保留apply_visual_elements_tool统一应用，只保存一次草稿

#### 错误处理

- MainAgent调用失败时记录错误但不阻断流程
- 工具调用无结果时默认跳过
- 保留原有的error传递机制

## 目录结构

```
c:\Users\64061\capcut-agents\
├── agents/
│   ├── main_graph.py           # [MODIFY] 重构工作流，集成MainAgent循环
│   ├── unified_agent.py        # [NEW] 统一的主Agent实现
│   ├── effect_agent_v2.py      # [DELETE] 删除子Agent
│   ├── sticker_agent_v2.py     # [DELETE] 删除子Agent
│   └── transition_agent_v2.py  # [DELETE] 删除子Agent
├── tools/
│   ├── add_tools.py            # [NEW] 四个Add工具定义
│   ├── visual_elements_tools.py # [KEEP] 保留统一应用工具
│   ├── effect_agent_tools.py   # [DELETE] 删除旧的agent专用工具
│   ├── sticker_agent_tools.py  # [DELETE] 删除旧的agent专用工具
│   └── transition_agent_tools.py # [DELETE] 删除旧的agent专用工具
└── config/                      # [KEEP] 保持现有配置文件
```

## 关键代码结构

### unified_agent.py - MainAgent核心类

```python
class UnifiedAgent:
    """统一的主Agent，负责根据上下文决策添加哪些视觉元素"""
    
    def __init__(self, temperature: float = 0.2):
        self.tools = get_add_tools()  # 四个Add工具
        self.llm = self._create_llm()
        self.llm_with_tools = self.llm.bind_tools(self.tools)
    
    def analyze_segment(
        self, 
        video_script: str,
        script_summary: str,
        segment: dict,
        segment_index: int,
        total_segments: int
    ) -> ToolCallsResult:
        """分析单个片段，返回工具调用结果"""
        ...
```

### add_tools.py - 四个Add工具

```python
class AddEffectInput(BaseModel):
    effect_name: str = Field(description="特效名称：心动/光环 I/气炸了")
    start_time: float = Field(description="开始时间（秒）")
    duration: float = Field(description="持续时间（秒）")
    reason: str = Field(description="添加理由")

@tool(args_schema=AddEffectInput)
def add_effect(effect_name: str, start_time: float, duration: float, reason: str) -> str:
    """添加特效到特效列表（仅添加到列表，不实际调用接口）"""
    # 返回结构化信息，由调用方收集到state
    return json.dumps({"action": "add_effect", ...})
```

## Agent Extensions

### SubAgent

- **code-explorer**
- Purpose: 搜索和分析现有代码结构，确保重构时引用正确
- Expected outcome: 确认所有依赖关系，避免遗漏关键文件