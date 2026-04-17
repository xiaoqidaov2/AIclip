"""
导出视频服务 - 同步导出草稿为视频文件
"""
import os
import shutil
import threading
from datetime import datetime
from src.utils.logger import logger
from src.schemas.export_video import ExportVideoRequest, ExportVideoResponse
import src.pyJianYingDraft as draft
import config

# 导出视频专用锁（确保任何时候只有一个线程执行剪映 RPA 导出）
_export_lock = threading.Lock()


def export_video(request: ExportVideoRequest) -> ExportVideoResponse:
    """
    导出草稿为视频文件（同步执行）
    
    Args:
        request: 导出视频请求
        
    Returns:
        ExportVideoResponse: 导出结果
    """
    draft_id = request.draft_id
    
    # 确定输出路径
    if request.output_path:
        outfile = request.output_path
    else:
        # 默认输出路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        outfile = os.path.join(config.VIDEO_OUTPUT_PATH, f"{draft_id}_{timestamp}.mp4")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    
    logger.info(f"开始导出草稿: {draft_id} -> {outfile}")
    
    try:
        # 检查JianyingController是否可用
        if draft.JianyingController is None:
            error_msg = (
                "剪映自动导出功能仅在Windows平台可用"
                if os.name != "nt"
                else "缺少Windows依赖，请安装: pip install capcut-mate[windows]"
            )
            logger.error(error_msg)
            return ExportVideoResponse(success=False, error=error_msg)
        
        # 检查剪映草稿路径配置
        if not config.JIANYING_DRAFT_PATH:
            error_msg = "未配置剪映草稿路径，请设置 JIANYING_DRAFT_PATH 环境变量或在 config.py 中配置"
            logger.error(error_msg)
            return ExportVideoResponse(success=False, error=error_msg)
        
        if not os.path.exists(config.JIANYING_DRAFT_PATH):
            error_msg = f"剪映草稿路径不存在: {config.JIANYING_DRAFT_PATH}"
            logger.error(error_msg)
            return ExportVideoResponse(success=False, error=error_msg)
        
        # 检查源草稿路径
        source_draft_path = os.path.join(config.DRAFT_DIR, draft_id)
        if not os.path.exists(source_draft_path):
            error_msg = f"源草稿路径不存在: {source_draft_path}"
            logger.error(error_msg)
            return ExportVideoResponse(success=False, error=error_msg)
        
        # 使用专用锁确保任何时候只有一个线程执行导出视频操作
        with _export_lock:
            logger.info(f"获取导出锁，开始导出: {draft_id}")
            
            # 将草稿从 temp/drafts 复制到剪映草稿文件夹
            target_draft_path = os.path.join(config.JIANYING_DRAFT_PATH, draft_id)
            
            # 如果目标路径已存在，先删除
            if os.path.exists(target_draft_path):
                logger.info(f"目标草稿路径已存在，先删除: {target_draft_path}")
                shutil.rmtree(target_draft_path)
            
            # 复制草稿到剪映草稿文件夹
            logger.info(f"复制草稿到剪映目录: {source_draft_path} -> {target_draft_path}")
            shutil.copytree(source_draft_path, target_draft_path)
            
            # 增加等待时间，确保剪映 APP 能够刷新并识别到新复制的草稿
            import time
            logger.info("等待 5 秒以确保剪映刷新草稿列表...")
            time.sleep(5)
            
            # 使用剪映RPA导出视频
            controller = draft.JianyingController()
            controller.export_draft(draft_id, outfile)
            
            logger.info(f"草稿导出成功: {draft_id} -> {outfile}")
            
        return ExportVideoResponse(success=True, output_path=outfile)
        
    except Exception as e:
        error_msg = f"导出视频失败: {str(e)}"
        logger.exception(error_msg)
        return ExportVideoResponse(success=False, error=error_msg)
