import json
from typing import Literal
from langchain.tools import tool
from pydantic import BaseModel, Field

class AddTransitionInput(BaseModel):
    """添加开幕效果的输入参数"""
    effect_name: Literal["开幕"] = Field(
        description="开幕效果名称，目前只支持'开幕'"
    )
    duration: float = Field(
        description="开幕效果持续时间（秒），建议1-2秒",
        ge=1,
        le=2
    )
    reason: str = Field(
        description="选择这个开幕效果的理由"
    )

@tool(args_schema=AddTransitionInput)
def add_transition(
    effect_name: str,
    duration: float,
    reason: str
) -> str:
    """
    添加开幕效果到转场列表。
    
    适用场景:
    - 开幕: 视频从黑屏展开到正常画面，适合所有视频的开头引入
    
    使用原则:
    - 开幕效果只在视频第一个片段使用
    - 持续时间建议1-2秒
    
    注意: 此工具仅将开幕效果信息添加到列表，不实际调用接口
    """
    result = {
        "action": "add_transition",
        "effect_name": effect_name,
        "start_time": 0,  # 开幕效果始终从0秒开始
        "duration": duration,
        "reason": reason
    }
    return json.dumps(result, ensure_ascii=False)
