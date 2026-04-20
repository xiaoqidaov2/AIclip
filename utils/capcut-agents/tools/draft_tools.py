"""
草稿工具节点 - 负责草稿的创建和保存
"""

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


class CreateDraftInput(BaseModel):
    """创建草稿的输入参数"""
    draft_name: str = Field(description="草稿名称")
    width: int = Field(default=1080, description="视频宽度")
    height: int = Field(default=1920, description="视频高度")
    fps: int = Field(default=30, description="帧率")


class SaveDraftInput(BaseModel):
    """保存草稿的输入参数"""
    draft_id: str = Field(description="草稿ID")
    output_path: str | None = Field(default=None, description="保存路径（可选）")


class CreateDraftOutput(BaseModel):
    """创建草稿的输出"""
    success: bool
    draft_id: str | None = None
    draft_path: str | None = None
    error: str | None = None


class SaveDraftOutput(BaseModel):
    """保存草稿的输出"""
    success: bool
    draft_path: str | None = None
    error: str | None = None


@tool(args_schema=CreateDraftInput, response_format="content_and_artifact")
def create_draft_tool(
    draft_name: str,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30
) -> tuple[str, dict]:
    """
    创建一个新的剪映草稿
    
    参数:
        draft_name: 草稿名称
        width: 视频宽度，默认1080
        height: 视频高度，默认1920（竖屏）
        fps: 帧率，默认30
    
    返回:
        包含草稿ID和路径的结果
    """
    try:
        from urllib.parse import parse_qs, urlparse

        try:
            from src.service.create_draft import create_draft as service_create_draft
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError("src.service.create_draft is unavailable") from exc

        draft_url = service_create_draft(width=width, height=height)

        parsed = urlparse(draft_url)
        draft_id = parse_qs(parsed.query).get("draft_id", [""])[0]

        from config import DRAFT_DIR
        draft_path = Path(DRAFT_DIR) / draft_id
        
        result = {
            "success": True,
            "draft_id": draft_id,
            "draft_path": str(draft_path),
            "width": width,
            "height": height,
            "fps": fps
        }
        
        content = f"✅ 草稿创建成功\n- 草稿ID: {draft_id}\n- 路径: {draft_path}"
        return content, result
        
    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
        content = f"❌ 草稿创建失败: {e}"
        return content, result


@tool(args_schema=SaveDraftInput, response_format="content_and_artifact")
def save_draft_tool(
    draft_id: str,
    output_path: str | None = None
) -> tuple[str, dict]:
    """
    保存草稿到指定路径
    
    参数:
        draft_id: 草稿ID
        output_path: 可选的保存路径
    
    返回:
        保存结果
    """
    try:
        from config import DRAFT_DIR

        draft_path = Path(DRAFT_DIR) / draft_id

        
        if not draft_path.exists():
            return f"❌ 草稿不存在: {draft_id}", {"success": False, "error": "Draft not found"}
        
        # 如果指定了输出路径，复制到该路径
        if output_path:
            import shutil
            dest_path = Path(output_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(draft_path, dest_path, dirs_exist_ok=True)
            final_path = str(dest_path)
        else:
            final_path = str(draft_path)
        
        result = {
            "success": True,
            "draft_path": final_path
        }
        
        content = f"✅ 草稿保存成功\n- 路径: {final_path}"
        return content, result
        
    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
        content = f"❌ 草稿保存失败: {e}"
        return content, result
