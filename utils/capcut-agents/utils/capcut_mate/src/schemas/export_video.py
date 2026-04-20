from pydantic import BaseModel, Field
from typing import Optional


class ExportVideoRequest(BaseModel):
    """导出视频请求参数"""
    draft_id: str = Field(..., description="草稿ID")
    output_path: Optional[str] = Field(default=None, description="导出路径（可选）")


class ExportVideoResponse(BaseModel):
    """导出视频响应参数"""
    success: bool = Field(..., description="是否成功")
    output_path: Optional[str] = Field(default=None, description="输出文件路径")
    error: Optional[str] = Field(default=None, description="错误信息")
