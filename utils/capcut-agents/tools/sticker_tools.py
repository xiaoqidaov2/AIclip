import json
from typing import Literal
from langchain.tools import tool
from pydantic import BaseModel, Field

class AddStickerInput(BaseModel):
    """添加贴纸的输入参数"""
    sticker_type: Literal["前方高能", "点赞关注"] = Field(
        description="贴纸类型，必须从给定选项中选择"
    )
    start_time: float = Field(
        description="贴纸开始时间（秒）",
        ge=0
    )
    duration: float = Field(
        description="贴纸持续时间（秒），建议1.5-3秒",
        ge=1.5,
        le=3
    )
    trigger_text: str = Field(
        description="触发贴纸的文案内容，必须与片段中的文本精确匹配"
    )
    reason: str = Field(
        description="添加贴纸的理由"
    )

@tool(args_schema=AddStickerInput)
def add_sticker(
    sticker_type: str,
    start_time: float,
    duration: float,
    trigger_text: str,
    reason: str
) -> str:
    """
    添加贴纸到贴纸列表。
    
    适用场景:
    - 前方高能: 文案中出现"前方高能"、"高能预警"、"注意看"、"重点来了"、"关键来了"时使用
    - 点赞关注: 文案中出现"点赞"、"关注"、"收藏"、"转发"、"一键三连"等引导语时使用
    
    使用原则:
    - 贴纸必须与文案中的引导语精确匹配
    - 如果文案中没有对应的引导语，绝对不能加贴纸
    - 一个视频最多加2个贴纸
    
    注意: 此工具仅将贴纸信息添加到列表，不实际调用接口
    """
    result = {
        "action": "add_sticker",
        "sticker_type": sticker_type,
        "start_time": start_time,
        "duration": duration,
        "trigger_text": trigger_text,
        "reason": reason
    }
    return json.dumps(result, ensure_ascii=False)
