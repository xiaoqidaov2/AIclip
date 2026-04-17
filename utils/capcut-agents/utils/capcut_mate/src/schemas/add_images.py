from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ImageInfoItem(BaseModel):
    """图片信息项"""
    image_url: str = Field(..., description="图片文件的URL地址或本地路径")
    width: int = Field(..., description="图片宽度(像素)")
    height: int = Field(..., description="图片高度(像素)")
    start: int = Field(..., description="显示开始时间(微秒)")
    end: int = Field(..., description="显示结束时间(微秒)")
    in_animation: Optional[str] = Field(default=None, description="入场动画类型")
    out_animation: Optional[str] = Field(default=None, description="出场动画类型")
    loop_animation: Optional[str] = Field(default=None, description="循环动画类型")
    in_animation_duration: Optional[int] = Field(default=None, description="入场动画时长(微秒)")
    out_animation_duration: Optional[int] = Field(default=None, description="出场动画时长(微秒)")
    loop_animation_duration: Optional[int] = Field(default=None, description="循环动画时长(微秒)")
    transition: Optional[str] = Field(default=None, description="转场效果类型")
    transition_duration: Optional[int] = Field(default=500000, description="转场效果时长(微秒)")


class AddImagesRequest(BaseModel):
    """批量添加图片请求参数"""
    draft_url: str = Field(..., description="草稿URL")
    image_infos: List[ImageInfoItem] = Field(default=[], description="图片信息列表")
    alpha: float = Field(default=1.0, description="全局透明度[0, 1]")
    scale_x: float = Field(default=1.0, description="X轴缩放比例")
    scale_y: float = Field(default=1.0, description="Y轴缩放比例")
    transform_x: int = Field(default=0, description="X轴位置偏移(像素)")
    transform_y: int = Field(default=0, description="Y轴位置偏移(像素)")


class SegmentInfo(BaseModel):
    """片段信息"""
    id: str = Field(..., description="片段ID")
    start: int = Field(..., description="开始时间(微秒)")
    end: int = Field(..., description="结束时间(微秒)")


class AddImagesResponse(BaseModel):
    """添加图片响应参数"""
    draft_url: str = Field(default="", description="草稿URL")
    track_id: str = Field(default="", description="视频轨道ID")
    image_ids: List[str] = Field(default=[], description="图片ID列表")
    segment_ids: List[str] = Field(default=[], description="片段ID列表")
    segment_infos: List[SegmentInfo] = Field(default=[], description="片段信息列表")