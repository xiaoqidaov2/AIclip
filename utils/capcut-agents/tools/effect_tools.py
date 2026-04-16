import json
from typing import Literal
from langchain.tools import tool
from pydantic import BaseModel, Field

class AddEffectInput(BaseModel):
    """添加特效的输入参数"""
    effect_name: Literal["心动", "光环 I", "气炸了", "笑哭", "难过"] = Field(
        description="特效名称，必须从给定选项中选择"
    )
    start_time: float = Field(
        description="特效开始时间（秒）",
        ge=0
    )
    duration: float = Field(
        description="特效持续时间（秒），建议1-5秒",
        ge=1,
        le=5
    )
    reason: str = Field(
        description="添加特效的理由，说明为什么选择这个特效"
    )

@tool(args_schema=AddEffectInput)
def add_effect(
    effect_name: str,
    start_time: float,
    duration: float,
    reason: str
) -> str:
    """
    添加特效到特效列表。
    
    适用场景:
    - 心动: 强调关键医学信息、重要数据、核心观点
    - 光环 I: 温和的健康建议、关爱提醒
    - 气炸了: 表示生气情绪
    - 笑哭: 无奈吐槽、调侃
    - 难过: 表达悲伤、遗憾或同情情绪
    
    使用原则:
    - 医疗科普视频特效使用率应低于20%
    - 仅在出现强烈情绪或关键重点时考虑使用
    - 避免在严肃内容上加特效
    
    注意: 此工具仅将特效信息添加到列表，不实际调用接口
    """
    result = {
        "action": "add_effect",
        "effect_name": effect_name,
        "start_time": start_time,
        "duration": duration,
        "reason": reason
    }
    return json.dumps(result, ensure_ascii=False)
