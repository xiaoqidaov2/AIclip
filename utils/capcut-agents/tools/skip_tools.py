import json
from langchain.tools import tool
from pydantic import BaseModel, Field

class SkipSegmentInput(BaseModel):
    """跳过片段的输入参数"""
    reason: str = Field(
        description="跳过当前片段的理由"
    )

@tool(args_schema=SkipSegmentInput)
def skip_segment(reason: str) -> str:
    """
    跳过当前片段，不添加任何视觉元素。
    
    适用场景:
    - 片段内容严肃专业，不适合加特效或贴纸
    - 片段时长太短
    - 没有匹配的触发词或情绪点
    - 已达到特效/贴纸上限
    
    这是默认选择，当不需要添加任何元素时使用
    """
    result = {
        "action": "skip",
        "reason": reason
    }
    return json.dumps(result, ensure_ascii=False)
