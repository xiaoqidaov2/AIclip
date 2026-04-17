---
name: transition-sticker-agent-tool-first-refactor
overview: 将 TransitionAgent 和 StickerAgent 重构为 Tool-First 架构，与 EffectAgentV2 保持一致的设计模式
todos:
  - id: create-transition-tools
    content: 创建 tools/transition_agent_tools.py，定义 add_opening_effect 工具
    status: completed
  - id: implement-transition-v2
    content: 实现 agents/transition_agent_v2.py，Tool-First 架构
    status: completed
    dependencies:
      - create-transition-tools
  - id: create-sticker-tools
    content: 创建 tools/sticker_agent_tools.py，定义 add_sticker 工具
    status: completed
  - id: implement-sticker-v2
    content: 实现 agents/sticker_agent_v2.py，Tool-First 架构
    status: completed
    dependencies:
      - create-sticker-tools
  - id: update-main-graph-v2
    content: 修改 agents/main_graph.py，切换为 V2 版本
    status: completed
    dependencies:
      - implement-transition-v2
      - implement-sticker-v2
  - id: add-tests-v2
    content: 编写两个 Agent 的测试文件
    status: completed
    dependencies:
      - implement-transition-v2
      - implement-sticker-v2
  - id: verify-refactor-v2
    content: 运行验证脚本确认重构完成
    status: completed
    dependencies:
      - add-tests-v2
      - update-main-graph-v2
---

## 产品概述

将 TransitionAgent（开幕 Agent）和 StickerAgent（贴纸 Agent）从「长系统提示词 + 固定流程」架构重构为「Claude 式 Tool-First」架构，与已完成的 EffectAgentV2 保持一致的设计模式。

## 核心需求

### TransitionAgent 重构

- 系统提示词从 ~15 行简化为核心原则（~5 行）
- 创建 `add_opening_effect` 工具，包含详细的开场效果选择指南
- LLM 根据文案内容自主选择合适的开幕效果
- 接口与现有 `main_graph.py` 保持兼容

### StickerAgent 重构

- 系统提示词从 ~25 行简化为核心原则（~10 行）
- 创建 `add_sticker` 工具，包含触发词匹配规则和使用场景
- LLM 根据片段文案自主判断是否需要添加贴纸
- 支持批量片段分析
- 接口与现有 `main_graph.py` 保持兼容

## 当前问题

### TransitionAgent

- 提示词在函数内部构建，不易维护
- LLM 被动返回 JSON，代码解析执行
- 只有"开幕"一个效果，扩展性差

### StickerAgent

- 两阶段逻辑（触发词匹配 → LLM 确认）混合在代码中
- 提示词硬编码在 `_analyze_segment_for_sticker` 函数中
- 触发词逻辑与 LLM 判断分离，不够灵活

## 技术栈

- **框架**: LangGraph + LangChain
- **Agent 模式**: ReAct (Reasoning + Acting) with Tool Calling
- **语言**: Python 3.10+
- **依赖**: langchain-openai, pydantic

## 架构设计

### 与 EffectAgentV2 保持一致的设计模式

```
┌─────────────────────────────────────────────────────────────┐
│  TransitionAgentV2                                          │
│  ├─ 系统提示词: ~5 行核心原则                                 │
│  ├─ 工具: add_opening_effect（含效果选择指南）                │
│  └─ 工具: skip_opening（可选跳过）                           │
├─────────────────────────────────────────────────────────────┤
│  StickerAgentV2                                             │
│  ├─ 系统提示词: ~10 行核心原则                                │
│  ├─ 工具: add_sticker（含触发词和场景指南）                   │
│  ├─ 工具: skip_sticker（跳过当前片段）                       │
│  └─ 批量分析支持                                             │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
c:/Users/64061/capcut-agents/
├── agents/
│   ├── transition_agent.py        # [KEEP] 保留旧版
│   ├── transition_agent_v2.py     # [NEW] Tool-First 重构版本
│   ├── sticker_agent.py           # [KEEP] 保留旧版
│   ├── sticker_agent_v2.py        # [NEW] Tool-First 重构版本
│   └── main_graph.py              # [MODIFY] 切换为 V2 版本
├── tools/
│   ├── transition_agent_tools.py  # [NEW] 开幕 Agent 工具定义
│   ├── sticker_agent_tools.py     # [NEW] 贴纸 Agent 工具定义
│   ├── transition_tools.py        # [EXISTING] 保持兼容
│   └── sticker_tools.py           # [EXISTING] 保持兼容
└── tests/
    ├── test_transition_agent_v2.py # [NEW] 开幕 Agent 测试
    └── test_sticker_agent_v2.py    # [NEW] 贴纸 Agent 测试
```

## 实现要点

### 1. TransitionAgentV2 工具设计

```python
@tool
def add_opening_effect(
    effect_name: Literal["开幕"],
    duration: float,
    reason: str
) -> str:
    """
    为视频添加开幕效果。
    
    ⚠️ 重要：开幕效果应简洁专业，不干扰内容观看。
    
    ## 可用效果
    
    ### "开幕" - 经典开场
    ✅ 适用：所有类型的知识分享、口播讲解
    ✅ 特点：从黑屏展开到正常画面，专业大方
    ✅ 推荐时长：1.5秒
    
    ## 选择原则
    1. 宁可简洁，不要花哨
    2. 时长控制在1-2秒
    3. 如果文案没有特殊氛围需求，选择"开幕"即可
    
    Args:
        effect_name: 效果名称，目前仅支持"开幕"
        duration: 效果时长（秒），推荐1.5秒
        reason: 选择理由
    """
```

### 2. StickerAgentV2 工具设计

```python
@tool
def add_sticker(
    sticker_type: Literal["前方高能", "点赞关注"],
    start_time: float,
    duration: float,
    reason: str
) -> str:
    """
    为视频片段添加贴纸。
    
    ⚠️ 核心原则：贴纸必须与文案中的引导语精确匹配！
    没有出现对应触发词，绝对不能添加贴纸。
    
    ## 可用贴纸类型
    
    ### "前方高能" - 预告重要内容
    **触发词（文案必须包含其一）：**
    - "前方高能"、"高能预警"
    - "注意看"、"重点来了"、"关键来了"
    
    ✅ 适用：预告重要内容、强调关键信息
    ❌ 不适用：文案中没有上述触发词时
    
    ### "点赞关注" - 引导互动
    **触发词（文案必须包含其一）：**
    - "点赞"、"关注"、"收藏"、"转发"
    - "点个赞"、"点个关注"
    - "记得点赞"、"记得关注"
    - "一键三连"
    
    ✅ 适用：明确引导观众进行互动操作
    ❌ 不适用：文案中没有上述触发词时
    
    ## 强制排除条件
    - 文案中没有出现对应触发词
    - 触发词只是作为普通内容提及（非引导语气）
    - 时长 < 1.5秒的片段
    
    Args:
        sticker_type: 贴纸类型名称
        start_time: 开始时间（秒）
        duration: 持续时长（秒），最长3秒
        reason: 使用理由，说明文案中的触发词
    """
```