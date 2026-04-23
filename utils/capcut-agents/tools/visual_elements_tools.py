"""
视觉元素统一应用工具 - 一次性添加所有视觉元素到草稿

整合开幕效果、特效、贴纸三种视觉元素，只触发一次草稿保存。
"""

import logging
import sys
from pathlib import Path
from typing import Tuple

from langchain.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
_LOG_PREFIX = "[tool][visual_elements]"

# 添加 capcut_mate 路径
CAPCUT_MATE_PATH = Path(__file__).parent.parent / "utils" / "capcut_mate"
if str(CAPCUT_MATE_PATH) not in sys.path:
    sys.path.insert(0, str(CAPCUT_MATE_PATH))


# 概念名称到剪映实际特效名称的映射
OPENING_EFFECT_MAP = {
    "开幕": "开幕",
    "复古DV": "复古DV",
    "赛博朋克 I": "赛博朋克",
    "星光": "星光",
    "梦境": "梦境",
    "电影感": "电影感",
}


# 贴纸类型到剪映真实资源 ID 的映射
STICKER_TYPE_MAP = {
    "前方高能": "7358279242573991222",  # 前方高能爆炸框互动文字
    "点赞关注": "7457448593948003646",  # 互动引导关注点赞评论
    "留言评论": "7600799910450990398",  # 涂鸦留言评论文字
}


class ApplyVisualElementsInput(BaseModel):

    """统一应用视觉元素的输入参数"""
    draft_id: str = Field(description="草稿ID")
    opening_effect: dict | None = Field(default=None, description="开幕效果，包含 effect_name, start_time, duration")
    effects: list[dict] | None = Field(default=None, description="特效列表")
    stickers: list[dict] | None = Field(default=None, description="贴纸列表")


@tool(args_schema=ApplyVisualElementsInput, response_format="content_and_artifact")
def apply_visual_elements_tool(
    draft_id: str,
    opening_effect: dict | None = None,
    effects: list[dict] | None = None,
    stickers: list[dict] | None = None,
) -> Tuple[str, dict]:
    """
    一次性应用所有视觉元素到草稿
    
    参数:
        draft_id: 草稿ID
        opening_effect: 开幕效果，包含:
            - effect_name: 特效名称（如"开幕"）
            - start_time: 开始时间（秒）
            - duration: 持续时间（秒）
        effects: 特效列表，每项包含:
            - effect_name: 特效名称
            - start_time: 开始时间（秒）
            - duration: 持续时间（秒）
        stickers: 贴纸列表，每项包含:
            - sticker_id: 贴纸ID
            - start_time: 开始时间（秒）
            - duration: 持续时间（秒）
            - scale: 缩放比例（可选）
            - transform_x: X偏移（可选）
            - transform_y: Y偏移（可选）
    
    返回:
        应用结果，包含各类元素的添加统计
    """
    from src.utils.draft_cache import DRAFT_CACHE
    from src.utils import helper
    from src.pyJianYingDraft import TrackType, Timerange, EffectSegment, StickerSegment, ClipSettings
    from src.pyJianYingDraft.metadata import VideoSceneEffectType, VideoCharacterEffectType
    import src.pyJianYingDraft as draft
    
    logger.info(f"{_LOG_PREFIX} 开始应用视觉元素: draft_id={draft_id}")
    
    # 1. 验证草稿存在
    if draft_id not in DRAFT_CACHE:
        error_msg = f"草稿不存在: draft_id={draft_id}"
        logger.error(f"{_LOG_PREFIX} {error_msg}")
        return error_msg, {"success": False, "error": error_msg}
    
    script = DRAFT_CACHE[draft_id]
    
    results = {
        "success": True,
        "opening": None,
        "effects": {"added": 0, "failed": 0, "details": []},
        "stickers": {"added": 0, "failed": 0, "details": []}
    }
    
    # 2. 添加开幕效果
    if opening_effect:
        try:
            effect_name = opening_effect.get("effect_name", "开幕")
            start_time = opening_effect.get("start_time", 0)
            duration = opening_effect.get("duration", 1.5)
            
            # 映射到剪映实际特效名称
            mapped_effect_name = OPENING_EFFECT_MAP.get(effect_name, "开幕")
            
            # 创建特效轨道
            track_name = f"opening_track_{helper.gen_unique_id()}"
            script.add_track(track_type=TrackType.effect, track_name=track_name)
            
            # 查找特效类型
            effect_type = _find_effect_type_by_name(mapped_effect_name)
            if effect_type:
                start_us = int(start_time * 1_000_000)
                duration_us = int(duration * 1_000_000)
                timerange = Timerange(start=start_us, duration=duration_us)
                effect_segment = EffectSegment(
                    effect_type=effect_type,
                    target_timerange=timerange
                )
                script.add_segment(effect_segment, track_name)
                
                results["opening"] = {
                    "success": True,
                    "effect_name": effect_name,
                    "duration": duration
                }
                logger.info(f"{_LOG_PREFIX} 开幕效果添加成功: {effect_name} ({duration}s)")
            else:
                results["opening"] = {"success": False, "error": f"特效类型未找到: {mapped_effect_name}"}
                logger.warning(f"{_LOG_PREFIX} 开幕效果类型未找到: {mapped_effect_name}")
        except Exception as e:
            results["opening"] = {"success": False, "error": str(e)}
            logger.error(f"{_LOG_PREFIX} 开幕效果添加失败: {e}")
    
    # 3. 批量添加特效
    if effects:
        # 创建特效轨道
        track_name = f"effect_track_{helper.gen_unique_id()}"
        script.add_track(track_type=TrackType.effect, track_name=track_name)
        
        for effect in effects:
            try:
                effect_name = effect.get("effect_name")
                start_time = effect.get("start_time", 0)
                duration = effect.get("duration", 3.0)
                
                # 查找特效类型
                effect_type = _find_effect_type_by_name(effect_name)
                if not effect_type:
                    results["effects"]["failed"] += 1
                    results["effects"]["details"].append({
                        "effect_name": effect_name,
                        "success": False,
                        "error": "特效类型未找到"
                    })
                    continue
                
                start_us = int(start_time * 1_000_000)
                duration_us = int(duration * 1_000_000)
                timerange = Timerange(start=start_us, duration=duration_us)
                effect_segment = EffectSegment(
                    effect_type=effect_type,
                    target_timerange=timerange
                )
                script.add_segment(effect_segment, track_name)
                
                results["effects"]["added"] += 1
                results["effects"]["details"].append({
                    "effect_name": effect_name,
                    "success": True,
                    "start_time": start_time,
                    "duration": duration
                })
                
            except Exception as e:
                results["effects"]["failed"] += 1
                results["effects"]["details"].append({
                    "effect_name": effect.get("effect_name"),
                    "success": False,
                    "error": str(e)
                })
                logger.warning(f"{_LOG_PREFIX} 特效添加失败: {e}")
        
        logger.info(f"{_LOG_PREFIX} 特效添加完成: 成功={results['effects']['added']}, 失败={results['effects']['failed']}")
    
    # 4. 批量添加贴纸
    if stickers:
        # 创建贴纸轨道
        track_name = f"sticker_track_{helper.gen_unique_id()}"
        script.add_track(track_type=draft.TrackType.sticker, track_name=track_name)
        
        # 获取草稿尺寸用于位置计算
        draft_width = script.width
        draft_height = script.height
        default_transform_y = int(-draft_height * 0.30)  # 默认放在画面下方
        
        for sticker in stickers:
            try:
                sticker_id = sticker.get("sticker_id")
                sticker_type = sticker.get("sticker_type")
                
                # 如果没有直接提供 sticker_id，尝试从映射表中获取
                if not sticker_id and sticker_type:
                    sticker_id = STICKER_TYPE_MAP.get(sticker_type)
                
                if not sticker_id:
                    results["stickers"]["failed"] += 1
                    results["stickers"]["details"].append({
                        "sticker_type": sticker_type,
                        "success": False,
                        "error": "未提供有效贴纸ID或无法识别的贴纸类型"
                    })
                    logger.warning(f"{_LOG_PREFIX} 贴纸 ID 缺失且无法映射: type={sticker_type}")
                    continue
                
                start_time = sticker.get("start_time", 0)
                duration = sticker.get("duration", 3)

                scale = sticker.get("scale", 1.0)
                transform_x = sticker.get("transform_x", 0)
                transform_y = sticker.get("transform_y", default_transform_y)
                
                start_us = int(start_time * 1_000_000)
                duration_us = int(duration * 1_000_000)
                
                # 创建图像调节设置
                clip_settings = ClipSettings(
                    scale_x=scale,
                    scale_y=scale,
                    transform_x=transform_x / draft_width,
                    transform_y=transform_y / draft_height
                )
                
                # 创建贴纸片段
                sticker_segment = StickerSegment(
                    resource_id=sticker_id,
                    target_timerange=Timerange(start=start_us, duration=duration_us),
                    clip_settings=clip_settings
                )
                script.add_segment(sticker_segment, track_name)
                
                results["stickers"]["added"] += 1
                results["stickers"]["details"].append({
                    "sticker_id": sticker_id,
                    "success": True,
                    "start_time": start_time,
                    "duration": duration
                })
                
            except Exception as e:
                results["stickers"]["failed"] += 1
                results["stickers"]["details"].append({
                    "sticker_id": sticker.get("sticker_id"),
                    "success": False,
                    "error": str(e)
                })
                logger.warning(f"{_LOG_PREFIX} 贴纸添加失败: {e}")
        
        logger.info(f"{_LOG_PREFIX} 贴纸添加完成: 成功={results['stickers']['added']}, 失败={results['stickers']['failed']}")
    
    # 5. 统一保存（关键：只保存一次）
    try:
        script.save()
        logger.info(f"{_LOG_PREFIX} 草稿保存成功: draft_id={draft_id}")
    except Exception as e:
        results["success"] = False
        results["error"] = f"保存失败: {e}"
        logger.error(f"{_LOG_PREFIX} 草稿保存失败: {e}")
        return f"❌ 草稿保存失败: {e}", results
    
    # 6. 生成结果摘要
    summary_parts = []
    if results["opening"]:
        summary_parts.append(f"开幕: {results['opening'].get('effect_name', '未知')}")
    if results["effects"]["added"] > 0:
        summary_parts.append(f"特效: {results['effects']['added']}个")
    if results["stickers"]["added"] > 0:
        summary_parts.append(f"贴纸: {results['stickers']['added']}个")
    
    summary = "✅ 视觉元素应用完成 - " + ", ".join(summary_parts) if summary_parts else "✅ 无视觉元素需要应用"
    
    return summary, results


def _find_effect_type_by_name(effect_title: str):
    """
    根据特效名称查找对应的特效类型
    
    Args:
        effect_title: 特效名称/标题
    
    Returns:
        对应的特效类型枚举，如果未找到则返回None
    """
    from src.pyJianYingDraft.metadata import VideoSceneEffectType, VideoCharacterEffectType
    
    # 搜索VideoSceneEffectType中的特效
    for effect_type in VideoSceneEffectType:
        if effect_type.value.name == effect_title:
            return effect_type
    
    # 搜索VideoCharacterEffectType中的特效
    for effect_type in VideoCharacterEffectType:
        if effect_type.value.name == effect_title:
            return effect_type
    
    logger.warning(f"{_LOG_PREFIX} 特效类型未找到: {effect_title}")
    return None
