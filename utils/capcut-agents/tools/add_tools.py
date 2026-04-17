"""
Add工具集 - 聚合入口
从各独立模块导入工具并提供统一获取接口
"""

import json
from .effect_tools import add_effect, AddEffectInput
from .sticker_tools import add_sticker, AddStickerInput
from .transition_tools import add_transition, AddTransitionInput
from .skip_tools import skip_segment, SkipSegmentInput

# ============== 工具获取函数 ==============

def get_add_tools():
    """获取所有Add工具列表"""
    return [add_effect, add_sticker, add_transition, skip_segment]


def parse_tool_result(result_str: str) -> dict:
    """解析工具返回的JSON字符串"""
    return json.loads(result_str)
