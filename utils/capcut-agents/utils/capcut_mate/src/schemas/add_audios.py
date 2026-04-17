from pydantic import BaseModel, Field
from typing import List, Optional


class AudioInfoItem(BaseModel):
    """音频信息项"""
    audio_url: str = Field(..., description="音频文件的URL地址或本地路径")
    start: int = Field(..., description="开始时间(微秒)")
    end: int = Field(..., description="结束时间(微秒)")
    duration: Optional[int] = Field(default=None, description="音频总时长(微秒)，不传则自动检测")
    volume: Optional[float] = Field(default=1.0, description="音量[0.0, 2.0]")
    audio_effect: Optional[str] = Field(default=None, description="音频效果名称")


class AddAudiosRequest(BaseModel):
    """批量添加音频请求参数"""
    draft_url: str = Field(..., description="草稿URL")
    audio_infos: List[AudioInfoItem] = Field(default=[], description="音频信息列表")


class AddAudiosResponse(BaseModel):
    """添加音频响应参数"""
    draft_url: str = Field(default="", description="草稿URL")
    track_id: str = Field(default="", description="音频轨道ID")
    audio_ids: List[str] = Field(default=[], description="音频ID列表")