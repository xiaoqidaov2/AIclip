"""
Unified Agent - 统一的主Agent

整合原有的特效、贴纸、开幕效果决策逻辑：
- 接收完整上下文（视频主题、整体基调）和单个片段
- 自主决策调用哪些工具（可同时调用多个或全部跳过）
- 支持单次LLM调用同时决策多个视觉元素

架构简化：
- 去掉子agent层，扁平化处理
- 三个Add工具 + 一个Skip工具
- 主Agent拥有全局视角，做出更智能的决策
"""

import json
import logging
from typing import TypedDict

from langchain_core.messages import SystemMessage, HumanMessage

from tools.add_tools import get_add_tools, parse_tool_result

logger = logging.getLogger(__name__)
_LOG_PREFIX = "[agent][unified_agent]"


# =============================================================================
# 系统提示词 - 整合特效、贴纸、开幕的决策逻辑
# =============================================================================

SYSTEM_PROMPT = """你是医疗科普短视频的视觉元素决策助手。

## 你的角色

你负责为视频的每个片段决定是否添加视觉元素（特效、贴纸、开幕效果）。
你拥有完整的视频上下文，能够做出全局最优的决策。

## 核心原则（必须遵守）

1. **专业第一**：医疗科普以内容传递为主，视觉元素只是辅助
2. **宁缺毋滥**：不符合场景的不加，宁可保守不过度
3. **精确匹配**：严格按照场景指南匹配，不凭语义推断
4. **全局视角**：结合整体上下文理解片段在视频中的语义位置

## 可用工具

你可以在一次决策中调用多个工具：

### 特效工具（add_effect）
可选特效：
- "心动" - 强调关键医学信息、重要数据、核心观点 💓
- "光环 I" - 温和的健康建议、关爱提醒 👼
- "气炸了" - 明确禁忌或风险警示 ⚠️
- "笑哭" - 无奈吐槽、调侃 😅
- "难过" - 表达悲伤、遗憾或同情 😢

### 贴纸工具（add_sticker）
可用贴纸：
- "前方高能" - 文案精确出现"前方高能"、"高能预警"、"注意看"、"重点来了"时
- "点赞关注" - 文案精确出现"点赞"、"关注"、"收藏"、"转发"、"一键三连"时

### 开幕工具（add_transition）
可用效果：
- "开幕" - 视频从黑屏展开，适合开头引入（仅第一个片段使用）

### 跳过工具（skip_segment）
- 当不需要添加任何视觉元素时调用

## 决策流程

对于每个片段，按以下顺序思考：

1. **检查是否是第一个片段**
   - 如果是第一个片段，**必须调用 add_transition 添加"开幕"效果**
   - 开幕是视频开头的必要视觉引导，**不受时长限制**，也不受"宁缺毋滥"原则约束

2. **检查贴纸触发词**
   - 扫描文案是否精确匹配贴纸触发词
   - 如果匹配 → 调用 add_sticker
   - 如果不匹配 → 不加贴纸

3. **检查特效场景**
   - 分析文案的情绪和内容类型
   - 如果匹配某个场景 → 调用 add_effect
   - 如果不匹配 → 不加特效

4. **最终决策**
   - 可以同时调用多个工具（特效+贴纸+开幕）
   - 可以只调用一个工具
   - **注意：第一个片段不能调用 skip_segment，必须添加开幕**

## 强制排除条件

以下情况不加特效：
- 片段时长 < 2秒
- 病理机制解释
- 症状说明
- 普通数据罗列
- 严肃的专业内容

## 数量限制

- 每个视频最多5个特效
- 每个视频最多2个贴纸
- **第一个片段必须添加开幕效果**（强制规则，不受其他限制影响）
- 开幕效果只在第一个片段使用，后续片段不再添加


记住：你的决策直接影响视频质量，请谨慎判断！"""


# =============================================================================
# 状态定义
# =============================================================================

class UnifiedAgentState(TypedDict):
    """Unified Agent 状态"""
    # 输入
    video_script: str          # 完整视频文案
    script_summary: str        # 文案总结（可选）
    current_segment: dict      # 当前片段 {text, start, end}
    segment_index: int         # 片段序号（从0开始）
    total_segments: int        # 总片段数
    
    # 已使用的计数（用于限制）
    effects_count: int         # 已添加特效数
    stickers_count: int        # 已添加贴纸数
    has_opening: bool          # 是否已添加开幕效果
    
    # 输出
    tool_calls: list[dict]     # 工具调用结果列表
    error: str | None


# =============================================================================
# Agent 核心类
# =============================================================================

class UnifiedAgent:
    """
    统一的主Agent
    
    负责根据完整上下文和当前片段，自主决策添加哪些视觉元素。
    """
    
    def __init__(self, temperature: float = 0.2):
        """
        初始化 Agent
        
        Args:
            temperature: LLM 温度参数，默认0.2保持保守决策
        """
        self.temperature = temperature
        self.tools = {tool.name: tool for tool in get_add_tools()}
        self.llm = self._create_llm()
        self.llm_with_tools = self.llm.bind_tools(list(self.tools.values()))
        
        logger.info(f"{_LOG_PREFIX} Unified Agent 初始化完成")
    
    def _create_llm(self):
        """创建 LLM 实例"""
        try:
            from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
            from langchain_openai import ChatOpenAI
            
            return ChatOpenAI(
                model=OPENAI_MODEL,
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL if OPENAI_BASE_URL else None,
                temperature=self.temperature
            )
        except Exception as e:
            logger.error(f"{_LOG_PREFIX} LLM 初始化失败: {e}")
            raise
    
    def analyze_segment(
        self,
        video_script: str,
        script_summary: str,
        segment: dict,
        segment_index: int,
        total_segments: int,
        effects_count: int = 0,
        stickers_count: int = 0,
        has_opening: bool = False
    ) -> dict:
        """
        分析单个片段，返回工具调用结果
        
        Args:
            video_script: 完整视频文案
            script_summary: 文案总结
            segment: 当前片段 {text, start, end}
            segment_index: 片段序号（从0开始）
            total_segments: 总片段数
            effects_count: 已添加特效数
            stickers_count: 已添加贴纸数
            has_opening: 是否已添加开幕效果
        
        Returns:
            {
                "tool_calls": [工具调用结果列表],
                "error": 错误信息
            }
        """
        segment_text = segment.get("text", "")
        start_time = segment.get("start", 0)
        end_time = segment.get("end", 0)
        duration = end_time - start_time
        
        # 构建上下文部分
        context_section = f"\n**视频整体上下文：**\n{script_summary}\n" if script_summary else ""
        
        # 构建限制提示
        limits_section = f"""
**当前限制状态：**
- 已添加特效数: {effects_count}/3
- 已添加贴纸数: {stickers_count}/2
- 是否已添加开幕: {"是" if has_opening else "否"}
"""
        
        # 构建输入
        input_text = f"""请分析以下视频片段并做出决策：

{context_section}
{limits_section}

**当前片段信息：**
- 文案: "{segment_text}"
- 时间: {start_time:.1f}s - {end_time:.1f}s
- 时长: {duration:.1f}s
- 片段序号: {segment_index + 1}/{total_segments}（{"第一个片段" if segment_index == 0 else ""}）

**决策要求：**

请根据上下文和限制状态，决定是否为当前片段添加视觉元素。

你可以：
1. 同时调用多个工具（如特效+贴纸）
2. 只调用一个工具
3. 调用 skip_segment 跳过

**请立即做出决策并调用工具。**"""
        
        try:
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=input_text)
            ]
            
            response = self.llm_with_tools.invoke(messages)
            
            tool_calls_result = []
            
            # 检查工具调用
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    logger.info(f"{_LOG_PREFIX} LLM决策: 调用工具 '{tool_name}' 参数: {tool_args}")
                    
                    # 构建结果
                    result = parse_tool_result(
                        self.tools[tool_name].invoke(tool_args)
                    )
                    result["tool_name"] = tool_name
                    tool_calls_result.append(result)
            
            # 如果没有工具调用，默认跳过
            if not tool_calls_result:
                logger.info(f"{_LOG_PREFIX} LLM未调用任何工具，默认跳过")
                tool_calls_result.append({
                    "action": "skip",
                    "reason": "LLM未做决策，默认跳过",
                    "tool_name": "skip_segment"
                })
            
            return {
                "tool_calls": tool_calls_result,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"{_LOG_PREFIX} 分析片段失败: {e}")
            return {
                "tool_calls": [],
                "error": str(e)
            }
    
    def process_video(
        self,
        video_script: str,
        timestamps: list[dict],
        max_effects: int = 5,
        max_stickers: int = 2
    ) -> dict:

        """
        处理整个视频，逐片段分析并收集视觉元素
        
        Args:
            video_script: 完整视频文案
            timestamps: 时间戳列表
            max_effects: 最大特效数
            max_stickers: 最大贴纸数
        
        Returns:
            {
                "transitions": [开幕效果列表],
                "effects": [特效列表],
                "stickers": [贴纸列表],
                "error": 错误信息
            }
        """
        logger.info(f"{_LOG_PREFIX} 开始处理视频，共 {len(timestamps)} 个片段")
        
        # 先总结文案
        script_summary = self._summarize_script(video_script)
        
        # 收集结果
        transitions = []
        effects = []
        stickers = []
        
        effects_count = 0
        stickers_count = 0
        has_opening = False
        
        try:
            for idx, segment in enumerate(timestamps):
                logger.info(
                    f"{_LOG_PREFIX} [{idx + 1}/{len(timestamps)}] 分析片段: "
                    f"\"{segment.get('text', '')[:30]}...\" "
                    f"({segment.get('start', 0):.1f}s-{segment.get('end', 0):.1f}s)"
                )
                
                result = self.analyze_segment(
                    video_script=video_script,
                    script_summary=script_summary,
                    segment=segment,
                    segment_index=idx,
                    total_segments=len(timestamps),
                    effects_count=effects_count,
                    stickers_count=stickers_count,
                    has_opening=has_opening
                )
                
                if result.get("error"):
                    logger.warning(f"{_LOG_PREFIX} 片段分析出错: {result['error']}")
                    continue
                
                # 处理工具调用结果
                for tool_call in result.get("tool_calls", []):
                    action = tool_call.get("action")
                    
                    if action == "add_effect" and effects_count < max_effects:
                        effects.append({
                            "effect_name": tool_call.get("effect_name"),
                            "start_time": tool_call.get("start_time"),
                            "duration": tool_call.get("duration"),
                            "scene": "人物特效",
                            "reason": tool_call.get("reason", "")
                        })
                        effects_count += 1
                        logger.info(f"{_LOG_PREFIX} ✅ 添加特效: {tool_call.get('effect_name')}")
                    
                    elif action == "add_sticker" and stickers_count < max_stickers:
                        stickers.append({
                            "sticker_type": tool_call.get("sticker_type"),
                            "start_time": tool_call.get("start_time"),
                            "duration": tool_call.get("duration"),
                            "trigger_text": tool_call.get("trigger_text"),
                            "reason": tool_call.get("reason", "")
                        })
                        stickers_count += 1
                        logger.info(f"{_LOG_PREFIX} ✅ 添加贴纸: {tool_call.get('sticker_type')}")
                    
                    elif action == "add_transition" and not has_opening:
                        transitions.append({
                            "effect_name": tool_call.get("effect_name"),
                            "start_time": 0,
                            "duration": tool_call.get("duration"),
                            "reason": tool_call.get("reason", "")
                        })
                        has_opening = True
                        logger.info(f"{_LOG_PREFIX} ✅ 添加开幕: {tool_call.get('effect_name')}")
                    
                    elif action == "skip":
                        logger.info(f"{_LOG_PREFIX} ⏭️ 跳过: {tool_call.get('reason', '无理由')}")
            
            logger.info(
                f"{_LOG_PREFIX} 处理完成 - 开幕: {len(transitions)}, "
                f"特效: {len(effects)}, 贴纸: {len(stickers)}"
            )
            
            return {
                "transitions": transitions,
                "effects": effects,
                "stickers": stickers,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"{_LOG_PREFIX} 处理视频失败: {e}")
            return {
                "transitions": transitions,
                "effects": effects,
                "stickers": stickers,
                "error": str(e)
            }
    
    def _summarize_script(self, video_script: str) -> str:
        """
        总结整篇文案，提取关键上下文信息
        
        Args:
            video_script: 完整视频文案
            
        Returns:
            文案总结（控制在200字以内）
        """
        if not video_script or len(video_script) < 100:
            return video_script
        
        summarize_prompt = f"""请用简洁的语言总结以下视频文案的核心内容和主题（100字以内）：

"{video_script}"

总结要点：
1. 视频主题是什么
2. 核心观点或结论
3. 情感基调（严肃/轻松/警示等）
"""
        
        try:
            messages = [HumanMessage(content=summarize_prompt)]
            response = self.llm.invoke(messages)
            summary = response.content.strip()
            logger.info(f"{_LOG_PREFIX} 文案总结完成: {summary[:50]}...")
            return summary
        except Exception as e:
            logger.warning(f"{_LOG_PREFIX} 文案总结失败，使用原文前500字: {e}")
            return video_script[:500]


# =============================================================================
# 兼容性函数 - 保持与旧接口兼容
# =============================================================================

def invoke_unified_agent(
    video_script: str,
    timestamps: list[dict],
    max_effects: int = 5,
    max_stickers: int = 2
) -> dict:

    """
    调用统一Agent的便捷函数
    
    保持与旧版 agent.invoke() 接口兼容
    """
    agent = UnifiedAgent()
    return agent.process_video(
        video_script=video_script,
        timestamps=timestamps,
        max_effects=max_effects,
        max_stickers=max_stickers
    )
