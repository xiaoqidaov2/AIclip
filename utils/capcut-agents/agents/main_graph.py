"""
主工作流图 - 编排完整的视频生成流程

工作流程:
1. create_draft → 创建草稿
2. add_videos → 添加视频
3. unified_agent → 主Agent（逐片段分析，决定特效/贴纸/开幕）
4. apply_visual_elements → 统一应用所有视觉元素
5. save_draft → 保存草稿
6. export_video → 导出视频

架构说明:
- 单Agent + 多工具模式，主Agent拥有全局视角
- 主Agent根据上下文自主决策调用哪些工具
- 统一应用节点一次性添加所有视觉元素，减少 IO 次数
"""

import logging
from typing import Any, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from tools.draft_tools import create_draft_tool, save_draft_tool
from tools.video_tools import add_videos_tool, export_video_tool
from tools.visual_elements_tools import apply_visual_elements_tool
from agents.unified_agent import UnifiedAgent

logger = logging.getLogger(__name__)

# 统一日志前缀格式: [workflow][节点名]
def _log(node: str, msg: str, level: str = "info"):
    prefix = f"[workflow][{node}]"
    getattr(logger, level)(f"{prefix} {msg}")


class VideoWorkflowState(TypedDict):
    """主工作流状态"""
    # 输入参数
    draft_name: str
    video_files: list[dict]
    video_script: str
    timestamps: list[dict]
    max_effects: int
    max_stickers: int
    
    # 中间状态
    draft_id: str | None
    draft_path: str | None
    
    # Agent结果
    transitions: list[dict]
    effects: list[dict]
    stickers: list[dict]
    
    # 输出结果
    final_video_path: str | None
    error: str | None


def create_video_workflow():
    """
    创建完整的视频生成工作流
    """
    
    # 初始化统一Agent
    unified_agent = UnifiedAgent()
    
    def node_create_draft(state: VideoWorkflowState) -> VideoWorkflowState:
        """创建草稿节点"""
        node = "create_draft"
        _log(node, "开始创建草稿...")
        try:
            width, height = 1080, 1920  # 默认竖屏
            
            content, result = create_draft_tool.func(
                draft_name=state.get("draft_name", "自动创建草稿"),
                width=width,
                height=height,
                fps=30
            )
            
            if result.get("success"):
                state["draft_id"] = result.get("draft_id")
                state["draft_path"] = result.get("draft_path")
                _log(node, f"草稿创建成功, draft_id={state['draft_id']}")
            else:
                state["error"] = result.get("error", "创建草稿失败")
                _log(node, f"草稿创建失败: {state['error']}", "error")
            
        except Exception as e:
            state["error"] = f"创建草稿失败: {str(e)}"
            _log(node, f"异常: {str(e)}", "error")
        
        return state
    
    def node_add_videos(state: VideoWorkflowState) -> VideoWorkflowState:
        """添加视频节点"""
        node = "add_videos"
        if state.get("error"):
            _log(node, f"跳过（上游错误: {state['error']})", "warning")
            return state
        
        video_count = len(state.get("video_files", []))
        _log(node, f"开始添加 {video_count} 个视频到草稿 {state['draft_id']}...")
        try:
            content, result = add_videos_tool.func(
                draft_id=state["draft_id"],
                video_files=state.get("video_files", []),
                max_concurrent=3
            )
            
            if not result.get("success"):
                state["error"] = f"添加视频失败: {result.get('error', '未知错误')}"
                _log(node, f"添加视频失败: {state['error']}", "error")
            else:
                _log(node, f"视频添加成功, 共 {video_count} 个")
            
        except Exception as e:
            state["error"] = f"添加视频失败: {str(e)}"
            _log(node, f"异常: {str(e)}", "error")
        
        return state
    
    def node_unified_agent(state: VideoWorkflowState) -> VideoWorkflowState:
        """
        统一Agent节点 - 逐片段分析并收集视觉元素
        
        主Agent拥有完整上下文，自主决策：
        - 是否添加开幕效果（仅第一个片段）
        - 是否添加特效
        - 是否添加贴纸
        - 或跳过
        """
        node = "unified_agent"
        if state.get("error"):
            _log(node, f"跳过（上游错误: {state['error']})", "warning")
            return state
        
        max_effects = state.get("max_effects", 5)
        max_stickers = state.get("max_stickers", 2)

        
        _log(
            node, 
            f"启动主Agent，共 {len(state.get('timestamps', []))} 个片段，"
            f"最大特效数={max_effects}, 最大贴纸数={max_stickers}"
        )
        
        try:
            result = unified_agent.process_video(
                video_script=state.get("video_script", ""),
                timestamps=state.get("timestamps", []),
                max_effects=max_effects,
                max_stickers=max_stickers
            )
            
            if result.get("error"):
                _log(node, f"主Agent执行失败（不阻断流程）: {result['error']}", "warning")
            else:
                # 收集结果
                transitions = result.get("transitions", [])
                effects = result.get("effects", [])
                stickers = result.get("stickers", [])
                
                state["transitions"] = transitions
                state["effects"] = effects
                state["stickers"] = stickers
                
                _log(node, f"分析完成 - 开幕: {len(transitions)}, 特效: {len(effects)}, 贴纸: {len(stickers)}")
                
                # 详细日志
                for t in transitions:
                    _log(node, f"  开幕: {t.get('effect_name')} ({t.get('duration')}秒) - {t.get('reason', '')}")
                
                for e in effects:
                    start = e.get('start_time', 0)
                    duration = e.get('duration', 0)
                    _log(node, f"  特效: {e.get('effect_name')} {start:.1f}s-{start+duration:.1f}s ({e.get('reason', '')})")
                
                for s in stickers:
                    start = s.get('start_time', 0)
                    duration = s.get('duration', 0)
                    _log(node, f"  贴纸: {s.get('sticker_type')} {start:.1f}s-{start+duration:.1f}s ({s.get('reason', '')})")
            
        except Exception as e:
            _log(node, f"异常（不阻断流程）: {str(e)}", "warning")
        
        return state
    
    def node_apply_visual_elements(state: VideoWorkflowState) -> VideoWorkflowState:
        """统一应用所有视觉元素节点 - 一次性添加并保存"""
        node = "apply_visual_elements"
        if state.get("error"):
            _log(node, f"跳过（上游错误: {state['error']})", "warning")
            return state
        
        # 收集所有视觉元素
        opening = state.get("transitions", [{}])[0] if state.get("transitions") else None
        effects = state.get("effects", [])
        stickers = state.get("stickers", [])
        
        # 如果没有任何视觉元素，跳过
        if not any([opening, effects, stickers]):
            _log(node, "无视觉元素需要应用，跳过")
            return state
        
        _log(node, f"应用视觉元素: 开幕={bool(opening)}, 特效={len(effects)}, 贴纸={len(stickers)}")
        
        try:
            content, result = apply_visual_elements_tool.func(
                draft_id=state["draft_id"],
                opening_effect=opening,
                effects=effects,
                stickers=stickers
            )
            
            if result.get("success"):
                summary = []
                if result.get("opening"):
                    summary.append(f"开幕: {result['opening'].get('effect_name')}")
                if result["effects"]["added"] > 0:
                    summary.append(f"特效: {result['effects']['added']}个")
                if result["stickers"]["added"] > 0:
                    summary.append(f"贴纸: {result['stickers']['added']}个")
                _log(node, f"应用完成 - {', '.join(summary)}")
            else:
                _log(node, f"应用失败: {result.get('error')}", "warning")
            
        except Exception as e:
            _log(node, f"异常（不阻断流程）: {str(e)}", "warning")
        
        return state
    
    def node_save_draft(state: VideoWorkflowState) -> VideoWorkflowState:
        """保存草稿节点"""
        node = "save_draft"
        if state.get("error"):
            _log(node, f"跳过（上游错误: {state['error']})", "warning")
            return state
        
        _log(node, f"保存草稿, draft_id={state['draft_id']}...")
        try:
            content, result = save_draft_tool.func(
                draft_id=state["draft_id"]
            )
            
            if not result.get("success"):
                state["error"] = f"保存草稿失败: {result.get('error', '未知错误')}"
                _log(node, f"保存草稿失败: {state['error']}", "error")
            else:
                _log(node, f"草稿保存成功, 路径={result.get('draft_path')}")
            
        except Exception as e:
            state["error"] = f"保存草稿失败: {str(e)}"
            _log(node, f"异常: {str(e)}", "error")
        
        return state
    
    def node_export_video(state: VideoWorkflowState) -> VideoWorkflowState:
        """导出视频节点"""
        node = "export_video"
        if state.get("error"):
            _log(node, f"跳过（上游错误: {state['error']})", "warning")
            return state
        
        _log(node, f"开始导出视频, draft_id={state['draft_id']}...")
        try:
            content, result = export_video_tool.func(
                draft_id=state["draft_id"]
            )
            
            if result.get("success"):
                state["final_video_path"] = result.get("output_path")
                _log(node, f"视频导出成功, 输出路径={state['final_video_path']}")
            else:
                state["error"] = f"导出视频失败: {result.get('error', '未知错误')}"
                _log(node, f"导出视频失败: {state['error']}", "error")
            
        except Exception as e:
            state["error"] = f"导出视频失败: {str(e)}"
            _log(node, f"异常: {str(e)}", "error")
        
        return state
    
    def should_continue(state: VideoWorkflowState) -> str:
        """判断是否继续执行"""
        if state.get("error"):
            return "error"
        return "continue"
    
    # 构建工作流
    workflow = StateGraph(VideoWorkflowState)
    
    # 添加节点
    workflow.add_node("create_draft", node_create_draft)
    workflow.add_node("add_videos", node_add_videos)
    workflow.add_node("unified_agent", node_unified_agent)            # 新的统一Agent节点
    workflow.add_node("apply_visual_elements", node_apply_visual_elements)
    workflow.add_node("save_draft", node_save_draft)
    workflow.add_node("export_video", node_export_video)
    workflow.add_node("error_handler", lambda s: s)
    
    # 设置入口
    workflow.set_entry_point("create_draft")
    
    # 设置流程边 - 简化后的流程
    workflow.add_edge("create_draft", "add_videos")
    workflow.add_edge("add_videos", "unified_agent")                  # 直接到统一Agent
    workflow.add_edge("unified_agent", "apply_visual_elements")
    workflow.add_edge("apply_visual_elements", "save_draft")
    workflow.add_edge("save_draft", "export_video")
    workflow.add_edge("export_video", END)
    workflow.add_edge("error_handler", END)
    
    # 使用内存检查点
    checkpointer = MemorySaver()
    
    return workflow.compile(checkpointer=checkpointer)


class VideoWorkflow:
    """视频工作流包装类"""
    
    def __init__(self):
        self.graph = create_video_workflow()
    
    def invoke(self, 
               draft_name: str,
               video_files: list[dict],
               video_script: str,
               timestamps: list[dict],
               max_effects: int = 5,
               max_stickers: int = 2) -> dict:

        """
        执行完整的视频生成工作流
        """
        initial_state: VideoWorkflowState = {
            "draft_name": draft_name,
            "video_files": video_files,
            "video_script": video_script,
            "timestamps": timestamps,
            "max_effects": max_effects,
            "max_stickers": max_stickers,
            "draft_id": None,
            "draft_path": None,
            "transitions": [],
            "effects": [],
            "stickers": [],
            "final_video_path": None,
            "error": None
        }
        
        config = {"configurable": {"thread_id": draft_name}}
        
        result = self.graph.invoke(initial_state, config=config)
        
        return {
            "success": result.get("error") is None,
            "draft_id": result.get("draft_id"),
            "draft_path": result.get("draft_path"),
            "final_video_path": result.get("final_video_path"),
            "transitions": result.get("transitions", []),
            "effects": result.get("effects", []),
            "stickers": result.get("stickers", []),
            "error": result.get("error")
        }
    
    def stream(self, **kwargs) -> Any:
        """流式执行工作流"""
        initial_state: VideoWorkflowState = {
            "draft_name": kwargs.get("draft_name", "未命名"),
            "video_files": kwargs.get("video_files", []),
            "video_script": kwargs.get("video_script", ""),
            "timestamps": kwargs.get("timestamps", []),
            "max_effects": kwargs.get("max_effects", 5),
            "max_stickers": kwargs.get("max_stickers", 2),

            "draft_id": None,
            "draft_path": None,
            "transitions": [],
            "effects": [],
            "stickers": [],
            "final_video_path": None,
            "error": None
        }
        
        config = {"configurable": {"thread_id": kwargs.get("draft_name", "default")}}
        
        for state in self.graph.stream(initial_state, config=config):
            yield state
