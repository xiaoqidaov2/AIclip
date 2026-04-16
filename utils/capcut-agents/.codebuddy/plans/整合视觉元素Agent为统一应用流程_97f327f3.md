---
name: 整合视觉元素Agent为统一应用流程
overview: 将 transition_agent、effect_agent、sticker_agent 三个Agent整合为"仅推荐"模式，最后通过统一的 apply_visual_elements_tool 一次性更新草稿，减少IO次数并提升原子性。
todos:
  - id: create-visual-elements-tool
    content: 新建 tools/visual_elements_tools.py，实现 apply_visual_elements_tool 统一应用工具
    status: completed
  - id: modify-effect-agent
    content: 修改 agents/effect_agent_v2.py，移除添加逻辑，只返回 effects 列表
    status: completed
    dependencies:
      - create-visual-elements-tool
  - id: modify-sticker-agent
    content: 修改 agents/sticker_agent_v2.py，移除添加逻辑，只返回 stickers 列表
    status: completed
    dependencies:
      - create-visual-elements-tool
  - id: modify-transition-agent
    content: 修改 agents/transition_agent_v2.py，移除添加逻辑，只返回 opening_effect
    status: completed
    dependencies:
      - create-visual-elements-tool
  - id: modify-main-graph
    content: 修改 agents/main_graph.py，新增 node_apply_visual_elements 节点，调整工作流边
    status: completed
    dependencies:
      - modify-effect-agent
      - modify-sticker-agent
      - modify-transition-agent
  - id: cleanup-old-tools
    content: 删除 tools 中的 add_effects_tool、add_transitions_tool、add_stickers_tool 函数
    status: completed
    dependencies:
      - modify-main-graph
---

## 产品概述

将三个视觉元素 Agent（开幕效果、特效、贴纸）的草稿更新操作整合为一次，减少 IO 开销，提升原子性和一致性。

## 核心功能

1. **Agent 层改造**：三个 Agent 只负责推荐视觉元素，不再直接更新草稿
2. **统一应用工具**：新增 `apply_visual_elements_tool`，一次性应用所有视觉元素
3. **删除冗余工具**：删除 `add_effects_tool`、`add_transitions_tool`、`add_stickers_tool`
4. **工作流优化**：在 `main_graph.py` 中新增统一应用节点

## 收益

- 草稿 IO 次数：3 次 → 1 次
- 原子性：部分生效 → 整体原子
- 支持整体回滚和预处理验证

## 技术栈

- 框架：Python + LangGraph + LangChain
- 底层服务：直接操作 `DRAFT_CACHE` 中的 `ScriptFile` 对象

## 实现方案

### 核心策略

**问题**：现有底层服务 `add_effects()` 和 `add_sticker()` 每次调用都会执行 `script.save()`，无法实现批量合并。

**解决方案**：新建统一工具直接操作 `DRAFT_CACHE` 中的 `ScriptFile` 对象，绕过底层服务的自动保存逻辑，只在最后调用一次 `script.save()`。

### 架构设计

```mermaid
flowchart TD
    subgraph 推荐阶段
        A[transition_agent] --> A1[opening_effect]
        B[effect_agent] --> B1[effects\[\]]
        C[sticker_agent] --> C1[stickers\[\]]
    end
    
    A1 --> D[apply_visual_elements_tool]
    B1 --> D
    C1 --> D
    
    D --> E[直接操作 DRAFT_CACHE]
    E --> F[script.save\(\) - 仅一次]
```

### 目录结构

```
c:\Users\64061\capcut-agents\
├── tools/
│   ├── visual_elements_tools.py   # [NEW] 统一视觉元素应用工具
│   ├── effect_tools.py            # [MODIFY] 删除 add_effects_tool，保留推荐相关函数
│   ├── sticker_tools.py           # [MODIFY] 删除 add_stickers_tool，保留搜索相关函数
│   └── transition_tools.py        # [MODIFY] 删除 add_transitions_tool，保留配置函数
├── agents/
│   ├── effect_agent_v2.py         # [MODIFY] 移除添加逻辑，只返回 effects[]
│   ├── sticker_agent_v2.py        # [MODIFY] 移除添加逻辑，只返回 stickers[]
│   ├── transition_agent_v2.py     # [MODIFY] 移除添加逻辑，只返回 opening_effect
│   └── main_graph.py              # [MODIFY] 新增统一应用节点，调整工作流
```

## 实现细节

### 关键点：绕过底层服务的自动保存

现有底层服务会自动保存：

- `src/service/add_effects.py` 第82行：`script.save()`
- `src/service/add_sticker.py` 第111-116行：`script.save()`

统一工具的实现方式：

1. 从 `DRAFT_CACHE` 获取 `ScriptFile` 对象
2. 直接调用内部的轨道添加和片段添加逻辑
3. 只在最后调用一次 `script.save()`

### 新工具核心逻辑

```python
# tools/visual_elements_tools.py 核心逻辑

def apply_visual_elements_tool(draft_id, opening_effect, effects, stickers):
    # 1. 从缓存获取草稿对象
    from src.utils.draft_cache import DRAFT_CACHE
    script = DRAFT_CACHE[draft_id]
    
    # 2. 添加开幕效果（如果有）
    if opening_effect:
        # 直接操作 script，不调用会自动保存的 add_effects 服务
        ...
    
    # 3. 批量添加特效（如果有）
    for effect in effects:
        ...
    
    # 4. 批量添加贴纸（如果有）
    for sticker in stickers:
        ...
    
    # 5. 统一保存（仅一次）
    script.save()
```