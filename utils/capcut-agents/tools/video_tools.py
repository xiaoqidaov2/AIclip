"""
视频工具节点 - 负责视频添加和导出
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# 添加 capcut_mate 到 Python 路径
_capcut_mate_path = str(Path(__file__).resolve().parents[1] / "utils" / "capcut_mate")
if _capcut_mate_path not in sys.path:
    sys.path.insert(0, _capcut_mate_path)

from langchain.tools import tool

from pydantic import BaseModel, Field

import config
from src.service.add_videos import add_videos_async
from src.service.export_video import export_video


class AddVideosInput(BaseModel):
    """添加视频的输入参数"""
    draft_id: str = Field(description="草稿ID")
    video_files: list[dict] = Field(description="视频文件列表，每个包含path和optional字段")
    max_concurrent: int = Field(default=3, description="最大并发数")


class ExportVideoInput(BaseModel):
    """导出视频的输入参数"""
    draft_id: str = Field(description="草稿ID")
    output_path: str | None = Field(default=None, description="导出路径（可选）")


@tool(args_schema=AddVideosInput, response_format="content_and_artifact")
def add_videos_tool(
    draft_id: str,
    video_files: list[dict],
    max_concurrent: int = 3
) -> tuple[str, dict]:
    """
    添加视频文件到草稿
    
    参数:
        draft_id: 草稿ID
        video_files: 视频文件列表，每项包含:
            - path: 视频文件路径
            - optional: 是否可选（可选，默认False）
        max_concurrent: 最大并发下载数，默认3
    
    返回:
        添加结果，包含成功和失败的视频列表
    """
    try:
        # 构建 draft_url
        draft_url = f"{config.DOWNLOAD_URL}openapi/capcut-mate/v1/get_draft?draft_id={draft_id}"
        
        # 转换 video_files 为 video_infos JSON 字符串
        video_infos_list = []
        for vf in video_files:
            duration = _get_video_duration(vf["path"])
            video_infos_list.append({
                "video_url": vf["path"],
                "start": 0,
                "end": duration
            })
        video_infos = json.dumps(video_infos_list)
        
        # 运行异步添加视频
        draft_url, track_id, video_ids, segment_ids = asyncio.run(add_videos_async(
            draft_url=draft_url,
            video_infos=video_infos
        ))
        
        result = {
            "success": video_files,
            "failed": [],
            "draft_url": draft_url,
            "track_id": track_id,
            "video_ids": video_ids,
            "segment_ids": segment_ids
        }
        
        content = f"✅ 视频添加完成\n- 成功: {len(video_files)}个\n- draft_url: {draft_url}"
        
        return content, result
        
    except Exception as e:
        result = {
            "success": [],
            "failed": video_files,
            "error": str(e)
        }
        content = f"❌ 视频添加失败: {e}"
        return content, result


# 辅助函数：获取视频时长（微秒）
def _get_video_duration(path: str) -> int:
    """获取视频时长（微秒）"""
    try:
        from src.pyJianYingDraft.local_materials import VideoMaterial
        vm = VideoMaterial(path)
        return vm.duration
    except Exception:
        return 5000000  # 默认5秒（微秒）


@tool(args_schema=ExportVideoInput, response_format="content_and_artifact")
def export_video_tool(
    draft_id: str,
    output_path: str | None = None
) -> tuple[str, dict]:
    """
    导出草稿为视频文件
    
    参数:
        draft_id: 草稿ID
        output_path: 可选的导出路径
    
    返回:
        导出结果
    """
    try:
        # 构建导出参数
        from src.schemas.export_video import ExportVideoRequest

        
        request = ExportVideoRequest(

            draft_id=draft_id,
            output_path=output_path
        )
        
        result = export_video(request)
        
        if result.success:
            content = f"✅ 视频导出成功\n- 输出路径: {result.output_path}"
            return content, {"success": True, "output_path": result.output_path}
        else:
            content = f"❌ 视频导出失败\n- 错误: {result.error}"
            return content, {"success": False, "error": result.error}
        
    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
        content = f"❌ 视频导出失败: {e}"
        return content, result
